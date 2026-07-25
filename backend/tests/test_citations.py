from app.chat.citations import parse_cited_labels, resolve_citations, split_answer_and_citations
from app.chat.prompts import CITATION_MARKER
from app.retrieval.schemas import RetrievalResult, RetrievedChunk, RetrievedEntity, RetrievedRelationship

ENTITY_A = RetrievedEntity(id="ent-a", name="Ada Lovelace", entity_type="Person", description="...")
ENTITY_B = RetrievedEntity(id="ent-b", name="Babbage Inc", entity_type="Organization", description="...")
CHUNK_A = RetrievedChunk(id="chunk-a", text="...", page_number=1, document_id="doc-1", filename="a.pdf")
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
    assert result["entities"] == ["ent-a"]
    assert result["chunks"] == ["chunk-a"]
    assert result["documents"] == ["doc-1"]


def test_resolve_citations_includes_relationship_between_two_cited_entities():
    result = resolve_citations(["E1", "E2"], LABEL_MAP, RETRIEVAL)
    assert result["relationships"] == ["rel-ab"]


def test_resolve_citations_drops_hallucinated_labels_silently():
    result = resolve_citations(["E1", "E99", "C77"], LABEL_MAP, RETRIEVAL)
    assert result["entities"] == ["ent-a"]
    assert result["chunks"] == []


def test_resolve_citations_falls_back_to_full_subgraph_when_nothing_resolves():
    result = resolve_citations([], LABEL_MAP, RETRIEVAL)
    assert set(result["entities"]) == {"ent-a", "ent-b"}
    assert result["chunks"] == ["chunk-a"]
    assert result["relationships"] == ["rel-ab"]
