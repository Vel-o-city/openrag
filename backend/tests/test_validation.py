import io

import pytest
from pypdf import PdfWriter

from app.ingestion.validation import UploadValidationError, sniff_mime_type, validate_upload


def make_pdf_bytes(num_pages: int = 1) -> bytes:
    writer = PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_sniff_mime_type_pdf():
    assert sniff_mime_type(make_pdf_bytes()) == "application/pdf"


def test_sniff_mime_type_rejects_spoofed_extension():
    # a plain text file's real bytes, regardless of what filename/extension it's given
    assert sniff_mime_type(b"just plain text, not a real pdf") == "text/plain"


def test_validate_upload_accepts_valid_pdf():
    mime_type = validate_upload(make_pdf_bytes())
    assert mime_type == "application/pdf"


def test_validate_upload_rejects_empty_file():
    with pytest.raises(UploadValidationError, match="empty"):
        validate_upload(b"")


def test_validate_upload_rejects_disallowed_type():
    with pytest.raises(UploadValidationError, match="Unsupported file type"):
        validate_upload(b"just plain text, not a real pdf")


def test_validate_upload_rejects_oversized_file(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "max_upload_mb", 0)
    with pytest.raises(UploadValidationError, match="exceeds the 0MB limit"):
        validate_upload(make_pdf_bytes())


def test_validate_upload_rejects_too_many_pages(monkeypatch):
    from app import config

    monkeypatch.setattr(config.settings, "max_upload_pages", 2)
    with pytest.raises(UploadValidationError, match="exceeds the 2-page limit"):
        validate_upload(make_pdf_bytes(num_pages=3))
