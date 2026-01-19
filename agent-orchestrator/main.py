import datetime
import logging
import os
import time
import uuid
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, validator

try:
    from azure.cosmos import CosmosClient, PartitionKey, exceptions as cosmos_exceptions
except ImportError:  # pragma: no cover - optional for local dev without Cosmos
    CosmosClient = None  # type: ignore
    PartitionKey = None  # type: ignore
    cosmos_exceptions = None  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("agent-orchestrator.auth")


class Settings:
    def __init__(self) -> None:
        self.secret_key = os.getenv("AUTH_SECRET_KEY", "dev-secret-change-me")
        self.algorithm = "HS256"
        self.access_token_minutes = int(os.getenv("AUTH_ACCESS_TOKEN_MINUTES", "30"))
        self.refresh_token_days = int(os.getenv("AUTH_REFRESH_TOKEN_DAYS", "7"))
        self.cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
        self.cosmos_key = os.getenv("COSMOS_KEY")
        self.cosmos_db = os.getenv("COSMOS_DATABASE", "agenticcloud")
        self.cosmos_users_container = os.getenv("COSMOS_USERS_CONTAINER", "users")
        origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173")
        self.cors_allow_origins = [origin.strip() for origin in origins.split(",") if origin.strip()]
        self.cookie_secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"


settings = Settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
rate_limit_store: Dict[str, List[float]] = {}


class RegisterEmailRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    email: EmailStr
    phone: str = Field(..., min_length=5, max_length=50)
    designation: str = Field(..., min_length=2, max_length=100)
    company_address: Optional[str] = None
    password: str = Field(..., min_length=8)
    confirm_password: str
    consent: bool

    @validator("confirm_password")
    def passwords_match(cls, v: str, values: Dict[str, str]) -> str:
        if "password" in values and v != values["password"]:
            raise ValueError("Passwords do not match.")
        return v

    @validator("consent")
    def consent_required(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Consent is required.")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class CompleteProfileRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., min_length=5, max_length=50)
    designation: str = Field(..., min_length=2, max_length=100)
    company_address: Optional[str] = None


class UserProfile(BaseModel):
    user_id: str
    name: str
    email: EmailStr
    phone: Optional[str] = None
    designation: Optional[str] = None
    company_address: Optional[str] = None
    auth_provider: str
    provider_subject_id: Optional[str] = None
    created_at: str
    updated_at: str
    last_login_at: Optional[str] = None


def sanitize_user(doc: Dict) -> UserProfile:
    return UserProfile(
        user_id=doc["user_id"],
        name=doc.get("name", ""),
        email=doc["email"],
        phone=doc.get("phone"),
        designation=doc.get("designation"),
        company_address=doc.get("company_address"),
        auth_provider=doc.get("auth_provider", "email"),
        provider_subject_id=doc.get("provider_subject_id"),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        last_login_at=doc.get("last_login_at"),
    )


class UserRepository:
    def get_by_email(self, email: str) -> Optional[Dict]:
        raise NotImplementedError

    def get_by_id(self, user_id: str) -> Optional[Dict]:
        raise NotImplementedError

    def create_user(self, doc: Dict) -> Dict:
        raise NotImplementedError

    def update_user(self, doc: Dict) -> Dict:
        raise NotImplementedError


class CosmosUserRepository(UserRepository):
    def __init__(self, settings: Settings) -> None:
        if CosmosClient is None:
            raise RuntimeError("azure-cosmos is not installed.")
        self.client = CosmosClient(settings.cosmos_endpoint, credential=settings.cosmos_key)
        self.database = self.client.create_database_if_not_exists(id=settings.cosmos_db)
        self.container = self.database.create_container_if_not_exists(
            id=settings.cosmos_users_container,
            partition_key=PartitionKey(path="/user_id"),
        )

    def get_by_email(self, email: str) -> Optional[Dict]:
        query = "SELECT * FROM c WHERE c.email = @email"
        items = list(
            self.container.query_items(
                query=query,
                parameters=[{"name": "@email", "value": email}],
                enable_cross_partition_query=True,
            )
        )
        return items[0] if items else None

    def get_by_id(self, user_id: str) -> Optional[Dict]:
        try:
            return self.container.read_item(item=user_id, partition_key=user_id)
        except Exception:
            return None

    def create_user(self, doc: Dict) -> Dict:
        return self.container.create_item(doc)

    def update_user(self, doc: Dict) -> Dict:
        return self.container.upsert_item(doc)


class InMemoryUserRepository(UserRepository):
    def __init__(self) -> None:
        self.users: Dict[str, Dict] = {}

    def get_by_email(self, email: str) -> Optional[Dict]:
        return next((u for u in self.users.values() if u["email"] == email), None)

    def get_by_id(self, user_id: str) -> Optional[Dict]:
        return self.users.get(user_id)

    def create_user(self, doc: Dict) -> Dict:
        self.users[doc["user_id"]] = doc
        return doc

    def update_user(self, doc: Dict) -> Dict:
        self.users[doc["user_id"]] = doc
        return doc


def get_repository() -> UserRepository:
    if settings.cosmos_endpoint and settings.cosmos_key:
        try:
            logger.info("Using Cosmos DB for user storage.")
            return CosmosUserRepository(settings)
        except Exception as exc:  # pragma: no cover - environment specific
            logger.warning("Falling back to in-memory user store: %s", exc)
    logger.info("Using in-memory user storage.")
    return InMemoryUserRepository()


repo_provider: UserRepository = get_repository()


def enforce_rate_limit(scope: str, limit: int = 10, window_seconds: int = 60) -> None:
    now = time.time()
    entries = [ts for ts in rate_limit_store.get(scope, []) if now - ts < window_seconds]
    if len(entries) >= limit:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests, slow down.")
    entries.append(now)
    rate_limit_store[scope] = entries


def create_token(data: Dict, expires_delta: datetime.timedelta, token_type: str) -> str:
    to_encode = data.copy()
    to_encode.update(
        {
            "type": token_type,
            "exp": datetime.datetime.utcnow() + expires_delta,
            "iat": datetime.datetime.utcnow(),
        }
    )
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def set_session_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_minutes * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.refresh_token_days * 24 * 60 * 60,
    )


