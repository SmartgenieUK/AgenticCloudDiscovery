"""Azure AD token acquisition for Service Principal authentication."""
import datetime
import logging
from typing import Dict

import httpx
from fastapi import HTTPException, status

logger = logging.getLogger("agent-orchestrator.azure_auth")

AZURE_AD_TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
ARM_SCOPE = "https://management.azure.com/.default"


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

        logger.info("Azure AD token acquired for tenant=%s client_id=%s (expires_in=%ds)", tenant_id, client_id, expires_in)
        return {"access_token": access_token, "expires_on": expires_on}

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Azure AD token request error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to acquire Azure token: {str(exc)}",
        )
