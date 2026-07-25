import re

URL_PATTERN = re.compile(r'https?://[^\s\)\]"\'>]+')


def find_unverified_urls(answer_text: str, source_texts: list[str]) -> list[str]:
    """URLs in the answer that don't appear verbatim in any retrieved source
    chunk — a redundant signal against a prompt-injection-planted link,
    since the chat prompt already tells the model never to invent URLs.

    Detection only, not stripping: by the time the full answer is known to
    check it, matching tokens have very likely already streamed to the
    client (see chat.py's incremental token emission), so there's nothing
    to silently edit. This surfaces as a flag for the citations payload/
    logs rather than pretending to redact already-sent text.
    """
    combined_sources = "\n".join(source_texts)
    urls = URL_PATTERN.findall(answer_text)
    return [url for url in urls if url not in combined_sources]
