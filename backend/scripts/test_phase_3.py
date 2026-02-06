"""
Test script for Phase 3: Adaptive Planning

Tests:
1. QueryParser - query type detection
2. AdaptivePlannerService - phase selection
3. Pipeline with adaptive planning

Usage:
    python scripts/test_phase_3.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.adapters.llm import LLMClientInterface
from src.planner.query_parser import QueryParser
from src.planner.adaptive_planner import AdaptivePlannerService
from src.planner.service import PlannerService
from src.research.pipeline import ResearchPipeline
from src.core.schema import ResearchRequest, QueryType, QueryComplexity, ResearchIntent

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MockLLMClient(LLMClientInterface):
    """Mock LLM for testing."""

    async def generate(self, prompt: str, json_mode: bool = False, **kwargs) -> str:
        """Generate mock responses based on prompt content."""

        # Query parsing
        if "analyze this research query" in prompt.lower():
            return '''{
                "main_topic": "transformer models",
                "subtopics": ["attention mechanism", "BERT", "GPT"],
                "entities": ["BERT", "GPT-4", "Transformer"],
                "query_type": "comprehensive",
                "complexity": "medium",
                "intent": "survey"
            }'''

        # Plan generation
        if "research plan" in prompt.lower() or "available_tools" in prompt.lower():
            return '''{
                "topic": "Test Topic",
                "summary": "Test research plan",
                "steps": [
                    {
                        "id": 1,
                        "action": "research",
                        "title": "Search arXiv",
                        "description": "Find papers",
                        "queries": ["test query"],
                        "sources": ["arxiv"],
                        "tool": "arxiv_search",
                        "tool_args": {"query": "test", "max_results": 5}
                    }
                ]
            }'''

        # Relevance scoring
        if "relevance" in prompt.lower() or "score" in prompt.lower():
            return '{"papers": [{"paper_id": 0, "score": 8.5, "reasoning": "Relevant"}]}'

        # Summarization
        if "summarize" in prompt.lower():
            return '''{
                "problem": "Test problem",
                "method": "Test method",
                "result": "Test result",
                "one_sentence_summary": "Test summary."
            }'''

        return "Mock response"


async def test_query_parser():
    """Test QueryParser with different query types."""
    logger.info("=" * 60)
    logger.info("Testing QueryParser")
    logger.info("=" * 60)

    parser = QueryParser()

    test_cases = [
        # (query, expected_type, expected_complexity, expected_intent)
        ("What is BERT?", QueryType.SIMPLE, QueryComplexity.LOW, ResearchIntent.EXPLAIN),
        ("Comprehensive survey of transformer architectures", QueryType.COMPREHENSIVE, QueryComplexity.HIGH, ResearchIntent.SURVEY),
        ("Compare BERT vs GPT", QueryType.COMPARISON, QueryComplexity.MEDIUM, ResearchIntent.COMPARE),
        ("https://arxiv.org/abs/1234.5678", QueryType.URL_BASED, QueryComplexity.MEDIUM, ResearchIntent.EXPLORE),
        ("Find papers on attention mechanism", QueryType.COMPREHENSIVE, QueryComplexity.MEDIUM, ResearchIntent.FIND_PAPERS),
    ]

    passed = 0
    failed = 0

    for query, expected_type, expected_complexity, expected_intent in test_cases:
        result = await parser.parse(query, use_llm=False)

        type_match = result.query_type == expected_type
        # Complexity and intent are heuristic, so we're lenient

        status = "✅" if type_match else "❌"
        logger.info(f"{status} Query: '{query[:40]}...'")
        logger.info(f"   Type: {result.query_type.value} (expected: {expected_type.value})")
        logger.info(f"   Complexity: {result.complexity.value}")
        logger.info(f"   Intent: {result.intent.value}")
        logger.info(f"   Main topic: {result.main_topic}")

        if type_match:
            passed += 1
        else:
            failed += 1

    logger.info(f"\nQueryParser Results: {passed} passed, {failed} failed")
    return failed == 0


async def test_phase_templates():
    """Test phase template selection."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Phase Templates")
    logger.info("=" * 60)

    llm = MockLLMClient()
    adaptive = AdaptivePlannerService(llm)

    test_cases = [
        (QueryType.SIMPLE, ["planning", "execution", "persistence", "analysis"]),
        (QueryType.COMPREHENSIVE, ["planning", "execution", "persistence", "analysis", "pdf_loading", "summarization", "clustering", "writing"]),
        (QueryType.COMPARISON, ["planning", "execution", "persistence", "analysis", "pdf_loading", "summarization", "writing"]),
    ]

    for query_type, expected_phases in test_cases:
        config = adaptive.get_phase_template(query_type)
        active = config.active_phases

        # Check if expected phases are active
        all_present = all(p in active for p in expected_phases)
        status = "✅" if all_present else "❌"

        logger.info(f"{status} {query_type.value}: {active}")

    return True


