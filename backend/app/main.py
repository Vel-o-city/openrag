import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.documents import jobs_router, router as documents_router
from app.api.graph import router as graph_router
from app.api.stats import router as stats_router
from app.config import settings
from app.deps import close_redis, get_redis, init_redis
from app.graph.neo4j_client import close_driver, init_driver
from app.graph.prune import prune_loop
from app.rate_limiter import limiter
from scripts.bootstrap_schema import bootstrap_schema


@asynccontextmanager
async def lifespan(app: FastAPI):
    driver = await init_driver()
    await bootstrap_schema(driver, settings.embedding_dimensions)
    await init_redis()
    prune_task = asyncio.create_task(prune_loop(driver))
    yield
    prune_task.cancel()
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
    app.include_router(graph_router)
    app.include_router(stats_router)
    app.include_router(chat_router)
    app.include_router(admin_router)

    @app.get("/api/health")
    async def health() -> dict:
        redis = get_redis()
        await redis.ping()
        return {"status": "ok"}

    return app


app = create_app()
