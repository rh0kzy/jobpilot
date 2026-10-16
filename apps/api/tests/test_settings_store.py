
from app.core import settings as runtime_settings
from app.core.settings_store import (
    config_path,
    get_settings_token,
    load_saved,
    mask_key,
    save_saved,
)


def test_mask_key():
    assert mask_key(None) is None
    assert mask_key("secret1234") == "********1234"


def test_file_permissions_and_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBPILOT_CONFIG_PATH", str(tmp_path / "s.json"))
    save_saved(load_saved().__class__(ai_api_key="abc123", ai_provider="gemini"))
    path = config_path()
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600
    saved = load_saved()
    assert saved.ai_api_key == "abc123"


def test_saved_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBPILOT_CONFIG_PATH", str(tmp_path / "s.json"))
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.setenv("SETTINGS_WRITABLE", "false")
    save_saved(load_saved().__class__(ai_api_key="saved-key", ai_provider="gemini"))
    settings = runtime_settings.get_settings()
    # settings object itself reads env only
    assert settings.gemini_api_key == "env-key"
    saved = load_saved()
    resolved = runtime_settings.resolve_ai_key(settings, saved.ai_provider, saved.ai_api_key)
    assert resolved == "saved-key"


def test_keys_not_in_responses():
    # Settings response uses masked values; ensure mask never returns full value.
    assert mask_key("supersecret") != "supersecret"


def test_get_settings_token_env(monkeypatch):
    monkeypatch.setenv("JOBPILOT_SETTINGS_TOKEN", "tok-1")
    assert get_settings_token() == "tok-1"