async def get_current_user(
    request: Request, repo: UserRepository = Depends(lambda: repo_provider)
) -> Dict:
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


app = FastAPI(title="Agentic Orchestrator Auth", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_correlation_id(request: Request, call_next):
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id
    return response


@app.get("/auth/oauth/providers")
def list_providers() -> Dict[str, List[str]]:
    return {"providers": ["google", "microsoft"]}


@app.get("/auth/oauth/{provider}/start")
def oauth_start(provider: str) -> Dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"OAuth start not yet implemented for {provider}.",
    )


@app.get("/auth/oauth/{provider}/callback")
def oauth_callback(provider: str) -> Dict[str, str]:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"OAuth callback not yet implemented for {provider}.",
    )


@app.post("/auth/register-email", response_model=UserProfile)
def register_email(request: Request, payload: RegisterEmailRequest, response: Response) -> UserProfile:
    client_id = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"register:{client_id}")
    repo = repo_provider
    if repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered.")
    hashed_password = pwd_context.hash(payload.password)
    now = datetime.datetime.utcnow().isoformat()
    user_doc = {
        "user_id": str(uuid.uuid4()),
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
    saved = repo.create_user(user_doc)
    access_token = create_token({"sub": saved["user_id"], "email": saved["email"]}, datetime.timedelta(minutes=settings.access_token_minutes), "access")
    refresh_token = create_token({"sub": saved["user_id"], "email": saved["email"]}, datetime.timedelta(days=settings.refresh_token_days), "refresh")
    set_session_cookies(response, access_token, refresh_token)
    logger.info("user_registered correlation_id=%s email=%s", request.state.correlation_id, payload.email)
    return sanitize_user(saved)


@app.post("/auth/login-email", response_model=UserProfile)
def login_email(request: Request, payload: LoginRequest, response: Response) -> UserProfile:
    client_id = request.client.host if request.client else "unknown"
    enforce_rate_limit(f"login:{client_id}")
    repo = repo_provider
    user = repo.get_by_email(payload.email)
    if not user or user.get("auth_provider") != "email":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    if not pwd_context.verify(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
    user["last_login_at"] = datetime.datetime.utcnow().isoformat()
    user["updated_at"] = user["last_login_at"]
    repo.update_user(user)
    access_token = create_token({"sub": user["user_id"], "email": user["email"]}, datetime.timedelta(minutes=settings.access_token_minutes), "access")
    refresh_token = create_token({"sub": user["user_id"], "email": user["email"]}, datetime.timedelta(days=settings.refresh_token_days), "refresh")
    set_session_cookies(response, access_token, refresh_token)
    logger.info("user_logged_in correlation_id=%s email=%s", request.state.correlation_id, payload.email)
    return sanitize_user(user)


@app.post("/auth/complete-profile", response_model=UserProfile)
def complete_profile(
    request: Request,
    payload: CompleteProfileRequest,
    user: Dict = Depends(get_current_user),
) -> UserProfile:
    repo = repo_provider
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


@app.get("/me", response_model=UserProfile)
def get_me(user: Dict = Depends(get_current_user)) -> UserProfile:
    return sanitize_user(user)


@app.get("/healthz")
def health() -> Dict[str, str]:
    return {"status": "ok"}
