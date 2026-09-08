from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

HOST = "sms.tencentcloudapi.com"
CONTENT_TYPE = "application/json; charset=utf-8"
ACTION = "SendSms"
VERSION = "2021-01-11"
SERVICE = "sms"


class SmsError(RuntimeError):
    def __init__(self, message: str, *, uncertain: bool, provider_code: str | None = None, provider_id: str | None = None):
        super().__init__(message)
        self.uncertain = uncertain
        self.provider_code = provider_code
        self.provider_id = provider_id


def normalize_phone(phone: str) -> str:
    if len(phone) == 11 and phone.startswith("1") and phone.isdigit():
        return "+86" + phone
    if phone.startswith("+") and phone[1:].isdigit():
        return phone
    raise TypeError("手机号格式不正确")


def _sha256(value: bytes | str) -> str:
    data = value.encode() if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def _hmac(key: bytes | str, value: str) -> bytes:
    data = key.encode() if isinstance(key, str) else key
    return hmac.new(data, value.encode(), hashlib.sha256).digest()


def sign_tc3(*, secret_id: str, secret_key: str, payload: str, timestamp: int) -> str:
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    signed_headers = "content-type;host;x-tc-action"
    canonical_headers = f"content-type:{CONTENT_TYPE}\nhost:{HOST}\nx-tc-action:{ACTION.lower()}\n"
    canonical_request = "\n".join(["POST", "/", "", canonical_headers, signed_headers, _sha256(payload)])
    scope = f"{date}/{SERVICE}/tc3_request"
    string_to_sign = "\n".join(["TC3-HMAC-SHA256", str(timestamp), scope, _sha256(canonical_request)])
    key = _hmac(_hmac(_hmac("TC3" + secret_key, date), SERVICE), "tc3_request")
    signature = hmac.new(key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    return f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"


class MockSms:
    mode = "mock"

    def send(self, kind: str, phone: str, params: list[str], body: str) -> dict:
        _validate_message(kind, phone, params, body, normalize=False)
        return {"status": "mock"}


@dataclass
class TencentSms:
    secret_id: str
    secret_key: str
    sms_app_id: str
    sign_name: str
    templates: dict[str, str]
    region: str
    mode: str = "tencent"

    def send(self, kind: str, phone: str, params: list[str], body: str) -> dict:
        normalized = _validate_message(kind, phone, params, body)
        payload = json.dumps({
            "PhoneNumberSet": [normalized], "SmsSdkAppId": self.sms_app_id,
            "SignName": self.sign_name, "TemplateId": self.templates[kind],
            "TemplateParamSet": params,
        }, separators=(",", ":"), ensure_ascii=False)
        timestamp = int(time.time())
        headers = {
            "Authorization": sign_tc3(secret_id=self.secret_id, secret_key=self.secret_key, payload=payload, timestamp=timestamp),
            "Content-Type": CONTENT_TYPE, "Host": HOST, "X-TC-Action": ACTION,
            "X-TC-Region": self.region, "X-TC-Timestamp": str(timestamp), "X-TC-Version": VERSION,
        }
        try:
            response = httpx.post(f"https://{HOST}/", content=payload.encode(), headers=headers, timeout=10.0)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise SmsError("短信发送结果未知", uncertain=True) from exc
        if response.status_code < 200 or response.status_code >= 300:
            raise SmsError("短信供应商明确拒绝请求", uncertain=False)
        try:
            result = response.json().get("Response", {})
            request_id = result.get("RequestId")
            if result.get("Error"):
                error = result["Error"]
                raise SmsError("短信供应商明确拒绝请求", uncertain=False, provider_code=error.get("Code"), provider_id=request_id)
            entries = result.get("SendStatusSet", [])
            if len(entries) != 1:
                raise SmsError("短信供应商响应无法确认", uncertain=True, provider_id=request_id)
            entry = entries[0]
            if entry.get("Code") != "Ok":
                raise SmsError("短信供应商明确拒绝请求", uncertain=False, provider_code=entry.get("Code"), provider_id=request_id)
            serial = entry.get("SerialNo")
            if not serial:
                raise SmsError("短信供应商响应缺少受理编号", uncertain=True, provider_id=request_id)
            return {"status": "sent", "providerId": serial}
        except SmsError:
            raise
        except (TypeError, ValueError, AttributeError) as exc:
            raise SmsError("短信供应商响应无法解析", uncertain=True) from exc


def _validate_message(kind: str, phone: str, params: list[str], body: str, *, normalize: bool = True) -> str:
    expected = {"otp": 2, "review": 2, "result": 2}
    if kind not in expected or not isinstance(params, list) or len(params) != expected.get(kind) or not all(isinstance(v, str) for v in params) or not isinstance(body, str):
        raise TypeError("短信内容格式不正确")
    return normalize_phone(phone) if normalize else phone


def create_sms_provider(config: dict[str, Any]):
    mode, provider = config.get("mode"), config.get("provider", "mock")
    if mode == "demo" and provider == "mock":
        return MockSms()
    if mode == "production" and provider != "tencent":
        raise ValueError("生产环境必须使用已配置的腾讯云短信，不能使用演示短信")
    if provider != "tencent":
        raise ValueError("短信供应商只能是mock或tencent")
    required = ["secret_id", "secret_key", "sms_app_id", "sign_name", "region"]
    for key in required:
        if not isinstance(config.get(key), str) or not config[key].strip():
            raise ValueError(f"腾讯云短信缺少配置：{key}")
    templates = config.get("templates") or {}
    for kind in ("otp", "review", "result"):
        if not isinstance(templates.get(kind), str) or not templates[kind].strip():
            raise ValueError(f"腾讯云短信缺少配置：templates.{kind}")
    return TencentSms(config["secret_id"], config["secret_key"], config["sms_app_id"], config["sign_name"], templates, config["region"])
