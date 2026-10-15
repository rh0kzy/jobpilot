from fastapi.testclient import TestClient

from app.main import app


def test_settings_get_masks_keys(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBPILOT_CONFIG_PATH", str(tmp_path / "s.json"))
    monkeypatch.setenv("JOBPILOT_SETTINGS_TOKEN", "tok-1")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret-key")
    monkeypatch.setenv("SETTINGS_WRITABLE", "true")
    client = TestClient(app, base_url="http://localhost")
    response = client.get("/settings")
    assert response.status_code == 200
    data = response.json()
    assert "gemini-secret-key" not in response.text
    assert data["ai_api_key"] is None or "*" in (data["ai_api_key"] or "")
    assert data["settings_writable"] is True


def test_put_requires_token(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBPILOT_CONFIG_PATH", str(tmp_path / "s.json"))
    monkeypatch.setenv("JOBPILOT_SETTINGS_TOKEN", "tok-1")
    monkeypatch.setenv("SETTINGS_WRITABLE", "true")
    client = TestClient(app, base_url="http://localhost")
    response = client.put("/settings", json={"ai_model": "x"})
    assert response.status_code == 403


def test_invalid_host_rejected(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBPILOT_CONFIG_PATH", str(tmp_path / "s.json"))
    monkeypatch.setenv("JOBPILOT_SETTINGS_TOKEN", "tok-1")
    client = TestClient(app, base_url="http://evil.com")
    response = client.get("/settings", headers={"Host": "evil.com"})
    assert response.status_code == 400


def test_put_with_token_saves(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBPILOT_CONFIG_PATH", str(tmp_path / "s.json"))
    monkeypatch.setenv("JOBPILOT_SETTINGS_TOKEN", "tok-1")
    monkeypatch.setenv("SETTINGS_WRITABLE", "true")
    client = TestClient(app, base_url="http://localhost")
    response = client.put(
        "/settings",
        json={"ai_api_key": "saved-key", "ai_provider": "gemini", "ai_model": "gemini-test"},
        headers={"X-JobPilot-Token": "tok-1"},
    )
    assert response.status_code == 200
    assert "saved-key" not in response.text
    assert response.json()["ai_configured"] is True


def test_writable_false_blocks_put(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBPILOT_CONFIG_PATH", str(tmp_path / "s.json"))
    monkeypatch.setenv("JOBPILOT_SETTINGS_TOKEN", "tok-1")
    monkeypatch.setenv("SETTINGS_WRITABLE", "false")
    client = TestClient(app, base_url="http://localhost")
    response = client.put(
        "/settings",
        json={"ai_model": "x"},
        headers={"X-JobPilot-Token": "tok-1"},
    )
    assert response.status_code == 403