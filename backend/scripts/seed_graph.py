"""Loads the curated seed documents into the graph.

Runs them through the real ingestion pipeline, so the entities, embeddings and
relationships are genuine rather than hand-written fixtures — the demo graph is
the pipeline's actual output.

    uv run python scripts/seed_graph.py

Idempotent: a document already present by sha256 is pinned rather than
re-ingested, so re-running costs nothing.
"""

import asyncio
import hashlib
import logging
from pathlib import Path

from neo4j import AsyncDriver
from redis.asyncio import Redis

from app.graph.writer import find_document_by_sha256, mark_document_as_seed
from app.ingestion.pipeline import process_document
from app.jobs.manager import new_job_id

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent / "seed_documents"

# Seeded documents are attributed to this instead of a hashed client IP. It
# never matches a real visitor's hash, so seeding can't consume anyone's
# upload rate limit or per-IP budget.
SEED_IP_HASH = "seed"


def discover_seed_documents(directory: Path = SEED_DIR) -> list[Path]:
    return sorted(directory.glob("*.pdf"))


async def seed_document(driver: AsyncDriver, redis: Redis, path: Path) -> str:
    """Ingests one seed document, or pins it if it's already in the graph.
    Returns "ingested" or "already-present"."""
    content = path.read_bytes()
    sha256 = hashlib.sha256(content).hexdigest()

    # process_document short-circuits on this same check *before* it reaches
    # write_document, so an existing copy would never get the is_seed flag.
    # Pin it here instead.
    existing = await find_document_by_sha256(driver, sha256)
    if existing is not None:
        await mark_document_as_seed(driver, existing["id"])
        return "already-present"

    await process_document(
        driver,
        redis,
        document_id=new_job_id(),
        job_id=new_job_id(),
        filename=path.name,
        content=content,
        mime_type="application/pdf",
        upload_ip_hash=SEED_IP_HASH,
        is_seed=True,
    )
    return "ingested"


async def seed_graph(driver: AsyncDriver, redis: Redis) -> dict[str, int]:
    documents = discover_seed_documents()
    if not documents:
        raise RuntimeError(f"No seed PDFs in {SEED_DIR} — run scripts/build_seed_pdfs.py first.")

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
