import hashlib

from fastapi import Request


def hash_client_ip(request: Request) -> str:
    """Never store raw IPs — a stable hash is enough to rate-limit/budget by
    visitor without keeping anything more identifying than necessary."""
    client_host = request.client.host if request.client else "unknown"
    return hashlib.sha256(client_host.encode()).hexdigest()
