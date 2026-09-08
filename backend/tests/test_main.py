from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_does_not_require_authentication(tmp_path):
    settings = Settings(
        mode="demo", database_url="postgresql://unused:unused@127.0.0.1:1/unused",
        auth_secret="test-secret", data_dir=tmp_path, public_url=None, host="127.0.0.1", port=3210,
        sms={"mode": "demo", "provider": "mock", "secret_id": "", "secret_key": "", "sms_app_id": "", "sign_name": "", "templates": {"otp": "", "review": "", "result": ""}, "region": "ap-guangzhou"},
    )
    app = create_app(settings, initialize=False)
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "mode": "demo", "smsProvider": "mock"}
