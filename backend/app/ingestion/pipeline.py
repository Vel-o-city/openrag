"""Full ingestion pipeline: extract -> chunk -> embed -> structured-extract ->
entity-resolve -> write to Neo4j, with progress reported via Redis job status.

Concurrency is bounded with a plain asyncio.Semaphore rather than a task
queue (Celery/RQ) — the workload is I/O-bound (LLM calls + Neo4j writes) and
already rate-limited upstream, so a semaphore is the simplest thing that
works for a one-week MVP.
"""

import asyncio
import hashlib
import logging
import time
import uuid
from typing import Awaitable, Callable, TypeVar

from neo4j import AsyncDriver
from redis.asyncio import Redis

from app.config import settings
from app.gemini.client import embed_text, embed_texts, extract_from_image, extract_from_text
from app.graph.writer import (
    find_document_by_sha256,
    resolve_or_create_entity,
    set_document_status,
    write_chunk,
    write_document,
    write_mention,
    write_relationship,
)
from app.ingestion.chunking import chunk_text
from app.ingestion.precheck import extract_native_text, looks_like_readable_text
from app.ingestion.schemas import ExtractionResult, VisionExtractionResult
from app.ingestion.vision import render_pdf_page_to_png
from app.jobs.manager import set_job_status
from app.security.budget import estimate_cost_usd, estimate_tokens, reserve_budget

logger = logging.getLogger(__name__)

MAX_CONCURRENT_LLM_CALLS = 3
_semaphore = asyncio.Semaphore(MAX_CONCURRENT_LLM_CALLS)

T = TypeVar("T")


async def _with_one_retry(call: Callable[[], Awaitable[T]]) -> T | None:
    """Run an LLM call under the concurrency semaphore; on any failure
    (network error or schema-validation failure surfacing as an exception),
    retry exactly once, then give up and let the caller mark this unit
    partially-failed rather than aborting the whole document."""
    for attempt in range(2):
        try:
            async with _semaphore:
                result = await call()
            if result is not None:
                return result
        except Exception:
            logger.warning("Extraction call failed (attempt %d/2)", attempt + 1, exc_info=True)
    return None


async def _write_extraction(
    driver: AsyncDriver,
    *,
    document_id: str,
    chunk_id: str,
    text: str,
    page_number: int,
    chunk_index: int,
    embedding: list[float],
    extraction: ExtractionResult,
) -> None:
    await write_chunk(
        driver,
        document_id=document_id,
        chunk_id=chunk_id,
        text=text,
        page_number=page_number,
        chunk_index=chunk_index,
        token_count=len(text) // 4,
        embedding=embedding,
    )

    if not extraction.entities:
        return

    entity_embeddings = await embed_texts([entity.name for entity in extraction.entities])

    name_to_id: dict[str, str] = {}
    for entity, entity_embedding in zip(extraction.entities, entity_embeddings):
        entity_id = await resolve_or_create_entity(
            driver,
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            aliases=entity.aliases_in_text,
            embedding=entity_embedding,
        )
        name_to_id[entity.name] = entity_id
        await write_mention(
            driver,
            chunk_id=chunk_id,
            entity_id=entity_id,
            mention_text=entity.name,
            confidence=1.0,
        )

    for rel in extraction.relationships:
        source_id = name_to_id.get(rel.source_entity_name)
        target_id = name_to_id.get(rel.target_entity_name)
        if source_id is None or target_id is None:
            continue
        await write_relationship(
            driver,
            source_entity_id=source_id,
            target_entity_id=target_id,
            predicate=rel.predicate,
            description=rel.description,
            confidence=1.0,
            source_chunk_id=chunk_id,
        )


