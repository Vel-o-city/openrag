"""Recursive character-based chunking, in the spirit of LangChain's
RecursiveCharacterTextSplitter but dependency-free — split on paragraph, then
line, then sentence, then word boundaries, falling back to a hard character
cut only when a single unit is still too long after every separator.
"""

CHARS_PER_TOKEN = 4  # rough heuristic, good enough for chunk sizing
TARGET_TOKENS = 650
OVERLAP_RATIO = 0.125

TARGET_CHARS = TARGET_TOKENS * CHARS_PER_TOKEN
OVERLAP_CHARS = int(TARGET_CHARS * OVERLAP_RATIO)

SEPARATORS = ["\n\n", "\n", ". ", " "]


def _hard_split(text: str) -> list[str]:
    return [text[i : i + TARGET_CHARS] for i in range(0, len(text), TARGET_CHARS)]


def _split_recursive(text: str, separators: list[str]) -> list[str]:
    if len(text) <= TARGET_CHARS:
        return [text]

    if not separators:
        return _hard_split(text)

    sep, rest = separators[0], separators[1:]
    raw_parts = text.split(sep)
    if len(raw_parts) == 1:
        return _split_recursive(text, rest)

    parts = [p + sep for p in raw_parts[:-1]] + [raw_parts[-1]]

    pieces: list[str] = []
    for part in parts:
        if len(part) > TARGET_CHARS:
            pieces.extend(_split_recursive(part, rest))
        else:
            pieces.append(part)
    return pieces


def _merge_with_overlap(pieces: list[str]) -> list[str]:
    chunks: list[str] = []
    current = ""

    for piece in pieces:
        if current and len(current) + len(piece) > TARGET_CHARS:
            chunks.append(current.strip())
            current = current[-OVERLAP_CHARS:] if OVERLAP_CHARS else ""
        current += piece

    if current.strip():
        chunks.append(current.strip())

    return chunks


def chunk_text(text: str) -> list[str]:
    """Split page/document text into overlapping chunks of roughly TARGET_TOKENS tokens."""
    text = text.strip()
    if not text:
        return []

    if len(text) <= TARGET_CHARS:
        return [text]

    pieces = _split_recursive(text, SEPARATORS)
    return _merge_with_overlap(pieces)
