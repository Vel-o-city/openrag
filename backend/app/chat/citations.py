import json
import re

from app.retrieval.schemas import RetrievalResult, RetrievedChunk, RetrievedEntity

LABEL_PATTERN = re.compile(r"\[(E\d+|C\d+)\]")


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


def resolve_citations(
    cited_labels: list[str],
    label_map: dict[str, object],
    retrieval: RetrievalResult,
) -> dict:
    """Resolve backend-owned labels back to real objects — a hallucinated
    label simply fails to resolve and is dropped, never reaching the
    frontend as a fake id.

    Pragmatic fallback: if nothing resolves at all, return the entire
    retrieved subgraph as "used" instead of the model-selected subset — less
    precise, but still delivers the visual citation-highlight payoff.
    """
    cited_entities: dict[str, RetrievedEntity] = {}
    cited_chunks: dict[str, RetrievedChunk] = {}

    for label in cited_labels:
        obj = label_map.get(label)
        if isinstance(obj, RetrievedEntity):
            cited_entities[obj.id] = obj
        elif isinstance(obj, RetrievedChunk):
            cited_chunks[obj.id] = obj

    if not cited_entities and not cited_chunks:
        cited_entities = {e.id: e for e in retrieval.entities}
        cited_chunks = {c.id: c for c in retrieval.chunks}

    cited_relationships = [
        rel
        for rel in retrieval.relationships
        if rel.source_id in cited_entities and rel.target_id in cited_entities
    ]
    document_ids = list(dict.fromkeys(c.document_id for c in cited_chunks.values()))

    return {
        "entities": [e.id for e in cited_entities.values()],
        "relationships": [r.id for r in cited_relationships],
        "chunks": [c.id for c in cited_chunks.values()],
        "documents": document_ids,
    }
