"""
Authentication API endpoints.

This module handles all authentication-related endpoints including:
- Login
- Registration
- Password reset
- Email verification
- Session management
"""

from datetime import timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import (
    ClientIpDep,
    CurrentUserDep,
    OptionalUserDep,
    RequestIdDep,
    SessionManagerDep,
    UserAgentDep,
    get_redis,
)
from app.core.database import AsyncSession, get_db
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SendVerificationCodeRequest,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from app.services.rate_limit_service import RateLimitService

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ============================================================================
# Dependencies
# ============================================================================

async def get_auth_service(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[object, Depends(get_redis)],
) -> AuthService:
    """Get auth service instance."""
    return AuthService(db, redis)


async def get_rate_limit_service(
    redis: Annotated[object, Depends(get_redis)],
) -> RateLimitService:
    """Get rate limit service instance."""
    return RateLimitService(redis)


async def get_email_service() -> EmailService:
    """Get email service instance."""
    return EmailService()


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
RateLimitServiceDep = Annotated[RateLimitService, Depends(get_rate_limit_service)]
EmailServiceDep = Annotated[EmailService, Depends(get_email_service)]


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    credentials: LoginRequest,
    auth_service: AuthServiceDep,
    rate_limit: RateLimitServiceDep,
    session_manager: SessionManagerDep,
    client_ip: ClientIpDep,
    user_agent: UserAgentDep,
    request_id: RequestIdDep,
):
    """
    Login with email and password.

    Supports session-based authentication with optional "remember me" functionality.
    """
    # Check if IP is banned
    if await rate_limit.is_banned(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Please try again later.",
        )

    # Check rate limit
    identifier = f"{client_ip}:{credentials.email.lower()}"
    is_allowed, current_count, reset_time = await rate_limit.check_rate_limit(
        identifier,
        "login",
        settings.rate_limit.login_attempts,
        settings.rate_limit.login_window,
    )

    if not is_allowed:
        # Ban the IP
        await rate_limit.ban(client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please try again later.",
        )

    # Authenticate user
    user = await auth_service.authenticate_user(credentials.email, credentials.password)

    if not user:
        # Record failed attempt
        await auth_service.update_last_login(
            user=None,
            success=False,
            ip_address=client_ip,
            user_agent=user_agent,
        )
        await rate_limit.record_attempt(identifier, "login")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Invalid email or password",
            },
        )

    # Create session
    session_id = await session_manager.create(
        user_id=str(user.id),
        email=user.email,
        name=user.name,
        ip_address=client_ip,
        user_agent=user_agent,
        remember_me=credentials.remember_me,
    )

    # Set session cookie
    response.set_cookie(
        key=settings.session.cookie_name,
        value=session_id,
        httponly=settings.session.cookie_httponly,
        secure=settings.session.cookie_secure,
        samesite=settings.session.cookie_samesite,
        max_age=settings.session.remember_ttl if credentials.remember_me else settings.session.ttl,
        path="/",
        domain=settings.session.cookie_domain or None,
    )

    # Update last login
    await auth_service.update_last_login(
        user=user,
        success=True,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    # Clear failed attempts on successful login
    await rate_limit.reset(identifier, "login")

    return LoginResponse(
        success=True,
        message="Login successful",
        user=UserResponse.from_user(user),
        redirect_to=settings.app.frontend_base_url,
    )


@router.post("/logout", response_model=AuthResponse)
async def logout(
    response: Response,
    request: Request,
    session_manager: SessionManagerDep,
    current_user: CurrentUserDep,
):
    """
    Logout current user and destroy session.
    """
    session_id = request.cookies.get(settings.session.cookie_name)

    if session_id:
        await session_manager.destroy(session_id)

    # Clear cookie
    response.delete_cookie(
        settings.session.cookie_name,
        path="/",
        domain=settings.session.cookie_domain or None,
    )

    return AuthResponse(success=True, message="Logout successful")


@router.post("/register", response_model=AuthResponse)
async def register(
    data: RegisterRequest,
    auth_service: AuthServiceDep,
    email_service: EmailServiceDep,
    rate_limit: RateLimitServiceDep,
    session_manager: SessionManagerDep,
    client_ip: ClientIpDep,
):
    """
    Register a new user account.

    Requires a verification code that was sent to the email address.
    """
    identifier = f"{client_ip}:{data.email.lower()}"

    # Check rate limit for verification code requests
    is_allowed, _, _ = await rate_limit.check_rate_limit(
        identifier,
        "register",
        settings.rate_limit.code_requests,
        settings.rate_limit.code_window,
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
        )

    # Verify the code
    if not await auth_service.consume_verification_code(data.email, data.verification_code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_CODE",
                "message": "Invalid or expired verification code",
            },
        )

    # Validate password
    is_valid, missing = await auth_service.validate_registration_password(data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "WEAK_PASSWORD",
                "message": f"Password requirements not met: {', '.join(missing)}",
            },
        )

    # Check if user already exists
    existing_user = await auth_service.get_user_by_email(data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_EXISTS",
                "message": "An account with this email already exists",
            },
        )

    # Create user
    user = await auth_service.create_user(
        email=data.email,
        password=data.password,
        name=data.name,
        is_verified=True,  # Verified via code
    )

    # Send welcome email
    await email_service.send_welcome(user.email, user.name)

    return AuthResponse(
        success=True,
        message="Registration successful",
    )


