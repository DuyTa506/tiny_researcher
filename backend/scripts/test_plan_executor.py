"""
Test Plan Executor

Tests the PlanExecutor to execute tool-based research plans.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.adapters.llm import LLMFactory
from src.planner.service import PlannerService
from src.planner.executor import PlanExecutor, StepStatus
from src.core.schema import ResearchRequest

def on_step_complete(step, result):
    """Callback for step completion"""
    status_icon = {
        StepStatus.COMPLETED: "[OK]",
        StepStatus.FAILED: "[FAIL]",
        StepStatus.SKIPPED: "[SKIP]"
    }.get(result.status, "[?]")
    
    title_safe = step.title.encode('ascii', 'ignore').decode()
    print(f"    {status_icon} Step {step.id}: {title_safe}")
    if result.tool_used:
        print(f"      Tool: {result.tool_used} -> {len(result.results)} results")
    if result.error:
        error_safe = str(result.error)[:80]
        print(f"      Error: {error_safe}")

async def main():
    print("=" * 70)
    print("  Test: Plan Executor - Execute Tool-Based Plan")
    print("=" * 70)
    
    # --- 1. Setup ---
    print("\n[1] Setting up LLM...")
    try:
        llm = LLMFactory.create_client(provider="openai")
        print("    OpenAI client ready")
    except ValueError as e:
        print(f"    Error: {e}")
        print("    Using fallback plan")
        llm = None
    
    # --- 2. Generate Plan ---
    print("\n[2] Generating research plan...")
    planner = PlannerService(llm)
    request = ResearchRequest(
        topic="Prompt Injection Attacks on LLM Agents",
        keywords=["prompt injection", "jailbreak LLM"],
        sources=[]
    )
    
    plan = await planner.generate_research_plan(request)
    print(f"    Plan: {plan.topic}")
    print(f"    Steps: {len(plan.steps)}")
    
    # Show plan
    print("\n    Plan Overview:")
    for step in plan.steps[:4]:  # Show first 4
        tool_info = f"[{step.tool}]" if step.tool else "[no tool]"
        print(f"      {step.id}. {step.title} {tool_info}")
    if len(plan.steps) > 4:
        print(f"      ... and {len(plan.steps) - 4} more steps")
    
    # --- 3. Execute Plan ---
    print("\n[3] Executing plan (will call tools)...")
    print("-" * 70)
    
    executor = PlanExecutor(on_step_complete=on_step_complete)
    
    # Only execute first 3 steps for quick test
    plan.steps = plan.steps[:3]
    
    results = await executor.execute(plan)
    
    # --- 4. Summary ---
    print("\n" + "=" * 70)
    print("  EXECUTION SUMMARY")
    print("=" * 70)
    
    progress = executor.progress
    print(f"\n  Steps executed: {progress.total_steps}")
    print(f"  Completed: {len(progress.completed_steps)}")
    print(f"  Failed: {len(progress.failed_steps)}")
    print(f"  Success rate: {progress.success_rate:.0%}")
    
    # Collect all papers
    all_papers = executor.get_all_papers()
    print(f"\n  Total papers collected: {len(all_papers)}")
    
    if all_papers:
        print("\n  Sample papers:")
        for i, paper in enumerate(all_papers[:5], 1):
            title = paper.get('title', 'N/A')[:50]
            title_safe = title.encode('ascii', 'ignore').decode()
            print(f"    {i}. {title_safe}...")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
