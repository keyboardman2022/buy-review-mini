from __future__ import annotations

import re
from typing import Literal, Sequence
from urllib.parse import urlparse


class DomainError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


Decision = Literal["accept", "reject"]
Rule = Literal["veto", "majority", "unanimous"]
Status = Literal["pending", "approved", "rejected"]
RULES = {"veto", "majority", "unanimous"}


def ensure(condition: object, message: str, status_code: int = 400) -> None:
    if not condition:
        raise DomainError(message, status_code)


def required_text(value: object, label: str, maximum: int) -> str:
    ensure(isinstance(value, str), f"{label}格式不正确")
    text = value.strip()
    ensure(0 < len(text) <= maximum, f"{label}请填写1～{maximum}个字")
    return text


def optional_text(value: object, label: str, maximum: int) -> str:
    if value is None or value == "":
        return ""
    return required_text(value, label, maximum)


def parse_phone(value: object) -> str:
    ensure(isinstance(value, str) and re.fullmatch(r"1[3-9]\d{9}", value), "请输入11位中国大陆手机号")
    return value


def parse_price(value: object) -> int:
    ensure(isinstance(value, int) and not isinstance(value, bool) and 0 < value <= 100_000_000, "价格必须大于0且不超过100万元，最多两位小数")
    return value


def parse_product(payload: dict) -> dict:
    link = optional_text(payload.get("link"), "商品链接", 2000)
    if link:
        parsed = urlparse(link)
        ensure(parsed.scheme in {"http", "https"} and bool(parsed.netloc) and not parsed.username and not parsed.password, "商品链接需以http或https开头")
    visibility = payload.get("visibility")
    ensure(visibility in {"friends", "private"}, "请选择可见范围")
    images = payload.get("images")
    ensure(isinstance(images, list) and len(images) <= 3 and all(isinstance(item, str) for item in images), "最多上传3张图片")
    return {
        "title": required_text(payload.get("title"), "商品名称", 80),
        "price": parse_price(payload.get("price")),
        "reason": required_text(payload.get("reason"), "购买理由", 1000),
        "category": required_text(payload.get("category"), "分类", 20),
        "link": link,
        "visibility": visibility,
        "images": list(dict.fromkeys(images)),
    }


def evaluate(rule: str, votes: Sequence[Decision | None]) -> Status:
    ensure(rule in RULES and bool(votes), "审批规则或人数不正确")
    ensure(all(vote in {None, "accept", "reject"} for vote in votes), "投票内容不正确")
    yes = votes.count("accept")
    no = votes.count("reject")
    total = len(votes)
    if rule == "veto":
        return "rejected" if no else "approved" if yes == total else "pending"
    if rule == "majority":
        return "approved" if yes > total / 2 else "rejected" if total - no <= total / 2 else "pending"
    return "pending" if yes + no < total else "approved" if yes == total else "rejected"
