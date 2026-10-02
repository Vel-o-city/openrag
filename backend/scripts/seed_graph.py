"""Load the official demo PDF through the real ingestion pipeline.

Run from backend: uv run python -m scripts.seed_graph
Checks the bundled source checksum, publishes provenance after full indexing,
and retires the known fictional samples without deleting visitor uploads.
Completed copies are reused without repeating embedding calls.
"""

import asyncio
import hashlib
import json
import logging
from pathlib import Path

from neo4j import AsyncDriver
from redis.asyncio import Redis

from app.graph.writer import find_document_by_sha256, mark_document_as_seed
from app.ingestion.pipeline import process_document
from app.jobs.manager import get_job_status, new_job_id

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent / "seed_documents"
MANIFEST = json.loads((SEED_DIR / "manifest.json").read_text())
LEGACY_SEEDS = [
    "halden-institute-memo.pdf",
    "kepler-initiative-report.pdf",
    "meridian-labs-overview.pdf",
]

# Seeded documents are attributed to this instead of a hashed client IP. It
# never matches a real visitor's hash, so seeding can't consume anyone's
# upload rate limit or per-IP budget.
SEED_IP_HASH = "seed"


def discover_seed_documents(directory: Path = SEED_DIR) -> list[Path]:
    return [directory / entry["filename"] for entry in MANIFEST]


async def seed_document(driver: AsyncDriver, redis: Redis, path: Path) -> str:
    """Ingests one seed document, or pins it if it's already in the graph.
    Returns "ingested" or "already-present"."""
    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()
    entry = next((item for item in MANIFEST if item["filename"] == path.name), None)
    if entry and sha256 != entry["sha256"]:
        raise RuntimeError(f"Source checksum mismatch: {path.name}")

    # process_document short-circuits on this same check *before* it reaches
    # write_document, so an existing copy would never get the is_seed flag.
    # Pin it here instead.
    existing = await find_document_by_sha256(driver, sha256)
    if existing is not None:
        if existing.get("status") != "done":
            raise RuntimeError(f"Existing sample is incomplete: {path.name}")
        await mark_document_as_seed(driver, existing["id"])
        return "already-present"

    job_id = new_job_id()
    await process_document(
        driver,
        redis,
        document_id=new_job_id(),
        job_id=job_id,
        filename=path.name,
        content=content,
        mime_type="application/pdf",
        upload_ip_hash=SEED_IP_HASH,
        is_seed=False,
    )
    job = await get_job_status(redis, job_id)
    if not job or job.get("status") != "done":
        raise RuntimeError(f"Sample did not finish indexing: {path.name}")
    return "ingested"


async def publish_seed_catalog(driver: AsyncDriver) -> None:
    """Publish provenance and retire only the known fictional samples atomically.

    The replacement must be fully indexed before the previous demo is unpinned.
    Visitor uploads and their chunks are preserved.
    """

    async def publish(tx):
        for entry in MANIFEST:
            result = await tx.run(
                """
                MATCH (d:Document {sha256: $sha256, status: 'done'})
                SET d.is_seed = true, d.title = $title,
                    d.publisher = $publisher, d.source_url = $source_url
                RETURN d.id AS id
                """,
                **entry,
            )
            if await result.single() is None:
                raise RuntimeError("Cannot publish an incomplete source catalog")
        await tx.run(
            """
            MATCH (d:Document)
            WHERE d.is_seed = true AND d.upload_ip_hash = $seed_ip
                  AND d.filename IN $filenames
            SET d.is_seed = false
            """,
            seed_ip=SEED_IP_HASH,
            filenames=LEGACY_SEEDS,
        )

    async with driver.session() as session:
        await session.execute_write(publish)


async def seed_graph(driver: AsyncDriver, redis: Redis) -> dict[str, int]:
    documents = discover_seed_documents()
    if not documents:
        raise RuntimeError(f"No seed PDFs in {SEED_DIR}")

    counts = {"ingested": 0, "already-present": 0, "failed": 0}
    for path in documents:
        try:
            outcome = await seed_document(driver, redis, path)
        except Exception:
            logger.exception("Failed to seed %s", path.name)
            counts["failed"] += 1
        else:
            counts[outcome] += 1
            logger.info("%s: %s", path.name, outcome)

    if counts["failed"] == 0:
        await publish_seed_catalog(driver)
    return counts


async def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from app.config import settings
    from app.graph.neo4j_client import close_driver, init_driver
    from app.graph.writer import count_all_nodes

    driver = await init_driver()
    redis: Redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        counts = await seed_graph(driver, redis)
        total_nodes = await count_all_nodes(driver)

        print(
            f"\nSeeded: {counts['ingested']} ingested, "
            f"{counts['already-present']} already present, {counts['failed']} failed."
        )
        print(f"Graph now holds {total_nodes} nodes.")

        if total_nodes > settings.max_graph_nodes // 2:
            print(
                f"WARNING: seeds occupy more than half the {settings.max_graph_nodes}-node cap, "
                "leaving little headroom for visitor uploads before pruning kicks in."
            )
    finally:
        await redis.aclose()
        await close_driver()


if __name__ == "__main__":
    asyncio.run(_main())
