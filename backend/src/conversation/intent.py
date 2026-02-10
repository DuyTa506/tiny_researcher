"""
IntentClassifier - Simple, multilingual intent detection.

Simplified to 5 intents to reduce LLM hallucination risk.
Works with any language via keyword matching + LLM fallback.
"""

import logging
import re
from typing import Optional, Set, List
from enum import Enum
from dataclasses import dataclass, field

from src.adapters.llm import LLMClientInterface

logger = logging.getLogger(__name__)


class UserIntent(str, Enum):
    """Simplified user intents - 6 categories."""
    CONFIRM = "confirm"      # User approves (yes, ok, proceed, đồng ý, 好的)
    CANCEL = "cancel"        # User rejects (no, cancel, hủy, 不要)
    EDIT = "edit"            # User wants to modify (add, remove, change)
    NEW_TOPIC = "new_topic"  # User provides research topic
    CHAT = "chat"            # Casual conversation, greetings, questions about the agent
    OTHER = "other"          # Unclear


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: UserIntent
    confidence: float
    edit_text: str  # For EDIT intent, the modification request
    original_message: str
    extracted_urls: List[str] = field(default_factory=list)  # URLs found in message


# URL regex pattern
_URL_PATTERN = re.compile(
    r'https?://[^\s<>"\')\]]+',
    re.IGNORECASE
)


# Multilingual keyword sets (extensible)
CONFIRM_KEYWORDS: Set[str] = {
    # English - single words
    "yes", "yeah", "yep", "ok", "okay", "sure", "proceed", "go",
    "approved", "approve", "confirm", "start", "begin", "run", "execute",
    "good", "fine", "great", "perfect", "lgtm", "alright", "right",
    "absolutely", "definitely", "certainly", "affirmative", "y",
    # Vietnamese
    "có", "đồng ý", "ok", "được", "tiếp tục", "chạy", "bắt đầu", "thực hiện",
    # Chinese
    "好", "好的", "可以", "行", "确认", "开始",
}

# Phrases that indicate confirmation (checked separately)
CONFIRM_PHRASES: Set[str] = {
    "do it", "let's go", "let's do it", "let do it", "go ahead",
    "go for it", "sounds good", "looks good", "that works",
    "make it so", "ship it", "let's start", "let's begin",
    "i agree", "i approve", "thats fine", "that's fine",
}

CANCEL_KEYWORDS: Set[str] = {
    # English
    "no", "nope", "nah", "cancel", "stop", "abort", "quit", "exit",
    "nevermind", "forget", "don't", "reject",
    # Vietnamese
    "không", "hủy", "dừng", "thôi", "bỏ", "hủy bỏ",
    # Chinese
    "不", "不要", "取消", "停止",
}

# Casual/chat indicators - greetings, questions about the agent, small talk
CHAT_KEYWORDS: Set[str] = {
    # English greetings
    "hi", "hello", "hey", "howdy", "sup",
    # Vietnamese greetings
    "chào", "xin",
    # Chinese greetings
    "你好", "嗨",
}

CHAT_PHRASES: Set[str] = {
    # English
    "what is your name", "what's your name", "who are you", "what are you",
    "how are you", "what can you do", "help me", "thank you", "thanks",
    "good morning", "good afternoon", "good evening", "good night",
    # Vietnamese
    "tên là gì", "mày là gì", "mày là ai", "bạn là ai", "bạn tên gì",
    "bạn là gì", "giúp tôi", "cảm ơn", "cám ơn", "làm gì được",
    "bạn có thể làm gì", "chào bạn", "xin chào",
    # Chinese
    "你叫什么", "你是谁", "谢谢",
}


