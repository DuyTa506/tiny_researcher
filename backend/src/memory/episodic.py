"""
EpisodicMemory - Remembers past research sessions.

Like human episodic memory:
- "Last time we researched transformers, we found these papers useful"
- "User preferred arXiv over HuggingFace for this topic"
- "This query pattern led to good results"
"""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class SessionOutcome(str, Enum):
    """How did the session go?"""
    SUCCESS = "success"      # User was satisfied
    PARTIAL = "partial"      # Some useful results
    FAILED = "failed"        # No useful results
    ABANDONED = "abandoned"  # User cancelled


@dataclass
class ResearchEpisode:
    """A single research session memory."""
    episode_id: str
    user_id: str

    # What was researched
    topic: str
    original_query: str
    refined_query: str = ""  # After clarification

    # What happened
    papers_found: int = 0
    relevant_papers: int = 0
    high_relevance_papers: int = 0
    clusters_created: int = 0

    # What the user did
    clarification_provided: str = ""  # User's answer to clarifying questions
    edits_made: List[str] = field(default_factory=list)  # Plan edits

    # Outcome
    outcome: SessionOutcome = SessionOutcome.SUCCESS
    user_feedback: str = ""  # Optional feedback
    useful_papers: List[str] = field(default_factory=list)  # Paper IDs user found useful

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    duration_seconds: float = 0.0

    # Context for future
    sources_used: List[str] = field(default_factory=list)
    keywords_effective: List[str] = field(default_factory=list)
    keywords_ineffective: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["outcome"] = self.outcome.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ResearchEpisode":
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["outcome"] = SessionOutcome(data["outcome"])
        return cls(**data)

    def summary(self) -> str:
        """Brief summary for context."""
        return (
            f"[{self.created_at.strftime('%Y-%m-%d')}] "
            f"'{self.topic}' - {self.relevant_papers} relevant papers, "
            f"outcome: {self.outcome.value}"
        )


class EpisodicMemory:
    """
    Stores and retrieves past research sessions.

    Enables:
    - "Find similar to what we found last time"
    - "Use the same sources that worked before"
    - Learning from past successes/failures
    """

    EPISODE_TTL = 86400 * 30  # 30 days
    MAX_EPISODES_PER_USER = 50

    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self, redis_url: str = "redis://localhost:6379/0"):
        """Connect to Redis."""
        self.redis = redis.from_url(redis_url, decode_responses=True)
        logger.info("EpisodicMemory connected to Redis")

    async def close(self):
        """Close connection."""
        if self.redis:
            await self.redis.close()

    def _user_key(self, user_id: str) -> str:
        return f"episodic:{user_id}"

    def _episode_key(self, episode_id: str) -> str:
        return f"episode:{episode_id}"

    async def save_episode(self, episode: ResearchEpisode):
        """Save a research episode."""
        if not self.redis:
            logger.warning("Redis not connected, cannot save episode")
            return

        # Save the episode
        episode_key = self._episode_key(episode.episode_id)
        await self.redis.setex(
            episode_key,
            self.EPISODE_TTL,
            json.dumps(episode.to_dict())
        )

        # Add to user's episode list
        user_key = self._user_key(episode.user_id)
        await self.redis.lpush(user_key, episode.episode_id)
        await self.redis.ltrim(user_key, 0, self.MAX_EPISODES_PER_USER - 1)
        await self.redis.expire(user_key, self.EPISODE_TTL)

        logger.debug(f"Saved episode {episode.episode_id} for user {episode.user_id}")

    async def get_episode(self, episode_id: str) -> Optional[ResearchEpisode]:
        """Get a specific episode."""
        if not self.redis:
            return None

        data = await self.redis.get(self._episode_key(episode_id))
        if data:
            return ResearchEpisode.from_dict(json.loads(data))
        return None

    async def get_user_episodes(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[ResearchEpisode]:
        """Get recent episodes for a user."""
        if not self.redis:
            return []

        user_key = self._user_key(user_id)
        episode_ids = await self.redis.lrange(user_key, 0, limit - 1)

        episodes = []
        for eid in episode_ids:
            episode = await self.get_episode(eid)
            if episode:
                episodes.append(episode)

        return episodes

    async def find_similar_episodes(
        self,
        user_id: str,
        topic: str,
        limit: int = 3
    ) -> List[ResearchEpisode]:
        """
        Find past episodes similar to current topic.

        Simple keyword matching for now. Could use vector similarity later.
        """
        episodes = await self.get_user_episodes(user_id, limit=20)

        # Simple keyword matching
        topic_words = set(topic.lower().split())
        scored = []

        for ep in episodes:
            ep_words = set(ep.topic.lower().split())
            overlap = len(topic_words & ep_words)
            if overlap > 0:
                scored.append((overlap, ep))

        # Sort by overlap and return top matches
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:limit]]

    async def get_effective_sources(
        self,
        user_id: str,
        topic: str
    ) -> List[str]:
        """
        Get sources that worked well for similar topics.
        """
        similar = await self.find_similar_episodes(user_id, topic, limit=5)

        # Count source effectiveness
        source_scores: Dict[str, int] = {}
        for ep in similar:
            if ep.outcome in [SessionOutcome.SUCCESS, SessionOutcome.PARTIAL]:
                for source in ep.sources_used:
                    source_scores[source] = source_scores.get(source, 0) + 1

        # Sort by score
        sorted_sources = sorted(
            source_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [s for s, _ in sorted_sources]

    async def get_effective_keywords(
        self,
        user_id: str,
        topic: str
    ) -> tuple[List[str], List[str]]:
        """
        Get keywords that worked/didn't work for similar topics.

        Returns: (effective_keywords, ineffective_keywords)
        """
        similar = await self.find_similar_episodes(user_id, topic, limit=5)

        effective = []
        ineffective = []

        for ep in similar:
            effective.extend(ep.keywords_effective)
            ineffective.extend(ep.keywords_ineffective)

        return list(set(effective)), list(set(ineffective))

    async def get_context_for_planning(
        self,
        user_id: str,
        topic: str
    ) -> Dict[str, Any]:
        """
        Get relevant context from past episodes for planning.

        Returns a dict that can be injected into the planner.
        """
        similar = await self.find_similar_episodes(user_id, topic, limit=3)

        if not similar:
            return {}

        context = {
            "similar_past_sessions": [ep.summary() for ep in similar],
            "recommended_sources": await self.get_effective_sources(user_id, topic),
        }

        effective, ineffective = await self.get_effective_keywords(user_id, topic)
        if effective:
            context["keywords_that_worked"] = effective
        if ineffective:
            context["keywords_to_avoid"] = ineffective

        return context
