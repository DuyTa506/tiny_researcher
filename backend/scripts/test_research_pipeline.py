"""
Test Research Pipeline

Full integration test: Plan → Execute → Persist → Analyze
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.adapters.llm import LLMFactory
from src.core.schema import ResearchRequest
from src.research.pipeline import ResearchPipeline

async def main():
    print("=" * 70)
    print("  Test: Full Research Pipeline")
    print("=" * 70)
    
    # --- 1. Setup ---
    print("\n[1] Setting up...")
    try:
        llm = LLMFactory.create_client(provider="openai")
        print("    LLM: OpenAI ready")
    except ValueError as e:
        print(f"    ERROR: {e}")
        return
    
    # --- 2. Create pipeline ---
    print("\n[2] Creating pipeline...")
    pipeline = ResearchPipeline(
        llm_client=llm,
        skip_analysis=False  # Enable analysis
    )
    
    # --- 3. Run pipeline ---
    print("\n[3] Running pipeline...")
    print("-" * 70)
    
    request = ResearchRequest(
        topic="Prompt Injection Defense Mechanisms",
        keywords=["prompt injection", "LLM security", "jailbreak defense"]
    )
    
    try:
        result = await pipeline.run(request)
    except Exception as e:
        print(f"\n    ERROR: {e}")
        print("    Make sure MongoDB is running: docker run -d -p 27017:27017 mongo:7")
        return
    
    # --- 4. Results ---
    print("\n" + "=" * 70)
    print("  PIPELINE RESULTS")
    print("=" * 70)
    
    print(f"\n  Plan ID: {result.plan_id[:8]}...")
    print(f"  Topic: {result.topic}")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    
    print(f"\n  Execution:")
    print(f"    Steps completed: {result.steps_completed}")
    print(f"    Steps failed: {result.steps_failed}")
    
    print(f"\n  Papers:")
    print(f"    Total collected: {result.total_collected}")
    print(f"    Unique (after dedup): {result.unique_papers}")
    print(f"    Duplicates removed: {result.duplicates_removed}")
    print(f"    Relevant (score >= 7): {result.relevant_papers}")
    
    if result.papers:
        print(f"\n  Top Relevant Papers:")
        sorted_papers = sorted(
            result.papers, 
            key=lambda p: p.relevance_score or 0, 
            reverse=True
        )[:5]
        
        for i, paper in enumerate(sorted_papers, 1):
            title = paper.title[:50].encode('ascii', 'ignore').decode()
            print(f"    {i}. [{paper.relevance_score:.1f}] {title}...")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
