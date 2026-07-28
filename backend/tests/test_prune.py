from unittest.mock import AsyncMock, patch

import pytest

from app.graph import prune


@pytest.mark.asyncio
async def test_prune_to_max_nodes_does_nothing_when_already_under_cap():
    with (
        patch.object(prune, "count_all_nodes", AsyncMock(return_value=100)),
        patch.object(prune, "list_documents_by_age", AsyncMock()) as list_mock,
        patch.object(prune, "delete_document_cascade", AsyncMock()) as delete_mock,
    ):
        deleted = await prune.prune_to_max_nodes(driver=object(), max_nodes=3000)

    assert deleted == 0
    list_mock.assert_not_called()
    delete_mock.assert_not_called()


@pytest.mark.asyncio
async def test_prune_to_max_nodes_deletes_oldest_documents_until_under_cap():
    # count_all_nodes is checked once per loop iteration: over cap, over cap, under cap -> stop
    node_counts = iter([4000, 3200, 2500])

    async def fake_count_all_nodes(driver):
        return next(node_counts)

    driver = object()
    with (
        patch.object(prune, "count_all_nodes", fake_count_all_nodes),
        patch.object(
            prune,
            "list_documents_by_age",
            AsyncMock(side_effect=[[{"id": "doc-oldest"}], [{"id": "doc-next-oldest"}]]),
        ),
        patch.object(prune, "delete_document_cascade", AsyncMock(return_value={"chunks_deleted": 1})) as delete_mock,
    ):
        deleted = await prune.prune_to_max_nodes(driver=driver, max_nodes=3000)

    assert deleted == 2
    assert delete_mock.await_args_list[0].args == (driver, "doc-oldest")
    assert delete_mock.await_args_list[1].args == (driver, "doc-next-oldest")


@pytest.mark.asyncio
async def test_prune_to_max_nodes_stops_if_no_documents_left_even_over_cap():
    with (
        patch.object(prune, "count_all_nodes", AsyncMock(return_value=5000)),
        patch.object(prune, "list_documents_by_age", AsyncMock(return_value=[])),
        patch.object(prune, "delete_document_cascade", AsyncMock()) as delete_mock,
    ):
        deleted = await prune.prune_to_max_nodes(driver=object(), max_nodes=3000)

    assert deleted == 0
    delete_mock.assert_not_called()


@pytest.mark.asyncio
async def test_prune_never_asks_for_seed_documents():
    """Seeds are permanently the oldest documents in the graph, so an
    age-ordered prune would delete the curated demo set first."""
    with (
        patch.object(prune, "count_all_nodes", AsyncMock(side_effect=[4000, 2000])),
        patch.object(
            prune, "list_documents_by_age", AsyncMock(return_value=[{"id": "doc-1"}])
        ) as list_mock,
        patch.object(prune, "delete_document_cascade", AsyncMock()),
    ):
        await prune.prune_to_max_nodes(driver=object(), max_nodes=3000)

    assert list_mock.await_args.kwargs.get("include_seed", False) is False


@pytest.mark.asyncio
async def test_prune_warns_when_only_seeds_remain_over_cap(caplog):
    with (
        patch.object(prune, "count_all_nodes", AsyncMock(return_value=5000)),
        patch.object(prune, "list_documents_by_age", AsyncMock(return_value=[])),
        patch.object(prune, "delete_document_cascade", AsyncMock()),
    ):
        with caplog.at_level("WARNING"):
            deleted = await prune.prune_to_max_nodes(driver=object(), max_nodes=3000)

    assert deleted == 0
    # Otherwise this retries silently every 6h with nothing to show for it.
    assert "only seed documents" in caplog.text
