import io

import magic
from pypdf import PdfReader

from app.config import settings

ALLOWED_MIME_TYPES = {"application/pdf", "image/png", "image/jpeg", "image/webp"}


class UploadValidationError(Exception):
    """Raised with a user-facing reason when an upload fails validation."""


def sniff_mime_type(content: bytes) -> str:
    """Determine the real file type from its bytes — never trust the client's
    Content-Type header or filename extension, both are trivially spoofable."""
    return magic.from_buffer(content, mime=True)


def validate_upload(content: bytes) -> str:
    """Validate an uploaded file's size, real type, and (for PDFs) page count.

    Returns the sniffed mime type on success. Raises UploadValidationError
    with a user-facing reason on failure. Must run before any expensive
    processing (OCR/LLM calls) is attempted.
    """
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise UploadValidationError(f"File exceeds the {settings.max_upload_mb}MB limit.")

    if len(content) == 0:
        raise UploadValidationError("Uploaded file is empty.")

    mime_type = sniff_mime_type(content)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise UploadValidationError(
            f"Unsupported file type ({mime_type}). Only PDF, PNG, JPEG, and WebP are accepted."
        )

    if mime_type == "application/pdf":
        try:
            reader = PdfReader(io.BytesIO(content))
            page_count = len(reader.pages)
        except Exception as exc:
            raise UploadValidationError("Could not read this PDF — it may be corrupted.") from exc

        if page_count > settings.max_upload_pages:
            raise UploadValidationError(
                f"PDF has {page_count} pages, which exceeds the {settings.max_upload_pages}-page limit."
            )

    return mime_type
