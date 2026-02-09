"""FastAPI dependencies for authentication."""
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


async def get_current_user(
    request: Request, repo: UserRepository = Depends(get_repo)
) -> Dict:
    """Extract and validate the current user from session cookie."""
    token = request.cookies.get("access_token")
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
