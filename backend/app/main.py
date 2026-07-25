from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.documents import jobs_router, router as documents_router
from app.config import settings
from app.deps import close_redis, get_redis, init_redis
from app.graph.neo4j_client import close_driver, init_driver
from scripts.bootstrap_schema import bootstrap_schema

limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)


@asynccontextmanager
async def lifespan(app: FastAPI):
    driver = await init_driver()
    await bootstrap_schema(driver, settings.embedding_dimensions)
    await init_redis()
    yield
    await close_redis()
    await close_driver()


def create_app() -> FastAPI:
    app = FastAPI(title="OpenRAG API", lifespan=lifespan)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(documents_router)
    app.include_router(jobs_router)

    @app.get("/api/health")
    async def health() -> dict:
        redis = get_redis()
        await redis.ping()
        return {"status": "ok"}

    return app


app = create_app()
