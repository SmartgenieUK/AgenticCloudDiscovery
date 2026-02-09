"""OAuth 2.0 configuration and client setup."""
from typing import Dict

from authlib.integrations.requests_client import OAuth2Session
from fastapi import HTTPException, status

from config import settings


def get_oauth_config(provider: str) -> Dict:
    """Get OAuth configuration for a given provider (google, microsoft)."""
    configs = {
        "google": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
            "redirect_uri": settings.google_redirect_uri,
            "scope": ["openid", "email", "profile"],
        },
        "microsoft": {
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "authorize_url": "https://login.microsoftonline.com/consumers/oauth2/v2.0/authorize",
            "token_url": "https://login.microsoftonline.com/consumers/oauth2/v2.0/token",
            "userinfo_url": "https://graph.microsoft.com/oidc/userinfo",
            "redirect_uri": settings.microsoft_redirect_uri,
            "scope": ["openid", "email", "profile"],
        },
    }
    config = configs.get(provider)
    if not config:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider.")
    if not config["client_id"] or not config["client_secret"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{provider} OAuth not configured.",
        )
    return config


def get_oauth_client(provider: str) -> OAuth2Session:
    """Create OAuth2 client session for the given provider."""
    config = get_oauth_config(provider)
    return OAuth2Session(
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        scope=config["scope"],
        redirect_uri=config["redirect_uri"],
    )
