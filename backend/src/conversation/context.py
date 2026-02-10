"""
ConversationContext - Working memory for dialogue state.

Manages:
- Message history (recent N turns)
- Dialogue state machine
- Pending plan (awaiting approval)
- Link to research session
"""

import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

import redis.asyncio as redis

from src.planner.adaptive_planner import AdaptivePlan
from src.core.schema import ResearchRequest

logger = logging.getLogger(__name__)


class DialogueState(str, Enum):
    """States in the conversation flow."""
    IDLE = "idle"                    # No active research
    CLARIFYING = "clarifying"        # Asking clarifying questions (NEW)
    PLANNING = "planning"            # Generating plan
    REVIEWING = "reviewing"          # Plan ready, awaiting approval
    EDITING = "editing"              # User is editing the plan
    EXECUTING = "executing"          # Pipeline running
    COMPLETE = "complete"            # Research done, can ask follow-ups
    ERROR = "error"                  # Something went wrong


class MessageRole(str, Enum):
    """Who sent the message."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """A single message in the conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {})
        )


@dataclass
class ConversationContext:
    """
    Working memory for a conversation session.

    Tracks:
    - Message history
    - Current dialogue state
    - Pending plan (if any)
    - Research session link
    """
    conversation_id: str
    user_id: str = "default"  # For memory tracking
    state: DialogueState = DialogueState.IDLE
    messages: List[Message] = field(default_factory=list)

    # Current research context
    current_topic: Optional[str] = None
    current_request: Optional[ResearchRequest] = None
    research_session_id: Optional[str] = None

    # Pending plan awaiting approval
    pending_plan: Optional[AdaptivePlan] = None

    # Clarification context (for CLARIFYING state)
    pending_clarification: Optional[dict] = None  # Stores ClarificationResult as dict

    # User-provided URLs extracted from messages
    pending_urls: List[str] = field(default_factory=list)

    # Results after execution
    result_summary: Optional[str] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    # Config
    max_messages: int = 50  # Keep last N messages

    def add_message(self, role: MessageRole, content: str, metadata: dict = None):
        """Add a message to history."""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {}
        )
        self.messages.append(message)
        self.updated_at = datetime.now()

        # Trim old messages
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages:]

    def add_user_message(self, content: str):
        """Convenience method for user messages."""
        self.add_message(MessageRole.USER, content)

    def add_assistant_message(self, content: str):
        """Convenience method for assistant messages."""
        self.add_message(MessageRole.ASSISTANT, content)

    def add_system_message(self, content: str):
        """Convenience method for system messages."""
        self.add_message(MessageRole.SYSTEM, content)

    def get_recent_messages(self, n: int = 10) -> List[Message]:
        """Get last N messages."""
        return self.messages[-n:]

    def get_message_history_text(self, n: int = 10) -> str:
        """Get message history as formatted text."""
        messages = self.get_recent_messages(n)
        lines = []
        for msg in messages:
            prefix = {"user": "Human", "assistant": "Agent", "system": "System"}
            lines.append(f"{prefix[msg.role.value]}: {msg.content}")
        return "\n".join(lines)

    def transition_to(self, new_state: DialogueState):
        """Transition to a new state."""
        logger.info(f"Conversation {self.conversation_id}: {self.state.value} → {new_state.value}")
        self.state = new_state
        self.updated_at = datetime.now()

    def set_pending_plan(self, plan: AdaptivePlan, request: ResearchRequest):
        """Set a plan that's awaiting approval."""
        self.pending_plan = plan
        self.current_request = request
        self.current_topic = request.topic
        self.transition_to(DialogueState.REVIEWING)

    def clear_pending_plan(self):
        """Clear the pending plan after approval/rejection."""
        self.pending_plan = None

    def is_awaiting_approval(self) -> bool:
        """Check if we're waiting for user to approve a plan."""
        return self.state == DialogueState.REVIEWING and self.pending_plan is not None

    def to_dict(self) -> dict:
        """Serialize for storage."""
        return {
            "conversation_id": self.conversation_id,
            "state": self.state.value,
            "messages": [m.to_dict() for m in self.messages],
            "current_topic": self.current_topic,
            "research_session_id": self.research_session_id,
            "result_summary": self.result_summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            # Note: pending_plan and current_request not serialized (complex objects)
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConversationContext":
        """Deserialize from storage."""
        ctx = cls(
            conversation_id=data["conversation_id"],
            state=DialogueState(data["state"]),
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            current_topic=data.get("current_topic"),
            research_session_id=data.get("research_session_id"),
            result_summary=data.get("result_summary"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"])
        )
        return ctx


class ConversationStore:
    """
    Redis-based storage for conversation contexts.

    Provides:
    - Save/load conversation state
    - TTL-based expiration
    """

    CONVERSATION_TTL = 7200  # 2 hours

    def __init__(self):
        self.redis: Optional[redis.Redis] = None

    async def connect(self, redis_url: str = "redis://localhost:6379/0"):
        """Connect to Redis."""
        self.redis = redis.from_url(redis_url, decode_responses=True)
        logger.info("ConversationStore connected to Redis")

    async def close(self):
        """Close Redis connection."""
        if self.redis:
            await self.redis.close()

    def _key(self, conversation_id: str) -> str:
        return f"conversation:{conversation_id}"

    async def save(self, context: ConversationContext):
        """Save conversation context to Redis."""
        if not self.redis:
            logger.warning("Redis not connected, cannot save conversation")
            return

        key = self._key(context.conversation_id)
        data = json.dumps(context.to_dict())
        await self.redis.setex(key, self.CONVERSATION_TTL, data)
        logger.debug(f"Saved conversation {context.conversation_id}")

    async def load(self, conversation_id: str) -> Optional[ConversationContext]:
        """Load conversation context from Redis."""
        if not self.redis:
            logger.warning("Redis not connected, cannot load conversation")
            return None

        key = self._key(conversation_id)
        data = await self.redis.get(key)

        if not data:
            return None

        return ConversationContext.from_dict(json.loads(data))

    async def delete(self, conversation_id: str):
        """Delete a conversation."""
        if self.redis:
            await self.redis.delete(self._key(conversation_id))

    async def extend_ttl(self, conversation_id: str):
        """Extend the TTL of a conversation."""
        if self.redis:
            await self.redis.expire(self._key(conversation_id), self.CONVERSATION_TTL)

    async def list_all(self) -> list:
        """List all active conversation IDs and basic metadata."""
        if not self.redis:
            return []

        conversations = []
        async for key in self.redis.scan_iter(match="conversation:*"):
            conv_id = key.replace("conversation:", "")
            data = await self.redis.get(key)
            if data:
                parsed = json.loads(data)
                conversations.append({
                    "conversation_id": conv_id,
                    "state": parsed.get("state", "unknown"),
                    "current_topic": parsed.get("current_topic"),
                    "created_at": parsed.get("created_at"),
                    "user_id": parsed.get("user_id"),
                    "message_count": len(parsed.get("messages", [])),
                })
        return conversations
