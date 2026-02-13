"""Azure AD token acquisition for Service Principal and Managed Identity authentication."""
import base64
import datetime
import json
import logging
from typing import Dict, Optional

import httpx
from azure.identity import (
    DefaultAzureCredential,
    InteractiveBrowserCredential,
    ManagedIdentityCredential,
)
from fastapi import HTTPException, status

logger = logging.getLogger("agent-orchestrator.azure_auth")

AZURE_AD_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
ARM_SCOPE = "https://management.azure.com/.default"


def _extract_display_name(token_str: str) -> Optional[str]:
    """Extract display name from a JWT access token (decode payload without verification)."""
    try:
        payload_b64 = token_str.split(".")[1]
        # Add base64 padding
        payload_b64 += "=" * (-len(payload_b64) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))
        return claims.get("name") or claims.get("upn") or claims.get("preferred_username")
    except Exception:
        return None


def acquire_sp_token(tenant_id: str, client_id: str, client_secret: str) -> Dict[str, str]:
    """
    Acquire an Azure AD bearer token using Service Principal client credentials.

    Args:
        tenant_id: Azure AD tenant ID
        client_id: Service Principal application (client) ID
        client_secret: Service Principal client secret

    Returns:
        Dict with 'access_token' and 'expires_on' (ISO timestamp)

    Raises:
        HTTPException(400) if token acquisition fails
    """
    url = AZURE_AD_TOKEN_URL.format(tenant_id=tenant_id)
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": ARM_SCOPE,
    }

    try:
        with httpx.Client(timeout=15) as client:
            resp = client.post(url, data=data)

        if resp.status_code != 200:
            body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            error_desc = body.get("error_description", resp.text[:300])
            logger.error("Azure AD token request failed: %s", error_desc)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to acquire Azure token: {error_desc}",
            )

        token_data = resp.json()
        access_token = token_data["access_token"]
        expires_in = int(token_data.get("expires_in", 3600))
        expires_on = (datetime.datetime.utcnow() + datetime.timedelta(seconds=expires_in)).isoformat() + "Z"

        display_name = _extract_display_name(access_token)
        logger.info("Azure AD token acquired for tenant=%s client_id=%s (expires_in=%ds, user=%s)", tenant_id, client_id, expires_in, display_name)
        return {"access_token": access_token, "expires_on": expires_on, "display_name": display_name}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Azure AD token request error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to acquire Azure token: {str(exc)}",
        )


def acquire_mi_token(tenant_id: Optional[str] = None) -> Dict[str, str]:
    """
    Acquire an Azure AD bearer token using interactive browser login.

    Locally: opens a browser window for Microsoft login (like 'az login').
    On Azure: falls back to Managed Identity (no browser needed).

    Args:
        tenant_id: Optional Azure AD tenant ID to scope the login

    Returns:
        Dict with 'access_token' and 'expires_on' (ISO timestamp)

    Raises:
        HTTPException(400) if authentication fails
    """
    # On Azure infrastructure, try Managed Identity first (no browser needed)
    try:
        credential = ManagedIdentityCredential()
        token = credential.get_token(ARM_SCOPE)
        expires_on = datetime.datetime.utcfromtimestamp(token.expires_on).isoformat() + "Z"
        display_name = _extract_display_name(token.token)
        logger.info("Azure token acquired via ManagedIdentityCredential (expires_on=%s, user=%s)", expires_on, display_name)
        return {"access_token": token.token, "expires_on": expires_on, "display_name": display_name}
    except Exception:
        logger.info("ManagedIdentityCredential not available, falling back to interactive browser login")

    # Local dev: open browser for interactive Microsoft login (like 'az login')
    try:
        kwargs = {}
        if tenant_id:
            kwargs["tenant_id"] = tenant_id
        logger.info("Opening browser for Azure login (tenant=%s)...", tenant_id or "common")
        credential = InteractiveBrowserCredential(**kwargs)
        token = credential.get_token(ARM_SCOPE)
        expires_on = datetime.datetime.utcfromtimestamp(token.expires_on).isoformat() + "Z"
        display_name = _extract_display_name(token.token)
        logger.info("Azure token acquired via interactive browser login (expires_on=%s, user=%s)", expires_on, display_name)
        return {"access_token": token.token, "expires_on": expires_on, "display_name": display_name}
    except Exception as exc:
        logger.error("Interactive browser login failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Azure login failed: {str(exc)}",
        )
