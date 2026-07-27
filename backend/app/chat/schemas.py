from typing import Literal

from pydantic import BaseModel

# Chunk text reaching the browser has to be bounded. chunk_text() targets
# TARGET_CHARS (2600), but the vision/OCR path writes a whole page
# transcription as one chunk without going through the chunker at all, so
# chunk length is not reliably bounded upstream. Worst case chunk *count* is
# also high — CHUNK_TOP_K + CHUNKS_PER_ENTITY across a 1-hop expansion can
# reach ~80 chunks, all emitted at once on the fallback path.
MAX_CITATION_TEXT_CHARS = 1200
MAX_CITED_CHUNKS = 8


class CitedChunk(BaseModel):
    id: str
    label: str
    """The backend-assigned label ("C3") this chunk was cited as, so the
    frontend can join an inline [C3] marker in the prose to this card."""
    text: str
    truncated: bool = False
    char_count: int
    """Length before clipping, so the UI can be honest about what it's hiding."""
    page_number: int
    document_id: str
    filename: str


class CitedDocument(BaseModel):
    id: str
    filename: str
    pages: list[int]


class LabelTarget(BaseModel):
    kind: Literal["entity", "chunk"]
    id: str
    name: str | None = None
    """Entities only. Carried here because the frontend's graph fetch is
    capped well below max_graph_nodes, so resolving an entity id against the
    loaded graph can miss and fall back to showing a raw uuid fragment."""


class CitationPayload(BaseModel):
    """The `citations` SSE event. Entities and relationships stay bare id
    lists — the frontend feeds them straight to the graph-highlight call —
    while chunks carry the provenance a reader actually needs: which file,
    which page, and the verbatim passage."""

    entities: list[str] = []
    relationships: list[str] = []
    chunks: list[CitedChunk] = []
    documents: list[CitedDocument] = []
    labels: dict[str, LabelTarget] = {}
    precise: bool = True
    """False when resolve_citations fell back to returning the whole retrieved
    subgraph because no model-emitted label resolved. Those passages were
    retrieved but not actually cited, and the UI should say so."""
    flagged_urls: list[str] = []
