import json
import re

from app.chat.schemas import (
    MAX_CITATION_TEXT_CHARS,
    MAX_CITED_CHUNKS,
    CitationPayload,
    CitedChunk,
    CitedDocument,
    LabelTarget,
)
from app.retrieval.schemas import RetrievalResult, RetrievedChunk, RetrievedEntity

LABEL_PATTERN = re.compile(r"\[(E\d+|C\d+)\]")

# PDF text extraction routinely emits C0 control characters and zero-width
# characters. They render as nothing, which makes them a convenient place to
# hide injected text from a human reading the cited passage — strip them
# before the text leaves the backend. Newlines and tabs are real formatting
# and are kept.
_CONTROL_CHARS = re.compile(
    "["
    "\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f"  # C0/C1 controls, keeping \t \n \r
    "\u200b-\u200f"  # zero-width space/joiners, LTR/RTL marks
    "\u2028\u2029"  # line/paragraph separators
    "\u202a-\u202e"  # bidi overrides — can visually reverse text
    "\u2066-\u2069"  # bidi isolates
    "\ufeff"  # zero-width no-break space / BOM
    "]"
)


def sanitize_source_text(text: str) -> str:
    return _CONTROL_CHARS.sub("", text)


def clip_source_text(text: str) -> tuple[str, bool]:
    """Clip to MAX_CITATION_TEXT_CHARS on a word boundary. Returns the text
    and whether it was clipped."""
    if len(text) <= MAX_CITATION_TEXT_CHARS:
        return text, False

    head = text[:MAX_CITATION_TEXT_CHARS]
    boundary = head.rfind(" ")
    # Only honour the word boundary if it isn't pathologically early — a
    # 1200-char run with no spaces would otherwise clip to almost nothing.
    if boundary > MAX_CITATION_TEXT_CHARS // 2:
        head = head[:boundary]
    return head.rstrip() + "…", True


def split_answer_and_citations(raw_text: str, marker: str) -> tuple[str, str | None]:
    if marker in raw_text:
        answer, _, trailer = raw_text.partition(marker)
        return answer.strip(), trailer.strip()
    return raw_text.strip(), None


def parse_cited_labels(answer_text: str, trailer: str | None) -> list[str]:
    labels: list[str] = []
    if trailer:
        try:
            parsed = json.loads(trailer)
            if isinstance(parsed, list):
                labels = [str(label) for label in parsed]
        except (json.JSONDecodeError, ValueError):
            labels = []

    # Redundant fallback signal: regex-scan the visible answer text too, in
    # case the trailing JSON array was malformed or missing.
    labels_from_text = LABEL_PATTERN.findall(answer_text)
    return list(dict.fromkeys(labels + labels_from_text))


def _label_by_object_id(label_map: dict[str, object]) -> dict[str, str]:
    """Invert the label map so a resolved object can name the label it was
    cited as. Needed on the fallback path too, where objects are pulled from
    the retrieval result rather than looked up by label."""
    return {obj.id: label for label, obj in label_map.items() if hasattr(obj, "id")}


def resolve_citations(
    cited_labels: list[str],
    label_map: dict[str, object],
    retrieval: RetrievalResult,
) -> CitationPayload:
    """Resolve backend-owned labels back to real objects — a hallucinated
    label simply fails to resolve and is dropped, never reaching the
    frontend as a fake id.

    Pragmatic fallback: if nothing resolves at all, return the entire
    retrieved subgraph as "used" instead of the model-selected subset — less
    precise, but still delivers the visual citation-highlight payoff. That
    case sets precise=False so the UI can present those passages as merely
    retrieved rather than actually cited.
    """
    cited_entities: dict[str, RetrievedEntity] = {}
    cited_chunks: dict[str, RetrievedChunk] = {}

    for label in cited_labels:
        obj = label_map.get(label)
        if isinstance(obj, RetrievedEntity):
            cited_entities[obj.id] = obj
        elif isinstance(obj, RetrievedChunk):
            cited_chunks[obj.id] = obj

    precise = bool(cited_entities or cited_chunks)
    if not precise:
        cited_entities = {e.id: e for e in retrieval.entities}
        cited_chunks = {c.id: c for c in retrieval.chunks}

    cited_relationships = [
        rel
        for rel in retrieval.relationships
        if rel.source_id in cited_entities and rel.target_id in cited_entities
    ]

    label_of = _label_by_object_id(label_map)

    # Bound the payload: the fallback path can carry ~80 chunks, and a
    # vision-transcribed page is a single unbounded chunk.
    kept_chunks = list(cited_chunks.values())[:MAX_CITED_CHUNKS]

    chunks: list[CitedChunk] = []
    for chunk in kept_chunks:
        sanitized = sanitize_source_text(chunk.text)
        text, truncated = clip_source_text(sanitized)
        chunks.append(
            CitedChunk(
                id=chunk.id,
                label=label_of.get(chunk.id, ""),
                text=text,
                truncated=truncated,
                char_count=len(sanitized),
                page_number=chunk.page_number,
                document_id=chunk.document_id,
                filename=sanitize_source_text(chunk.filename),
            )
        )

    pages_by_document: dict[str, set[int]] = {}
    filename_by_document: dict[str, str] = {}
    for chunk in chunks:
        pages_by_document.setdefault(chunk.document_id, set()).add(chunk.page_number)
        filename_by_document.setdefault(chunk.document_id, chunk.filename)

    documents = [
        CitedDocument(id=document_id, filename=filename_by_document[document_id], pages=sorted(pages))
        for document_id, pages in pages_by_document.items()
    ]

    # Every label the frontend might meet inline in the prose, so it can turn
    # [E1]/[C3] into a clickable footnote. Entities carry their name because
    # the client's graph fetch is capped and may not hold the node.
    labels: dict[str, LabelTarget] = {}
    for entity in cited_entities.values():
        label = label_of.get(entity.id)
        if label:
            labels[label] = LabelTarget(kind="entity", id=entity.id, name=entity.name)
    for chunk in chunks:
        if chunk.label:
            labels[chunk.label] = LabelTarget(kind="chunk", id=chunk.id)

    return CitationPayload(
        entities=[e.id for e in cited_entities.values()],
        relationships=[r.id for r in cited_relationships],
        chunks=chunks,
        documents=documents,
        labels=labels,
        precise=precise,
    )
