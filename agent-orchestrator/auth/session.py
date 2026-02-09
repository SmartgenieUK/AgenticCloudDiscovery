"""Session cookie management."""
import logging

from fastapi import Response

from config import settings

logger = logging.getLogger("agent-orchestrator.auth.session")


def set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set secure HTTP-only session cookies for access and refresh tokens."""
    samesite_value = settings.cookie_samesite if settings.cookie_samesite in {"lax", "strict", "none"} else "lax"
    if samesite_value == "none" and not settings.cookie_secure:
        logger.warning(
            "cookie_samesite=none requires secure cookies; falling back to lax for non-secure dev environment."
        )
        samesite_value = "lax"

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=samesite_value,
        max_age=settings.access_token_minutes * 60,
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=samesite_value,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/",
    )
