from app.chat.citations import parse_cited_labels, resolve_citations, split_answer_and_citations
from app.chat.prompts import CITATION_MARKER
from app.chat.schemas import MAX_CITATION_TEXT_CHARS, MAX_CITED_CHUNKS, CitationPayload
from app.retrieval.schemas import RetrievalResult, RetrievedChunk, RetrievedEntity, RetrievedRelationship

ENTITY_A = RetrievedEntity(id="ent-a", name="Ada Lovelace", entity_type="Person", description="...")
ENTITY_B = RetrievedEntity(id="ent-b", name="Babbage Inc", entity_type="Organization", description="...")
CHUNK_A = RetrievedChunk(
    id="chunk-a", text="Ada worked on the engine.", page_number=1, document_id="doc-1", filename="a.pdf"
)
REL_AB = RetrievedRelationship(id="rel-ab", source_id="ent-a", target_id="ent-b", predicate="works at", description="...")

LABEL_MAP = {"E1": ENTITY_A, "E2": ENTITY_B, "C1": CHUNK_A}
RETRIEVAL = RetrievalResult(entities=[ENTITY_A, ENTITY_B], chunks=[CHUNK_A], relationships=[REL_AB])


def test_split_answer_and_citations_with_marker():
    raw = f'The answer.\n{CITATION_MARKER}\n["E1","C1"]'
    answer, trailer = split_answer_and_citations(raw, CITATION_MARKER)
    assert answer == "The answer."
    assert trailer == '["E1","C1"]'


def test_split_answer_and_citations_without_marker():
    raw = "The answer with no trailer at all."
    answer, trailer = split_answer_and_citations(raw, CITATION_MARKER)
    assert answer == raw
    assert trailer is None


def test_parse_cited_labels_from_valid_trailer():
    labels = parse_cited_labels("The answer [E1].", '["E1","C1"]')
    assert labels == ["E1", "C1"]


def test_parse_cited_labels_falls_back_to_regex_scan_on_malformed_trailer():
    labels = parse_cited_labels("Cites [E1] and [C1] inline.", "not valid json")
    assert labels == ["E1", "C1"]


def test_parse_cited_labels_merges_trailer_and_text_without_duplicates():
    labels = parse_cited_labels("Cites [E1] inline.", '["E1","E2"]')
    assert labels == ["E1", "E2"]


def test_parse_cited_labels_empty_when_nothing_found():
    assert parse_cited_labels("No citations here.", None) == []


def test_resolve_citations_maps_labels_to_real_objects():
    result = resolve_citations(["E1", "C1"], LABEL_MAP, RETRIEVAL)
    assert result.entities == ["ent-a"]
    assert [c.id for c in result.chunks] == ["chunk-a"]
    assert [d.id for d in result.documents] == ["doc-1"]


def test_resolve_citations_includes_relationship_between_two_cited_entities():
    result = resolve_citations(["E1", "E2"], LABEL_MAP, RETRIEVAL)
    assert result.relationships == ["rel-ab"]


def test_resolve_citations_drops_hallucinated_labels_silently():
    result = resolve_citations(["E1", "E99", "C77"], LABEL_MAP, RETRIEVAL)
    assert result.entities == ["ent-a"]
    assert result.chunks == []


def test_resolve_citations_falls_back_to_full_subgraph_when_nothing_resolves():
    result = resolve_citations([], LABEL_MAP, RETRIEVAL)
    assert set(result.entities) == {"ent-a", "ent-b"}
    assert [c.id for c in result.chunks] == ["chunk-a"]
    assert result.relationships == ["rel-ab"]


# --- provenance actually reaching the payload -------------------------------


def test_cited_chunk_carries_verbatim_text_page_and_filename():
    chunk = resolve_citations(["C1"], LABEL_MAP, RETRIEVAL).chunks[0]
    assert chunk.text == "Ada worked on the engine."
    assert chunk.page_number == 1
    assert chunk.filename == "a.pdf"
    assert chunk.document_id == "doc-1"
    assert chunk.label == "C1"
    assert chunk.truncated is False
    assert chunk.char_count == len("Ada worked on the engine.")


def test_labels_cover_both_kinds_with_entity_names():
    labels = resolve_citations(["E1", "C1"], LABEL_MAP, RETRIEVAL).labels
    assert labels["E1"].kind == "entity"
    assert labels["E1"].id == "ent-a"
    assert labels["E1"].name == "Ada Lovelace"
    assert labels["C1"].kind == "chunk"
    assert labels["C1"].id == "chunk-a"
    assert labels["C1"].name is None


