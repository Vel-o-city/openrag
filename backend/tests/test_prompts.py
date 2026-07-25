from app.chat.prompts import build_context_block, build_user_message
from app.retrieval.schemas import RetrievalResult, RetrievedChunk, RetrievedEntity, RetrievedRelationship


def test_build_context_block_labels_entities_and_chunks_sequentially():
    entities = [
        RetrievedEntity(id="e1", name="Ada Lovelace", entity_type="Person", description="A mathematician."),
        RetrievedEntity(id="e2", name="Babbage Inc", entity_type="Organization", description="A company."),
    ]
    chunks = [
        RetrievedChunk(id="c1", text="Ada worked with Babbage.", page_number=1, document_id="d1", filename="a.pdf"),
    ]
    relationships = [
        RetrievedRelationship(id="r1", source_id="e1", target_id="e2", predicate="worked at", description="..."),
    ]
    retrieval = RetrievalResult(entities=entities, chunks=chunks, relationships=relationships)

    context, label_map = build_context_block(retrieval)

    assert "[E1] Ada Lovelace (Person): A mathematician." in context
    assert "[E2] Babbage Inc (Organization): A company." in context
    assert "[C1] (from a.pdf, page 1): Ada worked with Babbage." in context
    assert "[E1] --worked at--> [E2]" in context
    assert label_map["E1"] is entities[0]
    assert label_map["C1"] is chunks[0]


def test_build_context_block_skips_relationships_missing_from_entity_set():
    entities = [RetrievedEntity(id="e1", name="Solo", entity_type="Person", description="...")]
    relationships = [
        RetrievedRelationship(id="r1", source_id="e1", target_id="ghost", predicate="knows", description="..."),
    ]
    retrieval = RetrievalResult(entities=entities, chunks=[], relationships=relationships)

    context, _ = build_context_block(retrieval)

    assert "knows" not in context


def test_build_user_message_includes_question_and_context():
    message = build_user_message("CONTEXT_BLOCK", "What happened?")
    assert "CONTEXT_BLOCK" in message
    assert "What happened?" in message
