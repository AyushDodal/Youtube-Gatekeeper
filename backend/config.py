"""Validated configuration. Environment values override the local .env file."""
import os
from pathlib import Path
from urllib.parse import urlparse

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

ROOT = Path(__file__).resolve().parent.parent


class YouTubePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    min_session_minutes: int = Field(default=5, ge=5)
    max_session_minutes: int = Field(default=60, ge=5, le=1440)
    daily_limit_minutes: int = Field(default=120, ge=5, le=1440)

    @model_validator(mode="after")
    def check_limits(self):
        if self.min_session_minutes > self.max_session_minutes:
            raise ValueError("Minimum session duration must not exceed maximum.")
        return self


class GatekeeperPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    max_question_rounds: int = Field(default=8, ge=1, le=30)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    youtube: YouTubePolicy = Field(default_factory=YouTubePolicy)
    gatekeeper: GatekeeperPolicy = Field(default_factory=GatekeeperPolicy)
    ollama_model: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    database_path: Path = ROOT / "data" / "gatekeeper.sqlite3"
    hosts_path: Path | None = None
    dry_run: bool = False
    poll_interval_seconds: float = Field(default=1.0, ge=0.05, le=10)

    @field_validator("ollama_base_url")
    @classmethod
    def local_model_only(cls, value):
        parsed = urlparse(value)
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"", "/"}):
            raise ValueError("OLLAMA_BASE_URL must be an HTTP loopback URL without credentials or path.")
        return value.rstrip("/")


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    config_path = Path(os.getenv("GATEKEEPER_CONFIG_PATH", str(ROOT / "config.yaml")))
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = yaml.safe_load(config_path.read_text(encoding="utf-8-sig")) or {}
    database_path = Path(os.getenv("GATEKEEPER_DATABASE_PATH", "data/gatekeeper.sqlite3"))
    if not database_path.is_absolute():
        database_path = ROOT / database_path
    dry_run = os.getenv("GATEKEEPER_DRY_RUN", "false").lower()
    if dry_run not in {"true", "false", "1", "0"}:
        raise ValueError("GATEKEEPER_DRY_RUN must be true or false.")
    preview = dry_run in {"true", "1"}
    # Keep simulation sessions entirely separate from real access grants.
    if preview and "GATEKEEPER_DATABASE_PATH" not in os.environ:
        database_path = ROOT / "data" / "preview.sqlite3"
    return Settings(**config, ollama_model=os.getenv("OLLAMA_MODEL", "").strip(),
                    ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
                    database_path=database_path, dry_run=preview,
                    hosts_path=ROOT / "data" / "hosts.preview" if preview else None)
