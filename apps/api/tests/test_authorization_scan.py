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
