"""
Authentication API routes.

Endpoints: register, login, refresh, verify-email, password-reset, google-oauth.
"""

import secrets
from fastapi import APIRouter, HTTPException, Depends, status
import logging

from src.auth.schemas import (
    RegisterRequest, LoginRequest, RefreshTokenRequest,
    PasswordResetRequest, PasswordResetConfirm, ChangePasswordRequest,
    UpdateProfileRequest, GoogleAuthRequest,
    TokenResponse, UserResponse, MessageResponse,
)
from src.auth.service import AuthService
from src.auth.dependencies import get_auth_service, get_current_user
from src.auth.email_service import EmailService
from src.auth.oauth import exchange_google_code, GoogleOAuthError
from src.core.models import User

logger = logging.getLogger(__name__)

router = APIRouter()
email_service = EmailService()


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        role=user.role.value,
        email_verified=user.email_verified,
        preferences=user.preferences.model_dump() if user.preferences else {},
        usage_stats=user.usage_stats.model_dump() if user.usage_stats else {},
        created_at=user.created_at,
        last_login=user.last_login,
    )


def _token_response(auth: AuthService, user: User) -> TokenResponse:
    access_token, expires_in = auth.create_access_token(user.id, user.role.value)
    refresh_token = auth.create_refresh_token(user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )


# ── Registration ──

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    req: RegisterRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Register a new user account."""
    try:
        user = await auth.create_user(
            email=req.email,
            username=req.username,
            password=req.password,
            full_name=req.full_name,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    # Send verification email (non-blocking, best-effort)
    if user.verification_token:
        try:
            email_service.send_verification_email(user.email, user.verification_token)
        except Exception as e:
            logger.warning(f"Failed to send verification email: {e}")

    return _user_response(user)


# ── Login ──

@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Authenticate with email and password."""
    user = await auth.get_user_by_email(req.email)
    if not user or not auth.verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    await auth.update_last_login(user.id)
    return _token_response(auth, user)


# ── Refresh ──

@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    req: RefreshTokenRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Get a new access token using a refresh token."""
    payload = auth.decode_token(req.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user = await auth.get_user_by_id(payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return _token_response(auth, user)


# ── Profile ──

@router.get("/me", response_model=UserResponse)
async def get_profile(user: User = Depends(get_current_user)):
    """Get current user profile."""
    return _user_response(user)


@router.put("/me", response_model=UserResponse)
async def update_profile(
    req: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
):
    """Update current user profile."""
    updates = {}
    if req.full_name is not None:
        updates["full_name"] = req.full_name
    if req.username is not None:
        existing = await auth.get_user_by_username(req.username)
        if existing and existing.id != user.id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")
        updates["username"] = req.username
    if req.preferences is not None:
        updates["preferences"] = req.preferences

    if not updates:
        return _user_response(user)

    updated = await auth.update_profile(user.id, updates)
    return _user_response(updated)


@router.post("/me/change-password", response_model=MessageResponse)
async def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
):
    """Change current user's password."""
    success = await auth.change_password(user.id, req.current_password, req.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    return MessageResponse(message="Password changed successfully")


# ── Email Verification ──

@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: str,
    auth: AuthService = Depends(get_auth_service),
):
    """Verify email address with the token sent via email."""
    success = await auth.verify_email(token)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token",
        )
    return MessageResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    user: User = Depends(get_current_user),
    auth: AuthService = Depends(get_auth_service),
):
    """Resend email verification link."""
    if user.email_verified:
        return MessageResponse(message="Email already verified")

    token = auth.generate_verification_token()
    await auth.update_profile(user.id, {"verification_token": token})
    email_service.send_verification_email(user.email, token)
    return MessageResponse(message="Verification email sent")


# ── Password Reset ──

@router.post("/password-reset", response_model=MessageResponse)
async def request_password_reset(
    req: PasswordResetRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Request a password reset email."""
    token = await auth.set_reset_token(req.email)
    if token:
        email_service.send_password_reset_email(req.email, token)
    # Always return success to prevent email enumeration
    return MessageResponse(message="If the email exists, a reset link has been sent")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    req: PasswordResetConfirm,
    auth: AuthService = Depends(get_auth_service),
):
    """Reset password using the token from the email."""
    success = await auth.reset_password(req.token, req.new_password)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    return MessageResponse(message="Password reset successfully")


# ── Google OAuth ──

@router.post("/google", response_model=TokenResponse)
async def google_auth(
    req: GoogleAuthRequest,
    auth: AuthService = Depends(get_auth_service),
):
    """Authenticate or register via Google OAuth."""
    try:
        google_user = await exchange_google_code(req.code)
    except GoogleOAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    google_id = google_user.get("id")
    google_email = google_user.get("email", "").lower()
    google_name = google_user.get("name", "")
    google_picture = google_user.get("picture")

    if not google_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account has no email",
        )

    # Check if user exists by OAuth ID
    user = await auth.get_user_by_oauth("google", google_id)

    if not user:
        # Check if email already registered (link accounts)
        user = await auth.get_user_by_email(google_email)
        if user:
            # Link Google to existing account
            await auth.update_profile(user.id, {
                "oauth_provider": "google",
                "oauth_id": google_id,
                "email_verified": True,
                "avatar_url": google_picture or user.avatar_url,
            })
        else:
            # Create new user from Google
            username = google_email.split("@")[0]
            # Ensure unique username
            existing = await auth.get_user_by_username(username)
            if existing:
                username = f"{username}_{secrets.token_hex(3)}"

            user = await auth.create_user(
                email=google_email,
                username=username,
                password=secrets.token_hex(32),  # random password (won't be used)
                full_name=google_name,
                oauth_provider="google",
                oauth_id=google_id,
                email_verified=True,
            )
            if google_picture:
                await auth.update_profile(user.id, {"avatar_url": google_picture})

    await auth.update_last_login(user.id)
    return _token_response(auth, user)
