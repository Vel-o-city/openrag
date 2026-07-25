import hashlib
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile
from redis.asyncio import Redis

from app.deps import get_redis
from app.graph.neo4j_client import get_driver
from app.graph import writer as graph_writer
from app.ingestion.pipeline import process_document
from app.ingestion.precheck import extract_native_text, has_usable_native_text
from app.ingestion.validation import UploadValidationError, validate_upload
from app.jobs.manager import create_job, get_job_status, new_job_id, set_job_status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _hash_client_ip(request: Request) -> str:
    client_host = request.client.host if request.client else "unknown"
    return hashlib.sha256(client_host.encode()).hexdigest()


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
    except Exception as exc:
        logger.exception("Ingestion pipeline failed for document %s", document_id)
        await set_job_status(redis, job_id, status="failed", error=str(exc))


@router.post("")
async def upload_document(request: Request, background_tasks: BackgroundTasks, file: UploadFile) -> dict:
    content = await file.read()

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
        upload_ip_hash=_hash_client_ip(request),
    )

    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "queued",
        "mime_type": mime_type,
        "needs_vision_ocr": needs_vision_ocr,
    }


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict:
    document = await graph_writer.get_document(get_driver(), document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@jobs_router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    redis: Redis = get_redis()
    status = await get_job_status(redis, job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return status
