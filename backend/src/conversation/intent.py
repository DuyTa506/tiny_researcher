"""
IntentClassifier - Simple, multilingual intent detection.

Simplified to 5 intents to reduce LLM hallucination risk.
Works with any language via keyword matching + LLM fallback.
"""

import logging
from typing import Optional, Set
from enum import Enum
from dataclasses import dataclass

from src.adapters.llm import LLMClientInterface

logger = logging.getLogger(__name__)


class UserIntent(str, Enum):
    """Simplified user intents - only 5 categories."""
    CONFIRM = "confirm"      # User approves (yes, ok, proceed, đồng ý, 好的)
    CANCEL = "cancel"        # User rejects (no, cancel, hủy, 不要)
    EDIT = "edit"            # User wants to modify (add, remove, change)
    NEW_TOPIC = "new_topic"  # User provides research topic
    OTHER = "other"          # Questions, help, unclear


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: UserIntent
    confidence: float
    edit_text: str  # For EDIT intent, the modification request
    original_message: str


# Multilingual keyword sets (extensible)
CONFIRM_KEYWORDS: Set[str] = {
    # English
    "yes", "yeah", "yep", "ok", "okay", "sure", "proceed", "go", "do it",
    "approved", "approve", "confirm", "start", "begin", "run", "execute",
    "good", "fine", "great", "perfect", "lgtm",
    # Vietnamese
    "có", "đồng ý", "ok", "được", "tiếp tục", "chạy", "bắt đầu", "thực hiện",
    # Chinese
    "好", "好的", "可以", "行", "确认", "开始",
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


class IntentClassifier:
    """
    Simple intent classifier for multilingual support.

    Strategy:
    1. Keyword matching (fast, no LLM)
    2. LLM fallback for ambiguous cases
    """

    def __init__(self, llm_client: Optional[LLMClientInterface] = None):
        self.llm = llm_client

    def classify(self, message: str) -> IntentResult:
        """
        Classify user intent from message.

        Simple keyword-based classification.
        """
        message_clean = message.strip().lower()
        words = set(message_clean.split())

        # Check CONFIRM
        if words & CONFIRM_KEYWORDS or message_clean in CONFIRM_KEYWORDS:
            return IntentResult(
                intent=UserIntent.CONFIRM,
                confidence=0.9,
                edit_text="",
                original_message=message
            )

        # Check CANCEL
        if words & CANCEL_KEYWORDS or message_clean in CANCEL_KEYWORDS:
            return IntentResult(
                intent=UserIntent.CANCEL,
                confidence=0.9,
                edit_text="",
                original_message=message
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
                original_message=message
            )

        # If message is long enough, assume it's a new topic
        if len(message_clean) > 5 and len(words) >= 2:
            return IntentResult(
                intent=UserIntent.NEW_TOPIC,
                confidence=0.7,
                edit_text="",
                original_message=message
            )

        # Fallback
        return IntentResult(
            intent=UserIntent.OTHER,
            confidence=0.5,
            edit_text="",
            original_message=message
        )

    async def classify_with_llm(self, message: str) -> IntentResult:
        """
        Use LLM for ambiguous cases.

        Simple prompt with only 5 options to minimize hallucination.
        """
        # First try keyword matching
        result = self.classify(message)
        if result.confidence >= 0.8:
            return result

        if not self.llm:
            return result

        try:
            prompt = f"""Classify user intent. Choose ONE:
- confirm: User agrees/approves
- cancel: User rejects/stops
- edit: User wants to modify something
- new_topic: User provides a research topic
- other: Unclear

Message: "{message}"

Reply with just the intent word (confirm/cancel/edit/new_topic/other):"""

            response = await self.llm.generate(prompt)
            intent_str = response.strip().lower()

            # Map to enum
            intent_map = {
                "confirm": UserIntent.CONFIRM,
                "cancel": UserIntent.CANCEL,
                "edit": UserIntent.EDIT,
                "new_topic": UserIntent.NEW_TOPIC,
                "other": UserIntent.OTHER,
            }

            intent = intent_map.get(intent_str, UserIntent.OTHER)

            return IntentResult(
                intent=intent,
                confidence=0.8,
                edit_text=message if intent == UserIntent.EDIT else "",
                original_message=message
            )

        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
            return result

    def is_confirm(self, message: str) -> bool:
        """Quick check if message is confirmation."""
        return self.classify(message).intent == UserIntent.CONFIRM

    def is_cancel(self, message: str) -> bool:
        """Quick check if message is cancellation."""
        return self.classify(message).intent == UserIntent.CANCEL

    def is_edit(self, message: str) -> bool:
        """Quick check if message is edit request."""
        return self.classify(message).intent == UserIntent.EDIT
