"""Persistent (local) settings store with restrictive permissions."""

import json
import os
import secrets
from pathlib import Path

from pydantic import BaseModel


class SavedSettings(BaseModel):
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = None
    search_provider: str | None = None
    search_api_key: str | None = None


def config_path() -> Path:
    raw = os.getenv("JOBPILOT_CONFIG_PATH")
    if raw:
        return Path(raw)
    return Path.home() / ".config" / "jobpilot" / "settings.json"


def load_saved() -> SavedSettings:
    path = config_path()
    if not path.exists():
        return SavedSettings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SavedSettings()
    return SavedSettings(**data)


def save_saved(settings: SavedSettings) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def mask_key(value: str | None) -> str | None:
    if not value:
        return None
    return "*" * 8 + value[-4:]


def token_file_path() -> Path:
    raw = os.getenv("JOBPILOT_TOKEN_PATH")
    if raw:
        return Path(raw)
    return config_path().with_name("settings.token")


def get_settings_token() -> str:
    from app.core import settings as runtime_settings

    env = os.getenv("JOBPILOT_SETTINGS_TOKEN") or os.getenv("SETTINGS_LOCAL_TOKEN")
    try:
        env = env or runtime_settings.get_settings().local_settings_token
    except Exception:  # noqa: BLE001, S110
        pass
    if env:
        return str(env)
    path = token_file_path()
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    token = secrets.token_urlsafe(32)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token
