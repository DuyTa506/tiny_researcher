"""
Google OAuth handler.

Exchanges authorization code for user info via Google's token and userinfo endpoints.
"""

import logging
from typing import Optional
import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleOAuthError(Exception):
    pass


async def exchange_google_code(code: str) -> dict:
    """
    Exchange an authorization code for Google user info.

    Returns dict with keys: id, email, name, picture, verified_email
    Raises GoogleOAuthError on failure.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise GoogleOAuthError("Google OAuth not configured")

    async with httpx.AsyncClient() as client:
        # Step 1: Exchange code for access token
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

        if token_resp.status_code != 200:
            logger.error(f"Google token exchange failed: {token_resp.text}")
            raise GoogleOAuthError("Failed to exchange authorization code")

        token_data = token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise GoogleOAuthError("No access token in response")

        # Step 2: Fetch user info
        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

        if userinfo_resp.status_code != 200:
            logger.error(f"Google userinfo failed: {userinfo_resp.text}")
            raise GoogleOAuthError("Failed to fetch user info")

        return userinfo_resp.json()