def test_documents_aggregate_deduped_sorted_pages():
    chunks = [
        RetrievedChunk(id="c1", text="one", page_number=7, document_id="doc-1", filename="a.pdf"),
        RetrievedChunk(id="c2", text="two", page_number=2, document_id="doc-1", filename="a.pdf"),
        RetrievedChunk(id="c3", text="three", page_number=7, document_id="doc-1", filename="a.pdf"),
        RetrievedChunk(id="c4", text="four", page_number=1, document_id="doc-2", filename="b.pdf"),
    ]
    label_map = {f"C{i + 1}": c for i, c in enumerate(chunks)}
    retrieval = RetrievalResult(entities=[], chunks=chunks, relationships=[])

    documents = resolve_citations(list(label_map), label_map, retrieval).documents
    by_id = {d.id: d for d in documents}
    assert by_id["doc-1"].pages == [2, 7]
    assert by_id["doc-2"].pages == [1]
    assert by_id["doc-1"].filename == "a.pdf"


# --- payload bounding -------------------------------------------------------


def test_long_chunk_text_is_clipped_and_flagged():
    long_text = "word " * 1000  # 5000 chars
    chunk = RetrievedChunk(id="c1", text=long_text, page_number=1, document_id="doc-1", filename="a.pdf")
    retrieval = RetrievalResult(entities=[], chunks=[chunk], relationships=[])

    cited = resolve_citations(["C1"], {"C1": chunk}, retrieval).chunks[0]
    assert cited.truncated is True
    assert len(cited.text) <= MAX_CITATION_TEXT_CHARS + 1  # +1 for the ellipsis
    assert cited.text.endswith("…")
    assert cited.char_count == len(long_text)


def test_clipping_prefers_a_word_boundary():
    chunk = RetrievedChunk(
        id="c1", text="word " * 1000, page_number=1, document_id="doc-1", filename="a.pdf"
    )
    retrieval = RetrievalResult(entities=[], chunks=[chunk], relationships=[])

    text = resolve_citations(["C1"], {"C1": chunk}, retrieval).chunks[0].text
    assert not text.removesuffix("…").endswith("wor")  # never cuts mid-word here


def test_chunk_count_is_capped():
    chunks = [
        RetrievedChunk(id=f"c{i}", text="x", page_number=1, document_id="doc-1", filename="a.pdf")
        for i in range(MAX_CITED_CHUNKS + 5)
    ]
    label_map = {f"C{i + 1}": c for i, c in enumerate(chunks)}
    retrieval = RetrievalResult(entities=[], chunks=chunks, relationships=[])

    result = resolve_citations(list(label_map), label_map, retrieval)
    assert len(result.chunks) == MAX_CITED_CHUNKS


def test_control_and_zero_width_characters_are_stripped():
    hidden = "Visible​textwith‮hidden﻿parts"
    chunk = RetrievedChunk(id="c1", text=hidden, page_number=1, document_id="doc-1", filename="a.pdf")
    retrieval = RetrievalResult(entities=[], chunks=[chunk], relationships=[])

    text = resolve_citations(["C1"], {"C1": chunk}, retrieval).chunks[0].text
    assert text == "Visibletextwithhiddenparts"


def test_newlines_and_tabs_survive_sanitizing():
    chunk = RetrievedChunk(
        id="c1", text="line one\nline two\tindented", page_number=1, document_id="doc-1", filename="a.pdf"
    )
    retrieval = RetrievalResult(entities=[], chunks=[chunk], relationships=[])

    text = resolve_citations(["C1"], {"C1": chunk}, retrieval).chunks[0].text
    assert text == "line one\nline two\tindented"


# --- precise vs. fallback ---------------------------------------------------


def test_precise_is_true_when_labels_resolve():
    assert resolve_citations(["C1"], LABEL_MAP, RETRIEVAL).precise is True


def test_fallback_sets_precise_false_but_still_populates_labels():
    result = resolve_citations([], LABEL_MAP, RETRIEVAL)
    assert result.precise is False
    # Labels must still resolve on this path, or inline markers would go dead.
    assert result.labels["C1"].id == "chunk-a"
    assert result.labels["E1"].name == "Ada Lovelace"
    assert result.chunks[0].label == "C1"


def test_empty_payload_has_same_keys_as_a_populated_one():
    """Guards against EMPTY_CITATIONS drifting from the real shape."""
    populated = resolve_citations(["E1", "C1"], LABEL_MAP, RETRIEVAL)
    assert set(CitationPayload().model_dump()) == set(populated.model_dump())
