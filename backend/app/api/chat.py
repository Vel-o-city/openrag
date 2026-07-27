import json
import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.chat.citations import parse_cited_labels, resolve_citations
from app.chat.guardrails import find_unverified_urls
from app.chat.prompts import CITATION_MARKER, SYSTEM_PROMPT, build_context_block, build_user_message
from app.chat.schemas import CitationPayload
from app.config import settings
from app.deps import get_redis
from app.gemini.client import chat_stream
from app.graph.neo4j_client import get_driver
from app.rate_limiter import limiter
from app.retrieval.retriever import retrieve
from app.security.budget import estimate_cost_usd, estimate_tokens, reserve_budget
from app.security.ip import hash_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

EMPTY_CITATIONS = CitationPayload().model_dump_json()

BUDGET_EXCEEDED_MESSAGE = (
    "This demo has hit its daily budget cap — please check back tomorrow, "
    "or explore the graph / re-read earlier answers meanwhile."
)


class ChatRequest(BaseModel):
    message: str


async def _stream_chat_response(question: str, ip_hash: str):
    # Reserve-before-spend: estimate worst-case cost and check it against
    # the daily budget *before* touching the LLM at all. Real context size
    # isn't known until after retrieval, so this uses a fixed upper-bound
    # estimate for the assembled context rather than the exact figure.
    estimated_input_tokens = settings.typical_chat_context_tokens + estimate_tokens(question)
    estimated_cost = estimate_cost_usd(estimated_input_tokens, settings.max_estimated_chat_output_tokens)
    if not await reserve_budget(get_redis(), ip_hash, estimated_cost):
        yield {"event": "token", "data": json.dumps({"text": BUDGET_EXCEEDED_MESSAGE})}
        yield {"event": "citations", "data": EMPTY_CITATIONS}
        yield {"event": "done", "data": "{}"}
        return

    # Everything below can fail mid-stream (Neo4j hiccup, a Gemini API error
    # or quota exhaustion, a malformed model response) — without this guard,
    # an exception here kills the async generator outright and the SSE
    # connection gets torn down mid-chunk instead of ending cleanly.
    try:
        retrieval = await retrieve(get_driver(), question)
        context_block, label_map = build_context_block(retrieval)
        user_message = build_user_message(context_block, question)

        buffer = ""
        emitted_len = 0
        marker_index: int | None = None
        holdback = len(CITATION_MARKER) - 1

        async for delta in chat_stream(SYSTEM_PROMPT, user_message):
            buffer += delta

            if marker_index is None:
                idx = buffer.find(CITATION_MARKER)
                if idx != -1:
                    marker_index = idx
                    to_emit = buffer[emitted_len:marker_index]
                    if to_emit:
                        yield {"event": "token", "data": json.dumps({"text": to_emit})}
                        emitted_len = marker_index
                else:
                    safe_len = max(emitted_len, len(buffer) - holdback)
                    to_emit = buffer[emitted_len:safe_len]
                    if to_emit:
                        yield {"event": "token", "data": json.dumps({"text": to_emit})}
                        emitted_len = safe_len

        if marker_index is None:
            # Marker never arrived — flush whatever's left as visible text.
            to_emit = buffer[emitted_len:]
            if to_emit:
                yield {"event": "token", "data": json.dumps({"text": to_emit})}
            answer_text, trailer = buffer, None
        else:
            answer_text = buffer[:marker_index].strip()
            trailer = buffer[marker_index + len(CITATION_MARKER):].strip()

        cited_labels = parse_cited_labels(answer_text, trailer)
        citations = resolve_citations(cited_labels, label_map, retrieval)

        flagged_urls = find_unverified_urls(answer_text, [chunk.text for chunk in retrieval.chunks])
        if flagged_urls:
            logger.warning("Chat answer contained unverified URL(s): %s", flagged_urls)
            citations.flagged_urls = flagged_urls

        yield {"event": "citations", "data": citations.model_dump_json()}
    except Exception:
        logger.exception("Chat stream failed for question: %r", question)
        yield {
            "event": "token",
            "data": json.dumps({"text": "\n\nSorry — something went wrong answering that. Please try again."}),
        }
        yield {"event": "citations", "data": EMPTY_CITATIONS}

    yield {"event": "done", "data": "{}"}


@router.post("")
@limiter.limit(settings.chat_rate_limit)
async def chat(request: Request, body: ChatRequest) -> EventSourceResponse:
    ip_hash = hash_client_ip(request)
    return EventSourceResponse(_stream_chat_response(body.message, ip_hash))
