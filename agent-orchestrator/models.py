"""Pydantic models for API requests and responses."""
from typing import Dict, List, Optional
from pydantic import BaseModel, EmailStr, Field, validator


# ==================== Auth Models ====================

class RegisterEmailRequest(BaseModel):
    """Request model for email registration."""
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
    """Request model for email/password login."""
    email: EmailStr
    password: str


class ResetPasswordRequest(BaseModel):
    """Request model for password reset (dev mode: no email verification)."""
    email: EmailStr
    new_password: str = Field(..., min_length=8)
    confirm_password: str

    @validator("confirm_password")
    def passwords_match(cls, v: str, values: Dict[str, str]) -> str:
        if "new_password" in values and v != values["new_password"]:
            raise ValueError("Passwords do not match.")
        return v


class CompleteProfileRequest(BaseModel):
    """Request model for completing user profile (OAuth users)."""
    name: str = Field(..., min_length=2, max_length=200)
    phone: str = Field(..., min_length=5, max_length=50)
    designation: str = Field(..., min_length=2, max_length=100)
    company_address: Optional[str] = None


class UserProfile(BaseModel):
    """Response model for user profile (sanitized)."""
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


# ==================== Connection Models ====================

class CreateConnectionRequest(BaseModel):
    """Request model for creating a connection."""
    tenant_id: str = Field(..., min_length=2, max_length=100)
    subscription_ids: List[str] = Field(..., min_items=1)
    provider: str = Field(..., regex="^(oauth_delegated|service_principal|managed_identity)$")
    access_token: Optional[str] = None
    expires_at: Optional[str] = None
    rbac_tier: str = Field("inventory", regex="^(inventory|cost|security)$")
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    @validator("client_id", always=True)
    def sp_requires_credentials(cls, v, values):
        if values.get("provider") == "service_principal" and not v:
            raise ValueError("client_id is required for service_principal provider.")
        return v

    @validator("client_secret", always=True)
    def sp_requires_secret(cls, v, values):
        if values.get("provider") == "service_principal" and not v:
            raise ValueError("client_secret is required for service_principal provider.")
        return v


class Connection(BaseModel):
    """Response model for connection (sanitized - no access_token)."""
    connection_id: str
    user_id: str
    tenant_id: str
    subscription_ids: List[str]
    provider: str
    status: str
    expires_at: Optional[str] = None
    created_at: str
    updated_at: str
    rbac_tier: Optional[str] = None


# ==================== Discovery Models ====================

class DiscoveryRequest(BaseModel):
    """Request model for discovery execution."""
    connection_id: str
    tenant_id: Optional[str] = None
    subscription_id: Optional[str] = None
    tier: str = Field(..., regex="^(inventory|cost|security)$")

    @validator("tenant_id", always=True)
    def at_least_one_scope(cls, v, values):
        if not v and not values.get("subscription_id"):
            raise ValueError("tenant_id or subscription_id is required.")
        return v


class Discovery(BaseModel):
    """Response model for discovery job."""
    discovery_id: str
    connection_id: str
    tenant_id: Optional[str]
    subscription_id: Optional[str]
    tier: str
    stage: str
    status: str
    created_at: str
    updated_at: str
    results: Optional[Dict] = None
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    session_id: Optional[str] = None


class PlanStep(BaseModel):
    """Model for a single step in execution plan."""
    name: str
    status: str
    detail: Optional[Dict] = None


class ChatRequest(BaseModel):
    """Request model for chat/discovery via natural language."""
    message: str = Field(..., min_length=1, max_length=2000)
    connection_id: str
    tenant_id: Optional[str] = None
    subscription_id: Optional[str] = None
    tier: str = Field(..., regex="^(inventory|cost|security)$")
    session_id: Optional[str] = None

    @validator("tenant_id", always=True)
    def at_least_one_scope(cls, v, values):
        if not v and not values.get("subscription_id"):
            raise ValueError("tenant_id or subscription_id is required.")
        return v


class ChatResponse(BaseModel):
    """Response model for chat/discovery."""
    session_id: str
    trace_id: str
    correlation_id: str
    plan: List[PlanStep]
    discovery: Discovery
    final_response: str


# ==================== Helper Functions ====================

def sanitize_user(doc: Dict) -> UserProfile:
    """Sanitize user document for API response (removes password_hash, etc)."""
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


def sanitize_connection(doc: Dict) -> Connection:
    """Sanitize connection document for API response (removes access_token)."""
    return Connection(
        connection_id=doc["connection_id"],
        user_id=doc["user_id"],
        tenant_id=doc["tenant_id"],
        subscription_ids=doc.get("subscription_ids", []),
        provider=doc.get("provider", "oauth_delegated"),
        status=doc.get("status", "active"),
        expires_at=doc.get("expires_at"),
        created_at=doc.get("created_at", ""),
        updated_at=doc.get("updated_at", ""),
        rbac_tier=doc.get("rbac_tier"),
    )
