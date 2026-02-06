"""
Memory Module - Human-like memory for the research agent.

Memory Types:
- Working Memory: Current conversation (via ConversationContext)
- Episodic Memory: Past research sessions
- Procedural Memory: User preferences and patterns
- Semantic Memory: Domain knowledge (via VectorStore, separate module)

Usage:
    from src.memory import MemoryManager

    memory = MemoryManager()
    await memory.connect()

    # Get context for planning
    context = await memory.get_context(user_id, topic)

    # Record completed session
    await memory.record_session(user_id, session_id, topic, ...)

    # Learn from interaction
    await memory.learn_from_interaction(user_id, topic, language, sources)
"""

from src.memory.manager import MemoryManager, MemoryContext
from src.memory.episodic import EpisodicMemory, ResearchEpisode, SessionOutcome
from src.memory.preferences import PreferencesStore, UserPreferences

__all__ = [
    "MemoryManager",
    "MemoryContext",
    "EpisodicMemory",
    "ResearchEpisode",
    "SessionOutcome",
    "PreferencesStore",
    "UserPreferences",
]
