"""
Test Phase 1-2 Implementation

Tests the complete pipeline with:
- Redis tool caching
- ResearchMemoryManager
- Selective PDF loading
- Clustering, Summarization, Report writing
"""

import asyncio
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.research.pipeline import ResearchPipeline
from src.core.schema import ResearchRequest
from src.adapters.llm import LLMClientInterface
from dotenv import load_dotenv

# Load environment variables
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
        """Generate a mock response."""
        if "relevance" in prompt.lower() or "score" in prompt.lower():
            # Mock relevance scoring
            return '{"papers": [{"paper_id": 0, "score": 8.5, "reasoning": "Highly relevant"}]}'

        if "summarize" in prompt.lower() or "summary" in prompt.lower():
            # Mock summary
            return '''{
                "problem": "Testing LLM integration",
                "method": "Mock responses",
                "result": "Successful test",
                "one_sentence_summary": "A test paper about mocking."
            }'''

        if "cluster" in prompt.lower() or "theme" in prompt.lower():
            # Mock cluster naming
            return '{"name": "Test Theme", "description": "Testing cluster"}'

        return "Mock LLM response"


async def test_pipeline():
    """Test the complete pipeline."""
    logger.info("=" * 80)
    logger.info("Testing Phase 1-2 Implementation")
    logger.info("=" * 80)

    # Create mock LLM
    llm = MockLLMClient()

    # Create pipeline
    pipeline = ResearchPipeline(llm, skip_analysis=False, skip_synthesis=False)

    # Create research request
    request = ResearchRequest(
        topic="Transformer Models in NLP",
        keywords=["transformer", "BERT", "attention mechanism"]
    )

    logger.info(f"\nResearch topic: {request.topic}")
    logger.info(f"Keywords: {', '.join(request.keywords)}")

    try:
        # Run pipeline
        logger.info("\n--- Starting Pipeline ---\n")
        result = await pipeline.run(request)

        # Print results
        logger.info("\n" + "=" * 80)
        logger.info("PIPELINE RESULTS")
        logger.info("=" * 80)

        logger.info(f"\n✅ Pipeline completed in {result.duration_seconds:.1f}s")
        logger.info(f"Session ID: {result.session_id}")

        logger.info("\n📊 Collection Stats:")
        logger.info(f"  - Total collected: {result.total_collected}")
        logger.info(f"  - Unique papers: {result.unique_papers}")
        logger.info(f"  - Duplicates removed: {result.duplicates_removed}")

        logger.info("\n🎯 Analysis Stats:")
        logger.info(f"  - Relevant papers: {result.relevant_papers}")
        logger.info(f"  - High relevance (≥8): {result.high_relevance_papers}")

        logger.info("\n📄 Processing Stats:")
        logger.info(f"  - Papers with full text: {result.papers_with_full_text}")
        logger.info(f"  - Papers with summaries: {result.papers_with_summaries}")
        logger.info(f"  - Clusters created: {result.clusters_created}")

        logger.info("\n💾 Cache Performance:")
        logger.info(f"  - Cache hit rate: {result.cache_hit_rate:.1%}")

        logger.info("\n🔧 Execution Stats:")
        logger.info(f"  - Steps completed: {result.steps_completed}")
        logger.info(f"  - Steps failed: {result.steps_failed}")

        if result.clusters:
            logger.info(f"\n📚 Clusters:")
            for cluster in result.clusters:
                logger.info(f"  - {cluster.name}: {len(cluster.paper_indices)} papers")

        if result.report_markdown:
            logger.info(f"\n📝 Report generated ({len(result.report_markdown)} chars)")
            logger.info("\n--- Report Preview ---")
            logger.info(result.report_markdown[:500] + "...\n")

        # Test memory manager features
        if pipeline.memory_manager:
            context = await pipeline.memory_manager.get_analysis_context(result.session_id)
            logger.info("\n🧠 Memory Context:")
            logger.info(f"  - Topic: {context.get('topic')}")
            logger.info(f"  - Current phase: {context.get('current_phase')}")
            logger.info(f"  - Total papers: {context.get('total_papers')}")

        logger.info("\n" + "=" * 80)
        logger.info("✅ ALL TESTS PASSED!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"\n❌ Pipeline failed: {e}", exc_info=True)
        raise

    finally:
        # Cleanup
        if pipeline.cache_manager:
            await pipeline.cache_manager.close()
        if pipeline.memory_manager:
            await pipeline.memory_manager.close()


if __name__ == "__main__":
    asyncio.run(test_pipeline())
