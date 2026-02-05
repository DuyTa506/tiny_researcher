
"""
FULL PIPELINE TEST: User Input -> Planner -> Ingestion -> Analysis

This test demonstrates:
1. User provides topic/keywords/sources
2. Planner expands keywords using LLM
3. Ingestion collects papers from multiple sources:
   - ArxivSearcher (API search by keyword)
   - HuggingFaceSearcher (trending papers by keyword) 
   - ArxivCollector (direct URL)
   - RSSCollector (RSS feeds)
4. Analyzer scores relevance
5. Summarizer extracts key insights
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.adapters.llm import LLMFactory
from src.planner.service import PlannerService
from src.core.schema import ResearchRequest
from src.research.ingestion.searcher import ArxivSearcher, HuggingFaceSearcher
from src.research.ingestion.collector import IngestionFactory

# Mock Paper for analyzer/summarizer (they expect Paper model)
from dataclasses import dataclass
from typing import Optional

@dataclass
class MockPaper:
    title: str
    abstract: str
    arxiv_id: Optional[str] = None
    url: Optional[str] = None

async def main():
    print("=" * 70)
    print("  FULL PIPELINE: Input -> Planner -> Ingestion -> (Analyzer)")
    print("=" * 70)
    
    # --- 1. LLM Setup ---
    print("\n[1] Setting up LLM (OpenAI gpt-5-nano)...")
    llm = LLMFactory.create_client(provider="openai")
    print("    Done.")
    
    # --- 2. User Input ---
    print("\n[2] User Input (ResearchRequest):")
    request = ResearchRequest(
        topic="Text-to-SQL with Large Language Models",
        keywords=["text-to-sql", "NL2SQL"],  # User provides some seeds
        sources=[
            "https://arxiv.org/abs/2308.15363",  # Direct paper URL
        ],
        research_questions=[]  # Let LLM generate
    )
    print(f"    Topic: {request.topic}")
    print(f"    Keywords (user): {request.keywords}")
    print(f"    Sources (URLs): {request.sources}")
    
    # --- 3. Planner ---
    print("\n[3] Planner Agent (expand keywords + generate questions)...")
    planner = PlannerService(llm)
    plan = await planner.generate_research_plan(request)
    
    # Extract queries from plan steps
    all_queries = planner.get_all_queries(plan)
    
    print(f"    Plan Steps: {len(plan.steps)}")
    print(f"    Total Queries: {len(all_queries)}")
    print(f"    Sample queries: {all_queries[:3]}...")
    
    # --- 4. Ingestion (Multiple Sources) ---
    print("\n[4] Ingestion - Collecting from multiple sources...")
    all_papers = []
    
    # 4a. ArXiv API Search
    print("\n    [4a] ArxivSearcher (API):")
    arxiv = ArxivSearcher()
    for kw in all_queries[:2]:
        print(f"        Searching: '{kw}'")
        results = await arxiv.search(kw, max_results=2)
        print(f"        -> {len(results)} papers")
        all_papers.extend(results)
    
    # 4b. Direct URL Collection
    print("\n    [4b] ArxivCollector (Direct URLs):")
    for url in request.sources:
        collector = IngestionFactory.get_collector(url)
        print(f"        Collecting: {url}")
        results = await collector.collect(url)
        print(f"        -> {len(results)} papers")
        all_papers.extend(results)
    
    # 4c. HuggingFace (Optional - requires Playwright)
    print("\n    [4c] HuggingFaceSearcher (Trending):")
    try:
        hf = HuggingFaceSearcher()
        hf_results = await hf.search(plan.topic, max_results=2)
        print(f"        -> {len(hf_results)} papers from HF trending")
        all_papers.extend(hf_results)
    except Exception as e:
        print(f"        -> Skipped (Playwright not available): {e}")
    
    # Dedup
    seen = set()
    unique_papers = []
    for p in all_papers:
        pid = p.get('arxiv_id') or p.get('title')
        if pid and pid not in seen:
            seen.add(pid)
            unique_papers.append(p)
    
    print(f"\n    Total collected: {len(all_papers)}")
    print(f"    After dedup: {len(unique_papers)}")
    
    # --- 5. Show what happens next ---
    print("\n" + "=" * 70)
    print("  WHAT HAPPENS NEXT (Pipeline Stages):")
    print("=" * 70)
    print("""
    Papers (from Ingestion)
        |
        v
    +-----------------+
    | ANALYZER        |  <-- Score relevance (0-10)
    | - Relevance     |      Filter low scores
    | - Gap Detection |      Identify missing info -> new queries
    +-----------------+
        |
        v
    +-----------------+
    | SUMMARIZER      |  <-- Extract: Problem, Method, Result
    +-----------------+      One-sentence summary
        |
        v
    +-----------------+
    | CLUSTERER       |  <-- Group by theme (K-Means)
    |                 |      Label clusters with LLM
    +-----------------+
        |
        v
    +-----------------+
    | WRITER          |  <-- Generate Markdown report
    |                 |      With citations
    +-----------------+
        |
        v
    Final Report
    """)
    
    # --- 6. Sample Paper Data ---
    print("\n[5] Sample Paper Data (what gets passed to Analyzer):")
    if unique_papers:
        sample = unique_papers[0]
        print(f"    Title: {sample.get('title', 'N/A')[:60].encode('ascii','ignore').decode()}...")
        print(f"    ArXiv ID: {sample.get('arxiv_id', 'N/A')}")
        print(f"    Abstract: {sample.get('abstract', 'N/A')[:150].encode('ascii','ignore').decode()}...")
        print(f"    Source: {sample.get('source_type', 'unknown')}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
