"""
Authentication-related schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ============================================================================
# Request Schemas
# ============================================================================


class LoginRequest(BaseModel):
    """Login request schema."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=255)
    remember_me: bool = False


class RegisterRequest(BaseModel):
    """Registration request schema."""

    email: EmailStr
    verification_code: str = Field(min_length=4, max_length=10)
    password: str = Field(min_length=8, max_length=128)
    name: Optional[str] = Field(None, max_length=100)

    @field_validator("verification_code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Normalize verification code."""
        return v.strip()

    @field_validator("name")
    @classmethod
    def set_default_name(cls, v: Optional[str]) -> str:
        """Set default name from email if not provided."""
        if v is None or v.strip() == "":
            return v  # Will be set from email in service
        return v.strip()


class SendVerificationCodeRequest(BaseModel):
    """Send verification code request schema."""

    email: EmailStr


class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request schema."""

    token: Optional[str] = None
    code: Optional[str] = None
    new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_token_or_code(self) -> "ResetPasswordRequest":
        """Validate that either token or code is provided."""
        if not self.token and not self.code:
            raise ValueError("Either 'token' or 'code' must be provided")
        return self

    @field_validator("code")
    @classmethod
    def normalize_code(cls, v: Optional[str]) -> Optional[str]:
        """Normalize verification code."""
        if v:
            return v.strip()
        return v


class ChangePasswordRequest(BaseModel):
    """Change password request schema."""

    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=128)


# ============================================================================
# Response Schemas
# ============================================================================


class UserResponse(BaseModel):
    """User response schema."""

    id: str
    email: str
    name: str
    is_active: bool
    is_verified: bool
    created_at: Optional[str] = None
    last_login_at: Optional[str] = None

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        """Create UserResponse from User model."""
        return cls(
            id=str(user.id),
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at.isoformat() if user.created_at else None,
            last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        )


class LoginResponse(BaseModel):
    """Login response schema."""

    success: bool
    message: Optional[str] = None
    user: Optional[UserResponse] = None
    redirect_to: Optional[str] = None


class AuthResponse(BaseModel):
    """Generic auth response schema."""

    success: bool
    message: Optional[str] = None
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Error response schema."""

    success: bool = False
    error: Optional["ErrorDetail"] = None
    message: Optional[str] = None


class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str
    message: str
    details: Optional[list[str]] = None


# ============================================================================
# Meta Schemas
# ============================================================================


class MetaResponse(BaseModel):
    """Meta information for responses."""

    request_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PaginatedMeta(MetaResponse):
    """Meta information for paginated responses."""

    page: int
    page_size: int
    total: int
    total_pages: int


# ============================================================================
# Health Check
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    version: str
    database: Optional[str] = None
    redis: Optional[str] = None
