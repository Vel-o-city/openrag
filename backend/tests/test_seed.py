from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from scripts import seed_graph


@pytest.fixture
def seed_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "demo.pdf"
    path.write_bytes(b"%PDF-1.4 pretend contents")
    return path


@pytest.mark.asyncio
async def test_new_document_is_ingested_and_flagged_as_seed(seed_pdf: Path):
    with (
        patch.object(seed_graph, "find_document_by_sha256", AsyncMock(return_value=None)),
        patch.object(seed_graph, "process_document", AsyncMock()) as process_mock,
        patch.object(seed_graph, "mark_document_as_seed", AsyncMock()) as mark_mock,
    ):
        outcome = await seed_graph.seed_document(object(), object(), seed_pdf)

    assert outcome == "ingested"
    assert process_mock.await_args.kwargs["is_seed"] is True
    assert process_mock.await_args.kwargs["filename"] == "demo.pdf"
    mark_mock.assert_not_called()


@pytest.mark.asyncio
async def test_existing_document_is_pinned_rather_than_reingested(seed_pdf: Path):
    """process_document short-circuits on its own sha256 check before reaching
    write_document, so an already-present copy would never get is_seed set."""
    driver = object()
    with (
        patch.object(
            seed_graph, "find_document_by_sha256", AsyncMock(return_value={"id": "existing-doc"})
        ),
        patch.object(seed_graph, "process_document", AsyncMock()) as process_mock,
        patch.object(seed_graph, "mark_document_as_seed", AsyncMock()) as mark_mock,
    ):
        outcome = await seed_graph.seed_document(driver, object(), seed_pdf)

    assert outcome == "already-present"
    process_mock.assert_not_called()
    mark_mock.assert_awaited_once_with(driver, "existing-doc")


@pytest.mark.asyncio
async def test_seed_graph_counts_outcomes_and_survives_one_failure(tmp_path: Path):
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (tmp_path / name).write_bytes(b"%PDF-1.4 " + name.encode())

    outcomes = iter(["ingested", "already-present"])

    async def fake_seed_document(driver, redis, path):
        if path.name == "c.pdf":
            raise RuntimeError("extraction blew up")
        return next(outcomes)

    with (
        patch.object(seed_graph, "discover_seed_documents", lambda: sorted(tmp_path.glob("*.pdf"))),
        patch.object(seed_graph, "seed_document", fake_seed_document),
    ):
        counts = await seed_graph.seed_graph(object(), object())

    # One bad document must not abort the rest of the set.
    assert counts == {"ingested": 1, "already-present": 1, "failed": 1}


@pytest.mark.asyncio
async def test_seed_graph_raises_when_no_documents_are_present(tmp_path: Path):
    with patch.object(seed_graph, "discover_seed_documents", lambda: []):
        with pytest.raises(RuntimeError, match="No seed PDFs"):
            await seed_graph.seed_graph(object(), object())


def test_discover_seed_documents_finds_the_committed_pdfs():
    documents = seed_graph.discover_seed_documents()
    assert len(documents) >= 3
    assert all(path.suffix == ".pdf" for path in documents)


def test_seed_ip_hash_cannot_collide_with_a_real_client_hash():
    """Seeding must not consume a real visitor's upload limit or per-IP
    budget, both of which are keyed on the client IP hash."""
    from unittest.mock import Mock

    from app.security.ip import hash_client_ip

    request = Mock()
    request.client.host = "203.0.113.7"
    real_hash = hash_client_ip(request)

    assert real_hash != seed_graph.SEED_IP_HASH
    # A hex digest is long and hex-only; "seed" is neither, so no IP maps to it.
    assert len(real_hash) > len(seed_graph.SEED_IP_HASH)
    assert set(real_hash) <= set("0123456789abcdef")
