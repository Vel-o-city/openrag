"""Handle complete conversational turns without retrieving document evidence.

Match only the entire message: a greeting followed by a real question must
still reach retrieval, as must short document follow-ups such as "why?".
"""

import re


def conversational_reply(message: str) -> tuple[str, bool] | None:
    text = re.sub(r"[^\w\s]", " ", message.casefold())
    text = " ".join(text.split())
    if text in {
        "hi",
        "hello",
        "hey",
        "hiya",
        "yo",
        "hi there",
        "hello there",
        "hey there",
        "good morning",
        "good afternoon",
        "good evening",
    }:
        return (
            "Hi! I can help you explore the selected document. Pick a question below, "
            "or ask your own. You can open the citations in each sourced answer "
            "to check the original passage.",
            True,
        )
    if text in {"help", "what can you do", "how does this work", "how do i use this"}:
        return (
            "Ask me to explain, summarize, or find information in your selected "
            "documents. Try a question below, or upload your own file. Open a "
            "numbered citation to check the passage behind an answer.",
            True,
        )
    if text in {"thanks", "thank you", "thankyou", "thanks a lot", "thank you so much"}:
        return ("You're welcome! Ask another question whenever you're ready.", False)
    if text in {"ok", "okay", "got it", "sounds good"}:
        return (
            "Ready when you are. Ask another question about your selected documents.",
            False,
        )
    return None
