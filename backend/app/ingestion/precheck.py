import io

from pypdf import PdfReader

MIN_CHARS_PER_PAGE = 20
MIN_ALPHA_RATIO = 0.4


def extract_native_text(content: bytes) -> list[str]:
    """Return per-page text for a PDF. Empty string for pages with no text layer."""
    reader = PdfReader(io.BytesIO(content))
    return [page.extract_text() or "" for page in reader.pages]


def looks_like_readable_text(text: str) -> bool:
    """Cheap heuristic to reject junk/garbage before spending on LLM extraction.

    Not a language-detection or grammar check — just filters out empty,
    near-empty, or non-text-like content (e.g. binary garbage that slipped
    through as a PDF, or a scanned page with zero real text layer).
    """
    stripped = text.strip()
    if len(stripped) < MIN_CHARS_PER_PAGE:
        return False

    alpha_count = sum(1 for ch in stripped if ch.isalpha())
    alpha_ratio = alpha_count / len(stripped)
    return alpha_ratio >= MIN_ALPHA_RATIO


def has_usable_native_text(pages: list[str]) -> bool:
    """True if at least one page has a real, readable text layer.

    Pages that fail this need the vision-LLM OCR fallback path (Day 2) instead.
    """
    return any(looks_like_readable_text(page) for page in pages)
