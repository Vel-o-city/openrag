import json

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from app.chat.citations import parse_cited_labels, resolve_citations, split_answer_and_citations
from app.chat.prompts import CITATION_MARKER, SYSTEM_PROMPT, build_context_block, build_user_message
from app.config import settings
from app.gemini.client import chat_stream
from app.graph.neo4j_client import get_driver
from app.rate_limiter import limiter
from app.retrieval.retriever import retrieve

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str


async def _stream_chat_response(question: str):
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
        answer_text, trailer = buffer[:marker_index].strip(), buffer[marker_index + len(CITATION_MARKER):].strip()

    cited_labels = parse_cited_labels(answer_text, trailer)
    citations = resolve_citations(cited_labels, label_map, retrieval)

    yield {"event": "citations", "data": json.dumps(citations)}
    yield {"event": "done", "data": "{}"}


@router.post("")
@limiter.limit(settings.chat_rate_limit)
async def chat(request: Request, body: ChatRequest) -> EventSourceResponse:
    return EventSourceResponse(_stream_chat_response(body.message))
