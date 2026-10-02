import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.api import chat, documents
from app.chat.citations import parse_cited_labels
from app.retrieval import retriever
from app.retrieval.schemas import RetrievalResult, RetrievedChunk
from app.ingestion import pipeline


def retrieval():
    return RetrievalResult(
        chunks=[
            RetrievedChunk(
                id="chunk-a",
                text="The deadline is 12 October.",
                page_number=2,
                document_id="doc-a",
                filename="plan.pdf",
            )
        ],
        entities=[],
        relationships=[],
    )


def fake_driver(rows):
    result = MagicMock()
    result.__aiter__.return_value = [
        MagicMock(data=lambda row=row: row) for row in rows
    ]
    record = MagicMock(data=lambda: rows[0]) if rows else None
    if record is not None:
        record.__getitem__.side_effect = rows[0].__getitem__
    result.single = AsyncMock(return_value=record)
    session = MagicMock()
    session.run = AsyncMock(return_value=result)
    driver = MagicMock()
    driver.session.return_value.__aenter__.return_value = session
    return driver, session


def test_request_rejects_empty_or_unbounded_inputs():
    for body in [
        {"message": "  "},
        {"message": "a" * 4001},
        {"message": "ok", "document_ids": ["id"] * 21},
        {"message": "ok", "history": [{"role": "system", "text": "spoof"}]},
    ]:
        with pytest.raises(ValidationError):
            chat.ChatRequest(**body)
    assert chat.ChatRequest(message=" hello ").message == "hello"


def test_grouped_inline_citations_survive_missing_trailer():
    assert parse_cited_labels("The deadline [C2, C1]; the cost [C3; C2].", None) == [
        "C2",
        "C1",
        "C3",
    ]


@pytest.mark.asyncio
async def test_scoped_retrieval_ranks_inside_documents_without_shared_entities():
    driver, session = fake_driver([retrieval().chunks[0].model_dump()])
    with patch.object(retriever, "embed_text", AsyncMock(return_value=[0.1, 0.2])):
        answer = await retriever.retrieve(driver, "deadline", document_ids=["doc-a"])
    query = session.run.call_args.args[0]
    assert "d.id IN $document_ids" in query
    assert "d.status IN ['done', 'partial']" in query
    assert "vector.similarity.cosine" in query
    assert session.run.call_args.kwargs["document_ids"] == ["doc-a"]
    assert answer.chunks[0].document_id == "doc-a"
    assert answer.entities == answer.relationships == []


@pytest.mark.asyncio
async def test_empty_selection_does_not_call_model_or_database():
    with patch.object(chat, "reserve_budget", AsyncMock()) as budget, patch.object(
        chat, "retrieve", AsyncMock()
    ) as retrieve:
        events = [
            event async for event in chat._stream_chat_response("hello", "ip", [])
        ]
    budget.assert_not_called()
    retrieve.assert_not_called()
    assert events[-1]["event"] == "done"
    with patch.object(retriever, "embed_text", AsyncMock()) as embed:
        assert (await retriever.retrieve(MagicMock(), "hello", [])).chunks == []
    embed.assert_not_called()


@pytest.mark.asyncio
async def test_followup_keeps_scope_and_history_and_hides_citation_trailer():
    async def stream(system, message, **kwargs):
        assert "user: What is the deadline?" in message
        assert "Visitor question: Which month?" in message
        for delta in ["October [C1].\n---CIT", 'ATIONS---\n["C1"]']:
            yield delta

    with patch.object(
        chat, "reserve_budget", AsyncMock(return_value=True)
    ), patch.object(chat, "get_redis"), patch.object(chat, "get_driver"), patch.object(
        chat, "retrieve", AsyncMock(return_value=retrieval())
    ) as retrieve, patch.object(
        chat, "chat_stream", stream
    ):
        events = [
            event
            async for event in chat._stream_chat_response(
                "Which month?",
                "ip",
                ["doc-a"],
                [chat.HistoryMessage(role="user", text="What is the deadline?")],
            )
        ]
    assert retrieve.call_args.kwargs["document_ids"] == ["doc-a"]
    assert "What is the deadline?" in retrieve.call_args.args[1]
    visible = "".join(
        json.loads(e["data"])["text"] for e in events if e["event"] == "token"
    )
    assert visible.strip() == "October [C1]."
    payload = json.loads(next(e["data"] for e in events if e["event"] == "citations"))
    assert payload["chunks"][0]["document_id"] == "doc-a"
    assert payload["chunks"][0]["page_number"] == 2
    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_stream_failure_is_explicit_not_an_uncited_success():
    async def broken_stream(*args, **kwargs):
        yield "An incomplete answer with some text "
        raise RuntimeError("network")

    with patch.object(
        chat, "reserve_budget", AsyncMock(return_value=True)
    ), patch.object(chat, "get_redis"), patch.object(chat, "get_driver"), patch.object(
        chat, "retrieve", AsyncMock(return_value=retrieval())
    ), patch.object(
        chat, "chat_stream", broken_stream
    ):
        events = [
            event
            async for event in chat._stream_chat_response("deadline", "ip", ["doc-a"])
        ]
    assert any(e["event"] == "error" for e in events)
    assert events[-1]["event"] == "done"


