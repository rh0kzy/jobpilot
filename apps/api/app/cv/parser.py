"""Extract raw text from CV files (PDF/DOCX)."""

from pathlib import Path


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _extract_pdf(path)
    if suffix in {".docx", ".doc"}:
        return _extract_docx(path)
    raise ValueError(f"Unsupported CV format: {suffix}")


def _extract_pdf(path: Path) -> str:
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(path))
        return "\n".join(page.get_text() for page in doc)
    except Exception:  # noqa: BLE001, S110
        pass
    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception:  # noqa: BLE001
        return ""


def _extract_docx(path: Path) -> str:
    try:
        import docx

        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)
    except Exception:  # noqa: BLE001
        return ""
