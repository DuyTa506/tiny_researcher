"""
Authentication service.

Handles JWT generation/validation, password hashing, and token management.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt
import jwt
import logging

from src.core.config import settings
from src.core.models import User, UserRole, UserPreferences, UserUsageStats
from src.core.database import get_database, USERS_COLLECTION
from bson import ObjectId

logger = logging.getLogger(__name__)


class AuthService:
    """Handles authentication logic."""

    @property
    def collection(self):
        return get_database()[USERS_COLLECTION]

    # ── Password ──

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))

    # ── JWT ──

    @staticmethod
    def create_access_token(user_id: str, role: str) -> Tuple[str, int]:
        """Returns (token, expires_in_seconds)."""
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        expire = datetime.now(timezone.utc) + expires_delta
        payload = {
            "sub": user_id,
            "role": role,
            "type": "access",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )
        return token, int(expires_delta.total_seconds())

    @staticmethod
    def create_refresh_token(user_id: str) -> str:
        expires_delta = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        expire = datetime.now(timezone.utc) + expires_delta
        payload = {
            "sub": user_id,
            "type": "refresh",
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "jti": secrets.token_hex(16),
        }
        return jwt.encode(
            payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate a JWT. Returns payload or None."""
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug(f"Invalid token: {e}")
            return None

    # ── Tokens for email flows ──

    @staticmethod
    def generate_verification_token() -> str:
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_reset_token() -> str:
        return secrets.token_urlsafe(32)

    # ── User CRUD ──

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        doc = await self.collection.find_one({"_id": ObjectId(user_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
            return User(**doc)
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        doc = await self.collection.find_one({"email": email.lower()})
        if doc:
            doc["_id"] = str(doc["_id"])
            return User(**doc)
        return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        doc = await self.collection.find_one({"username": username})
        if doc:
            doc["_id"] = str(doc["_id"])
            return User(**doc)
        return None

    async def get_user_by_oauth(self, provider: str, oauth_id: str) -> Optional[User]:
        doc = await self.collection.find_one(
            {
                "oauth_provider": provider,
                "oauth_id": oauth_id,
            }
        )
        if doc:
            doc["_id"] = str(doc["_id"])
            return User(**doc)
        return None

    async def create_user(
        self,
        email: str,
        username: str,
        password: str,
        full_name: Optional[str] = None,
        oauth_provider: Optional[str] = None,
        oauth_id: Optional[str] = None,
        email_verified: bool = False,
    ) -> User:
        """Create a new user. Raises ValueError if email/username taken."""
        email = email.lower().strip()

        existing = await self.get_user_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        existing = await self.get_user_by_username(username)
        if existing:
            raise ValueError("Username already taken")

        verification_token = (
            self.generate_verification_token() if not email_verified else None
        )

        user = User(
            email=email,
            username=username,
            password_hash=self.hash_password(password) if password else "",
            full_name=full_name,
            email_verified=email_verified,
            verification_token=verification_token,
            oauth_provider=oauth_provider,
            oauth_id=oauth_id,
            preferences=UserPreferences(),
            usage_stats=UserUsageStats(),
        )

        doc = user.model_dump(exclude={"id"}, by_alias=True)
        result = await self.collection.insert_one(doc)
        user.id = str(result.inserted_id)
        return user

    async def verify_email(self, token: str) -> bool:
        """Mark user as verified if token matches."""
        result = await self.collection.update_one(
            {"verification_token": token, "email_verified": False},
            {
                "$set": {
                    "email_verified": True,
                    "verification_token": None,
                    "updated_at": datetime.now(),
                }
            },
        )
        return result.modified_count > 0

    async def set_reset_token(self, email: str) -> Optional[str]:
        """Generate and store a password reset token. Returns token or None."""
        user = await self.get_user_by_email(email)
        if not user:
            return None

        token = self.generate_reset_token()
        expires = datetime.now() + timedelta(hours=1)
        await self.collection.update_one(
            {"_id": ObjectId(user.id)},
            {
                "$set": {
                    "reset_token": token,
                    "reset_token_expires": expires,
                    "updated_at": datetime.now(),
                }
            },
        )
        return token

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using a valid reset token."""
        doc = await self.collection.find_one(
            {
                "reset_token": token,
                "reset_token_expires": {"$gt": datetime.now()},
            }
        )
        if not doc:
            return False

        await self.collection.update_one(
            {"_id": doc["_id"]},
            {
                "$set": {
                    "password_hash": self.hash_password(new_password),
                    "reset_token": None,
                    "reset_token_expires": None,
                    "updated_at": datetime.now(),
                }
            },
        )
        return True

    async def update_last_login(self, user_id: str):
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login": datetime.now()}},
        )

    async def update_profile(self, user_id: str, updates: dict) -> Optional[User]:
        updates["updated_at"] = datetime.now()
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": updates},
        )
        return await self.get_user_by_id(user_id)

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> bool:
        user = await self.get_user_by_id(user_id)
        if not user or not self.verify_password(current_password, user.password_hash):
            return False
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {
                "$set": {
                    "password_hash": self.hash_password(new_password),
                    "updated_at": datetime.now(),
                }
            },
        )
        return True

    async def increment_stat(self, user_id: str, field: str, amount: int = 1):
        """Increment a usage stat field (e.g. 'usage_stats.papers_collected')."""
        await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {f"usage_stats.{field}": amount}},
        )

    async def ensure_indexes(self):
        """Create indexes for the users collection."""
        await self.collection.create_index("email", unique=True)
        await self.collection.create_index("username", unique=True)
        await self.collection.create_index("verification_token", sparse=True)
        await self.collection.create_index("reset_token", sparse=True)
        await self.collection.create_index(
            [("oauth_provider", 1), ("oauth_id", 1)], sparse=True
        )
        logger.info("User indexes created")
