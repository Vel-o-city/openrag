import json
import time
import uuid

from redis.asyncio import Redis

JOB_KEY_PREFIX = "job:"
JOB_TTL_SECONDS = 60 * 60 * 24  # 24h — plenty for a demo, keeps Redis tidy


def new_job_id() -> str:
    return str(uuid.uuid4())


async def create_job(redis: Redis, job_id: str, document_id: str) -> None:
    await set_job_status(redis, job_id, status="queued", document_id=document_id, progress=0)


async def set_job_status(
    redis: Redis,
    job_id: str,
    *,
    status: str,
    document_id: str | None = None,
    progress: int | None = None,
    error: str | None = None,
) -> None:
    key = f"{JOB_KEY_PREFIX}{job_id}"
    existing = await redis.get(key)
    data = json.loads(existing) if existing else {}

    data["status"] = status
    data["updated_at"] = time.time()
    if document_id is not None:
        data["document_id"] = document_id
    if progress is not None:
        data["progress"] = progress
    if error is not None:
        data["error"] = error

    await redis.set(key, json.dumps(data), ex=JOB_TTL_SECONDS)


async def get_job_status(redis: Redis, job_id: str) -> dict | None:
    raw = await redis.get(f"{JOB_KEY_PREFIX}{job_id}")
    return json.loads(raw) if raw else None
