from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    mode: str
    database_url: str
    auth_secret: str
    data_dir: Path
    public_url: str | None
    host: str
    port: int
    wechat: dict
    sms: dict

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()
        mode = os.getenv("APP_MODE", "demo")
        secret = os.getenv("AUTH_SECRET", "")
        if mode == "production" and len(secret) < 32:
            raise ValueError("生产环境必须配置至少32字符的AUTH_SECRET")
        if not secret:
            secret = "demo-only-secret-do-not-use-in-production-2026"
        return cls(
            mode=mode,
            database_url=os.getenv("DATABASE_URL", "postgresql://buy_before:local_buy_before_password@127.0.0.1:5432/buy_before"),
            auth_secret=secret,
            data_dir=Path(os.getenv("DATA_DIR", "./data")).resolve(),
            public_url=os.getenv("PUBLIC_URL") or None,
            host=os.getenv("HOST", "127.0.0.1"),
            port=int(os.getenv("PORT", "3210")),
            wechat={"app_id": os.getenv("WECHAT_APP_ID", ""), "app_secret": os.getenv("WECHAT_APP_SECRET", "")},
            sms={
                "mode": mode, "provider": os.getenv("SMS_PROVIDER", "mock"),
                "secret_id": os.getenv("TENCENT_SECRET_ID", ""), "secret_key": os.getenv("TENCENT_SECRET_KEY", ""),
                "sms_app_id": os.getenv("TENCENT_SMS_APP_ID", ""), "sign_name": os.getenv("TENCENT_SMS_SIGN_NAME", ""),
                "templates": {"otp": os.getenv("TENCENT_SMS_TEMPLATE_OTP", ""), "review": os.getenv("TENCENT_SMS_TEMPLATE_REVIEW", ""), "result": os.getenv("TENCENT_SMS_TEMPLATE_RESULT", "")},
                "region": os.getenv("TENCENT_SMS_REGION", "ap-guangzhou"),
            },
        )
