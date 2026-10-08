"""Runtime configuration, all env-overridable.

Secrets are dev defaults only. Production must inject FIRSTLIGHT_SECRET.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    app_name: str = "FirstLight"
    version: str = "0.2.0"
    host: str = os.environ.get("FIRSTLIGHT_HOST", "127.0.0.1")
    port: int = int(os.environ.get("FIRSTLIGHT_PORT", "8000"))
    secret: str = os.environ.get("FIRSTLIGHT_SECRET", "dev-only-secret-change-me")
    token_ttl_seconds: int = int(os.environ.get("FIRSTLIGHT_TOKEN_TTL", "86400"))
    db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("FIRSTLIGHT_DB", str(_REPO / "data" / "firstlight.db"))
        )
    )
    data_dir: Path = field(
        default_factory=lambda: Path(
            os.environ.get("FIRSTLIGHT_DATA", str(_REPO / "data"))
        )
    )
    web_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("FIRSTLIGHT_WEB", str(_REPO / "web")))
    )
    auto_seed: bool = field(default_factory=lambda: _bool("FIRSTLIGHT_AUTO_SEED", True))
    notify_channel: str = os.environ.get("FIRSTLIGHT_NOTIFY", "console")
    smtp_host: str = os.environ.get("FIRSTLIGHT_SMTP_HOST", "")
    smtp_port: int = int(os.environ.get("FIRSTLIGHT_SMTP_PORT", "587"))
    smtp_user: str = os.environ.get("FIRSTLIGHT_SMTP_USER", "")
    smtp_password: str = os.environ.get("FIRSTLIGHT_SMTP_PASSWORD", "")
    webhook_url: str = os.environ.get("FIRSTLIGHT_WEBHOOK_URL", "")
    log_level: str = os.environ.get("FIRSTLIGHT_LOG", "INFO")

    @property
    def db_exists(self) -> bool:
        return self.db_path.exists()


settings = Settings()