# OpenRAG

**A live, public knowledge graph you can see, extend, and chat with — grounded, cited answers instead of black-box RAG.**

> 🚧 Under active development. **[Live demo](https://openrag.sanket.website)** is deployed but currently just a placeholder page — the real graph explorer/chat UI lands across Days 4-7 of the build plan below. Backend API is fully live at every step so far.

## What is this?

Most RAG chatbots are a black box: you ask a question, something gets retrieved behind the scenes, and you get an answer with no way to see what it actually knew or where the answer came from.

OpenRAG flips that around. Upload a PDF or image and watch it turn into an explorable knowledge graph — entities and relationships extracted live, rendered as a real graph you can pan, zoom, and click through. Ask the chatbot a question and watch the *exact* nodes it used to answer light up on the graph in real time, with citations back to the source document and page.

It's a single shared, public instance — anyone who visits can add to the same graph everyone else sees.

## Tech stack

- **Backend:** Python, FastAPI, async SSE streaming
- **Graph + vectors:** Neo4j (native vector index — one database for both graph traversal and similarity search)
- **LLM:** Google Gemini (extraction, embeddings, chat)
- **Frontend:** React, Vite, TypeScript, Tailwind, `react-force-graph`
- **Hosting:** Neo4j AuraDB Free, Upstash Redis, Render, Cloudflare Pages — fully managed, $0/month

## Design decisions / trade-offs

- Chose Neo4j's native vector index over a separate vector DB (ChromaDB/Milvus) — one database serves both graph traversal and similarity search, simpler architecture for a solo-maintained project.
- Chose `pypdf`/`pypdfium2` over PyMuPDF for PDF parsing — PyMuPDF is AGPL-3.0, which risks forcing this whole repo under AGPL once publicly deployed.
- Chose fully-managed free-tier hosting (AuraDB Free, Render free tier) over a self-hosted VM — every self-hosted option requires a credit card at signup; this doesn't. Comes with two known, monitored trade-offs (see `.github/workflows/`): Render's free tier spins down after 15 min idle, and AuraDB Free auto-pauses after 72h idle. Both are mitigated with scheduled keep-alive pings plus uptime monitoring.
- Uploads are fully open, no login required — maximizes the "try it right now" effect, but means the ingestion path has real abuse/cost/prompt-injection safeguards built in from day one, not bolted on later.

## Known limitations

- No authentication — this is a single shared public demo instance, not multi-tenant.
- Moderation is a manual "flag this node" button plus periodic resets, not automated content scanning.
- Rate limiting is IP-based, so visitors behind a shared NAT (office, university) are jointly throttled.
- Hosted entirely on free tiers — see the trade-offs above.

## Local development

Requires Docker, Node ≥18, and [uv](https://docs.astral.sh/uv/).

```bash
# Local Neo4j + Redis
docker compose up -d

# Backend
cd backend
cp .env.example .env   # defaults already match docker-compose, no edits needed
uv run uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Backend tests: `cd backend && uv run pytest`
Frontend tests: `cd frontend && npm test`

## License

MIT — see [LICENSE](LICENSE).

This is a personal portfolio project, provided as-is with no warranty or uptime guarantee. Content is public and user-submitted; don't upload private, confidential, or sensitive documents. If something here is inappropriate or infringes your rights, open an issue and it'll be removed.
