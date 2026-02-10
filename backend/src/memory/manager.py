"""
MemoryManager - Unified interface for all memory types.

Coordinates:
- Working Memory: Current conversation (ConversationContext)
- Episodic Memory: Past research sessions
- Procedural Memory: User preferences and patterns

Semantic Memory is handled by the VectorStore separately.
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.memory.episodic import EpisodicMemory, ResearchEpisode, SessionOutcome
from src.memory.preferences import PreferencesStore, UserPreferences

logger = logging.getLogger(__name__)


@dataclass
class MemoryContext:
    """
    Combined context from all memory types for a query.

    Injected into planning/clarification for better responses.
    """

    # From episodic memory
    similar_sessions: List[str] = None  # Summaries of similar past sessions
    recommended_sources: List[str] = None
    keywords_effective: List[str] = None
    keywords_to_avoid: List[str] = None

    # From preferences
    preferred_language: str = "en"
    preferred_sources: List[str] = None
    min_papers: int = 10
    max_papers: int = 50

    # Derived insights
    user_experience_level: str = "new"  # "new", "regular", "expert"
    has_relevant_history: bool = False

    def to_prompt_context(self) -> str:
        """Format as context for LLM prompts."""
        lines = []

        if self.has_relevant_history and self.similar_sessions:
            lines.append("**Past relevant research:**")
            for session in self.similar_sessions[:3]:
                lines.append(f"  - {session}")

        if self.keywords_effective:
            lines.append(
                f"**Keywords that worked before:** {', '.join(self.keywords_effective[:5])}"
            )

        if self.keywords_to_avoid:
            lines.append(
                f"**Keywords to avoid:** {', '.join(self.keywords_to_avoid[:3])}"
            )

        if self.recommended_sources:
            lines.append(
                f"**Recommended sources:** {', '.join(self.recommended_sources)}"
            )

        return "\n".join(lines) if lines else ""


class MemoryManager:
    """
    Unified memory manager coordinating all memory types.

    Usage:
        memory = MemoryManager()
        await memory.connect()

        # Get context for planning
        context = await memory.get_context(user_id, topic)

        # Record a completed session
        await memory.record_session(episode)

        # Update preferences from behavior
        await memory.learn_from_interaction(user_id, ...)
    """

    def __init__(self):
        self.episodic = EpisodicMemory()
        self.preferences = PreferencesStore()
        self._connected = False

    async def connect(self, redis_url: str = "redis://localhost:6379/0"):
        """Connect all memory stores."""
        await self.episodic.connect(redis_url)
        await self.preferences.connect(redis_url)
        self._connected = True
        logger.info("MemoryManager connected")

    async def close(self):
        """Close all connections."""
        await self.episodic.close()
        await self.preferences.close()
        self._connected = False

    async def get_context(self, user_id: str, topic: str) -> MemoryContext:
        """
        Get combined context from all memory types for a topic.

        This is the main entry point for enriching planning/clarification.
        """
        context = MemoryContext()

        # Get user preferences
        prefs = await self.preferences.get(user_id)
        context.preferred_language = prefs.preferred_language
        context.preferred_sources = prefs.preferred_sources
        context.min_papers = prefs.min_papers
        context.max_papers = prefs.max_papers

        # Determine experience level
        if prefs.interaction_count == 0:
            context.user_experience_level = "new"
        elif prefs.interaction_count < 10:
            context.user_experience_level = "regular"
        else:
            context.user_experience_level = "expert"

        # Get episodic context
        episodic_context = await self.episodic.get_context_for_planning(user_id, topic)

        if episodic_context:
            context.has_relevant_history = True
            context.similar_sessions = episodic_context.get("similar_past_sessions", [])
            context.recommended_sources = episodic_context.get(
                "recommended_sources", []
            )
            context.keywords_effective = episodic_context.get(
                "keywords_that_worked", []
            )
            context.keywords_to_avoid = episodic_context.get("keywords_to_avoid", [])

        return context

    async def record_session(
        self,
        user_id: str,
        session_id: str,
        topic: str,
        original_query: str,
        refined_query: str = "",
        papers_found: int = 0,
        relevant_papers: int = 0,
        high_relevance_papers: int = 0,
        sources_used: List[str] = None,
        keywords_effective: List[str] = None,
        keywords_ineffective: List[str] = None,
        outcome: SessionOutcome = SessionOutcome.SUCCESS,
        duration_seconds: float = 0.0,
    ):
        """
        Record a completed research session to episodic memory.
        """
        episode = ResearchEpisode(
            episode_id=session_id,
            user_id=user_id,
            topic=topic,
            original_query=original_query,
            refined_query=refined_query,
            papers_found=papers_found,
            relevant_papers=relevant_papers,
            high_relevance_papers=high_relevance_papers,
            sources_used=sources_used or [],
            keywords_effective=keywords_effective or [],
            keywords_ineffective=keywords_ineffective or [],
            outcome=outcome,
            duration_seconds=duration_seconds,
        )

        await self.episodic.save_episode(episode)
        logger.info(f"Recorded session {session_id} for user {user_id}")

    async def learn_from_interaction(
        self,
        user_id: str,
        topic: str,
        language: str = "en",
        sources: List[str] = None,
        papers_count: int = None,
    ):
        """
        Update preferences based on user interaction.
        """
        await self.preferences.update_from_interaction(
            user_id=user_id,
            topic=topic,
            language=language,
            sources=sources,
            papers_count=papers_count,
        )

    async def get_preferences(self, user_id: str) -> UserPreferences:
        """Get user preferences."""
        return await self.preferences.get(user_id)

    async def update_preferences(self, user_id: str, **updates):
        """Update specific preference fields."""
        prefs = await self.preferences.get(user_id)

        for key, value in updates.items():
            if hasattr(prefs, key):
                setattr(prefs, key, value)

        await self.preferences.save(prefs)

    async def get_user_history_summary(self, user_id: str, limit: int = 5) -> List[str]:
        """Get summary of user's recent research history."""
        episodes = await self.episodic.get_user_episodes(user_id, limit=limit)
        return [ep.summary() for ep in episodes]

    async def should_skip_clarification(self, user_id: str, topic: str) -> bool:
        """
        Determine if we should skip clarification for this user/topic.

        Based on:
        - User preference
        - Similar past sessions (user knows what they want)
        """
        prefs = await self.preferences.get(user_id)

        # User explicitly wants to skip
        if prefs.skip_clarification:
            return True

        # Expert user with similar past sessions
        if prefs.interaction_count >= 10:
            similar = await self.episodic.find_similar_episodes(user_id, topic, limit=1)
            if similar and similar[0].outcome == SessionOutcome.SUCCESS:
                return True

        return False
