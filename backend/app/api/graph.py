from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from redis.asyncio import Redis

from app.config import settings
from app.deps import get_redis
from app.graph.neo4j_client import get_driver
from app.rate_limiter import limiter
from app.security.ip import hash_client_ip
from app.security.moderation import flag_entity

router = APIRouter(prefix="/api/graph", tags=["graph"])


class FlagRequest(BaseModel):
    reason: str | None = None


@router.get("")
async def get_graph(
    limit: int = Query(200, le=1000),
    cursor: str | None = None,
    entity_type: str | None = None,
    search: str | None = None,
) -> dict:
    """Keyset-paginated graph query — never offset pagination, since that
    silently skips/duplicates rows under concurrent inserts. `cursor` is the
    last entity id seen; ids form a stable (if not insertion-ordered) total
    order, which is all keyset pagination needs."""
    where_clauses = []
    params: dict = {"limit": limit}

    if cursor:
        where_clauses.append("e.id > $cursor")
        params["cursor"] = cursor
    if entity_type:
        where_clauses.append("$entity_type IN labels(e)")
        params["entity_type"] = entity_type
    if search:
        where_clauses.append("toLower(e.canonical_name) CONTAINS toLower($search)")
        params["search"] = search

    where = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(
            f"""
            MATCH (e:Entity)
            {where}
            RETURN e.id AS id, e.canonical_name AS name, e.entity_type AS entity_type,
                   e.description AS description, e.mention_count AS mention_count
            ORDER BY e.id
            LIMIT $limit
            """,
            **params,
        )
        nodes = [record.data() async for record in result]
        node_ids = [n["id"] for n in nodes]

        edges = []
        if node_ids:
            result = await session.run(
                """
                MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
                WHERE a.id IN $node_ids AND b.id IN $node_ids
                RETURN a.id AS source, b.id AS target, r.predicate AS predicate,
                       r.description AS description, r.confidence AS confidence
                """,
                node_ids=node_ids,
            )
            edges = [record.data() async for record in result]

    next_cursor = nodes[-1]["id"] if len(nodes) == limit else None
    return {"nodes": nodes, "edges": edges, "next_cursor": next_cursor}


@router.get("/{entity_id}/neighbors")
async def get_neighbors(entity_id: str) -> dict:
    driver = get_driver()
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (e:Entity {id: $id})
            OPTIONAL MATCH (e)-[r:RELATES_TO]-(n:Entity)
            RETURN e.id AS id, e.canonical_name AS name, e.entity_type AS entity_type,
                   e.description AS description,
                   collect(DISTINCT CASE WHEN n IS NULL THEN NULL ELSE {
                       id: n.id, name: n.canonical_name, entity_type: n.entity_type,
                       predicate: r.predicate
                   } END) AS neighbors
            """,
            id=entity_id,
        )
        record = await result.single()

    if record is None or record["id"] is None:
        raise HTTPException(status_code=404, detail="Entity not found.")

    data = record.data()
    data["neighbors"] = [n for n in data["neighbors"] if n is not None]
    return data


@router.post("/{entity_id}/flag")
@limiter.limit(settings.flag_rate_limit)
async def flag_node(entity_id: str, request: Request, body: FlagRequest) -> dict:
    """Public, unauthenticated — anyone can flag a node as objectionable.
    Appends to an append-only log for later manual review via
    GET /api/admin/moderation; nothing is auto-removed from the graph."""
    redis: Redis = get_redis()
    await flag_entity(redis, entity_id=entity_id, reason=body.reason, ip_hash=hash_client_ip(request))
    return {"status": "flagged"}
