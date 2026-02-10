"""
QueryClarifier - Analyzes queries and generates clarifying questions.

A real researcher asks questions before diving in.
This module detects when clarification is needed and generates smart questions.
"""

import logging
from typing import Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from src.adapters.llm import LLMClientInterface

logger = logging.getLogger(__name__)


class QueryComplexity(str, Enum):
    """How complex is the query?"""
    SIMPLE = "simple"      # Clear, single objective
    COMPOUND = "compound"  # Multiple related objectives
    AMBIGUOUS = "ambiguous"  # Unclear terms or goals


@dataclass
class ClarificationResult:
    """Result of query analysis."""
    needs_clarification: bool
    complexity: QueryComplexity
    questions: List[str] = field(default_factory=list)
    understanding: str = ""  # Agent's interpretation
    sub_queries: List[str] = field(default_factory=list)  # Decomposed queries
    original_query: str = ""
    detected_language: str = "English"  # Detected user language


# Compound query indicators
COMPOUND_INDICATORS = [
    " and ", " then ", " also ", " plus ",
    " và ", " rồi ", " thêm ",  # Vietnamese
    ", ",  # Comma often separates objectives
]

# Goal ambiguity indicators (needs goal clarification)
GOAL_INDICATORS = [
    "find", "search", "look for", "get",
    "tìm", "kiếm",  # Vietnamese
]

# Exploration indicators (theoretical vs existing work)
EXPLORATION_WORDS = [
    "can", "could", "possible", "if", "whether", "how to",
    "có thể", "liệu",  # Vietnamese
]


