import pytest

from app.domain import DomainError
from app.wechat import exchange_login_code, exchange_phone_code


def test_wechat_code_exchange_returns_openid_without_exposing_session_key(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"openid": "openid-123", "session_key": "must-stay-server-side"}

    monkeypatch.setattr("app.wechat.httpx.get", lambda *args, **kwargs: Response())
    assert exchange_login_code({"app_id": "app", "app_secret": "secret"}, "wx-code") == "openid-123"


def test_wechat_code_exchange_requires_server_credentials():
    with pytest.raises(DomainError, match="尚未配置"):
        exchange_login_code({"app_id": "", "app_secret": ""}, "wx-code")


def test_phone_code_exchange_returns_mainland_number(monkeypatch):
    class TokenResponse:
        def raise_for_status(self): return None
        def json(self): return {"access_token": "token"}

    class PhoneResponse:
        def raise_for_status(self): return None
        def json(self): return {"errcode": 0, "phone_info": {"purePhoneNumber": "13800138000"}}

    monkeypatch.setattr("app.wechat.httpx.get", lambda *args, **kwargs: TokenResponse())
    monkeypatch.setattr("app.wechat.httpx.post", lambda *args, **kwargs: PhoneResponse())
    assert exchange_phone_code({"app_id": "app", "app_secret": "secret"}, "phone-code") == "13800138000"
