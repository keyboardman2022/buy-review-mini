from __future__ import annotations

import httpx

from .domain import DomainError, ensure, required_text


def exchange_login_code(config: dict, code_value: object) -> str:
    code = required_text(code_value, "微信登录凭证", 256)
    app_id = config.get("app_id", "")
    app_secret = config.get("app_secret", "")
    ensure(app_id and app_secret, "服务端尚未配置微信登录密钥", 503)
    try:
        response = httpx.get(
            "https://api.weixin.qq.com/sns/jscode2session",
            params={"appid": app_id, "secret": app_secret, "js_code": code, "grant_type": "authorization_code"},
            timeout=8.0,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise DomainError("微信登录服务暂时不可用，请重试", 503) from exc
    if payload.get("errcode"):
        raise DomainError("微信登录凭证已失效，请重新登录", 401)
    openid = payload.get("openid")
    ensure(isinstance(openid, str) and openid, "微信登录未返回用户标识", 503)
    return openid


def exchange_phone_code(config: dict, code_value: object) -> str:
    code = required_text(code_value, "手机号授权凭证", 256)
    app_id = config.get("app_id", "")
    app_secret = config.get("app_secret", "")
    ensure(app_id and app_secret, "服务端尚未配置微信登录密钥", 503)
    try:
        token_response = httpx.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": app_id, "secret": app_secret},
            timeout=8.0,
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        ensure(access_token, "获取微信接口凭证失败", 503)
        phone_response = httpx.post(
            "https://api.weixin.qq.com/wxa/business/getuserphonenumber",
            params={"access_token": access_token}, json={"code": code}, timeout=8.0,
        )
        phone_response.raise_for_status()
        payload = phone_response.json()
    except DomainError:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise DomainError("微信手机号授权服务暂时不可用", 503) from exc
    if payload.get("errcode"):
        raise DomainError("手机号授权已失效，请重新授权", 400)
    phone = (payload.get("phone_info") or {}).get("purePhoneNumber")
    ensure(isinstance(phone, str) and phone, "微信没有返回手机号", 503)
    return phone
