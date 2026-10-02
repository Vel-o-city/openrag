import json
from unittest.mock import AsyncMock, patch

import pytest

from app.api import chat
from app.chat.conversation import conversational_reply


@pytest.mark.parametrize(
    "message",
    [
        "hi",
        "  Hi!!! 👋  ",
        "hello there",
        "hey",
        "help",
        "what can you do?",
        "thanks!",
        "Okay.",
    ],
)
@pytest.mark.asyncio
async def test_conversational_turn_does_not_retrieve_or_spend_model_budget(message):
    with (
        patch.object(chat, "reserve_budget", AsyncMock()) as budget,
        patch.object(chat, "retrieve", AsyncMock()) as retrieve,
        patch.object(chat, "chat_stream") as model,
        patch.object(chat, "get_driver") as driver,
    ):
        events = [
            event
            async for event in chat._stream_chat_response(message, "ip", ["doc-a"])
        ]
    budget.assert_not_called()
    retrieve.assert_not_called()
    model.assert_not_called()
    driver.assert_not_called()
    assert events[-1]["event"] == "done"
    payload = json.loads(next(e["data"] for e in events if e["event"] == "citations"))
    assert payload["chunks"] == payload["documents"] == []


@pytest.mark.parametrize(
    "message",
    [
        "Hi, what does Article 26 say?",
        "thanks, explain education",
        "why?",
        "what about children?",
        "What does hi mean in the document?",
        "ok, summarize it",
        "Which article protects expression?",
    ],
)
def test_real_questions_and_followups_are_not_swallowed(message):
    assert conversational_reply(message) is None
