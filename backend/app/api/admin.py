"""Admin endpoints, gated by a single shared bearer token — proportionate
for a one-admin demo. No admin UI in MVP scope; call these via curl/httpie.
"""

from fastapi import APIRouter, Header, HTTPException
from redis.asyncio import Redis

from app.config import settings
from app.deps import get_redis
from app.graph.neo4j_client import get_driver
from app.graph.writer import delete_document_cascade, wipe_graph
from app.security.moderation import list_flags

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
async def admin_reset_graph(authorization: str | None = Header(None)) -> dict:
    """Hard reset — wipes every node and relationship. There's no curated
    seed set to restore yet (Day 7), so this leaves an empty graph."""
    _require_admin(authorization)
    await wipe_graph(get_driver())
    return {"status": "reset"}
