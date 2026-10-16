"""Writable local settings endpoints."""


import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.core import settings as runtime_settings
from app.core.settings_store import (
    get_settings_token,
    load_saved,
    mask_key,
    save_saved,
)
from app.providers.factory import get_provider

TOKEN_HEADER = "x-jobpilot-token"

def _allowed_hosts() -> set[str]:
    return {h.strip().lower() for h in runtime_settings.get_settings().allowed_hosts.split(",") if h.strip()}

def require_host(request: Request) -> None:
    host = request.headers.get("host", "")
    hostname = host.split(":", 1)[0].strip().lower()
    if hostname not in _allowed_hosts():
        raise HTTPException(status_code=400, detail={"code": "invalid_host", "message": "Invalid Host header"})

def require_settings_token(request: Request) -> None:
    provided = request.headers.get(TOKEN_HEADER)
    expected = get_settings_token()
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail={"code": "invalid_settings_token", "message": "Settings token is required"})

router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_host)])


class SettingsResponse(BaseModel):
    ai_provider: str
    ai_model: str
    ai_api_key: str | None
    ai_configured: bool
    search_provider: str
    search_api_key: str | None
    search_configured: bool
    settings_writable: bool


class SettingsUpdate(BaseModel):
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_api_key: str | None = None
    search_provider: str | None = None
    search_api_key: str | None = None


class TestKeyResponse(BaseModel):
    ok: bool
    message: str


def _writable() -> bool:
    return runtime_settings.get_settings().settings_writable


def _current() -> tuple:
    settings = runtime_settings.get_settings()
    saved = load_saved()
    ai_provider = saved.ai_provider or settings.ai_provider
    ai_model = saved.ai_model or settings.ai_model
    ai_key = saved.ai_api_key or runtime_settings.resolve_ai_key(
        settings, saved.ai_provider, saved.ai_api_key
    )
    search_provider = saved.search_provider or settings.search_provider
    search_key = saved.search_api_key or runtime_settings.resolve_search_key(
        settings, saved.search_provider, saved.search_api_key
    )
    return settings, saved, ai_provider, ai_model, ai_key, search_provider, search_key


def _require_writable() -> None:
    if not _writable():
        raise HTTPException(status_code=403, detail={"code": "settings_read_only", "message": "Settings are read-only"})


@router.get("", response_model=SettingsResponse)
def get_settings() -> SettingsResponse:
    _settings, _saved, ai_provider, ai_model, ai_key, search_provider, search_key = _current()
    return SettingsResponse(
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_api_key=mask_key(ai_key),
        ai_configured=bool(ai_key),
        search_provider=search_provider,
        search_api_key=mask_key(search_key),
        search_configured=bool(search_key),
        settings_writable=_writable(),
    )


@router.put("", response_model=SettingsResponse)
def update_settings(request: Request, payload: SettingsUpdate) -> SettingsResponse:
    require_settings_token(request)
    _require_writable()
    saved = load_saved()
    if payload.ai_provider is not None:
        saved.ai_provider = payload.ai_provider
    if payload.ai_model is not None:
        saved.ai_model = payload.ai_model
    if payload.ai_api_key is not None:
        saved.ai_api_key = payload.ai_api_key
    if payload.search_provider is not None:
        saved.search_provider = payload.search_provider
    if payload.search_api_key is not None:
        saved.search_api_key = payload.search_api_key
    save_saved(saved)
    return get_settings()


@router.post("/test-key", response_model=TestKeyResponse)
async def test_key(request: Request) -> TestKeyResponse:
    require_settings_token(request)
    try:
        provider = get_provider()
    except Exception as exc:  # noqa: BLE001
        return TestKeyResponse(ok=False, message=str(exc))
    try:
        ok = await provider.health_check()
    except Exception:  # noqa: BLE001
        return TestKeyResponse(ok=False, message="Key invalid or provider unreachable")
    if not ok:
        return TestKeyResponse(ok=False, message="Key invalid or provider unreachable")
    return TestKeyResponse(ok=True, message="Key looks valid")


@router.get("/token")
def settings_token() -> dict[str, str]:
    return {"token": get_settings_token()}
