from fastapi import APIRouter

from app.graph.neo4j_client import get_driver

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("")
async def get_stats() -> dict:
    driver = get_driver()
    async with driver.session() as session:
        entities = (await (await session.run("MATCH (e:Entity) RETURN count(e) AS c")).single())["c"]
        relationships = (
            await (await session.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) AS c")).single()
        )["c"]
        documents = (await (await session.run("MATCH (d:Document) RETURN count(d) AS c")).single())["c"]

    return {"entities": entities, "relationships": relationships, "documents": documents}
