"""
Conversation module for Phase 4: Conversational Interface.

Humanoid design:
- 5 intents: CONFIRM, CANCEL, EDIT, NEW_TOPIC, OTHER
- 2 query types: QUICK, FULL
- CLARIFYING state: Ask questions before planning (like a real researcher)
- Works with any language (Vietnamese, English, Chinese, etc.)
"""

from src.conversation.context import (
    ConversationContext,
    DialogueState,
    Message,
    MessageRole
)
from src.conversation.intent import IntentClassifier, UserIntent
from src.conversation.clarifier import QueryClarifier, ClarificationResult
from src.conversation.dialogue import DialogueManager

__all__ = [
    "ConversationContext",
    "DialogueState",
    "Message",
    "MessageRole",
    "IntentClassifier",
    "UserIntent",
    "QueryClarifier",
    "ClarificationResult",
    "DialogueManager"
]
