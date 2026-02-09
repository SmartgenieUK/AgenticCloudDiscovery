"""Authentication utility functions."""
import time
from typing import Dict, List

from fastapi import HTTPException, status

# In-memory rate limit store (for MVP, use Redis in production)
rate_limit_store: Dict[str, List[float]] = {}


def enforce_rate_limit(scope: str, limit: int = 10, window_seconds: int = 60) -> None:
    """Enforce rate limiting per scope (e.g., IP address, user ID)."""
    now = time.time()
    entries = [ts for ts in rate_limit_store.get(scope, []) if now - ts < window_seconds]
    if len(entries) >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, slow down.",
        )
    entries.append(now)
    rate_limit_store[scope] = entries