class IntentClassifier:
    """
    Simple intent classifier for multilingual support.

    Strategy:
    1. Keyword matching (fast, no LLM)
    2. LLM fallback for ambiguous cases
    """

    def __init__(self, llm_client: Optional[LLMClientInterface] = None):
        self.llm = llm_client

    def _extract_urls(self, message: str) -> List[str]:
        """Extract URLs from message text."""
        return _URL_PATTERN.findall(message)

    def classify(self, message: str) -> IntentResult:
        """
        Classify user intent from message.

        Simple keyword-based classification.
        Also extracts URLs found in the message.
        """
        # Extract URLs first
        extracted_urls = self._extract_urls(message)

        message_clean = message.strip().lower()
        words = set(message_clean.split())

        # Check CONFIRM - keywords and phrases
        if words & CONFIRM_KEYWORDS or message_clean in CONFIRM_KEYWORDS:
            return IntentResult(
                intent=UserIntent.CONFIRM,
                confidence=0.9,
                edit_text="",
                original_message=message,
                extracted_urls=extracted_urls
            )

        # Check CONFIRM phrases (multi-word expressions)
        for phrase in CONFIRM_PHRASES:
            if phrase in message_clean:
                return IntentResult(
                    intent=UserIntent.CONFIRM,
                    confidence=0.85,
                    edit_text="",
                    original_message=message,
                    extracted_urls=extracted_urls
                )

        # Check CANCEL
        if words & CANCEL_KEYWORDS or message_clean in CANCEL_KEYWORDS:
            return IntentResult(
                intent=UserIntent.CANCEL,
                confidence=0.9,
                edit_text="",
                original_message=message,
                extracted_urls=extracted_urls
            )

        # Check EDIT (has modification keywords)
        edit_indicators = {"add", "remove", "delete", "change", "modify", "update",
                          "thêm", "xóa", "sửa", "đổi",  # Vietnamese
                          "添加", "删除", "修改"}  # Chinese
        if words & edit_indicators:
            return IntentResult(
                intent=UserIntent.EDIT,
                confidence=0.8,
                edit_text=message,
                original_message=message,
                extracted_urls=extracted_urls
            )

        # Check CHAT - greetings, questions about the agent, small talk
        if words & CHAT_KEYWORDS:
            return IntentResult(
                intent=UserIntent.CHAT,
                confidence=0.85,
                edit_text="",
                original_message=message,
                extracted_urls=extracted_urls
            )

        # Check CHAT phrases (multi-word)
        for phrase in CHAT_PHRASES:
            if phrase in message_clean:
                return IntentResult(
                    intent=UserIntent.CHAT,
                    confidence=0.9,
                    edit_text="",
                    original_message=message,
                    extracted_urls=extracted_urls
                )

        # If message is long enough, assume it's a new topic
        if len(message_clean) > 5 and len(words) >= 2:
            return IntentResult(
                intent=UserIntent.NEW_TOPIC,
                confidence=0.7,
                edit_text="",
                original_message=message,
                extracted_urls=extracted_urls
            )

        # Fallback
        return IntentResult(
            intent=UserIntent.OTHER,
            confidence=0.5,
            edit_text="",
            original_message=message,
            extracted_urls=extracted_urls
        )

    async def classify_with_llm(
        self,
        message: str,
        context: str = ""
    ) -> IntentResult:
        """
        Use LLM for intent classification.

        Args:
            message: User message
            context: Optional context about current state (e.g., "User was asked to confirm a plan")
        """
        if not self.llm:
            return self.classify(message)

        try:
            context_hint = f"\nContext: {context}" if context else ""
            prompt = f"""Classify user intent. Choose ONE:
- confirm: User agrees, approves, or wants to proceed
- cancel: User rejects, stops, or wants to abort
- edit: User wants to modify or change something
- new_topic: User provides a NEW RESEARCH TOPIC to investigate (must be an academic/scientific topic)
- chat: User is making casual conversation, greeting, asking about you, asking for help, or saying something NOT related to academic research
- other: Unclear
{context_hint}
Message: "{message}"

IMPORTANT: Only classify as "new_topic" if the message is clearly a research/academic topic the user wants to investigate. Greetings, questions about the assistant, small talk, and general questions should be "chat".

Reply with just the intent word (confirm/cancel/edit/new_topic/chat/other):"""

            response = await self.llm.generate(prompt)
            intent_str = response.strip().lower().split()[0]  # Take first word only

            # Map to enum
            intent_map = {
                "confirm": UserIntent.CONFIRM,
                "cancel": UserIntent.CANCEL,
                "edit": UserIntent.EDIT,
                "new_topic": UserIntent.NEW_TOPIC,
                "chat": UserIntent.CHAT,
                "other": UserIntent.OTHER,
            }

            intent = intent_map.get(intent_str, UserIntent.OTHER)

            return IntentResult(
                intent=intent,
                confidence=0.9,
                edit_text=message if intent == UserIntent.EDIT else "",
                original_message=message,
                extracted_urls=self._extract_urls(message)
            )

        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
            # Fallback to keyword matching
            return self.classify(message)

    def is_confirm(self, message: str) -> bool:
        """Quick check if message is confirmation."""
        return self.classify(message).intent == UserIntent.CONFIRM

    def is_cancel(self, message: str) -> bool:
        """Quick check if message is cancellation."""
        return self.classify(message).intent == UserIntent.CANCEL

    def is_edit(self, message: str) -> bool:
        """Quick check if message is edit request."""
        return self.classify(message).intent == UserIntent.EDIT
