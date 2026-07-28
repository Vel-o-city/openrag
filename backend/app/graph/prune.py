"""Periodic prune loop — bounds both abuse accumulation and UI legibility.
A few thousand nodes is plenty for a compelling, still-navigable graph; the
real ceiling to design for is legibility, not any storage limit. A plain
asyncio.sleep loop is enough here — no Celery-beat needed for a check that
only needs to run a few times a day.
"""

import asyncio
import logging

from neo4j import AsyncDriver

from app.config import settings
from app.graph.writer import count_all_nodes, delete_document_cascade, list_documents_by_age

logger = logging.getLogger(__name__)


async def prune_to_max_nodes(driver: AsyncDriver, max_nodes: int) -> int:
    """Deletes the oldest documents (cascading to their chunks and any
    now-orphaned entities) until the graph is back under max_nodes. Returns
    the number of documents deleted."""
    documents_deleted = 0
    while await count_all_nodes(driver) > max_nodes:
        documents = await list_documents_by_age(driver, oldest_first=True)
        if not documents:
            # Nothing left that's eligible — the remainder is the pinned seed
            # set. Better to sit over the cap than delete the demo content,
            # but say so, since otherwise this retries silently every 6h.
            logger.warning(
                "Graph is over the %d node cap with only seed documents left; leaving it alone.",
                max_nodes,
            )
            break
        await delete_document_cascade(driver, documents[0]["id"])
        documents_deleted += 1
    return documents_deleted


async def prune_loop(driver: AsyncDriver) -> None:
    """Runs forever until cancelled — meant to be launched as a background
    asyncio task from the app's lifespan and cancelled on shutdown."""
    while True:
        await asyncio.sleep(settings.prune_check_interval_seconds)
        try:
            deleted = await prune_to_max_nodes(driver, settings.max_graph_nodes)
            if deleted:
                logger.info(
                    "Pruned %d oldest document(s) to stay under %d nodes", deleted, settings.max_graph_nodes
                )
        except Exception:
            logger.exception("Prune loop iteration failed")
