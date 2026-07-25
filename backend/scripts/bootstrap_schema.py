"""Idempotent Neo4j schema bootstrap — constraints + vector indexes.

Safe to run on every app startup (all statements are `IF NOT EXISTS`),
and also runnable standalone: `uv run python scripts/bootstrap_schema.py`
"""

import asyncio

from neo4j import AsyncDriver

STATEMENTS = [
    "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT entity_id_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE INDEX entity_name_normalized IF NOT EXISTS FOR (e:Entity) ON (e.name_normalized)",
    "CREATE FULLTEXT INDEX entity_name_fulltext IF NOT EXISTS FOR (e:Entity) ON EACH [e.canonical_name]",
]

VECTOR_INDEX_TEMPLATE = """
CREATE VECTOR INDEX {name} IF NOT EXISTS
FOR (n:{label}) ON (n.embedding)
OPTIONS {{indexConfig: {{
  `vector.dimensions`: {dimensions},
  `vector.similarity_function`: 'cosine'
}}}}
"""


async def bootstrap_schema(driver: AsyncDriver, embedding_dimensions: int) -> None:
    async with driver.session() as session:
        for stmt in STATEMENTS:
            await session.run(stmt)

        await session.run(
            VECTOR_INDEX_TEMPLATE.format(
                name="chunk_embedding_idx", label="Chunk", dimensions=embedding_dimensions
            )
        )
        await session.run(
            VECTOR_INDEX_TEMPLATE.format(
                name="entity_embedding_idx", label="Entity", dimensions=embedding_dimensions
            )
        )


async def _main() -> None:
    from app.config import settings
    from app.graph.neo4j_client import close_driver, init_driver

    driver = await init_driver()
    try:
        await bootstrap_schema(driver, settings.embedding_dimensions)
        print("Schema bootstrap complete.")
    finally:
        await close_driver()


if __name__ == "__main__":
    asyncio.run(_main())
