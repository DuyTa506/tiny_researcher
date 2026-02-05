
"""
Test: New Planner with Editable Research Plan

This demonstrates the new workflow:
1. User provides topic
2. Planner generates step-by-step plan (editable)
3. Plan is displayed for user review
4. (Future: User can edit before execution)
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

async def main():
    print("=" * 70)
    print("  NEW PLANNER: Editable Research Plan")
    print("=" * 70)
    
    # --- 1. Setup ---
    print("\n[1] Setting up LLM...")
    llm = LLMFactory.create_client(provider="openai")
    planner = PlannerService(llm)
    
    # --- 2. User Input ---
    print("\n[2] User Input:")
    request = ResearchRequest(
        topic="How to build a Deep Research Agent with Python"
    )
    print(f"    Topic: {request.topic}")
    
    # --- 3. Generate Plan ---
    print("\n[3] Generating Research Plan...")
    plan = await planner.generate_research_plan(request)
    
    # --- 4. Display Plan (This is what user sees and can edit) ---
    print("\n" + "=" * 70)
    print("  RESEARCH PLAN (User can edit this before execution)")
    print("=" * 70)
    print(plan.to_display())
    
    # --- 5. Show extracted queries ---
    print("\n[5] All Search Queries (extracted from plan):")
    queries = planner.get_all_queries(plan)
    for i, q in enumerate(queries[:10], 1):
        print(f"    {i}. {q}")
    
    # --- 6. Show JSON (for API response) ---
    print("\n[6] Plan as JSON (for frontend):")
    import json
    print(json.dumps(plan.model_dump(), indent=2, ensure_ascii=False)[:500] + "...")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
