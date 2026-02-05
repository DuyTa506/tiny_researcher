"""
Test MongoDB Connection and Repositories

Tests the MongoDB layer with sample paper data.
"""

import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.core.database import connect_mongodb, close_mongodb
from src.core.models import Paper, PaperStatus
from src.storage.repositories import PaperRepository

async def main():
    print("=" * 60)
    print("  Test: MongoDB Connection & Repositories")
    print("=" * 60)
    
    # --- 1. Connect to MongoDB ---
    print("\n[1] Connecting to MongoDB...")
    try:
        db = await connect_mongodb()
        print(f"    Connected to: {db.name}")
    except Exception as e:
        print(f"    ERROR: {e}")
        print("    Make sure MongoDB is running:")
        print("    docker run -d -p 27017:27017 mongo:7")
        return
    
    # --- 2. Create test papers ---
    print("\n[2] Creating test papers...")
    repo = PaperRepository()
    
    papers = [
        Paper(
            arxiv_id="2401.00001",
            title="Test Paper 1: Prompt Injection Attacks",
            abstract="This paper studies prompt injection attacks...",
            authors=["Author A", "Author B"],
            source="arxiv",
            plan_id="test-plan-001"
        ),
        Paper(
            arxiv_id="2401.00002",
            title="Test Paper 2: LLM Agent Safety",
            abstract="A comprehensive study on LLM agent safety...",
            authors=["Author C"],
            source="arxiv",
            plan_id="test-plan-001"
        ),
        Paper(
            arxiv_id="2401.00003",
            title="Test Paper 3: Jailbreak Defense",
            abstract="Methods for defending against jailbreak attacks...",
            authors=["Author D", "Author E"],
            source="huggingface",
            plan_id="test-plan-001"
        )
    ]
    
    paper_ids = await repo.create_many(papers)
    print(f"    Created {len(paper_ids)} papers")
    for i, pid in enumerate(paper_ids):
        print(f"      {i+1}. {pid}")
    
    # --- 3. Query papers ---
    print("\n[3] Querying papers...")
    
    # Get by plan
    plan_papers = await repo.get_by_plan("test-plan-001")
    print(f"    Papers in plan: {len(plan_papers)}")
    
    # Get by arxiv_id
    paper = await repo.get_by_arxiv_id("2401.00002")
    if paper:
        print(f"    Found: {paper.title[:40]}...")
    
    # --- 4. Update paper ---
    print("\n[4] Updating paper score...")
    await repo.update_score(paper_ids[0], 8.5)
    updated = await repo.get_by_id(paper_ids[0])
    print(f"    Score: {updated.relevance_score}")
    print(f"    Status: {updated.status}")
    
    # --- 5. Get relevant papers ---
    print("\n[5] Getting relevant papers (score >= 7)...")
    relevant = await repo.get_relevant("test-plan-001", min_score=7.0)
    print(f"    Found {len(relevant)} relevant papers")
    
    # --- 6. Cleanup ---
    print("\n[6] Cleanup (optional: drop test data)...")
    # Uncomment to drop: await db.papers.delete_many({"plan_id": "test-plan-001"})
    
    await close_mongodb()
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
