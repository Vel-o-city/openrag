import uuid

from neo4j import AsyncDriver, AsyncManagedTransaction

from app.graph.entity_resolution import find_best_candidate, normalize_name

FULLTEXT_SHORTLIST_SIZE = 10
ALLOWED_ENTITY_TYPES = {"Person", "Organization", "Location", "Event", "Concept", "Other"}


def new_id() -> str:
    return str(uuid.uuid4())


async def wipe_graph(driver: AsyncDriver) -> None:
    """Deletes every node and relationship — a full hard reset. There's no
    curated seed set to reset *to* yet (that's a Day-7 item), so this leaves
    an empty graph rather than pretending one exists."""

    async def _tx(tx: AsyncManagedTransaction) -> None:
        await tx.run("MATCH (n) DETACH DELETE n")

    async with driver.session() as session:
        await session.execute_write(_tx)


async def find_document_by_sha256(driver: AsyncDriver, sha256: str) -> dict | None:
    async def _tx(tx: AsyncManagedTransaction) -> dict | None:
        result = await tx.run(
            "MATCH (d:Document {sha256: $sha256}) RETURN d LIMIT 1", sha256=sha256
        )
        record = await result.single()
        return dict(record["d"]) if record else None

    async with driver.session() as session:
        return await session.execute_read(_tx)


async def get_document(driver: AsyncDriver, document_id: str) -> dict | None:
    async def _tx(tx: AsyncManagedTransaction) -> dict | None:
        result = await tx.run("MATCH (d:Document {id: $id}) RETURN d LIMIT 1", id=document_id)
        record = await result.single()
        return dict(record["d"]) if record else None

    async with driver.session() as session:
        return await session.execute_read(_tx)


async def list_documents_by_age(driver: AsyncDriver, oldest_first: bool = True) -> list[dict]:
    order = "ASC" if oldest_first else "DESC"

    async def _tx(tx: AsyncManagedTransaction) -> list[dict]:
        result = await tx.run(f"MATCH (d:Document) RETURN d.id AS id, d.uploaded_at AS uploaded_at ORDER BY d.uploaded_at {order}")
        return [record.data() async for record in result]

    async with driver.session() as session:
        return await session.execute_read(_tx)


async def count_all_nodes(driver: AsyncDriver) -> int:
    async def _tx(tx: AsyncManagedTransaction) -> int:
        result = await tx.run("MATCH (n) RETURN count(n) AS c")
        record = await result.single()
        return record["c"] if record else 0

    async with driver.session() as session:
        return await session.execute_read(_tx)


async def prune_orphaned_entities(driver: AsyncDriver) -> int:
    """Deletes any Entity with no remaining MENTIONS from any chunk — a
    general cleanup pass, not scoped to one document, since orphans can
    accumulate from partial extraction failures too."""

    async def _tx(tx: AsyncManagedTransaction) -> int:
        result = await tx.run(
            """
            MATCH (e:Entity)
            WHERE NOT (e)<-[:MENTIONS]-()
            WITH collect(e) AS orphans
            FOREACH (e IN orphans | DETACH DELETE e)
            RETURN size(orphans) AS orphan_count
            """
        )
        record = await result.single()
        return record["orphan_count"] if record else 0

    async with driver.session() as session:
        return await session.execute_write(_tx)


async def delete_document_cascade(driver: AsyncDriver, document_id: str) -> dict | None:
    """Deletes a Document and its Chunks, then prunes any Entity left with
    no remaining mentions. Returns None if the document doesn't exist."""

    async def _tx(tx: AsyncManagedTransaction) -> dict | None:
        result = await tx.run(
            """
            MATCH (d:Document {id: $document_id})
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            WITH d, collect(c) AS chunks
            FOREACH (c IN chunks | DETACH DELETE c)
            WITH d, size(chunks) AS chunk_count
            DETACH DELETE d
            RETURN chunk_count
            """,
            document_id=document_id,
        )
        return await result.single()

    async with driver.session() as session:
        record = await session.execute_write(_tx)

    if record is None:
        return None

    orphans_deleted = await prune_orphaned_entities(driver)
    return {"chunks_deleted": record["chunk_count"], "orphans_deleted": orphans_deleted}


async def write_document(
    driver: AsyncDriver,
    *,
    document_id: str,
    filename: str,
    sha256: str,
    mime_type: str,
    source_type: str,
    page_count: int,
    upload_ip_hash: str,
    uploaded_at: float,
    status: str,
) -> None:
    async def _tx(tx: AsyncManagedTransaction) -> None:
        await tx.run(
            """
            MERGE (d:Document {id: $document_id})
            SET d.filename = $filename,
                d.sha256 = $sha256,
                d.mime_type = $mime_type,
                d.source_type = $source_type,
                d.page_count = $page_count,
                d.upload_ip_hash = $upload_ip_hash,
                d.uploaded_at = $uploaded_at,
                d.status = $status
            """,
            document_id=document_id,
            filename=filename,
            sha256=sha256,
            mime_type=mime_type,
            source_type=source_type,
            page_count=page_count,
            upload_ip_hash=upload_ip_hash,
            uploaded_at=uploaded_at,
            status=status,
        )

    async with driver.session() as session:
        await session.execute_write(_tx)


