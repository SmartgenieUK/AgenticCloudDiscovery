"""Authentication route handlers for OAuth, registration, and login."""
import datetime
import logging
import time
import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from passlib.context import CryptContext
from starlette.responses import RedirectResponse

from config import settings
from models import (
    CompleteProfileRequest,
    LoginRequest,
    RegisterEmailRequest,
    ResetPasswordRequest,
    UserProfile,
    sanitize_user,
)
from users import UserRepository

from .dependencies import get_current_user, get_repo
from .jwt import create_token
from .oauth import get_oauth_client, get_oauth_config
from .session import set_session_cookies
from .utils import enforce_rate_limit

logger = logging.getLogger("agent-orchestrator.auth")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

# OAuth state storage (use Redis in production)
oauth_state_store: Dict[str, Dict] = {}
oauth_providers = ["google", "microsoft"]

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/oauth/providers")
def list_providers() -> Dict[str, List[str]]:
    """List available OAuth providers."""
    return {"providers": oauth_providers}


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str, request: Request) -> Dict[str, str]:
    """Initiate OAuth flow by redirecting to provider's authorization URL."""
    if provider not in oauth_providers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider.")
    client_ip = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"oauth_start:{client_ip}")

    session = get_oauth_client(provider)
    config = get_oauth_config(provider)
    authorization_url, state = session.create_authorization_url(
        config["authorize_url"],
        state=str(uuid.uuid4()),
        prompt="select_account",
    )
    oauth_state_store[state] = {"provider": provider, "created_at": time.time()}
    return {"authorization_url": authorization_url, "state": state}


@router.get("/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    request: Request,
    response: Response,
    code: Optional[str] = None,
    state: Optional[str] = None,
):
    """Handle OAuth callback from provider, create/update user, and set session cookies."""
    if provider not in oauth_providers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider.")
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing OAuth parameters.")

    state_entry = oauth_state_store.get(state)
    if (
        not state_entry
        or state_entry.get("provider") != provider
        or (time.time() - state_entry.get("created_at", 0)) > 600
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state.")

    config = get_oauth_config(provider)
    session = get_oauth_client(provider)
    try:
        session.fetch_token(config["token_url"], code=code)
        userinfo_resp = session.get(config["userinfo_url"])
        userinfo = userinfo_resp.json()
    except Exception as exc:
        logger.exception(
            "oauth_callback_failed correlation_id=%s provider=%s error=%s",
            getattr(request.state, "correlation_id", ""),
            provider,
            exc,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth callback failed.")

    email = userinfo.get("email")
    subject = userinfo.get("sub") or userinfo.get("id")
    name = userinfo.get("name") or userinfo.get("preferred_username") or (email.split("@")[0] if email else "")
    if not email or not subject:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth profile missing required fields."
        )

    repo = get_repo()
    existing = repo.get_by_email(email)
    if existing and existing.get("auth_provider") != provider:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered with another provider."
        )

    now = datetime.datetime.utcnow().isoformat()
    if not existing:
        user_doc = {
            "user_id": str(uuid.uuid4()),
            "id": None,  # populated below
            "name": name,
            "email": email,
            "phone": None,
            "designation": None,
            "company_address": None,
            "auth_provider": provider,
            "provider_subject_id": subject,
            "password_hash": None,
            "created_at": now,
            "updated_at": now,
            "last_login_at": now,
        }
        user_doc["id"] = user_doc["user_id"]
        saved = repo.create_user(user_doc)
    else:
        existing.update(
            {
                "provider_subject_id": existing.get("provider_subject_id") or subject,
                "last_login_at": now,
                "updated_at": now,
            }
        )
        saved = repo.update_user(existing)

    access_token = create_token(
        {"sub": saved["user_id"], "email": saved["email"]},
        datetime.timedelta(minutes=settings.access_token_minutes),
        "access",
    )
    refresh_token = create_token(
        {"sub": saved["user_id"], "email": saved["email"]},
        datetime.timedelta(days=settings.refresh_token_days),
        "refresh",
    )
    oauth_state_store.pop(state, None)

    needs_profile = not saved.get("phone") or not saved.get("designation")
    target_path = "/complete-profile" if needs_profile else "/dashboard"
    target = f"{settings.ui_base_url.rstrip('/')}{target_path}"

    logger.info(
        "oauth_login_success correlation_id=%s provider=%s email=%s",
        getattr(request.state, "correlation_id", ""),
        provider,
        email,
    )

    redirect_response = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    set_session_cookies(redirect_response, access_token, refresh_token)
    return redirect_response


