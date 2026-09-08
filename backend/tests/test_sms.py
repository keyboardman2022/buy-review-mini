import json
from datetime import datetime, timezone

import pytest

from app.sms import SmsError, create_sms_provider, normalize_phone, sign_tc3


def test_mock_is_demo_only():
    provider = create_sms_provider({"mode": "demo", "provider": "mock"})
    assert provider.send("otp", "13800138000", ["123456", "5"], "body") == {"status": "mock"}
    with pytest.raises(ValueError, match="生产环境"):
        create_sms_provider({"mode": "production", "provider": "mock"})


def test_mainland_phone_is_normalized_to_e164():
    assert normalize_phone("13800138000") == "+8613800138000"
    assert normalize_phone("+8613800138000") == "+8613800138000"


def test_tc3_signature_matches_independent_fixture():
    payload = json.dumps({
        "PhoneNumberSet": ["+8613800138000"], "SmsSdkAppId": "1400006666",
        "SignName": "TestSign", "TemplateId": "1110", "TemplateParamSet": ["4370", "5"],
    }, separators=(",", ":"), ensure_ascii=False)
    authorization = sign_tc3(
        secret_id="AKIDEXAMPLE",
        secret_key="SECRETKEYEXAMPLE",
        payload=payload,
        timestamp=1_551_113_065,
    )
    assert authorization == (
        "TC3-HMAC-SHA256 Credential=AKIDEXAMPLE/2019-02-25/sms/tc3_request, "
        "SignedHeaders=content-type;host;x-tc-action, "
        "Signature=a4069f084fcf415e62ab9df4793ec361cabef25d998878f220142a325865ba50"
    )


def test_tencent_adapter_selects_template_and_rejects_provider_error(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        def json(self):
            return {"Response": {"SendStatusSet": [{"Code": "FailedOperation.Template", "Message": "bad", "SerialNo": ""}], "RequestId": "r1"}}

    def fake_post(url, *, content, headers, timeout):
        captured.update(url=url, body=json.loads(content), headers=headers, timeout=timeout)
        return Response()

    monkeypatch.setattr("app.sms.httpx.post", fake_post)
    provider = create_sms_provider({
        "mode": "production", "provider": "tencent", "secret_id": "id", "secret_key": "key",
        "sms_app_id": "app", "sign_name": "签名", "region": "ap-guangzhou",
        "templates": {"otp": "1", "review": "2", "result": "3"},
    })
    with pytest.raises(SmsError) as caught:
        provider.send("review", "13800138000", ["小林", "耳机"], "body")
    assert caught.value.uncertain is False
    assert captured["body"]["PhoneNumberSet"] == ["+8613800138000"]
    assert captured["body"]["TemplateId"] == "2"
