from fastapi import APIRouter, HTTPException, Request, UploadFile
from redis.asyncio import Redis

from app.deps import get_redis
from app.ingestion.precheck import extract_native_text, has_usable_native_text
from app.ingestion.validation import UploadValidationError, validate_upload
from app.jobs.manager import create_job, get_job_status, new_job_id

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("")
async def upload_document(request: Request, file: UploadFile) -> dict:
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

    # Day 2 wires up the actual background extraction task here (asyncio.Semaphore
    # + entity resolution + Cypher writer). For now the job is recorded as queued
    # so the polling/SSE contract can be built and tested against real responses.

    return {
        "document_id": document_id,
        "job_id": job_id,
        "status": "queued",
        "mime_type": mime_type,
        "needs_vision_ocr": needs_vision_ocr,
    }


@router.get("/{document_id}")
async def get_document(document_id: str) -> dict:
    raise HTTPException(status_code=501, detail="Document metadata storage lands in Day 2's Cypher writer.")


jobs_router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@jobs_router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    redis: Redis = get_redis()
    status = await get_job_status(redis, job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return status
