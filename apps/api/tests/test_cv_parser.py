from pathlib import Path

from app.cv.parser import extract_text


def test_pdf_en():
    text = extract_text(Path("tests/fixtures/cv_en.pdf"))
    assert "Python" in text


def test_docx_fr():
    text = extract_text(Path("tests/fixtures/cv_fr.docx"))
    assert "FastAPI" in text or "Python" in text


def test_reject_bad_suffix():
    import pytest

    with pytest.raises(ValueError):
        extract_text(Path("tests/fixtures/nope.txt"))