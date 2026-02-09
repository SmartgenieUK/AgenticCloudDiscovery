"""JWT token creation and validation."""
import datetime
from typing import Dict

from jose import jwt

from config import settings


def create_token(data: Dict, expires_delta: datetime.timedelta, token_type: str) -> str:
    """Create a JWT token with expiration and type (access or refresh)."""
    to_encode = data.copy()
    to_encode.update(
        {
            "type": token_type,
            "exp": datetime.datetime.utcnow() + expires_delta,
            "iat": datetime.datetime.utcnow(),
        }
    )
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
