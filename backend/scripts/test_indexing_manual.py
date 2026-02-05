import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.storage.vector_store import vector_service

async def main():
    print("--- Testing Vector Service (Embedded Qdrant) ---")
    
    # 1. Mock Data
    paper = {
        "title": "Attention Is All You Need",
        "abstract": "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.",
        "arxiv_id": "1706.03762",
        "url": "https://arxiv.org/abs/1706.03762",
        "published_date": "2017-06-12",
        "source_type": "manual_test"
    }
    
    # 2. Index
    print(f"Indexing paper: {paper['title']}...")
    # upsert_paper is synchronous in standard client? 
    # Wait, QdrantClient sync vs async. 
    # In my previous code `upsert_paper` calls `self.client.upsert` which is synchronous for `QdrantClient`. 
    # The `AsyncQdrantClient` is for async. 
    # My `VectorService` uses `QdrantClient`, so methods are sync.
    # But `main` is async. I can just call it.
    
    try:
        vector_service.upsert_paper(paper)
        print("Upsert successful.")
    except Exception as e:
        print(f"Upsert failed: {e}")
        return

    # 3. Search
    query = "transformer architecture"
    print(f"\nSearching for: '{query}'...")
    results = vector_service.search(query, limit=1)
    
    print(f"Found {len(results)} results.")
    for res in results:
        print(f"Score: {res['score']}")
        print(f"Payload: {res['payload']}")

if __name__ == "__main__":
    asyncio.run(main())
