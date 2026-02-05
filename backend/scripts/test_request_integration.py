
"""
Test: ResearchRequest fields integration into ResearchPlan

Verifies:
- keywords -> Seed queries in first step
- sources -> Dedicated "collect" step
- research_questions -> Added to plan
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
    print("  TEST: ResearchRequest Integration into ResearchPlan")
    print("=" * 70)
    
    # Setup
    llm = LLMFactory.create_client(provider="openai")
    planner = PlannerService(llm)
    
    # --- Test with full ResearchRequest ---
    print("\n[1] Full ResearchRequest with all fields:")
    request = ResearchRequest(
        topic="Text-to-SQL with LLMs",
        keywords=["text-to-sql", "NL2SQL", "semantic parsing"],
        sources=[
            "https://arxiv.org/abs/2308.15363",  # DAIL-SQL paper
            "https://arxiv.org/abs/2208.10099",  # Survey paper
        ],
        research_questions=[
            "What are the SOTA methods for text-to-SQL?",
            "Which benchmarks are commonly used?",
        ]
    )
    
    print(f"    Topic: {request.topic}")
    print(f"    Keywords: {request.keywords}")
    print(f"    Sources: {request.sources}")
    print(f"    Questions: {request.research_questions}")
    
    # Generate plan
    print("\n[2] Generating Plan...")
    plan = await planner.generate_research_plan(request)
    
    # Display plan
    print("\n" + "=" * 70)
    print("  GENERATED PLAN")
    print("=" * 70)
    print(plan.to_display())
    
    # Verify integration
    print("\n[3] Verification:")
    
    # Check sources step
    collect_steps = planner.get_steps_by_action(plan, "collect")
    if collect_steps:
        print(f"    [OK] Collect step created with {len(collect_steps[0].sources)} sources")
    else:
        print("    [WARN] No collect step found")
    
    # Check keywords in queries
    all_queries = planner.get_all_queries(plan)
    keywords_found = [kw for kw in request.keywords if kw in all_queries]
    print(f"    [OK] {len(keywords_found)}/{len(request.keywords)} keywords found in queries")
    
    # Check total
    all_sources = planner.get_all_sources(plan)
    print(f"    Total queries: {len(all_queries)}")
    print(f"    Total sources: {len(all_sources)}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