async def _process_native_page(
    driver: AsyncDriver, redis: Redis, ip_hash: str, *, document_id: str, page_number: int, text: str
) -> bool:
    """Returns True if every chunk on this page extracted cleanly."""
    all_ok = True
    for chunk_index, chunk in enumerate(chunk_text(text)):
        estimated_cost = estimate_cost_usd(
            estimate_tokens(chunk), settings.max_estimated_extraction_output_tokens
        )
        if not await reserve_budget(redis, ip_hash, estimated_cost):
            logger.warning("Extraction skipped for page %d chunk %d: daily budget exceeded", page_number, chunk_index)
            all_ok = False
            continue

        extraction = await _with_one_retry(lambda c=chunk: extract_from_text(c))
        if extraction is None:
            all_ok = False
            continue

        embedding = await _with_one_retry(lambda c=chunk: embed_text(c))
        if embedding is None:
            all_ok = False
            continue

        await _write_extraction(
            driver,
            document_id=document_id,
            chunk_id=str(uuid.uuid4()),
            text=chunk,
            page_number=page_number,
            chunk_index=chunk_index,
            embedding=embedding,
            extraction=extraction,
        )
    return all_ok


async def _process_vision_page(
    driver: AsyncDriver, redis: Redis, ip_hash: str, *, document_id: str, page_number: int, image_bytes: bytes, image_mime: str
) -> bool:
    """Scanned/image pages are treated as one chunk each, reusing the single
    combined vision call's transcription + entities/relationships."""
    estimated_cost = estimate_cost_usd(
        settings.estimated_vision_input_tokens, settings.max_estimated_extraction_output_tokens
    )
    if not await reserve_budget(redis, ip_hash, estimated_cost):
        logger.warning("Vision extraction skipped for page %d: daily budget exceeded", page_number)
        return False

    extraction: VisionExtractionResult | None = await _with_one_retry(
        lambda: extract_from_image(image_bytes, image_mime)
    )
    if extraction is None or not extraction.transcribed_text.strip():
        return False

    embedding = await _with_one_retry(lambda: embed_text(extraction.transcribed_text))
    if embedding is None:
        return False

    await _write_extraction(
        driver,
        document_id=document_id,
        chunk_id=str(uuid.uuid4()),
        text=extraction.transcribed_text,
        page_number=page_number,
        chunk_index=0,
        embedding=embedding,
        extraction=extraction,
    )
    return True


async def process_document(
    driver: AsyncDriver,
    redis: Redis,
    *,
    document_id: str,
    job_id: str,
    filename: str,
    content: bytes,
    mime_type: str,
    upload_ip_hash: str,
) -> None:
    sha256 = hashlib.sha256(content).hexdigest()

    existing = await find_document_by_sha256(driver, sha256)
    if existing is not None:
        await set_job_status(
            redis, job_id, status="done", document_id=existing["id"], progress=100
        )
        return

    source_type = "pdf" if mime_type == "application/pdf" else "image"
    native_pages = extract_native_text(content) if source_type == "pdf" else [""]
    page_count = len(native_pages)

    await write_document(
        driver,
        document_id=document_id,
        filename=filename,
        sha256=sha256,
        mime_type=mime_type,
        source_type=source_type,
        page_count=page_count,
        upload_ip_hash=upload_ip_hash,
        uploaded_at=time.time(),
        status="processing",
    )
    await set_job_status(redis, job_id, status="running", document_id=document_id, progress=5)

    any_failures = False
    for page_number, native_text in enumerate(native_pages, start=1):
        try:
            if source_type == "pdf" and looks_like_readable_text(native_text):
                ok = await _process_native_page(
                    driver, redis, upload_ip_hash, document_id=document_id, page_number=page_number, text=native_text
                )
            else:
                image_bytes = (
                    render_pdf_page_to_png(content, page_number - 1)
                    if source_type == "pdf"
                    else content
                )
                image_mime = "image/png" if source_type == "pdf" else mime_type
                ok = await _process_vision_page(
                    driver,
                    redis,
                    upload_ip_hash,
                    document_id=document_id,
                    page_number=page_number,
                    image_bytes=image_bytes,
                    image_mime=image_mime,
                )
            any_failures = any_failures or not ok
        except Exception:
            logger.exception("Unhandled error processing page %d of %s", page_number, document_id)
            any_failures = True

        progress = 5 + int(90 * page_number / page_count)
        await set_job_status(redis, job_id, status="running", progress=progress)

    final_status = "partial" if any_failures else "done"
    await set_document_status(driver, document_id, final_status)
    await set_job_status(redis, job_id, status=final_status, progress=100)
