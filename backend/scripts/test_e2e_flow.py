
import asyncio
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.adapters.llm import LLMFactory
from src.planner.service import PlannerService
from src.core.schema import ResearchRequest
from src.research.ingestion.searcher import ArxivSearcher

async def main():
    print("=" * 60)
    print("  END-TO-END FLOW: User Input -> Planner -> Ingestion")
    print("=" * 60)
    
    # --- 1. Create LLM Client (OpenAI) ---
    print("\n[1] Initializing LLM Client (OpenAI gpt-5-nano)...")
    try:
        llm = LLMFactory.create_client(provider="openai")
        print("    [OK] OpenAI client created")
    except ValueError as e:
        print(f"    [ERROR] {e}")
        print("    Please set OPENAI_API_KEY in .env file")
        return
    
    # --- 2. User Input (ResearchRequest) ---
    print("\n[2] Creating Research Request...")
    request = ResearchRequest(
        topic="Agentic AI Workflows",
        keywords=[],  # Empty - let LLM generate
        research_questions=[],  # Empty - let LLM generate
        sources=[]
    )
    print(f"    Topic: {request.topic}")
    print(f"    Keywords (user): {request.keywords} (empty - will autofill)")
    print(f"    Questions (user): {request.research_questions} (empty - will autofill)")
    
    # --- 3. Planner Agent (with real LLM) ---
    print("\n[3] Running Planner Agent...")
    planner = PlannerService(llm)
    plan = await planner.generate_research_plan(request)
    
    # Extract queries from plan steps
    all_queries = planner.get_all_queries(plan)
    
    print(f"    [OK] Research Plan Created:")
    print(f"    Steps: {len(plan.steps)}")
    print(f"    Queries: {all_queries[:5]}")
    
    # --- 4. Ingestion (ArXiv Search) ---
    print("\n[4] Running Ingestion (ArXiv Search)...")
    arxiv = ArxivSearcher()
    
    all_papers = []
    for kw in all_queries[:2]:  # Limit to first 2 queries
        print(f"    Searching: '{kw}'")
        results = await arxiv.search(kw, max_results=3)
        print(f"    -> Found {len(results)} papers")
        all_papers.extend(results)
    
    # Dedup
    seen = set()
    unique_papers = []
    for p in all_papers:
        if p['arxiv_id'] not in seen:
            seen.add(p['arxiv_id'])
            unique_papers.append(p)
    
    # --- Summary ---
    print("\n" + "=" * 60)
    print(f"  FLOW COMPLETE!")
    print(f"  Papers collected: {len(unique_papers)}")
    print("=" * 60)
    
    print("\n  Sample papers:")
    for i, p in enumerate(unique_papers[:5], 1):
        title = p['title'][:50].encode('ascii', 'ignore').decode()
        print(f"    {i}. {title}...")

if __name__ == "__main__":
    asyncio.run(main())