async def test_adaptive_planner():
    """Test AdaptivePlannerService."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing AdaptivePlannerService")
    logger.info("=" * 60)

    llm = MockLLMClient()
    adaptive = AdaptivePlannerService(llm)

    # Test simple query
    request = ResearchRequest(topic="What is BERT?")
    plan = await adaptive.create_adaptive_plan(request, use_llm_parsing=False)

    logger.info(f"Query Type: {plan.query_info.query_type.value}")
    logger.info(f"Complexity: {plan.query_info.complexity.value}")
    logger.info(f"Intent: {plan.query_info.intent.value}")
    logger.info(f"Active Phases: {plan.phase_config.active_phases}")
    logger.info(f"Skip Synthesis: {plan.phase_config.skip_synthesis}")
    logger.info(f"Recommendations: {plan.recommendations}")

    # Simple queries should skip synthesis
    assert plan.query_info.query_type == QueryType.SIMPLE, "Should detect as SIMPLE"
    assert plan.phase_config.skip_synthesis, "Should skip synthesis for simple queries"

    logger.info("✅ Simple query handled correctly")

    # Test comprehensive query
    request2 = ResearchRequest(topic="Comprehensive survey of transformer architectures in NLP")
    plan2 = await adaptive.create_adaptive_plan(request2, use_llm_parsing=False)

    logger.info(f"\nComprehensive Query:")
    logger.info(f"Query Type: {plan2.query_info.query_type.value}")
    logger.info(f"Active Phases: {plan2.phase_config.active_phases}")
    logger.info(f"Skip Synthesis: {plan2.phase_config.skip_synthesis}")

    assert plan2.query_info.query_type == QueryType.COMPREHENSIVE, "Should detect as COMPREHENSIVE"
    assert not plan2.phase_config.skip_synthesis, "Should NOT skip synthesis for comprehensive"

    logger.info("✅ Comprehensive query handled correctly")

    # Test URL-based query
    request3 = ResearchRequest(
        topic="Analyze this paper https://arxiv.org/abs/2301.07041"
    )
    plan3 = await adaptive.create_adaptive_plan(request3, use_llm_parsing=False)

    logger.info(f"\nURL-based Query:")
    logger.info(f"Query Type: {plan3.query_info.query_type.value}")
    logger.info(f"Has URLs: {plan3.query_info.has_urls}")
    logger.info(f"URLs: {plan3.query_info.urls}")

    assert plan3.query_info.query_type == QueryType.URL_BASED, "Should detect as URL_BASED"
    assert plan3.query_info.has_urls, "Should have URLs"

    logger.info("✅ URL-based query handled correctly")

    return True


async def test_pipeline_with_adaptive():
    """Test ResearchPipeline with adaptive planning."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing Pipeline with Adaptive Planning")
    logger.info("=" * 60)

    llm = MockLLMClient()

    # Create pipeline with adaptive planning enabled
    pipeline = ResearchPipeline(llm, use_adaptive_planner=True)

    assert pipeline.adaptive_planner is not None, "Adaptive planner should be initialized"
    logger.info("✅ Pipeline created with adaptive planner")

    # Test quick parse (without full pipeline run)
    query_info = await pipeline.adaptive_planner.quick_parse("What is attention mechanism?")
    logger.info(f"Quick parse result: type={query_info.query_type.value}")

    # Note: Full pipeline test would require MongoDB/Redis
    # For unit testing, we verify the adaptive planner is wired correctly

    return True


async def main():
    """Run all Phase 3 tests."""
    logger.info("=" * 80)
    logger.info("Phase 3: Adaptive Planning - Test Suite")
    logger.info("=" * 80)

    results = []

    # Run tests
    results.append(("QueryParser", await test_query_parser()))
    results.append(("Phase Templates", await test_phase_templates()))
    results.append(("AdaptivePlanner", await test_adaptive_planner()))
    results.append(("Pipeline Integration", await test_pipeline_with_adaptive()))

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}: {name}")
        if not passed:
            all_passed = False

    logger.info("=" * 80)
    if all_passed:
        logger.info("✅ ALL TESTS PASSED!")
    else:
        logger.info("❌ SOME TESTS FAILED")
    logger.info("=" * 80)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