@router.post("/register-email", response_model=UserProfile)
def register_email(request: Request, payload: RegisterEmailRequest, response: Response) -> UserProfile:
    """Register a new user with email and password."""
    client_id = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"register:{client_id}")

    repo = get_repo()
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")

    hashed_password = pwd_context.hash(payload.password)
    now = datetime.datetime.utcnow().isoformat()
    user_doc = {
        "user_id": str(uuid.uuid4()),
        "id": None,  # populated below
        "name": payload.name,
        "email": payload.email,
        "phone": payload.phone,
        "designation": payload.designation,
        "company_address": payload.company_address,
        "auth_provider": "email",
        "provider_subject_id": None,
        "password_hash": hashed_password,
        "created_at": now,
        "updated_at": now,
        "last_login_at": now,
    }
    user_doc["id"] = user_doc["user_id"]
    saved = repo.create_user(user_doc)

    access_token = create_token(
        {"sub": saved["user_id"], "email": saved["email"]},
        datetime.timedelta(minutes=settings.access_token_minutes),
        "access",
    )
    refresh_token = create_token(
        {"sub": saved["user_id"], "email": saved["email"]},
        datetime.timedelta(days=settings.refresh_token_days),
        "refresh",
    )
    set_session_cookies(response, access_token, refresh_token)

    logger.info("user_registered correlation_id=%s email=%s", request.state.correlation_id, payload.email)
    return sanitize_user(saved)


@router.post("/login-email", response_model=UserProfile)
def login_email(request: Request, payload: LoginRequest, response: Response) -> UserProfile:
    """Login with email and password."""
    client_id = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"login:{client_id}")

    repo = get_repo()
    user = repo.get_by_email(payload.email)
    if not user or user.get("auth_provider") != "email":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not pwd_context.verify(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    user["last_login_at"] = datetime.datetime.utcnow().isoformat()
    user["updated_at"] = user["last_login_at"]
    repo.update_user(user)

    access_token = create_token(
        {"sub": user["user_id"], "email": user["email"]},
        datetime.timedelta(minutes=settings.access_token_minutes),
        "access",
    )
    refresh_token = create_token(
        {"sub": user["user_id"], "email": user["email"]},
        datetime.timedelta(days=settings.refresh_token_days),
        "refresh",
    )
    set_session_cookies(response, access_token, refresh_token)

    logger.info("user_logged_in correlation_id=%s email=%s", request.state.correlation_id, payload.email)
    return sanitize_user(user)


@router.post("/reset-password")
def reset_password(request: Request, payload: ResetPasswordRequest) -> Dict[str, str]:
    """Reset password for an email-registered user (dev mode: no email verification)."""
    client_id = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"reset:{client_id}")

    repo = get_repo()
    user = repo.get_by_email(payload.email)
    if not user or user.get("auth_provider") != "email":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No email-registered account found for this address.",
        )

    user["password_hash"] = pwd_context.hash(payload.new_password)
    user["updated_at"] = datetime.datetime.utcnow().isoformat()
    repo.update_user(user)

    logger.info("password_reset correlation_id=%s email=%s", request.state.correlation_id, payload.email)
    return {"status": "ok", "message": "Password has been reset. You can now log in."}


@router.post("/complete-profile", response_model=UserProfile)
def complete_profile(
    request: Request,
    payload: CompleteProfileRequest,
    user: Dict = Depends(get_current_user),
) -> UserProfile:
    """Complete user profile (for OAuth users missing phone/designation)."""
    repo = get_repo()
    user.update(
        {
            "name": payload.name,
            "phone": payload.phone,
            "designation": payload.designation,
            "company_address": payload.company_address,
            "updated_at": datetime.datetime.utcnow().isoformat(),
        }
    )
    saved = repo.update_user(user)

    logger.info("profile_completed correlation_id=%s user_id=%s", request.state.correlation_id, user["user_id"])
    return sanitize_user(saved)


@router.get("/debug-session")
def debug_session(request: Request) -> Dict[str, bool]:
    """Debug endpoint to check session cookie status."""
    access_cookie = "access_token" in request.cookies
    refresh_cookie = "refresh_token" in request.cookies
    return {
        "has_access_cookie": access_cookie,
        "has_refresh_cookie": refresh_cookie,
        "authenticated": False if not access_cookie else True,
    }
