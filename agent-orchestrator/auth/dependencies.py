"""FastAPI dependencies for authentication."""
import os
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt

from config import settings
from users import UserRepository

# Global repository provider (set by main.py after initialization)
_repo_provider: Optional[UserRepository] = None


def set_repo_provider(provider: UserRepository) -> None:
    """Set the global repository provider (called from main.py after initialization)."""
    global _repo_provider
    _repo_provider = provider


def get_repo() -> UserRepository:
    """Get the user repository instance."""
    if _repo_provider is None:
        raise RuntimeError("Repository provider not initialized. Call set_repo_provider() first.")
    return _repo_provider


_DEV_USER = {
    "user_id": "dev-user-00000000",
    "id": "dev-user-00000000",
    "name": "Dev User",
    "email": "dev@localhost",
    "phone": "0000000000",
    "designation": "Developer",
    "company_address": None,
    "auth_provider": "email",
    "provider_subject_id": None,
    "password_hash": None,
    "created_at": "2025-01-01T00:00:00",
    "updated_at": "2025-01-01T00:00:00",
    "last_login_at": "2025-01-01T00:00:00",
}

# DEV MODE: Set to True to bypass authentication entirely
DEV_SKIP_AUTH = os.getenv("DEV_SKIP_AUTH", "true").lower() == "true"


async def get_current_user(
    request: Request, repo: UserRepository = Depends(get_repo)
) -> Dict:
    """Extract and validate the current user from session cookie."""
    token = request.cookies.get("access_token")

    # DEV MODE: return a stub user when no token is present
    if not token and DEV_SKIP_AUTH:
        return _DEV_USER

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "access":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type.")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    return user
