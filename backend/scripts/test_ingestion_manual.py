
import asyncio
import sys
import os
from unittest.mock import MagicMock

# Mock external dependencies for database
sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()

mock_config = MagicMock()
mock_config.settings.DATABASE_URL = "postgresql+asyncpg://mock:mock@localhost/mock"
mock_config.settings.ENVIRONMENT = "testing"
sys.modules["src.core.config"] = mock_config

from sqlalchemy.orm import DeclarativeBase
class MockBase(DeclarativeBase):
    pass
mock_db = MagicMock()
mock_db.Base = MockBase
sys.modules["src.core.database"] = mock_db

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.planner.service import PlannerService
from src.research.ingestion.collector import IngestionFactory, RSSCollector, ArxivCollector
from src.research.ingestion.searcher import ArxivSearcher, HuggingFaceSearcher
from src.adapters.llm import LLMFactory
from src.core.schema import ResearchRequest
import structlog

logger = structlog.get_logger()

async def main():
    print("=" * 60)
    print("  FULL INGESTION TEST: Keywords + URL Sources")
    print("=" * 60)
    
    # --- 1. Create Research Request ---
    print("\n[1] Creating ResearchRequest...")
    request = ResearchRequest(
        topic="Text-to-SQL",
        keywords=["text-to-sql", "semantic parsing"],
        sources=[
            "https://arxiv.org/abs/2308.15363",  # Direct ArXiv URL
        ],
        research_questions=["What are SOTA methods?", "What datasets are used?"]
    )
    print(f"    Topic: {request.topic}")
    print(f"    Keywords: {request.keywords}")
    print(f"    Sources: {request.sources}")
    
    print("\n[2] Creating Comprehensive Plan...")
    llm = LLMFactory.create_client(provider="gemini", api_key="mock")
    planner = PlannerService(llm)
    plan = await planner.generate_research_plan(request)
    
    # Extract queries and sources from plan
    all_queries = planner.get_all_queries(plan)
    all_sources = planner.get_all_sources(plan)
    
    print(f"    Plan Steps: {len(plan.steps)}")
    print(f"    Total Queries: {len(all_queries)}")
    print(f"    Sources: {all_sources}")
    
    all_papers = []
    
    # --- 3. Collect from URL Sources ---
    print("\n[3] Collecting from URL Sources...")
    for url in all_sources:
        collector = IngestionFactory.get_collector(url)
        print(f"    Processing: {url}")
        print(f"    Collector: {type(collector).__name__}")
        
        try:
            papers = await collector.collect(url)
            print(f"    -> Collected {len(papers)} items")
            all_papers.extend(papers)
            
            if papers:
                p = papers[0]
                print(f"       Title: {p.get('title', 'N/A')[:60]}...")
        except Exception as e:
            print(f"    -> Error: {e}")
    
    # --- 4. Search by Keywords (ArXiv API) ---
    print("\n[4] Searching ArXiv by Keywords...")
    arxiv_searcher = ArxivSearcher()
    
    for kw in all_queries[:2]:  # Limit to first 2 queries for test
        print(f"    Searching: '{kw}'")
        try:
            results = await arxiv_searcher.search(kw, max_results=3)
            print(f"    -> Found {len(results)} papers")
            all_papers.extend(results)
            
            for r in results[:2]:
                title_safe = r['title'][:50].encode('ascii', 'ignore').decode()
                print(f"       - {title_safe}...")
        except Exception as e:
            print(f"    -> Error: {e}")
    
    # --- 5. Optional: HuggingFace Search ---
    # Commented out because it requires Playwright browser
    print("\n[5] Searching HuggingFace Trending...")
    hf_searcher = HuggingFaceSearcher()
    hf_results = await hf_searcher.search(plan.topic, max_results=3)
    print(f"    -> Found {len(hf_results)} papers")
    all_papers.extend(hf_results)
    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"  TOTAL PAPERS COLLECTED: {len(all_papers)}")
    print("=" * 60)
    
    # Deduplicate by arxiv_id
    seen_ids = set()
    unique_papers = []
    for p in all_papers:
        arxiv_id = p.get('arxiv_id')
        if arxiv_id and arxiv_id not in seen_ids:
            seen_ids.add(arxiv_id)
            unique_papers.append(p)

    
    print(f"  Unique papers (after dedup): {len(unique_papers)}")
    
    print("\n  Sample papers:")
    for i, p in enumerate(unique_papers):
        title_safe = p.get('title', 'N/A')[:50].encode('ascii', 'ignore').decode()
        print(f"    {i+1}. [{p.get('source_type', 'unknown')}] {title_safe}...")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
