
import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.research.ingestion.searcher import ArxivSearcher

async def main():
    print("=== Test: ArxivSearcher ===\n")
    
    searcher = ArxivSearcher()
    
    # Test 1: Simple keyword search
    print("[1] Simple keyword search: 'text-to-sql'")
    results = await searcher.search("text-to-sql", max_results=5)
    print(f"  Found {len(results)} papers")
    if results:
        first = results[0]
        print(f"  First paper:")
        print(f"    Title: {first['title'][:80].encode('ascii', 'ignore').decode()}...")
        print(f"    ArXiv ID: {first['arxiv_id']}")
        print(f"    Published: {first['published']}")
        print(f"    Authors: {len(first['authors'])} authors")
        print(f"    Categories: {first['categories']}")
    
    print()
    
    # Test 2: Search with category filter
    print("[2] Keyword + Category filter: 'transformer' in cs.CL")
    results2 = await searcher.search("transformer", categories=["cs.CL"], max_results=3)
    print(f"  Found {len(results2)} papers")
    for r in results2:
        print(f"    - {r['title'][:60]}... ({r['categories']})")
        
    print()
    
    # Test 3: Multiple keywords
    print("[3] Multiple keywords: ['LLM', 'agent']")
    results3 = await searcher.search_by_keywords(["LLM", "agent"], max_results=3)
    print(f"  Found {len(results3)} papers")
    for r in results3:
        print(f"    - {r['title'][:60]}...")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
