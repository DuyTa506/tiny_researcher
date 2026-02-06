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

    async def _analyze_with_llm(
        self,
        query: str,
        complexity: QueryComplexity
    ) -> ClarificationResult:
        """LLM-based smart analysis."""
        prompt = f"""You are a research assistant. Analyze this query and think like a researcher.

Query: "{query}"

Think step by step:
1. What is the user really trying to achieve?
2. Is anything unclear or ambiguous?
3. What clarifying questions would help?

Respond in this format (keep it short):
UNDERSTANDING: [Your interpretation in 1 sentence]
SUBQUERIES: [If compound, list sub-objectives separated by |, otherwise "none"]
QUESTIONS: [1-2 clarifying questions separated by |, or "none" if query is clear]

Examples:
- For "find attention-free methods and adapt to linear transformers":
  UNDERSTANDING: User wants to find attention-free architectures and evaluate their adaptability to linear transformers
  SUBQUERIES: attention-free methods/architectures | linear transformer adaptation
  QUESTIONS: Are you looking for existing work or exploring new research directions? | What's your use case - NLP, vision, or general?

- For "BERT paper":
  UNDERSTANDING: User wants to find the BERT paper
  SUBQUERIES: none
  QUESTIONS: none

Now analyze the query:"""

        try:
            response = await self.llm.generate(prompt)
            return self._parse_llm_response(response, query, complexity)
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
        """Format clarification result as a user-friendly message."""
        lines = []

        # Show understanding
        lines.append(f"**My understanding:** {result.understanding}")
        lines.append("")

        # Show sub-queries if compound
        if result.sub_queries:
            lines.append("**I see these objectives:**")
            for i, sq in enumerate(result.sub_queries, 1):
                lines.append(f"  {i}. {sq}")
            lines.append("")

        # Ask questions
        if result.questions:
            lines.append("**Before I search, can you clarify:**")
            for q in result.questions:
                lines.append(f"  - {q}")

        return "\n".join(lines)
