import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from redis.asyncio import Redis

from app.config import settings
from app.chat.citations import sanitize_source_text
from app.deps import get_redis
from app.graph.neo4j_client import get_driver
from app.graph import writer as graph_writer
from app.ingestion.pipeline import process_document
from app.ingestion.precheck import extract_native_text, has_usable_native_text
from app.ingestion.validation import UploadValidationError, validate_upload
from app.jobs.manager import create_job, get_job_status, new_job_id, set_job_status
from app.rate_limiter import limiter
from app.security.ip import hash_client_ip
from app.security.turnstile import verify_turnstile_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


async def _run_pipeline(
    *,
    document_id: str,
    job_id: str,
    filename: str,
    content: bytes,
    mime_type: str,
    upload_ip_hash: str,
) -> None:
    redis: Redis = get_redis()
    try:
        await process_document(
            get_driver(),
            redis,
            document_id=document_id,
            job_id=job_id,
            filename=filename,
            content=content,
            mime_type=mime_type,
            upload_ip_hash=upload_ip_hash,
        )
    except Exception:
        logger.exception("Ingestion pipeline failed for document %s", document_id)
        await graph_writer.set_document_status(get_driver(), document_id, "failed")
        await set_job_status(
            redis,
            job_id,
            status="failed",
            error="Processing failed. Please retry the upload.",
        )


@router.post("")
@limiter.limit(settings.upload_rate_limit)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile,
    turnstile_token: str | None = Form(None),
) -> dict:
    client_host = request.client.host if request.client else None
    if not await verify_turnstile_token(turnstile_token, client_host):
        raise HTTPException(
            status_code=403, detail="Turnstile verification failed. Please try again."
        )

    content = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)

    try:
        mime_type = validate_upload(content)
    except UploadValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    needs_vision_ocr = True
    if mime_type == "application/pdf":
        pages = extract_native_text(content)
        needs_vision_ocr = not has_usable_native_text(pages)

    document_id = new_job_id()
    job_id = new_job_id()

    redis: Redis = get_redis()
    await create_job(redis, job_id, document_id)

    background_tasks.add_task(
        _run_pipeline,
        document_id=document_id,
        job_id=job_id,
        filename=file.filename or "upload",
        content=content,
        mime_type=mime_type,
        upload_ip_hash=hash_client_ip(request),
    )

    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "queued",
        "mime_type": mime_type,
        "needs_vision_ocr": needs_vision_ocr,
    }


PUBLIC_FIELDS = (
    "id",
    "filename",
    "mime_type",
    "source_type",
    "page_count",
    "uploaded_at",
    "status",
    "is_seed",
)


@router.get("")
async def list_documents(
    document_ids: list[str] = Query(default=[], max_length=20)
) -> list[dict]:
    # The demo is public, but its library shows only curated samples and the
    # IDs this browser remembers, rather than advertising strangers' uploads.
    async with get_driver().session() as session:
        result = await session.run(
            """
            MATCH (d:Document)
            WHERE coalesce(d.is_seed, false) OR d.id IN $ids
            OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
            WITH d, count(c) AS chunk_count
            RETURN d { .id, .filename, .mime_type, .source_type, .page_count,
                       .uploaded_at, .status, .is_seed, chunk_count: chunk_count } AS document
            ORDER BY d.is_seed DESC, d.uploaded_at DESC
            LIMIT 23
            """,
            ids=document_ids,
        )
        return [dict(record["document"]) async for record in result]


@router.get("/{document_id}/chunks/{chunk_id}")
async def get_passage(document_id: str, chunk_id: str) -> dict:
    async with get_driver().session() as session:
        result = await session.run(
            """
            MATCH (d:Document {id: $document_id})-[:HAS_CHUNK]->(c:Chunk {id: $chunk_id})
            RETURN c.id AS id, c.text AS text, c.page_number AS page_number,
                   d.id AS document_id, d.filename AS filename
            """,
            document_id=document_id,
            chunk_id=chunk_id,
        )
        record = await result.single()
    if record is None:
        raise HTTPException(
            status_code=404, detail="Source passage is no longer available."
        )
    passage = record.data()
    passage["text"] = sanitize_source_text(passage["text"])
    return passage


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict:
    document = await graph_writer.get_document(get_driver(), document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {key: document.get(key) for key in PUBLIC_FIELDS}


jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@jobs_router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    redis: Redis = get_redis()
    status = await get_job_status(redis, job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return status
