from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import secrets
import time
import uuid
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from .db import Database
from .domain import DomainError, RULES, ensure, evaluate, parse_phone, parse_product, required_text
from .wechat import exchange_login_code, exchange_phone_code


COLORS = ("#176B5B", "#D05F47", "#536D9B")
FINAL_LABELS = {"approved": "已通过", "rejected": "未通过", "expired": "已过期", "cancelled": "已撤回"}


def now_ms() -> int:
    return int(time.time() * 1000)


class Service:
    def __init__(self, db: Database, *, secret: str, data_dir: Path, mode: str, sms, wechat: dict | None = None, clock=now_ms):
        self.db = db
        self.secret = secret.encode()
        self.data_dir = data_dir
        self.mode = mode
        self.sms = sms
        self.wechat = wechat or {}
        self.clock = clock
        self.upload_dir = data_dir / "uploads"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _hash(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    def _code_hash(self, challenge_id: str, code: str) -> str:
        return hmac.new(self.secret, f"{challenge_id}:{code}".encode(), hashlib.sha256).hexdigest()

    def _user(self, row: dict | None) -> dict | None:
        if not row:
            return None
        phone = row["phone"]
        masked = "虚构演示账号" if phone and phone.startswith("demo:") else f"{phone[:3]}****{phone[-4:]}" if phone else "微信登录"
        return {"id": row["id"], "name": row["name"], "initial": row["name"][:1], "code": row["code"], "phoneMasked": masked, "hasPhone": bool(phone), "color": row["color"]}

    def _lookup_user(self, conn, user_id: str) -> dict | None:
        return conn.execute("SELECT * FROM users WHERE id=%s", (user_id,)).fetchone()

    def _create_user(self, conn, phone: str | None, name: str, user_id: str | None = None, *, wechat_openid: str | None = None) -> dict:
        user_id = user_id or self._id()
        for _ in range(5):
            code = secrets.token_hex(5).upper()
            row = conn.execute(
                "INSERT INTO users(id,phone,wechat_openid,name,code,color,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING *",
                (user_id, phone, wechat_openid, name, code, secrets.choice(COLORS), self.clock()),
            ).fetchone()
            if row:
                return row
        raise DomainError("无法生成唯一好友邀请码，请稍后再试", 503)

    def _new_session(self, conn, row: dict) -> dict:
        token = secrets.token_urlsafe(32)
        now = self.clock()
        conn.execute("DELETE FROM sessions WHERE expires_at<=%s", (now,))
        conn.execute("INSERT INTO sessions(hash,user_id,expires_at) VALUES(%s,%s,%s)", (self._hash(token), row["id"], now + 30 * 86_400_000))
        return {"token": token, "user": self._user(row)}

    def authenticate(self, token: str | None) -> dict:
        ensure(isinstance(token, str) and len(token) <= 128, "请先登录", 401)
        row = self.db.fetchone(
            "SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.hash=%s AND s.expires_at>%s",
            (self._hash(token), self.clock()),
        )
        ensure(row, "登录已失效，请重新登录", 401)
        return row

    def request_code(self, phone_value: object, ip: str) -> dict:
        phone = parse_phone(phone_value)
        now = self.clock()
        challenge_id, code = self._id(), f"{secrets.randbelow(1_000_000):06d}"
        with self.db.transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"otp:{phone}",))
            last = conn.execute("SELECT created_at FROM challenges WHERE phone=%s ORDER BY created_at DESC LIMIT 1", (phone,)).fetchone()
            ensure(not last or now - last["created_at"] >= 60_000, "验证码发送频繁，请60秒后重试", 429)
            count = conn.execute("SELECT count(*) n FROM challenges WHERE phone=%s AND created_at>%s", (phone, now - 86_400_000)).fetchone()["n"]
            ensure(count < 10, "今日验证码次数已用完", 429)
            ip_count = conn.execute("SELECT count(*) n FROM challenges WHERE ip=%s AND created_at>%s", (ip, now - 3_600_000)).fetchone()["n"]
            ensure(ip_count < 20, "请求过于频繁，请稍后重试", 429)
            conn.execute("UPDATE challenges SET used=TRUE WHERE phone=%s", (phone,))
            conn.execute(
                "INSERT INTO challenges(id,phone,hash,ip,created_at,expires_at) VALUES(%s,%s,%s,%s,%s,%s)",
                (challenge_id, phone, self._code_hash(challenge_id, code), ip, now, now + 300_000),
            )
        try:
            self.sms.send("otp", phone, [code, "5"], f"验证码{code}，5分钟内有效。")
        except Exception as exc:
            self.db.execute("UPDATE challenges SET used=TRUE WHERE id=%s", (challenge_id,))
            raise DomainError("短信发送未确认，请稍后重新获取验证码", 503) from exc
        result = {"challengeId": challenge_id, "expiresIn": 300, "retryAfter": 60}
        if self.mode == "demo" and self.sms.mode == "mock":
            result["demoCode"] = code
        return result

    def wechat_login(self, code_value: object) -> dict:
        if self.mode == "demo" and not self.wechat.get("app_secret"):
            required_text(code_value, "微信登录凭证", 256)
            return self.demo_login("a")
        openid = exchange_login_code(self.wechat, code_value)
        with self.db.transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"wechat:{openid}",))
            row = conn.execute("SELECT * FROM users WHERE wechat_openid=%s", (openid,)).fetchone()
            if not row:
                row = self._create_user(conn, None, f"微信用户{openid[-4:]}", wechat_openid=openid)
            return self._new_session(conn, row)

    def login(self, payload: dict) -> dict:
        phone = parse_phone(payload.get("phone"))
        challenge_id = required_text(payload.get("challengeId"), "验证码请求", 100)
        code = required_text(payload.get("code"), "验证码", 6)
        ensure(len(code) == 6 and code.isdigit(), "请输入6位验证码")
        name = required_text(payload.get("name") or "新朋友", "昵称", 24)
        result = None
        with self.db.transaction() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"login:{phone}",))
            challenge = conn.execute("SELECT * FROM challenges WHERE id=%s AND phone=%s FOR UPDATE", (challenge_id, phone)).fetchone()
            ensure(challenge and not challenge["used"] and challenge["attempts"] < 5 and challenge["expires_at"] > self.clock(), "验证码已失效，请重新获取")
            conn.execute("UPDATE challenges SET attempts=attempts+1 WHERE id=%s", (challenge_id,))
            if hmac.compare_digest(challenge["hash"], self._code_hash(challenge_id, code)):
                conn.execute("UPDATE challenges SET used=TRUE WHERE id=%s", (challenge_id,))
                row = conn.execute("SELECT * FROM users WHERE phone=%s", (phone,)).fetchone() or self._create_user(conn, phone, name)
                result = self._new_session(conn, row)
        ensure(result, "验证码不正确")
        return result

    def demo_login(self, account: object) -> dict:
        ensure(self.mode == "demo", "接口不存在", 404)
        ensure(account in {"a", "b", "c"}, "演示账号不正确")
        products = {
            "a": ("通勤降噪耳机", 89_900, "旧耳机续航不足，想在通勤时听播客。", "数码"),
            "b": ("周末徒步背包", 32_900, "每个月会出去徒步两次，想换一个轻一点的背包。", "运动"),
            "c": ("手冲咖啡入门套装", 26_800, "想在周末尝试自己冲咖啡，先从基础套装开始。", "生活"),
        }
        with self.db.transaction() as conn:
            for letter, name in (("a", "小满 · 演示"), ("b", "阿禾 · 演示"), ("c", "可可 · 演示")):
                user_id = f"demo-{letter}"
                if not self._lookup_user(conn, user_id):
                    self._create_user(conn, f"demo:{letter}", name, user_id)
                    title, price, reason, category = products[letter]
                    conn.execute(
                        "INSERT INTO items(id,owner_id,title,price,reason,category,link,visibility,images,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,'','friends','[]'::jsonb,%s,%s)",
                        (self._id(), user_id, title, price, reason, category, self.clock(), self.clock()),
                    )
            initialized = conn.execute("SELECT 1 FROM friend_requests WHERE id='demo-initialized'").fetchone()
            if not initialized:
                for a, b in (("demo-a", "demo-b"), ("demo-a", "demo-c"), ("demo-b", "demo-c")):
                    conn.execute("INSERT INTO friends(a,b,created_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING", (a, b, self.clock()))
                conn.execute("INSERT INTO friend_requests(id,sender,recipient,status,created_at) VALUES('demo-initialized','demo-a','demo-b','accepted',%s)", (self.clock(),))
            return self._new_session(conn, self._lookup_user(conn, f"demo-{account}"))

    def logout(self, token: str) -> dict:
        self.db.execute("DELETE FROM sessions WHERE hash=%s", (self._hash(token),))
        return {"ok": True}

    def me(self, user: dict) -> dict:
        self.expire_pending()
        with self.db.connect() as conn:
            cart = conn.execute("SELECT count(*) n FROM items WHERE owner_id=%s AND NOT deleted", (user["id"],)).fetchone()["n"]
            pending = conn.execute("SELECT count(*) n FROM votes v JOIN approvals a ON a.id=v.approval_id WHERE v.user_id=%s AND v.decision IS NULL AND a.status='pending'", (user["id"],)).fetchone()["n"]
            friends = conn.execute("SELECT count(*) n FROM friends WHERE a=%s OR b=%s", (user["id"], user["id"])).fetchone()["n"]
        return {"user": self._user(user), "stats": {"cartCount": cart, "pendingCount": pending, "friendCount": friends}, "mode": self.mode, "smsProvider": self.sms.mode}

    def rename(self, user_id: str, value: object) -> dict:
        self.db.execute("UPDATE users SET name=%s WHERE id=%s", (required_text(value, "昵称", 24), user_id))
        return {"user": self._user(self.db.fetchone("SELECT * FROM users WHERE id=%s", (user_id,)))}

    def bind_wechat_phone(self, user_id: str, code_value: object) -> dict:
        phone = parse_phone(exchange_phone_code(self.wechat, code_value))
        self.db.execute("UPDATE users SET phone=%s WHERE id=%s", (phone, user_id))
        return {"user": self._user(self.db.fetchone("SELECT * FROM users WHERE id=%s", (user_id,)))}

    @staticmethod
    def _pair(a: str, b: str) -> tuple[str, str]:
        return tuple(sorted((a, b)))

    def _linked(self, conn, a: str, b: str) -> bool:
        if a == b:
            return True
        return bool(conn.execute("SELECT 1 FROM friends WHERE a=%s AND b=%s", self._pair(a, b)).fetchone())

    def friends(self, user_id: str) -> dict:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT u.* FROM users u WHERE u.id IN (SELECT CASE WHEN a=%s THEN b ELSE a END FROM friends WHERE a=%s OR b=%s) ORDER BY name", (user_id, user_id, user_id)).fetchall()
            requests = conn.execute("SELECT * FROM friend_requests WHERE status='pending' AND (sender=%s OR recipient=%s) ORDER BY created_at DESC", (user_id, user_id)).fetchall()
            incoming = [{"id": r["id"], "user": self._user(self._lookup_user(conn, r["sender"])), "createdAt": r["created_at"]} for r in requests if r["recipient"] == user_id]
            outgoing = [{"id": r["id"], "user": self._user(self._lookup_user(conn, r["recipient"])), "createdAt": r["created_at"]} for r in requests if r["sender"] == user_id]
        return {"friends": [self._user(row) for row in rows], "incoming": incoming, "outgoing": outgoing}

    def request_friend(self, user_id: str, code_value: object) -> dict:
        code = required_text(code_value, "好友邀请码", 20).upper()
        now = self.clock()
        with self.db.transaction() as conn:
            target = conn.execute("SELECT * FROM users WHERE code=%s", (code,)).fetchone()
            ensure(target, "未找到此邀请码，请向好友确认", 404)
            ensure(target["id"] != user_id, "不能添加自己")
            ensure(not self._linked(conn, user_id, target["id"]), "你们已经是好友", 409)
            pair = self._pair(user_id, target["id"])
            ensure(not conn.execute("SELECT 1 FROM friend_requests WHERE status='pending' AND LEAST(sender,recipient)=%s AND GREATEST(sender,recipient)=%s", pair).fetchone(), "已有待处理申请，请在好友页面查看", 409)
            ensure(conn.execute("SELECT count(*) n FROM friends WHERE a=%s OR b=%s", (user_id, user_id)).fetchone()["n"] < 100, "首版最多添加100位好友")
            ensure(conn.execute("SELECT count(*) n FROM friend_requests WHERE sender=%s AND created_at>%s", (user_id, now - 86_400_000)).fetchone()["n"] < 30, "今日好友申请次数已达上限", 429)
            conn.execute("INSERT INTO friend_requests(id,sender,recipient,status,created_at) VALUES(%s,%s,%s,'pending',%s)", (self._id(), user_id, target["id"], now))
        return {"ok": True}

    def respond_friend(self, user_id: str, request_id: str, accept: object) -> dict:
        ensure(isinstance(accept, bool), "请选择接受或拒绝")
        with self.db.transaction() as conn:
            request = conn.execute("SELECT * FROM friend_requests WHERE id=%s FOR UPDATE", (request_id,)).fetchone()
            ensure(request, "好友申请不存在", 404)
            ensure(request["recipient"] == user_id, "只能处理发给你的好友申请", 403)
            ensure(request["status"] == "pending", "该申请已经处理", 409)
            if accept:
                ensure(conn.execute("SELECT count(*) n FROM friends WHERE a=%s OR b=%s", (user_id, user_id)).fetchone()["n"] < 100, "好友人数已达上限")
                a, b = self._pair(user_id, request["sender"])
                conn.execute("INSERT INTO friends(a,b,created_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING", (a, b, self.clock()))
            conn.execute("UPDATE friend_requests SET status=%s WHERE id=%s", ("accepted" if accept else "rejected", request_id))
        return {"ok": True}

    def remove_friend(self, user_id: str, friend_id: str) -> dict:
        a, b = self._pair(user_id, friend_id)
        self.db.execute("DELETE FROM friends WHERE a=%s AND b=%s", (a, b))
        return {"ok": True}

    def _media_signature(self, media_id: str, expires: int) -> str:
        return hmac.new(self.secret, f"{media_id}:{expires}".encode(), hashlib.sha256).hexdigest()

    def media_url(self, media_id: str, base_url: str) -> str:
        expires = self.clock() + 600_000
        return f"{base_url}/api/media/{media_id}?expires={expires}&sig={self._media_signature(media_id, expires)}"

    def upload_media(self, user_id: str, payload: dict, base_url: str) -> dict:
        encoded = payload.get("base64")
        mime = payload.get("mime")
        ensure(mime in {"image/png", "image/jpeg", "image/webp"}, "仅支持PNG、JPEG或WebP图片")
        ensure(isinstance(encoded, str) and 0 < len(encoded) <= 4_200_000, "单张图片不能超过3MB")
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise DomainError("图片内容无法识别") from exc
        ensure(0 < len(content) <= 3 * 1024 * 1024, "单张图片不能超过3MB")
        valid_magic = ((mime == "image/png" and content.startswith(b"\x89PNG\r\n\x1a\n")) or
                       (mime == "image/jpeg" and content.startswith(b"\xff\xd8\xff")) or
                       (mime == "image/webp" and content[:4] == b"RIFF" and content[8:12] == b"WEBP"))
        ensure(valid_magic, "图片格式与文件内容不一致")
        media_id = self._id()
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[mime]
        path = self.upload_dir / f"{media_id}{suffix}"
        with self.db.transaction() as conn:
            count = conn.execute("SELECT count(*) n FROM media WHERE owner_id=%s", (user_id,)).fetchone()["n"]
            total = conn.execute("SELECT coalesce(sum(size),0) n FROM media WHERE owner_id=%s", (user_id,)).fetchone()["n"]
            ensure(count < 300 and total + len(content) <= 300 * 1024 * 1024, "图片空间已达上限")
            path.write_bytes(content)
            try:
                conn.execute("INSERT INTO media(id,owner_id,mime,size,created_at) VALUES(%s,%s,%s,%s,%s)",
                             (media_id, user_id, mime, len(content), self.clock()))
            except Exception:
                path.unlink(missing_ok=True)
                raise
        return {"id": media_id, "url": self.media_url(media_id, base_url)}

    def read_media(self, media_id: str, expires_value: object, signature: object) -> tuple[bytes, str]:
        try:
            expires = int(expires_value)
        except (TypeError, ValueError) as exc:
            raise DomainError("图片链接无效", 403) from exc
        ensure(self.clock() <= expires <= self.clock() + 600_000, "图片链接已过期", 403)
        ensure(isinstance(signature, str) and hmac.compare_digest(signature, self._media_signature(media_id, expires)), "图片签名无效", 403)
        row = self.db.fetchone("SELECT * FROM media WHERE id=%s", (media_id,))
        ensure(row, "图片不存在", 404)
        suffix = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}[row["mime"]]
        path = self.upload_dir / f"{media_id}{suffix}"
        ensure(path.exists(), "图片文件不存在", 404)
        return path.read_bytes(), row["mime"]

    def _item_row(self, conn, item_id: str, *, lock: bool = False):
        row = conn.execute(f"SELECT * FROM items WHERE id=%s AND NOT deleted{' FOR UPDATE' if lock else ''}", (item_id,)).fetchone()
        ensure(row, "商品不存在", 404)
        return row

    def _item_visible(self, conn, row: dict, viewer_id: str) -> bool:
        return row["owner_id"] == viewer_id or (row["visibility"] == "friends" and self._linked(conn, row["owner_id"], viewer_id))

    def _check_images(self, conn, user_id: str, images: list[str]) -> None:
        if not images:
            return
        rows = conn.execute("SELECT id FROM media WHERE owner_id=%s AND id=ANY(%s)", (user_id, images)).fetchall()
        ensure({row["id"] for row in rows} == set(images), "商品图片必须由当前账号上传")

    def _format_item(self, conn, row: dict, viewer_id: str, base_url: str) -> dict:
        reactions = conn.execute("SELECT count(*) FILTER (WHERE value=1) likes,count(*) FILTER (WHERE value=-1) dislikes,max(value) FILTER (WHERE user_id=%s) mine FROM reactions WHERE item_id=%s", (viewer_id, row["id"])).fetchone()
        comments = conn.execute("SELECT count(*) n FROM comments WHERE item_id=%s", (row["id"],)).fetchone()["n"]
        images = list(row["images"] or [])
        return {"id": row["id"], "ownerId": row["owner_id"], "owner": self._user(self._lookup_user(conn, row["owner_id"])),
                "title": row["title"], "price": row["price"], "reason": row["reason"], "category": row["category"],
                "link": row["link"], "visibility": row["visibility"], "images": images,
                "imageUrls": [self.media_url(value, base_url) for value in images], "createdAt": row["created_at"], "updatedAt": row["updated_at"],
                "likes": reactions["likes"], "dislikes": reactions["dislikes"], "myReaction": reactions["mine"] or 0, "commentCount": comments}

    def list_items(self, user_id: str, scope: str, base_url: str) -> dict:
        ensure(scope in {"feed", "mine"}, "商品列表范围不正确")
        with self.db.connect() as conn:
            if scope == "mine":
                rows = conn.execute("SELECT * FROM items WHERE owner_id=%s AND NOT deleted ORDER BY created_at DESC LIMIT 100", (user_id,)).fetchall()
            else:
                rows = conn.execute("SELECT i.* FROM items i JOIN friends f ON (f.a=%s AND f.b=i.owner_id) OR (f.b=%s AND f.a=i.owner_id) WHERE i.visibility='friends' AND NOT i.deleted ORDER BY i.created_at DESC LIMIT 100", (user_id, user_id)).fetchall()
            return {"items": [self._format_item(conn, row, user_id, base_url) for row in rows]}

    def item_detail(self, user_id: str, item_id: str, base_url: str) -> dict:
        with self.db.connect() as conn:
            row = self._item_row(conn, item_id)
            ensure(self._item_visible(conn, row, user_id), "你无权查看此商品", 403)
            comment_rows = conn.execute("SELECT c.*,u.id uid,u.phone,u.name,u.code,u.color FROM comments c JOIN users u ON u.id=c.user_id WHERE c.item_id=%s ORDER BY c.created_at", (item_id,)).fetchall()
            comments = [{"id": c["id"], "itemId": item_id, "text": c["text"], "createdAt": c["created_at"],
                         "user": self._user({"id": c["uid"], "phone": c["phone"], "name": c["name"], "code": c["code"], "color": c["color"]})} for c in comment_rows]
            return {"item": self._format_item(conn, row, user_id, base_url), "comments": comments}

    def create_item(self, user_id: str, payload: dict, base_url: str) -> dict:
        product = parse_product(payload)
        now = self.clock()
        item_id = self._id()
        with self.db.transaction() as conn:
            self._check_images(conn, user_id, product["images"])
            row = conn.execute("INSERT INTO items(id,owner_id,title,price,reason,category,link,visibility,images,created_at,updated_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                               (item_id, user_id, product["title"], product["price"], product["reason"], product["category"], product["link"], product["visibility"], Jsonb(product["images"]), now, now)).fetchone()
            return {"item": self._format_item(conn, row, user_id, base_url)}

    def update_item(self, user_id: str, item_id: str, payload: dict, base_url: str) -> dict:
        product = parse_product(payload)
        with self.db.transaction() as conn:
            current = self._item_row(conn, item_id, lock=True)
            ensure(current["owner_id"] == user_id, "只能修改自己的商品", 403)
            self._check_images(conn, user_id, product["images"])
            row = conn.execute("UPDATE items SET title=%s,price=%s,reason=%s,category=%s,link=%s,visibility=%s,images=%s,updated_at=%s WHERE id=%s RETURNING *",
                               (product["title"], product["price"], product["reason"], product["category"], product["link"], product["visibility"], Jsonb(product["images"]), self.clock(), item_id)).fetchone()
            return {"item": self._format_item(conn, row, user_id, base_url)}

    def delete_item(self, user_id: str, item_id: str) -> dict:
        with self.db.transaction() as conn:
            row = self._item_row(conn, item_id, lock=True)
            ensure(row["owner_id"] == user_id, "只能移除自己的商品", 403)
            conn.execute("UPDATE items SET deleted=true,updated_at=%s WHERE id=%s", (self.clock(), item_id))
        return {"ok": True}

    def add_comment(self, user_id: str, item_id: str, value: object) -> dict:
        text = required_text(value, "评论", 300)
        with self.db.transaction() as conn:
            item = self._item_row(conn, item_id)
            ensure(self._item_visible(conn, item, user_id), "你无权评论此商品", 403)
            comment_id = self._id()
            now = self.clock()
            conn.execute("INSERT INTO comments(id,item_id,user_id,text,created_at) VALUES(%s,%s,%s,%s,%s)", (comment_id, item_id, user_id, text, now))
            user = self._lookup_user(conn, user_id)
        return {"comment": {"id": comment_id, "itemId": item_id, "text": text, "createdAt": now, "user": self._user(user)}}

    def delete_comment(self, user_id: str, comment_id: str) -> dict:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT c.*,i.owner_id FROM comments c JOIN items i ON i.id=c.item_id WHERE c.id=%s FOR UPDATE", (comment_id,)).fetchone()
            ensure(row, "评论不存在", 404)
            ensure(user_id in {row["user_id"], row["owner_id"]}, "无权删除此评论", 403)
            conn.execute("DELETE FROM comments WHERE id=%s", (comment_id,))
        return {"ok": True}

    def react(self, user_id: str, item_id: str, value: object) -> dict:
        ensure(type(value) is int and value in {-1, 0, 1}, "请选择点赞、下踩或取消")
        with self.db.transaction() as conn:
            item = self._item_row(conn, item_id)
            ensure(self._item_visible(conn, item, user_id), "你无权评价此商品", 403)
            if value == 0:
                conn.execute("DELETE FROM reactions WHERE item_id=%s AND user_id=%s", (item_id, user_id))
            else:
                conn.execute("INSERT INTO reactions(item_id,user_id,value) VALUES(%s,%s,%s) ON CONFLICT(item_id,user_id) DO UPDATE SET value=excluded.value", (item_id, user_id, value))
        return {"ok": True}

    def _approval_row(self, conn, approval_id: str, *, lock: bool = False):
        row = conn.execute(f"SELECT * FROM approvals WHERE id=%s{' FOR UPDATE' if lock else ''}", (approval_id,)).fetchone()
        ensure(row, "审批不存在", 404)
        return row

    def _add_outbox(self, conn, approval: dict, sender: str, recipient: str, kind: str, params: list[str], body: str, event_key: str) -> None:
        conn.execute("INSERT INTO outbox(id,event_key,approval_id,sender,recipient,kind,body,params,status,created_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'queued',%s) ON CONFLICT(event_key) DO NOTHING",
                     (self._id(), event_key, approval["id"], sender, recipient, kind, body, Jsonb(params), self.clock()))

    def _add_result_outbox(self, conn, approval: dict) -> None:
        label = FINAL_LABELS[approval["status"]]
        title = approval["snapshot"]["title"]
        self._add_outbox(conn, approval, approval["owner_id"], approval["owner_id"], "result", [title, label], f"“{title}”审批结果：{label}", f"result:{approval['id']}:{approval['status']}")

    def _expire_locked(self, conn, approval: dict, at: int) -> dict:
        if approval["status"] == "pending" and approval["expires_at"] <= at:
            approval = conn.execute("UPDATE approvals SET status='expired' WHERE id=%s RETURNING *", (approval["id"],)).fetchone()
            self._add_result_outbox(conn, approval)
        return approval

    def expire_pending(self) -> int:
        count = 0
        with self.db.transaction() as conn:
            rows = conn.execute("SELECT * FROM approvals WHERE status='pending' AND expires_at<=%s FOR UPDATE SKIP LOCKED", (self.clock(),)).fetchall()
            for row in rows:
                self._expire_locked(conn, row, self.clock())
                count += 1
        return count

    def _format_approval(self, conn, row: dict, base_url: str) -> dict:
        votes = conn.execute("SELECT v.*,u.id uid,u.phone,u.name,u.code,u.color FROM votes v JOIN users u ON u.id=v.user_id WHERE v.approval_id=%s ORDER BY u.name", (row["id"],)).fetchall()
        snapshot = row["snapshot"]
        images = list(snapshot.get("images", []))
        return {"id": row["id"], "ownerId": row["owner_id"], "owner": self._user(self._lookup_user(conn, row["owner_id"])),
                "itemId": row["item_id"], "title": snapshot["title"], "price": snapshot["price"], "reason": snapshot["reason"],
                "category": snapshot["category"], "link": snapshot.get("link", ""), "images": images,
                "imageUrls": [self.media_url(value, base_url) for value in images], "rule": row["rule"], "status": row["status"],
                "createdAt": row["created_at"], "expiresAt": row["expires_at"],
                "reviewers": [{"id": v["uid"], "user": self._user({"id": v["uid"], "phone": v["phone"], "name": v["name"], "code": v["code"], "color": v["color"]}),
                               "decision": v["decision"], "comment": v["comment"], "votedAt": v["voted_at"]} for v in votes]}

    def list_approvals(self, user_id: str, scope: str, base_url: str) -> dict:
        ensure(scope in {"sent", "inbox", "pending", "handled"}, "审批列表范围不正确")
        self.expire_pending()
        with self.db.connect() as conn:
            if scope == "sent":
                rows = conn.execute("SELECT * FROM approvals WHERE owner_id=%s ORDER BY created_at DESC LIMIT 100", (user_id,)).fetchall()
            elif scope == "pending":
                rows = conn.execute("SELECT a.* FROM approvals a JOIN votes v ON v.approval_id=a.id WHERE v.user_id=%s AND v.decision IS NULL AND a.status='pending' ORDER BY a.expires_at,a.id LIMIT 100", (user_id,)).fetchall()
            elif scope == "handled":
                rows = conn.execute("SELECT a.* FROM approvals a JOIN votes v ON v.approval_id=a.id WHERE v.user_id=%s AND (v.decision IS NOT NULL OR a.status<>'pending') ORDER BY a.created_at DESC LIMIT 100", (user_id,)).fetchall()
            else:
                rows = conn.execute("SELECT a.* FROM approvals a JOIN votes v ON v.approval_id=a.id WHERE v.user_id=%s ORDER BY a.created_at DESC LIMIT 100", (user_id,)).fetchall()
            pending_count = conn.execute("SELECT count(*) n FROM approvals a JOIN votes v ON v.approval_id=a.id WHERE v.user_id=%s AND v.decision IS NULL AND a.status='pending'", (user_id,)).fetchone()["n"]
            return {"approvals": [self._format_approval(conn, row, base_url) for row in rows], "pendingCount": pending_count}

    def create_approval(self, user_id: str, payload: dict, base_url: str) -> dict:
        item_id = required_text(payload.get("itemId"), "商品", 80)
        rule = payload.get("rule")
        reviewer_ids = payload.get("reviewerIds")
        ensure(rule in RULES, "请选择审批结论规则")
        ensure(isinstance(reviewer_ids, list) and 1 <= len(reviewer_ids) <= 10 and all(isinstance(value, str) for value in reviewer_ids), "请选择1～10位好友")
        reviewer_ids = list(dict.fromkeys(reviewer_ids))
        ensure(len(reviewer_ids) >= 1, "请至少选择1位好友")
        now = self.clock()
        with self.db.transaction() as conn:
            item = self._item_row(conn, item_id, lock=True)
            ensure(item["owner_id"] == user_id, "只能为自己的商品发起审批", 403)
            for reviewer_id in reviewer_ids:
                ensure(reviewer_id != user_id and self._linked(conn, user_id, reviewer_id), "审批人必须是你的当前好友")
            duplicate = conn.execute("SELECT 1 FROM approvals WHERE owner_id=%s AND item_id=%s AND status='pending'", (user_id, item_id)).fetchone()
            ensure(not duplicate, "该商品已有进行中的审批", 409)
            snapshot = {key: item[key] for key in ("title", "price", "reason", "category", "link")}
            snapshot["images"] = list(item["images"] or [])
            approval = conn.execute("INSERT INTO approvals(id,owner_id,item_id,snapshot,rule,status,created_at,expires_at) VALUES(%s,%s,%s,%s,%s,'pending',%s,%s) RETURNING *",
                                    (self._id(), user_id, item_id, Jsonb(snapshot), rule, now, now + 72 * 3_600_000)).fetchone()
            owner = self._lookup_user(conn, user_id)
            for reviewer_id in reviewer_ids:
                conn.execute("INSERT INTO votes(approval_id,user_id) VALUES(%s,%s)", (approval["id"], reviewer_id))
                self._add_outbox(conn, approval, user_id, reviewer_id, "review", [owner["name"], snapshot["title"]], f"{owner['name']}请你审批“{snapshot['title']}”", f"review:{approval['id']}:{reviewer_id}")
            return {"approval": self._format_approval(conn, approval, base_url)}

    def approval_detail(self, user_id: str, approval_id: str, base_url: str) -> dict:
        self.expire_pending()
        with self.db.connect() as conn:
            approval = self._approval_row(conn, approval_id)
            permitted = approval["owner_id"] == user_id or conn.execute("SELECT 1 FROM votes WHERE approval_id=%s AND user_id=%s", (approval_id, user_id)).fetchone()
            ensure(permitted, "你无权查看此审批", 403)
            return {"approval": self._format_approval(conn, approval, base_url)}

    def vote(self, user_id: str, approval_id: str, payload: dict, base_url: str) -> dict:
        decision = payload.get("decision")
        ensure(decision in {"accept", "reject"}, "请选择接受或拒绝")
        comment = required_text(payload.get("comment"), "审批评论", 300)
        at = self.clock()
        expired = False
        result = None
        with self.db.transaction() as conn:
            approval = self._approval_row(conn, approval_id, lock=True)
            vote = conn.execute("SELECT * FROM votes WHERE approval_id=%s AND user_id=%s FOR UPDATE", (approval_id, user_id)).fetchone()
            ensure(vote, "你不是此审批的审批人", 403)
            approval = self._expire_locked(conn, approval, at)
            if approval["status"] == "expired":
                expired = True
            else:
                ensure(approval["status"] == "pending", "该审批已经结束", 409)
                ensure(self._linked(conn, approval["owner_id"], user_id), "你们已不是好友，无法继续审批", 403)
                ensure(vote["decision"] is None, "你已经提交过审批意见", 409)
                conn.execute("UPDATE votes SET decision=%s,comment=%s,voted_at=%s WHERE approval_id=%s AND user_id=%s", (decision, comment, at, approval_id, user_id))
                values = [row["decision"] for row in conn.execute("SELECT decision FROM votes WHERE approval_id=%s", (approval_id,)).fetchall()]
                status = evaluate(approval["rule"], values)
                if status != "pending":
                    approval = conn.execute("UPDATE approvals SET status=%s WHERE id=%s RETURNING *", (status, approval_id)).fetchone()
                    self._add_result_outbox(conn, approval)
                result = self._format_approval(conn, approval, base_url)
        if expired:
            raise DomainError("该审批已过期", 409)
        return {"approval": result}

    def cancel_approval(self, user_id: str, approval_id: str, base_url: str) -> dict:
        at = self.clock()
        expired = False
        result = None
        with self.db.transaction() as conn:
            approval = self._approval_row(conn, approval_id, lock=True)
            ensure(approval["owner_id"] == user_id, "只能撤回自己发起的审批", 403)
            approval = self._expire_locked(conn, approval, at)
            if approval["status"] == "expired":
                expired = True
            else:
                ensure(approval["status"] == "pending", "该审批已经结束", 409)
                approval = conn.execute("UPDATE approvals SET status='cancelled' WHERE id=%s RETURNING *", (approval_id,)).fetchone()
                self._add_result_outbox(conn, approval)
                result = self._format_approval(conn, approval, base_url)
        if expired:
            raise DomainError("该审批已过期", 409)
        return {"approval": result}

    def deliver_outbox_once(self, limit: int = 100) -> int:
        delivered = 0
        for _ in range(limit):
            with self.db.transaction() as conn:
                row = conn.execute("SELECT o.*,u.phone FROM outbox o JOIN users u ON u.id=o.recipient WHERE o.status='queued' ORDER BY o.created_at FOR UPDATE OF o SKIP LOCKED LIMIT 1").fetchone()
                if not row:
                    break
                conn.execute("UPDATE outbox SET status='sending' WHERE id=%s", (row["id"],))
            if not row["phone"]:
                self.db.execute("UPDATE outbox SET status='failed',error='接收人尚未授权短信手机号' WHERE id=%s", (row["id"],))
                delivered += 1
                continue
            try:
                response = self.sms.send(row["kind"], row["phone"], list(row["params"]), row["body"])
                self.db.execute("UPDATE outbox SET status=%s,provider_id=%s,error=NULL WHERE id=%s", (response["status"], response.get("providerId"), row["id"]))
            except Exception as exc:
                uncertain = bool(getattr(exc, "uncertain", False))
                self.db.execute("UPDATE outbox SET status=%s,error=%s,provider_id=%s WHERE id=%s", ("unknown" if uncertain else "failed", str(exc)[:500], getattr(exc, "provider_id", None), row["id"]))
            delivered += 1
        return delivered

    def messages(self, user_id: str) -> dict:
        rows = self.db.fetchall("SELECT o.*,u.name recipient_name FROM outbox o JOIN users u ON u.id=o.recipient WHERE o.sender=%s OR o.recipient=%s ORDER BY o.created_at DESC LIMIT 100", (user_id, user_id))
        return {"messages": [{"id": row["id"], "kind": row["kind"], "body": row["body"], "status": row["status"], "createdAt": row["created_at"],
                              "approvalId": row["approval_id"], "direction": "received" if row["recipient"] == user_id and row["sender"] != user_id else "sent", "recipientName": row["recipient_name"]} for row in rows],
                "mode": self.mode, "smsProvider": self.sms.mode}