class QueryClarifier:
    """
    Analyzes queries and generates clarifying questions.

    Thinks like a researcher:
    1. Is this query clear or ambiguous?
    2. What are the user's real objectives?
    3. What do I need to know before searching?
    """

    def __init__(self, llm_client: Optional[LLMClientInterface] = None):
        self.llm = llm_client

    async def analyze(self, query: str) -> ClarificationResult:
        """
        Analyze a query and determine if clarification is needed.

        Returns ClarificationResult with questions if needed.
        """
        query_lower = query.lower().strip()

        # Detect complexity
        complexity = self._detect_complexity(query_lower)

        # Simple queries don't need clarification
        if complexity == QueryComplexity.SIMPLE and len(query.split()) < 6:
            return ClarificationResult(
                needs_clarification=False,
                complexity=complexity,
                original_query=query
            )

        # Use LLM for smart analysis if available
        if self.llm:
            return await self._analyze_with_llm(query, complexity)

        # Rule-based fallback
        return self._analyze_with_rules(query, complexity)

    def _detect_complexity(self, query_lower: str) -> QueryComplexity:
        """Detect query complexity."""
        # Check for compound indicators
        for indicator in COMPOUND_INDICATORS:
            if indicator in query_lower:
                # Make sure it's actually compound (not just "research and development")
                parts = query_lower.split(indicator)
                if len(parts) >= 2 and all(len(p.strip()) > 3 for p in parts[:2]):
                    return QueryComplexity.COMPOUND

        # Check for exploration/theoretical questions
        if any(word in query_lower for word in EXPLORATION_WORDS):
            return QueryComplexity.AMBIGUOUS

        # Long queries are often complex
        if len(query_lower.split()) > 10:
            return QueryComplexity.COMPOUND

        return QueryComplexity.SIMPLE

    def _analyze_with_rules(
        self,
        query: str,
        complexity: QueryComplexity
    ) -> ClarificationResult:
        """Rule-based query analysis."""
        questions = []
        sub_queries = []
        query_lower = query.lower()

        # Compound query - always ask for clarification
        if complexity == QueryComplexity.COMPOUND:
            # Try to split
            for indicator in COMPOUND_INDICATORS:
                if indicator in query_lower:
                    parts = query.split(indicator[0] if indicator.startswith(" ") else indicator)
                    sub_queries = [p.strip() for p in parts if len(p.strip()) > 3]
                    break

            if sub_queries:
                questions.append(
                    "This has multiple parts. Which is most important to you?"
                )
            else:
                questions.append(
                    "This seems like a complex question. What's your main goal?"
                )

        # Exploration query - clarify existing vs theoretical
        if any(word in query_lower for word in EXPLORATION_WORDS):
            questions.append(
                "Are you looking for existing research, or exploring if this is possible?"
            )

        understanding = f"Research query: {query}"

        return ClarificationResult(
            needs_clarification=len(questions) > 0,
            complexity=complexity,
            questions=questions[:2],  # Max 2 questions
            understanding=understanding,
            sub_queries=sub_queries,
            original_query=query
        )

    def _detect_language(self, query: str) -> str:
        """Detect language from query text using word boundary matching."""
        query_lower = query.lower()

        # Split into words for word-boundary matching
        words = query_lower.split()

        # Vietnamese indicators (common words that are unique to Vietnamese)
        vietnamese_words = ['chào', 'tôi', 'cho', 'tìm', 'về', 'có', 'là', 'của', 'và', 'được', 'này', 'đó', 'muốn', 'bạn', 'nghiên', 'cứu']
        vietnamese_count = sum(1 for word in vietnamese_words if word in words)
        if vietnamese_count >= 2:  # Require at least 2 Vietnamese words
            return "Vietnamese"

        # Spanish indicators
        spanish_words = ['hola', 'buscar', 'encontrar', 'sobre', 'investigación', 'qué', 'cómo', 'dónde']
        spanish_count = sum(1 for word in spanish_words if word in words)
        if spanish_count >= 2:
            return "Spanish"

        # French indicators (excluding common words like "me", "pour")
        french_words = ['bonjour', 'chercher', 'trouver', 'recherche', 'recherches', 'où']
        french_count = sum(1 for word in french_words if word in words)
        if french_count >= 2:
            return "French"

        # German indicators
        german_words = ['hallo', 'suchen', 'finden', 'über', 'forschung']
        german_count = sum(1 for word in german_words if word in words)
        if german_count >= 2:
            return "German"

        # Default to English
        return "English"

    async def _analyze_with_llm(
        self,
        query: str,
        complexity: QueryComplexity
    ) -> ClarificationResult:
        """LLM-based smart analysis."""
        # Detect user's language
        detected_language = self._detect_language(query)

        prompt = f"""You are a friendly research assistant having a natural conversation with a user.

User's query: "{query}"

The user is speaking in {detected_language}. You MUST respond in {detected_language} in a natural, conversational way.

Think like a researcher:
1. What is the user really trying to achieve?
2. Is anything unclear or ambiguous?
3. What clarifying questions would help?

Respond in this format (all text in {detected_language}):
UNDERSTANDING: [Your interpretation in 1 sentence - natural tone, not robotic]
SUBQUERIES: [If compound, list sub-objectives separated by |, otherwise "none"]
QUESTIONS: [1-2 clarifying questions separated by |, or "none" if query is clear - ask naturally like a colleague]

Important tone guidelines:
- Be conversational and friendly, not formal or robotic
- Use natural language like you're talking to a colleague
- Don't use templates like "I understand that..." - just state your understanding naturally
- Ask questions conversationally, not in a checklist format

Examples:

English query "find attention-free methods and adapt to linear transformers":
  UNDERSTANDING: You want to explore attention-free architectures and see how they could work with linear transformers
  SUBQUERIES: attention-free methods | linear transformer adaptation
  QUESTIONS: Are you looking at existing work or thinking about new directions? | What domain are you targeting - language, vision, or something else?

Vietnamese query "cho tôi một vài nghiên cứu mới nhất về vision transformers":
  UNDERSTANDING: Bạn muốn tìm các nghiên cứu gần đây về vision transformers
  SUBQUERIES: none
  QUESTIONS: Bạn quan tâm đến ứng dụng cụ thể nào không - phân loại ảnh, phát hiện đối tượng, hay tổng quát? | Bạn muốn so sánh với CNN hay chỉ tìm hiểu ViT thôi?

Now analyze the query (remember to respond in {detected_language}):"""

        try:
            response = await self.llm.generate(prompt)
            result = self._parse_llm_response(response, query, complexity)
            result.detected_language = detected_language  # Store detected language
            return result
        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")
            return self._analyze_with_rules(query, complexity)

    def _parse_llm_response(
        self,
        response: str,
        query: str,
        complexity: QueryComplexity
    ) -> ClarificationResult:
        """Parse LLM response into ClarificationResult."""
        understanding = ""
        sub_queries = []
        questions = []

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("UNDERSTANDING:"):
                understanding = line.replace("UNDERSTANDING:", "").strip()
            elif line.startswith("SUBQUERIES:"):
                content = line.replace("SUBQUERIES:", "").strip()
                if content.lower() != "none":
                    sub_queries = [q.strip() for q in content.split("|") if q.strip()]
            elif line.startswith("QUESTIONS:"):
                content = line.replace("QUESTIONS:", "").strip()
                if content.lower() != "none":
                    questions = [q.strip() for q in content.split("|") if q.strip()]

        return ClarificationResult(
            needs_clarification=len(questions) > 0,
            complexity=complexity,
            questions=questions[:2],
            understanding=understanding or f"Research query: {query}",
            sub_queries=sub_queries,
            original_query=query
        )

    def format_clarification_message(self, result: ClarificationResult) -> str:
        """Format clarification result as a natural, conversational message."""
        lines = []

        # Show understanding naturally
        lines.append(result.understanding)

        # Show sub-queries if compound (more natural format)
        if result.sub_queries:
            lines.append("")
            if result.detected_language == "Vietnamese":
                lines.append("Tôi thấy bạn muốn tìm hiểu về:")
            elif result.detected_language == "Spanish":
                lines.append("Veo que quieres investigar:")
            elif result.detected_language == "French":
                lines.append("Je vois que vous voulez rechercher:")
            elif result.detected_language == "German":
                lines.append("Ich sehe, Sie möchten recherchieren:")
            else:
                lines.append("I see you want to look into:")

            for i, sq in enumerate(result.sub_queries, 1):
                lines.append(f"{i}. {sq}")

        # Ask questions naturally
        if result.questions:
            lines.append("")
            for q in result.questions:
                lines.append(q)

        return "\n".join(lines)