async def set_document_status(driver: AsyncDriver, document_id: str, status: str) -> None:
    async def _tx(tx: AsyncManagedTransaction) -> None:
        await tx.run(
            "MATCH (d:Document {id: $document_id}) SET d.status = $status",
            document_id=document_id,
            status=status,
        )

    async with driver.session() as session:
        await session.execute_write(_tx)


async def write_chunk(
    driver: AsyncDriver,
    *,
    document_id: str,
    chunk_id: str,
    text: str,
    page_number: int,
    chunk_index: int,
    token_count: int,
    embedding: list[float],
) -> None:
    async def _tx(tx: AsyncManagedTransaction) -> None:
        await tx.run(
            """
            MATCH (d:Document {id: $document_id})
            CREATE (c:Chunk {
                id: $chunk_id, text: $text, page_number: $page_number,
                chunk_index: $chunk_index, token_count: $token_count, embedding: $embedding
            })
            CREATE (d)-[:HAS_CHUNK {page_number: $page_number, chunk_index: $chunk_index}]->(c)
            """,
            document_id=document_id,
            chunk_id=chunk_id,
            text=text,
            page_number=page_number,
            chunk_index=chunk_index,
            token_count=token_count,
            embedding=embedding,
        )

    async with driver.session() as session:
        await session.execute_write(_tx)


async def resolve_or_create_entity(
    driver: AsyncDriver,
    *,
    name: str,
    entity_type: str,
    description: str,
    aliases: list[str],
    embedding: list[float] | None,
) -> str:
    """Look up a fulltext-shortlisted match within the same coarse type and
    merge into it if the resolver's signals agree, else create a new entity.
    Runs as one write transaction keyed on (name_normalized, entity_type) so
    the lookup+merge is atomic per call, bounding (not eliminating) the race
    window against concurrent uploads creating the same entity twice."""
    if entity_type not in ALLOWED_ENTITY_TYPES:
        raise ValueError(f"Unknown entity_type: {entity_type}")

    name_normalized = normalize_name(name)

    async def _tx(tx: AsyncManagedTransaction) -> str:
        result = await tx.run(
            """
            CALL db.index.fulltext.queryNodes('entity_name_fulltext', $search_text)
            YIELD node, score
            WHERE node:%s
            RETURN node.id AS id, node.name_normalized AS name_normalized,
                   node.embedding AS embedding, node.aliases AS aliases
            ORDER BY score DESC
            LIMIT $limit
            """
            % entity_type,
            search_text=name,
            limit=FULLTEXT_SHORTLIST_SIZE,
        )
        candidates = [record.data() async for record in result]

        match = find_best_candidate(name_normalized, embedding, candidates)

        if match is not None:
            merged_aliases = list(dict.fromkeys((match.get("aliases") or []) + aliases + [name]))
            await tx.run(
                """
                MATCH (e:Entity {id: $id})
                SET e.mention_count = coalesce(e.mention_count, 0) + 1,
                    e.aliases = $aliases
                """,
                id=match["id"],
                aliases=merged_aliases,
            )
            return match["id"]

        entity_id = new_id()
        await tx.run(
            """
            CREATE (e:Entity:%s {
                id: $id, canonical_name: $name, name_normalized: $name_normalized,
                entity_type: $entity_type, aliases: $aliases, description: $description,
                embedding: $embedding, mention_count: 1
            })
            """
            % entity_type,
            id=entity_id,
            name=name,
            name_normalized=name_normalized,
            entity_type=entity_type,
            aliases=list(dict.fromkeys(aliases + [name])),
            description=description,
            embedding=embedding,
        )
        return entity_id

    async with driver.session() as session:
        return await session.execute_write(_tx)


async def write_mention(
    driver: AsyncDriver,
    *,
    chunk_id: str,
    entity_id: str,
    mention_text: str,
    confidence: float,
) -> None:
    async def _tx(tx: AsyncManagedTransaction) -> None:
        await tx.run(
            """
            MATCH (c:Chunk {id: $chunk_id}), (e:Entity {id: $entity_id})
            MERGE (c)-[m:MENTIONS]->(e)
            SET m.mention_text = $mention_text, m.confidence = $confidence
            """,
            chunk_id=chunk_id,
            entity_id=entity_id,
            mention_text=mention_text,
            confidence=confidence,
        )

    async with driver.session() as session:
        await session.execute_write(_tx)


async def write_relationship(
    driver: AsyncDriver,
    *,
    source_entity_id: str,
    target_entity_id: str,
    predicate: str,
    description: str,
    confidence: float,
    source_chunk_id: str,
) -> None:
    async def _tx(tx: AsyncManagedTransaction) -> None:
        await tx.run(
            """
            MATCH (source:Entity {id: $source_entity_id}), (target:Entity {id: $target_entity_id})
            MERGE (source)-[r:RELATES_TO {predicate: $predicate}]->(target)
            ON CREATE SET r.id = $id, r.description = $description, r.confidence = $confidence,
                          r.source_chunk_ids = [$source_chunk_id]
            ON MATCH SET r.source_chunk_ids = CASE
                WHEN $source_chunk_id IN r.source_chunk_ids THEN r.source_chunk_ids
                ELSE r.source_chunk_ids + $source_chunk_id
            END
            """,
            id=new_id(),
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            predicate=predicate,
            description=description,
            confidence=confidence,
            source_chunk_id=source_chunk_id,
        )

    async with driver.session() as session:
        await session.execute_write(_tx)
