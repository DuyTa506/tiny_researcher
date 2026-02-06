"""
Research Memory Manager

Centralized session memory for research workflows.
Implements hot (in-process) + warm (Redis) + cold (MongoDB) storage layers.
"""

import logging
import json
import uuid
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import redis.asyncio as aioredis

from src.core.models import Paper
from src.core.config import settings
from src.storage.repositories import PaperRepository

logger = logging.getLogger(__name__)


@dataclass
class ResearchSession:
    """
    Research session metadata.

    Tracks the current state of a research workflow including:
    - Papers collected/analyzed
    - Directions/clusters identified
    - Phase transitions
    """
    session_id: str
    topic: str
    created_at: datetime
    updated_at: datetime

    # Phase tracking
    current_phase: str = "idle"  # idle, planning, execution, analysis, synthesis, complete
    phases_completed: List[str] = field(default_factory=list)

    # Paper tracking
    total_papers: int = 0
    unique_papers: int = 0
    high_relevance_papers: int = 0

    # Metadata
    plan_id: Optional[str] = None
    report_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ResearchMemoryManager:
    """
    Centralized memory manager for research sessions.

    Architecture:
    - Hot layer (in-process): Current session state, paper registry
    - Warm layer (Redis): Session checkpoints, recent papers
    - Cold layer (MongoDB): Persistent storage

    Usage:
        memory = ResearchMemoryManager()
        await memory.connect()

        # Create session
        session_id = await memory.create_session("AI Research")

        # Register papers
        for paper in papers:
            await memory.register_paper(session_id, paper)

        # Checkpoint
        await memory.checkpoint(session_id, "analysis")

        # Restore
        session = await memory.restore_session(session_id)
    """

    SESSION_TTL = 86400  # 24 hours

    def __init__(
        self,
        redis_url: str = None,
        paper_repo: PaperRepository = None
    ):
        """
        Initialize memory manager.

        Args:
            redis_url: Redis connection URL
            paper_repo: MongoDB paper repository
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis: Optional[aioredis.Redis] = None
        self.paper_repo = paper_repo or PaperRepository()

        # Hot layer (in-process)
        self._sessions: Dict[str, ResearchSession] = {}
        self._paper_registry: Dict[str, List[Paper]] = {}  # session_id -> papers
        self._dedup_registry: Dict[str, set] = {}  # session_id -> set of arxiv_ids

    async def connect(self):
        """Connect to Redis (warm layer)."""
        try:
            self.redis = await aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=False  # We'll handle serialization
            )
            await self.redis.ping()
            logger.info("ResearchMemoryManager connected to Redis")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Warm layer disabled.")
            self.redis = None

    async def close(self):
        """Close connections."""
        if self.redis:
            await self.redis.close()

    async def create_session(self, topic: str, plan_id: str = None) -> str:
        """
        Create a new research session.

        Args:
            topic: Research topic
            plan_id: Optional plan ID

        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = ResearchSession(
            session_id=session_id,
            topic=topic,
            created_at=now,
            updated_at=now,
            plan_id=plan_id
        )

        # Store in hot layer
        self._sessions[session_id] = session
        self._paper_registry[session_id] = []
        self._dedup_registry[session_id] = set()

        # Store in warm layer
        if self.redis:
            await self._save_session_to_redis(session)

        logger.info(f"Created research session {session_id} for topic: {topic}")
        return session_id

    async def get_session(self, session_id: str) -> Optional[ResearchSession]:
        """
        Get session from memory (hot -> warm -> None).

        Args:
            session_id: Session ID

        Returns:
            ResearchSession or None
        """
        # Check hot layer
        if session_id in self._sessions:
            return self._sessions[session_id]

        # Check warm layer
        if self.redis:
            session = await self._load_session_from_redis(session_id)
            if session:
                # Promote to hot layer
                self._sessions[session_id] = session
                return session

        return None

    async def register_paper(
        self,
        session_id: str,
        paper: Paper,
        skip_dedup: bool = False
    ) -> bool:
        """
        Register a paper in the session.

        Args:
            session_id: Session ID
            paper: Paper to register
            skip_dedup: Skip deduplication check

        Returns:
            True if paper was added, False if duplicate
        """
        session = await self.get_session(session_id)
        if not session:
            logger.warning(f"Session {session_id} not found")
            return False

        # Deduplication
        if not skip_dedup:
            if session_id not in self._dedup_registry:
                self._dedup_registry[session_id] = set()

            dedup_key = paper.arxiv_id or paper.title
            if dedup_key in self._dedup_registry[session_id]:
                logger.debug(f"Duplicate paper: {paper.title[:50]}")
                return False

            self._dedup_registry[session_id].add(dedup_key)

        # Add to registry
        if session_id not in self._paper_registry:
            self._paper_registry[session_id] = []

        self._paper_registry[session_id].append(paper)

        # Update session stats
        session.total_papers = len(self._paper_registry[session_id])
        session.unique_papers = len(self._dedup_registry[session_id])
        if paper.relevance_score and paper.relevance_score >= 8.0:
            session.high_relevance_papers += 1
        session.updated_at = datetime.utcnow()

        logger.debug(f"Registered paper in session {session_id}: {paper.title[:50]}")
        return True

    async def get_papers(self, session_id: str) -> List[Paper]:
        """Get all papers for a session."""
        return self._paper_registry.get(session_id, [])

    async def transition_phase(self, session_id: str, new_phase: str):
        """
        Transition session to a new phase.

        Args:
            session_id: Session ID
            new_phase: New phase name
        """
        session = await self.get_session(session_id)
        if not session:
            return

        if session.current_phase not in session.phases_completed:
            session.phases_completed.append(session.current_phase)

        session.current_phase = new_phase
        session.updated_at = datetime.utcnow()

        logger.info(f"Session {session_id} transitioned to phase: {new_phase}")

        # Save checkpoint
        if self.redis:
            await self._save_session_to_redis(session)

    async def checkpoint(self, session_id: str, phase_id: str):
        """
        Create a checkpoint for the session.

        Args:
            session_id: Session ID
            phase_id: Phase identifier
        """
        session = await self.get_session(session_id)
        if not session:
            return

        papers = await self.get_papers(session_id)

        # Convert session to dict and handle datetime serialization
        session_dict = asdict(session)
        session_dict['created_at'] = session.created_at.isoformat()
        session_dict['updated_at'] = session.updated_at.isoformat()

        checkpoint_data = {
            "session": session_dict,
            "papers_count": len(papers),
            "phase_id": phase_id,
            "timestamp": datetime.utcnow().isoformat()
        }

        if self.redis:
            key = f"checkpoint:{session_id}:{phase_id}"
            await self.redis.setex(
                key,
                self.SESSION_TTL,
                json.dumps(checkpoint_data)
            )
            logger.info(f"Checkpoint saved for session {session_id} at phase {phase_id}")

    async def restore_from_checkpoint(
        self,
        session_id: str,
        phase_id: str
    ) -> Optional[ResearchSession]:
        """
        Restore session from a checkpoint.

        Args:
            session_id: Session ID
            phase_id: Phase identifier

        Returns:
            Restored session or None
        """
        if not self.redis:
            logger.warning("Redis not available, cannot restore checkpoint")
            return None

        try:
            key = f"checkpoint:{session_id}:{phase_id}"
            data = await self.redis.get(key)

            if not data:
                logger.warning(f"No checkpoint found for {session_id}:{phase_id}")
                return None

            checkpoint = json.loads(data)
            session_dict = checkpoint["session"]

            # Reconstruct session
            session = ResearchSession(
                session_id=session_dict["session_id"],
                topic=session_dict["topic"],
                created_at=datetime.fromisoformat(session_dict["created_at"]),
                updated_at=datetime.fromisoformat(session_dict["updated_at"]),
                current_phase=session_dict["current_phase"],
                phases_completed=session_dict["phases_completed"],
                total_papers=session_dict["total_papers"],
                unique_papers=session_dict["unique_papers"],
                high_relevance_papers=session_dict["high_relevance_papers"],
                plan_id=session_dict.get("plan_id"),
                report_id=session_dict.get("report_id"),
                metadata=session_dict.get("metadata", {})
            )

            # Promote to hot layer
            self._sessions[session_id] = session

            logger.info(f"Restored session {session_id} from checkpoint {phase_id}")
            return session

        except Exception as e:
            logger.error(f"Error restoring checkpoint: {e}")
            return None

    async def get_analysis_context(self, session_id: str) -> Dict[str, Any]:
        """
        Get analysis context for the session.

        Returns metadata useful for analysis like:
        - Total papers
        - Date distribution
        - Source distribution

        Args:
            session_id: Session ID

        Returns:
            Context dictionary
        """
        session = await self.get_session(session_id)
        if not session:
            return {}

        papers = await self.get_papers(session_id)

        # Calculate date distribution
        dates = [p.published_date for p in papers if p.published_date]
        date_range = {
            "earliest": min(dates) if dates else None,
            "latest": max(dates) if dates else None
        }

        # Calculate source distribution
        sources = {}
        for paper in papers:
            source = "arxiv" if paper.arxiv_id else "other"
            sources[source] = sources.get(source, 0) + 1

        return {
            "session_id": session_id,
            "topic": session.topic,
            "total_papers": session.total_papers,
            "unique_papers": session.unique_papers,
            "high_relevance_papers": session.high_relevance_papers,
            "date_range": date_range,
            "sources": sources,
            "current_phase": session.current_phase
        }

    async def _save_session_to_redis(self, session: ResearchSession):
        """Save session to Redis."""
        if not self.redis:
            return

        try:
            key = f"session:{session.session_id}"
            data = json.dumps(asdict(session), default=str)
            await self.redis.setex(key, self.SESSION_TTL, data)
        except Exception as e:
            logger.error(f"Error saving session to Redis: {e}")

    async def _load_session_from_redis(self, session_id: str) -> Optional[ResearchSession]:
        """Load session from Redis."""
        if not self.redis:
            return None

        try:
            key = f"session:{session_id}"
            data = await self.redis.get(key)

            if not data:
                return None

            session_dict = json.loads(data)

            return ResearchSession(
                session_id=session_dict["session_id"],
                topic=session_dict["topic"],
                created_at=datetime.fromisoformat(session_dict["created_at"]),
                updated_at=datetime.fromisoformat(session_dict["updated_at"]),
                current_phase=session_dict["current_phase"],
                phases_completed=session_dict["phases_completed"],
                total_papers=session_dict["total_papers"],
                unique_papers=session_dict["unique_papers"],
                high_relevance_papers=session_dict["high_relevance_papers"],
                plan_id=session_dict.get("plan_id"),
                report_id=session_dict.get("report_id"),
                metadata=session_dict.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Error loading session from Redis: {e}")
            return None
