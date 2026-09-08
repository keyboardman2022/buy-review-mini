from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import Body, Depends, FastAPI, Header, Query, Request
from fastapi.responses import JSONResponse, Response
from psycopg.errors import UniqueViolation

from .config import Settings
from .db import Database
from .domain import DomainError
from .service import Service
from .sms import create_sms_provider


def create_app(settings: Settings | None = None, *, clock=None, initialize: bool = True) -> FastAPI:
    settings = settings or Settings.from_env()
    db = Database(settings.database_url)
    service_options = {"secret": settings.auth_secret, "data_dir": settings.data_dir, "mode": settings.mode, "sms": create_sms_provider(settings.sms)}
    if clock is not None:
        service_options["clock"] = clock
    service = Service(db, **service_options)

    async def worker() -> None:
        while True:
            try:
                await asyncio.to_thread(service.expire_pending)
                await asyncio.to_thread(service.deliver_outbox_once)
            except Exception:
                pass
            await asyncio.sleep(2)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if initialize:
            await asyncio.to_thread(db.initialize)
        task = asyncio.create_task(worker()) if initialize else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="买前问问 API", version="0.2.0", lifespan=lifespan)
    app.state.service = service
    app.state.settings = settings

    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError):
        return JSONResponse({"error": exc.message}, status_code=exc.status_code)

    @app.exception_handler(UniqueViolation)
    async def unique_conflict(_: Request, __: UniqueViolation):
        return JSONResponse({"error": "操作发生冲突，请刷新后重试"}, status_code=409)

    def base_url(request: Request) -> str:
        return (settings.public_url or str(request.base_url)).rstrip("/")

    def current_user(authorization: str | None = Header(default=None)) -> dict:
        token = authorization[7:] if authorization and authorization.startswith("Bearer ") else None
        return service.authenticate(token)

    def token_value(authorization: str | None = Header(default=None)) -> str:
        return authorization[7:] if authorization and authorization.startswith("Bearer ") else ""

    @app.get("/api/health")
    def health():
        return {"ok": True, "mode": settings.mode, "smsProvider": service.sms.mode}

    @app.post("/api/auth/code")
    def request_code(request: Request, payload: dict = Body(...)):
        return service.request_code(payload.get("phone"), request.client.host if request.client else "unknown")

    @app.post("/api/auth/login")
    def login(payload: dict = Body(...)):
        return service.login(payload)

    @app.post("/api/auth/demo")
    def demo(payload: dict = Body(...)):
        return service.demo_login(payload.get("account"))

    @app.post("/api/auth/logout")
    def logout(_: dict = Depends(current_user), token: str = Depends(token_value)):
        return service.logout(token)

    @app.get("/api/me")
    def me(user: dict = Depends(current_user)):
        return service.me(user)

    @app.patch("/api/me")
    def rename(payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.rename(user["id"], payload.get("name"))

    @app.get("/api/friends")
    def friends(user: dict = Depends(current_user)):
        return service.friends(user["id"])

    @app.post("/api/friends/request")
    def friend_request(payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.request_friend(user["id"], payload.get("code"))

    @app.post("/api/friends/{request_id}/respond")
    def friend_respond(request_id: str, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.respond_friend(user["id"], request_id, payload.get("accept"))

    @app.delete("/api/friends/{friend_id}")
    def friend_delete(friend_id: str, user: dict = Depends(current_user)):
        return service.remove_friend(user["id"], friend_id)

    @app.post("/api/media")
    def media_upload(request: Request, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.upload_media(user["id"], payload, base_url(request))

    @app.get("/api/media/{media_id}")
    def media_read(media_id: str, expires: str = Query(...), sig: str = Query(...)):
        content, mime = service.read_media(media_id, expires, sig)
        return Response(content, media_type=mime, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})

    @app.get("/api/items")
    def items(request: Request, scope: str = Query("feed"), user: dict = Depends(current_user)):
        return service.list_items(user["id"], scope, base_url(request))

    @app.post("/api/items")
    def item_create(request: Request, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.create_item(user["id"], payload, base_url(request))

    @app.get("/api/items/{item_id}")
    def item_detail(item_id: str, request: Request, user: dict = Depends(current_user)):
        return service.item_detail(user["id"], item_id, base_url(request))

    @app.patch("/api/items/{item_id}")
    def item_update(item_id: str, request: Request, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.update_item(user["id"], item_id, payload, base_url(request))

    @app.delete("/api/items/{item_id}")
    def item_delete(item_id: str, user: dict = Depends(current_user)):
        return service.delete_item(user["id"], item_id)

    @app.post("/api/items/{item_id}/comments")
    def comment_create(item_id: str, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.add_comment(user["id"], item_id, payload.get("text"))

    @app.delete("/api/comments/{comment_id}")
    def comment_delete(comment_id: str, user: dict = Depends(current_user)):
        return service.delete_comment(user["id"], comment_id)

    @app.post("/api/items/{item_id}/reaction")
    def reaction(item_id: str, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.react(user["id"], item_id, payload.get("value"))

    @app.get("/api/approvals")
    def approvals(request: Request, scope: str = Query("inbox"), user: dict = Depends(current_user)):
        return service.list_approvals(user["id"], scope, base_url(request))

    @app.post("/api/approvals")
    def approval_create(request: Request, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.create_approval(user["id"], payload, base_url(request))

    @app.get("/api/approvals/{approval_id}")
    def approval_detail(approval_id: str, request: Request, user: dict = Depends(current_user)):
        return service.approval_detail(user["id"], approval_id, base_url(request))

    @app.post("/api/approvals/{approval_id}/vote")
    def approval_vote(approval_id: str, request: Request, payload: dict = Body(...), user: dict = Depends(current_user)):
        return service.vote(user["id"], approval_id, payload, base_url(request))

    @app.post("/api/approvals/{approval_id}/cancel")
    def approval_cancel(approval_id: str, request: Request, user: dict = Depends(current_user)):
        return service.cancel_approval(user["id"], approval_id, base_url(request))

    @app.get("/api/messages")
    def messages(user: dict = Depends(current_user)):
        return service.messages(user["id"])

    return app


app = create_app()
