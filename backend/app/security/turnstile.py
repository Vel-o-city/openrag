import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


async def verify_turnstile_token(token: str | None, remote_ip: str | None = None) -> bool:
    """Verifies a Turnstile widget response token server-side.

    Returns True (and logs a warning) when no secret key is configured, so
    local dev works without a real Turnstile setup. Once
    TURNSTILE_SECRET_KEY is set, a missing or invalid token is rejected.
    """
    if not settings.turnstile_secret_key:
        logger.warning("TURNSTILE_SECRET_KEY not set — skipping Turnstile verification (dev only).")
        return True

    if not token:
        return False

    payload = {"secret": settings.turnstile_secret_key, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            response = await http_client.post(VERIFY_URL, data=payload)
            response.raise_for_status()
            result = response.json()
    except httpx.HTTPError:
        logger.exception("Turnstile verification request failed")
        return False

    if not result.get("success"):
        logger.info("Turnstile verification failed: %s", result.get("error-codes"))
    return bool(result.get("success"))
