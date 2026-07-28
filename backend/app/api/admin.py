"""Admin endpoints, gated by a single shared bearer token — proportionate
for a one-admin demo. No admin UI in MVP scope; call these via curl/httpie.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from redis.asyncio import Redis

from app.config import settings
from app.deps import get_redis
from app.graph.neo4j_client import get_driver
from app.graph.writer import delete_document_cascade, wipe_graph
from app.security.moderation import list_flags

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _run_seed() -> None:
    # Imported lazily: scripts/ isn't a package the app depends on at import
    # time, and seeding is an occasional admin action, not a hot path.
    from scripts.seed_graph import seed_graph

    try:
        counts = await seed_graph(get_driver(), get_redis())
        logger.info("Seed complete: %s", counts)
    except Exception:
        logger.exception("Seeding failed")


def _require_admin(authorization: str | None) -> None:
    if not authorization or authorization != f"Bearer {settings.admin_token}":
        raise HTTPException(status_code=401, detail="Missing or invalid admin token.")


@router.delete("/documents/{document_id}")
async def admin_delete_document(document_id: str, authorization: str | None = Header(None)) -> dict:
    _require_admin(authorization)
    result = await delete_document_cascade(get_driver(), document_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "deleted", **result}


@router.get("/moderation")
async def admin_list_moderation_flags(authorization: str | None = Header(None)) -> dict:
    _require_admin(authorization)
    redis: Redis = get_redis()
    return {"flags": await list_flags(redis)}


@router.post("/reset")
async def admin_reset_graph(
    background_tasks: BackgroundTasks,
    reseed: bool = False,
    authorization: str | None = Header(None),
) -> dict:
    """Hard reset — wipes every node and relationship, seed documents
    included. Pass ?reseed=true to reload the curated seed set afterwards,
    which runs in the background since re-ingesting costs a run of LLM calls."""
    _require_admin(authorization)
    await wipe_graph(get_driver())

    if reseed:
        background_tasks.add_task(_run_seed)
    return {"status": "reset", "reseeding": reseed}


@router.post("/seed")
async def admin_seed_graph(
    background_tasks: BackgroundTasks, authorization: str | None = Header(None)
) -> dict:
    """Loads the curated seed documents. Idempotent — documents already in the
    graph are pinned rather than re-ingested. Runs in the background rather
    than holding the request open for a run of LLM calls."""
    _require_admin(authorization)
    background_tasks.add_task(_run_seed)
    return {"status": "seeding"}