@router.post("/send-verification-code", response_model=AuthResponse)
async def send_verification_code(
    data: SendVerificationCodeRequest,
    auth_service: AuthServiceDep,
    email_service: EmailServiceDep,
    rate_limit: RateLimitServiceDep,
    client_ip: ClientIpDep,
):
    """
    Send a verification code to the specified email address.

    This can be used for registration or other verification purposes.
    """
    identifier = f"{client_ip}:{data.email.lower()}"

    # Check rate limit
    is_allowed, current_count, reset_time = await rate_limit.check_rate_limit(
        identifier,
        "send_code",
        settings.rate_limit.code_requests,
        settings.rate_limit.code_window,
    )

    if not is_allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many code requests. Please try again later.",
        )

    # Generate and store code
    ttl_minutes = settings.verify.verify_code_ttl // 60
    code = await auth_service.create_verification_code(
        data.email,
        ttl=settings.verify.verify_code_ttl,
    )

    # Send email
    if settings.smtp.enabled:
        await email_service.send_verification_code(data.email, code, ttl_minutes)

    return AuthResponse(
        success=True,
        message="Verification code sent",
    )


@router.post("/forgot-password", response_model=AuthResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    auth_service: AuthServiceDep,
    email_service: EmailServiceDep,
    rate_limit: RateLimitServiceDep,
    client_ip: ClientIpDep,
):
    """
    Request a password reset link/code.

    For security, this endpoint always returns success even if the email doesn't exist.
    """
    identifier = f"{client_ip}:{data.email.lower()}"

    # Check rate limit
    is_allowed, _, _ = await rate_limit.check_rate_limit(
        identifier,
        "forgot_password",
        settings.rate_limit.code_requests,
        settings.rate_limit.code_window,
    )

    if not is_allowed:
        # Still return success but don't actually send
        return AuthResponse(
            success=True,
            message="If an account exists with this email, a reset link has been sent.",
        )

    # Check if user exists
    user = await auth_service.get_user_by_email(data.email)

    if user:
        # Create password reset
        token, code = await auth_service.create_password_reset(user)

        # Send email based on mode
        ttl_minutes = settings.verify.reset_token_ttl // 60

        if settings.verify.reset_mode == "token":
            reset_link = f"{settings.app.frontend_base_url}/auth/reset?token={token}"
            await email_service.send_password_reset(user.email, reset_link, ttl_minutes)
        elif settings.verify.reset_mode == "code":
            await email_service.send_password_reset_code(user.email, code, ttl_minutes)
        else:  # both
            reset_link = f"{settings.app.frontend_base_url}/auth/reset?token={token}"
            await email_service.send_password_reset(user.email, reset_link, ttl_minutes)

    # Always return success (security best practice)
    return AuthResponse(
        success=True,
        message="If an account exists with this email, a reset link has been sent.",
    )


@router.post("/reset-password", response_model=AuthResponse)
async def reset_password(
    data: ResetPasswordRequest,
    auth_service: AuthServiceDep,
    rate_limit: RateLimitServiceDep,
    client_ip: ClientIpDep,
):
    """
    Reset password using a token or code.

    Accepts either a token (from email link) or a manually entered code.
    """
    # Validate password
    from app.core.security import PasswordPolicy
    password_policy = PasswordPolicy()
    is_valid, missing = password_policy.validate(data.new_password)

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "WEAK_PASSWORD",
                "message": f"Password requirements not met: {', '.join(missing)}",
            },
        )

    # Get reset record
    reset = await auth_service.get_valid_password_reset(token=data.token, code=data.code)

    if not reset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_TOKEN",
                "message": "Invalid or expired reset token/code",
            },
        )

    # Reset password
    success = await auth_service.reset_password(reset, data.new_password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "RESET_FAILED",
                "message": "Failed to reset password",
            },
        )

    return AuthResponse(
        success=True,
        message="Password reset successful",
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
):
    """
    Get current authenticated user information.
    """
    user = await auth_service.get_user_by_id(current_user.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.from_user(user)


@router.post("/change-password", response_model=AuthResponse)
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
):
    """
    Change password for authenticated user.

    Requires current password for verification.
    """
    user = await auth_service.get_user_by_id(current_user.user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Validate new password
    is_valid, missing = await auth_service.validate_registration_password(data.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "WEAK_PASSWORD",
                "message": f"Password requirements not met: {', '.join(missing)}",
            },
        )

    # Change password
    success = await auth_service.change_password(user, data.current_password, data.new_password)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "INVALID_PASSWORD",
                "message": "Current password is incorrect",
            },
        )

    return AuthResponse(
        success=True,
        message="Password changed successfully",
    )


@router.get("/sessions", response_model=dict)
async def list_sessions(
    current_user: CurrentUserDep,
    auth_service: AuthServiceDep,
    redis: Annotated[object, Depends(get_redis)],
):
    """
    List all active sessions for the current user.
    """
    # Get session count
    key = f"{settings.redis.session_prefix}user:{current_user.user_id}"
    session_ids = await redis.smembers(key)

    return {
        "success": True,
        "data": {
            "active_sessions": len(session_ids),
            "max_sessions": settings.session.max_sessions_per_user,
        },
    }


@router.delete("/sessions", response_model=AuthResponse)
async def revoke_all_sessions(
    response: Response,
    request: Request,
    current_user: CurrentUserDep,
    session_manager: SessionManagerDep,
):
    """
    Revoke all sessions for the current user except the current one.
    """
    # Get current session ID
    current_session_id = request.cookies.get(settings.session.cookie_name)

    # Revoke all sessions
    await session_manager.destroy_all_for_user(current_user.user_id)

    # Create new session for current user
    import uuid
    new_session_id = await session_manager.create(
        user_id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
    )

    # Update cookie
    response.set_cookie(
        key=settings.session.cookie_name,
        value=new_session_id,
        httponly=settings.session.cookie_httponly,
        secure=settings.session.cookie_secure,
        samesite=settings.session.cookie_samesite,
        max_age=settings.session.ttl,
        path="/",
        domain=settings.session.cookie_domain or None,
    )

    return AuthResponse(
        success=True,
        message="All sessions revoked",
    )
