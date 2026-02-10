"""
UserPreferences - Procedural memory for learned user patterns.

Like human procedural memory:
- "This user prefers Vietnamese output"
- "This user always wants more than 20 papers"
- "This user likes detailed reports"
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict

import redis.asyncio as redis

logger = logging.getLogger(__name__)


@dataclass
class UserPreferences:
    """User preferences learned over time."""

    user_id: str

    # Language preferences
    preferred_language: str = "en"  # Output language
    input_languages: List[str] = field(default_factory=lambda: ["en"])

    # Research preferences
    preferred_sources: List[str] = field(default_factory=lambda: ["arxiv"])
    min_papers: int = 10
    max_papers: int = 50
    relevance_threshold: float = 7.0  # Minimum relevance score

    # Output preferences
    report_style: str = "detailed"  # "brief", "detailed", "academic"
    include_abstracts: bool = True
    include_clusters: bool = True

    # Workflow preferences
    skip_clarification: bool = False  # User prefers direct planning
    auto_approve_simple: bool = False  # Auto-approve simple queries

    # Learned patterns (updated from behavior)
    common_topics: List[str] = field(default_factory=list)
    favorite_keywords: List[str] = field(default_factory=list)

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    interaction_count: int = 0

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "UserPreferences":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)

    def update_from_behavior(
        self,
        topic: str,
        language_used: str,
        sources_used: List[str],
        papers_requested: Optional[int] = None,
    ):
        """Learn from user behavior."""
        self.interaction_count += 1
        self.updated_at = datetime.now()

        # Track common topics
        topic_words = topic.lower().split()[:3]  # First 3 words
        topic_key = " ".join(topic_words)
        if topic_key not in self.common_topics:
            self.common_topics.append(topic_key)
            self.common_topics = self.common_topics[-20:]  # Keep last 20

        # Track language
        if language_used and language_used not in self.input_languages:
            self.input_languages.append(language_used)

        # Track sources
        for source in sources_used:
            if source not in self.preferred_sources:
                self.preferred_sources.append(source)

        # Track paper count preferences
        if papers_requested and papers_requested > self.max_papers:
            self.max_papers = min(papers_requested, 100)


class PreferencesStore:
    """
    Stores and retrieves user preferences.

    Implements procedural memory - learning user patterns over time.
    """

    PREFERENCES_TTL = 86400 * 90  # 90 days

    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        self._cache: Dict[str, UserPreferences] = {}  # In-memory cache

    async def connect(self, redis_url: str = "redis://localhost:6379/0"):
        """Connect to Redis."""
        self.redis = redis.from_url(redis_url, decode_responses=True)
        logger.info("PreferencesStore connected to Redis")

    async def close(self):
        """Close connection."""
        if self.redis:
            await self.redis.close()

    def _key(self, user_id: str) -> str:
        return f"preferences:{user_id}"

    async def get(self, user_id: str) -> UserPreferences:
        """Get user preferences, creating default if not exists."""
        # Check cache
        if user_id in self._cache:
            return self._cache[user_id]

        # Load from Redis
        if self.redis:
            data = await self.redis.get(self._key(user_id))
            if data:
                prefs = UserPreferences.from_dict(json.loads(data))
                self._cache[user_id] = prefs
                return prefs

        # Create default
        prefs = UserPreferences(user_id=user_id)
        self._cache[user_id] = prefs
        return prefs

    async def save(self, prefs: UserPreferences):
        """Save user preferences."""
        self._cache[prefs.user_id] = prefs

        if self.redis:
            await self.redis.setex(
                self._key(prefs.user_id),
                self.PREFERENCES_TTL,
                json.dumps(prefs.to_dict()),
            )
            logger.debug(f"Saved preferences for user {prefs.user_id}")

    async def update_from_interaction(
        self,
        user_id: str,
        topic: str,
        language: str = "en",
        sources: List[str] = None,
        papers_count: int = None,
    ):
        """Update preferences based on user interaction."""
        prefs = await self.get(user_id)
        prefs.update_from_behavior(
            topic=topic,
            language_used=language,
            sources_used=sources or [],
            papers_requested=papers_count,
        )
        await self.save(prefs)

    async def detect_language(self, text: str) -> str:
        """Simple language detection based on characters."""
        # Vietnamese detection
        vietnamese_chars = set(
            "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
        )
        if any(c in vietnamese_chars for c in text.lower()):
            return "vi"

        # Chinese detection
        for char in text:
            if "\u4e00" <= char <= "\u9fff":
                return "zh"

        return "en"

    def get_planning_hints(self, prefs: UserPreferences) -> Dict[str, Any]:
        """Get hints for the planner based on preferences."""
        return {
            "preferred_sources": prefs.preferred_sources,
            "min_papers": prefs.min_papers,
            "max_papers": prefs.max_papers,
            "output_language": prefs.preferred_language,
            "common_topics": prefs.common_topics[-5:],  # Recent topics
        }