@pytest.mark.asyncio
async def test_document_metadata_does_not_expose_tracking_or_content_hash():
    with patch.object(documents, "get_driver"), patch.object(
        documents.graph_writer,
        "get_document",
        AsyncMock(
            return_value={
                "id": "doc-a",
                "filename": "plan.pdf",
                "upload_ip_hash": "private",
                "sha256": "secret-hash",
                "status": "done",
            }
        ),
    ):
        result = await documents.get_document("doc-a")
    assert result["id"] == "doc-a"
    assert "upload_ip_hash" not in result and "sha256" not in result


@pytest.mark.asyncio
async def test_passage_requires_document_and_chunk_pair_and_sanitizes_text():
    driver, session = fake_driver(
        [{"id": "chunk-a", "text": "safe\u202eevil", "document_id": "doc-a"}]
    )
    with patch.object(documents, "get_driver", return_value=driver):
        result = await documents.get_passage("doc-a", "chunk-a")
    assert session.run.call_args.kwargs == {
        "document_id": "doc-a",
        "chunk_id": "chunk-a",
    }
    assert "HAS_CHUNK" in session.run.call_args.args[0]
    assert result["text"] == "safeevil"


@pytest.mark.asyncio
async def test_native_document_indexes_text_without_graph_extraction():
    with patch.object(
        pipeline.settings, "enable_graph_enrichment", False
    ), patch.object(
        pipeline, "reserve_budget", AsyncMock(return_value=True)
    ), patch.object(
        pipeline, "embed_text", AsyncMock(return_value=[0.1])
    ), patch.object(
        pipeline,
        "extract_from_text",
        AsyncMock(side_effect=RuntimeError("graph unavailable")),
    ) as extract, patch.object(
        pipeline, "_write_extraction", AsyncMock()
    ) as write:
        assert await pipeline._process_native_page(
            MagicMock(),
            MagicMock(),
            "ip",
            document_id="doc-a",
            page_number=1,
            text="A readable source paragraph.",
        )
    extract.assert_not_called()
    assert write.call_args.kwargs["text"] == "A readable source paragraph."


@pytest.mark.asyncio
async def test_no_indexed_pages_is_failed_not_partial():
    driver, _ = fake_driver([{"count": 0}])
    with patch.object(
        pipeline, "find_document_by_sha256", AsyncMock(return_value=None)
    ), patch.object(
        pipeline, "extract_native_text", return_value=["Readable paragraph here."]
    ), patch.object(
        pipeline, "looks_like_readable_text", return_value=True
    ), patch.object(
        pipeline, "write_document", AsyncMock()
    ), patch.object(
        pipeline, "_process_native_page", AsyncMock(return_value=False)
    ), patch.object(
        pipeline, "set_document_status", AsyncMock()
    ) as status, patch.object(
        pipeline, "set_job_status", AsyncMock()
    ) as job:
        await pipeline.process_document(
            driver,
            MagicMock(),
            document_id="doc-a",
            job_id="job-a",
            filename="plan.pdf",
            content=b"pdf",
            mime_type="application/pdf",
            upload_ip_hash="ip",
        )
    assert status.call_args.args[-1] == "failed"
    assert job.call_args.kwargs["status"] == "failed"


@pytest.mark.asyncio
async def test_reset_discards_old_answer_buffer_and_reserves_fallback_cost():
    async def restarting_stream(*args, **kwargs):
        yield "Old answer [C1] that must be discarded.\n"
        yield None
        yield 'Final answer [C1].\n---CITATIONS---\n["C1"]'

    with patch.object(
        chat, "reserve_budget", AsyncMock(return_value=True)
    ) as budget, patch.object(chat, "get_redis"), patch.object(
        chat, "get_driver"
    ), patch.object(
        chat, "retrieve", AsyncMock(return_value=retrieval())
    ), patch.object(
        chat, "chat_stream", restarting_stream
    ):
        events = [
            event
            async for event in chat._stream_chat_response("deadline", "ip", ["doc-a"])
        ]
    reset_index = next(i for i, event in enumerate(events) if event["event"] == "reset")
    final_text = "".join(
        json.loads(e["data"])["text"]
        for e in events[reset_index + 1 :]
        if e["event"] == "token"
    )
    assert final_text.strip() == "Final answer [C1]."
    assert budget.await_count == 2
    assert events[-1]["event"] == "done"
