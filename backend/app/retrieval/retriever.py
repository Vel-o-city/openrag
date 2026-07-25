"""Hybrid GraphRAG retrieval: vector search seeds both chunks and entities,
cross-pollinates between the two, expands one hop over RELATES_TO to pull in
structurally-connected entities even without a direct vector match, then
attaches representative source chunks to every entity so everything in the
final context is citable back to a real document.
"""

from neo4j import AsyncDriver

from app.gemini.client import embed_text
from app.retrieval.schemas import RetrievalResult, RetrievedChunk, RetrievedEntity, RetrievedRelationship

CHUNK_TOP_K = 5
ENTITY_TOP_K = 5
CHUNKS_PER_ENTITY = 2
MAX_HOP_NEIGHBORS = 30


async def _vector_search_chunks(driver: AsyncDriver, embedding: list[float], k: int) -> list[dict]:
    async with driver.session() as session:
        result = await session.run(
            """
            CALL db.index.vector.queryNodes('chunk_embedding_idx', $k, $embedding)
            YIELD node, score
            MATCH (d:Document)-[:HAS_CHUNK]->(node)
            RETURN node.id AS id, node.text AS text, node.page_number AS page_number,
                   d.id AS document_id, d.filename AS filename
            ORDER BY score DESC
            """,
            k=k,
            embedding=embedding,
        )
        return [record.data() async for record in result]


async def _vector_search_entities(driver: AsyncDriver, embedding: list[float], k: int) -> list[dict]:
    async with driver.session() as session:
        result = await session.run(
            """
            CALL db.index.vector.queryNodes('entity_embedding_idx', $k, $embedding)
            YIELD node, score
            RETURN node.id AS id, node.canonical_name AS name, node.entity_type AS entity_type,
                   node.description AS description
            ORDER BY score DESC
            """,
            k=k,
            embedding=embedding,
        )
        return [record.data() async for record in result]


async def _entities_mentioned_in_chunks(driver: AsyncDriver, chunk_ids: list[str]) -> list[dict]:
    if not chunk_ids:
        return []
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (c:Chunk)-[:MENTIONS]->(e:Entity)
            WHERE c.id IN $chunk_ids
            RETURN DISTINCT e.id AS id, e.canonical_name AS name, e.entity_type AS entity_type,
                            e.description AS description
            """,
            chunk_ids=chunk_ids,
        )
        return [record.data() async for record in result]


async def _representative_chunks_for_entities(
    driver: AsyncDriver, entity_ids: list[str], per_entity: int
) -> list[dict]:
    if not entity_ids:
        return []
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (e:Entity)<-[:MENTIONS]-(c:Chunk)
            WHERE e.id IN $entity_ids
            MATCH (d:Document)-[:HAS_CHUNK]->(c)
            WITH e, c, d
            ORDER BY c.chunk_index
            WITH e, collect({id: c.id, text: c.text, page_number: c.page_number,
                              document_id: d.id, filename: d.filename})[0..$per_entity] AS chunks
            UNWIND chunks AS chunk
            RETURN DISTINCT chunk.id AS id, chunk.text AS text, chunk.page_number AS page_number,
                   chunk.document_id AS document_id, chunk.filename AS filename
            """,
            entity_ids=entity_ids,
            per_entity=per_entity,
        )
        return [record.data() async for record in result]


async def _expand_one_hop(driver: AsyncDriver, entity_ids: list[str]) -> tuple[list[dict], list[dict]]:
    """Returns (neighbor_entities, relationship_edges) for a 1-hop expansion
    from the seed entities over RELATES_TO in either direction."""
    if not entity_ids:
        return [], []

    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (e:Entity)-[r:RELATES_TO]-(n:Entity)
            WHERE e.id IN $entity_ids
            RETURN DISTINCT n.id AS id, n.canonical_name AS name, n.entity_type AS entity_type,
                   n.description AS description, r.id AS rel_id, r.predicate AS predicate,
                   r.description AS rel_description,
                   startNode(r).id AS source_id, endNode(r).id AS target_id
            LIMIT $limit
            """,
            entity_ids=entity_ids,
            limit=MAX_HOP_NEIGHBORS,
        )
        rows = [record.data() async for record in result]

    neighbors = {
        row["id"]: {
            "id": row["id"],
            "name": row["name"],
            "entity_type": row["entity_type"],
            "description": row["description"],
        }
        for row in rows
    }
    relationships = {
        row["rel_id"]: {
            "id": row["rel_id"],
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "predicate": row["predicate"],
            "description": row["rel_description"],
        }
        for row in rows
    }
    return list(neighbors.values()), list(relationships.values())


async def _relationships_among(driver: AsyncDriver, entity_ids: list[str]) -> list[dict]:
    if not entity_ids:
        return []
    async with driver.session() as session:
        result = await session.run(
            """
            MATCH (a:Entity)-[r:RELATES_TO]->(b:Entity)
            WHERE a.id IN $entity_ids AND b.id IN $entity_ids
            RETURN DISTINCT r.id AS id, a.id AS source_id, b.id AS target_id,
                   r.predicate AS predicate, r.description AS description
            """,
            entity_ids=entity_ids,
        )
        return [record.data() async for record in result]


async def retrieve(driver: AsyncDriver, query: str) -> RetrievalResult:
    query_embedding = await embed_text(query)

    seed_chunks = await _vector_search_chunks(driver, query_embedding, CHUNK_TOP_K)
    seed_entities = await _vector_search_entities(driver, query_embedding, ENTITY_TOP_K)

    seed_chunk_ids = [c["id"] for c in seed_chunks]
    seed_entity_ids = [e["id"] for e in seed_entities]

    # Cross-pollinate: entities mentioned in seed chunks join the entity set,
    # and representative chunks for vector-seeded entities join the chunk set.
    entities_from_chunks = await _entities_mentioned_in_chunks(driver, seed_chunk_ids)
    chunks_from_entities = await _representative_chunks_for_entities(
        driver, seed_entity_ids, CHUNKS_PER_ENTITY
    )

    entities_by_id = {e["id"]: e for e in seed_entities + entities_from_chunks}
    chunks_by_id = {c["id"]: c for c in seed_chunks + chunks_from_entities}

    # 1-hop Cypher expansion from the seed entity set — the actual graph part
    # of GraphRAG, pulling in structurally-connected entities without needing
    # a direct vector match.
    neighbor_entities, hop_relationships = await _expand_one_hop(driver, list(entities_by_id.keys()))
    for entity in neighbor_entities:
        entities_by_id.setdefault(entity["id"], entity)

    # Attach 1-2 representative source chunks to every entity in the final
    # set (including 1-hop neighbors pulled in above with no chunks yet), so
    # everything in context is citable back to a real document.
    extra_chunks = await _representative_chunks_for_entities(
        driver, list(entities_by_id.keys()), CHUNKS_PER_ENTITY
    )
    for chunk in extra_chunks:
        chunks_by_id.setdefault(chunk["id"], chunk)

    relationships_among_final = await _relationships_among(driver, list(entities_by_id.keys()))
    relationships_by_id = {r["id"]: r for r in hop_relationships + relationships_among_final}

    return RetrievalResult(
        chunks=[RetrievedChunk(**c) for c in chunks_by_id.values()],
        entities=[RetrievedEntity(**e) for e in entities_by_id.values()],
        relationships=[RetrievedRelationship(**r) for r in relationships_by_id.values()],
    )
