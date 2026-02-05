"""
Test Planner Tool Generation

Verifies that PlannerService generates steps with tool assignments.
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
    print("=" * 60)
    print("  Test: Planner Tool Generation")
    print("=" * 60)
    
    # --- 1. Setup LLM ---
    print("\n[1] Setting up LLM...")
    try:
        llm = LLMFactory.create_client(provider="openai")
        print("    OpenAI client ready")
    except ValueError as e:
        print(f"    Error: {e}")
        print("    Falling back to mock plan")
        llm = None
    
    # --- 2. Generate Plan ---
    print("\n[2] Generating plan with tools...")
    planner = PlannerService(llm)
    plan = await planner.generate_research_plan(
        ResearchRequest(topic="Building LLM Agents with Python")
    )
    
    # --- 3. Check Tool Assignments ---
    print("\n[3] Steps with Tool Assignments:")
    print("-" * 60)
    
    for step in plan.steps:
        print(f"\nStep {step.id}: {step.title}")
        print(f"  Action: {step.action}")
        print(f"  Tool: {step.tool or '(none)'}")
        if step.tool_args:
            print(f"  Tool Args: {step.tool_args}")
        print(f"  Queries: {step.queries[:2]}..." if len(step.queries) > 2 else f"  Queries: {step.queries}")
    
    # --- 4. Summary ---
    print("\n" + "=" * 60)
    steps_with_tools = [s for s in plan.steps if s.tool]
    print(f"  Total steps: {len(plan.steps)}")
    print(f"  Steps with tools: {len(steps_with_tools)}")
    
    if steps_with_tools:
        print("\n  Tool usage:")
        from collections import Counter
        tool_counts = Counter(s.tool for s in steps_with_tools)
        for tool, count in tool_counts.items():
            print(f"    - {tool}: {count} steps")
    else:
        print("\n  WARNING: No steps have tool assignments!")
        print("  This might mean:")
        print("    - LLM didn't follow the prompt format")
        print("    - Fallback plan was used (no LLM)")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
