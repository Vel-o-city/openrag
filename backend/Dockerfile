FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

EXPOSE 8000


# --timeout-keep-alive raised well above uvicorn's 5s default: retrieval
# (several sequential Neo4j round trips) plus the LLM's time-to-first-token
# can occasionally exceed 5s before /api/chat writes any SSE bytes, and the
# default timeout can tear down the connection mid-stream when that happens.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "120"]
