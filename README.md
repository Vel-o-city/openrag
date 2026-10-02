# OpenRAG

**Upload a document. Ask a question. Check the source.**

[Live demo](https://openrag.sanket.website) · [Source code](https://github.com/Vel-o-city/openrag)

OpenRAG is a document Q&A portfolio demo. Visitors can immediately ask questions about the official UN Universal Declaration of Human Rights, or upload a PDF/image of their own. Answers stream into the chat with numbered citations. Clicking a citation opens the extracted passage, filename, and page number so the reader can check the evidence.

## What works

- Native-text PDFs, scanned PDFs, PNG, JPEG, and WebP; up to 20 MB and 20 pages.
- Upload progress, partial-page reporting, transient connection retries, and reconnection after a page refresh.
- A document library with selected sources. A finished upload becomes the active source automatically.
- Retrieval restricted to those selected files; no shared entity summaries can import facts from another document.
- Follow-up conversation context, streamed answers, stop/retry controls, and explicit interruption errors.
- Clickable inline citations and source cards with full extracted passages on demand.
- Responsive document drawer and source inspector. No graph visualization in the interface.

## Architecture

React/TypeScript/Vite → FastAPI → Gemini embeddings and streamed generation → Neo4j document/chunk storage. Redis stores ingestion jobs and cost reservations. PDF text comes from `pypdf`; scanned pages are rendered with `pypdfium2` and transcribed by Gemini vision.

Selected-document retrieval ranks embedded chunks **inside the selected documents**, rather than retrieving global matches and filtering afterwards. Source labels are assigned by the backend and resolved against real chunk IDs. Unknown labels are discarded. If the model omits usable citations, the UI labels returned passages as related passages rather than precise citations. Citations identify evidence; they do not guarantee that every claim is correct.

Native text is indexed without requiring graph extraction. Optional legacy graph enrichment (`ENABLE_GRAPH_ENRICHMENT=true`) and graph/admin APIs remain available behind the scenes, but document chat uses source passages only.

The deployed stack uses Cloudflare Pages, Render, Neo4j AuraDB, and Upstash Redis. Render may take time to wake after inactivity. The library shows a visible connection error and retry action in that case.

## Local development

Requires Docker, Python 3.12+, [uv](https://docs.astral.sh/uv/), and Node 22.13+ (Node 24 recommended).

```bash
docker compose up -d --wait

cd backend
cp .env.example .env
# Set GEMINI_API_KEY in .env. Keep database URLs local for local development.
uv sync
uv run uvicorn app.main:app --reload
```

In another terminal:

```bash
cd frontend
npm ci
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Load the official demo PDF through the real ingestion pipeline:

```bash
cd backend
uv run python -m scripts.seed_graph
```

The unchanged eight-page OHCHR PDF and its provenance/checksum manifest are in `backend/scripts/seed_documents/`. Seeding checks the checksum and requires complete indexing before publishing the source. A successful run unpins the three former fictional seeds while preserving visitor uploads. Seeds are protected from automatic pruning. The library selects the declaration on first load, with questions about equality, education, and freedom of expression. Citation inspectors link to the official PDF at the cited page. Changing sources starts a new chat.

After deploying to an existing database, run the authenticated `POST /api/admin/seed` endpoint (or the seed module against that environment) once to update the preloaded catalog. See the seed directory README for source attribution and reuse terms.

For an isolated stack alongside other projects:

```bash
NEO4J_HTTP_PORT=17474 NEO4J_BOLT_PORT=17687 REDIS_PORT=16380 docker compose -p openrag-demo up -d --wait
```

Set backend `NEO4J_URI=bolt://localhost:17687` and `REDIS_URL=redis://localhost:16380/0`. If the backend port changes, update `VITE_API_BASE_URL` accordingly. Allow the frontend origin in `CORS_ORIGINS` (JSON array syntax). Production builds use `frontend/.env.production`; never put localhost in that file.

Turnstile is optional locally: leave both `TURNSTILE_SECRET_KEY` and `VITE_TURNSTILE_SITE_KEY` empty. Production uploads need matching backend/frontend Turnstile configuration. Set a strong `ADMIN_TOKEN` before deploying.

## Validation

```bash
cd backend && uv run pytest
cd frontend && npm test
cd frontend && npm run build
cd frontend && npm run lint
```

Tests cover document scope, history, citation resolution, stream interruptions, upload reconnection, duplicate document IDs, metadata filtering, and unreadable uploads, alongside the existing backend and frontend checks.

## Demo boundaries

This is a public instance without authentication or tenant isolation. A browser remembers its own uploaded document IDs, but this is a convenience, not an access-control boundary. Do not upload confidential files. Original binary uploads are processed in memory; the source inspector displays indexed text, not a stored PDF viewer. Non-seed documents can be pruned as the database fills up. Limits are IP-based and Gemini availability/quota can interrupt requests.

MIT — see [LICENSE](LICENSE).
