from app.normalize.normalizer import scan_authorization_text


def test_authorization_scan_multilingual():
    text = "Authorized to work in the US. W2 only. Doit résider au Canada. Ciudadano requerido."
    matches = scan_authorization_text(text)
    assert "authorized to work" in matches
    assert "w2" in matches
    assert "doit résider" in matches or "doit resid" in " ".join(matches)
    assert "ciudadano" in matches


def test_no_invented_authorization():
    assert scan_authorization_text("Remote software engineer role") == []


def test_authorization_boilerplate_fixture_has_no_requirement():
    from pathlib import Path
    text = Path("tests/fixtures/auth_boilerplate.txt").read_text()
    from app.normalize.normalizer import scan_authorization_requirements
    assert scan_authorization_requirements(text) == []


def test_authorization_requirement_fixture_returns_sentence():
    from pathlib import Path
    text = Path("tests/fixtures/auth_requirement.txt").read_text()
    from app.normalize.normalizer import extract_work_authorization, scan_authorization_requirements
    matches = scan_authorization_requirements(text)
    assert matches
    value = extract_work_authorization(text)
    assert "authorized to work" in (value or "").lower()
    assert "security clearance" in (value or "").lower()
