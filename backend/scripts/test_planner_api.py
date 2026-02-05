"""
Test: Planner API Endpoints

Run this after starting the API server:
  uvicorn src.api.main:app --reload
"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000/api/v1/plan"

async def test_planner_api():
    print("=" * 60)
    print("  Testing Planner API Endpoints")
    print("=" * 60)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Create plan
        print("\n[1] POST /plan - Create new plan")
        response = await client.post(BASE_URL, json={
            "topic": "Agentic AI Workflows",
            "keywords": ["AI agent", "autonomous agent"],
            "sources": ["https://arxiv.org/abs/2308.15363"],
            "research_questions": ["What are the key components?"],
            "language": "vi"
        })
        print(f"    Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            plan_id = data["plan_id"]
            print(f"    Plan ID: {plan_id}")
            print(f"    Plan Status: {data['status']}")
            print(f"    Steps: {len(data['plan']['steps'])}")
            print(f"\n    Display:\n{data['display'][:500]}...")
            
            # 2. Get plan
            print("\n[2] GET /plan/{id} - Get plan")
            response = await client.get(f"{BASE_URL}/{plan_id}")
            print(f"    Status: {response.status_code}")
            
            # 3. Update plan
            print("\n[3] PUT /plan/{id} - Update plan")
            updated_steps = data['plan']['steps'][:3]  # Keep first 3 steps
            updated_steps[0]['title'] = "UPDATED: " + updated_steps[0]['title']
            
            response = await client.put(f"{BASE_URL}/{plan_id}", json={
                "steps": updated_steps
            })
            print(f"    Status: {response.status_code}")
            if response.status_code == 200:
                print(f"    Updated step 1 title: {response.json()['plan']['steps'][0]['title']}")
            
            # 4. Delete plan
            print("\n[4] DELETE /plan/{id} - Delete plan")
            response = await client.delete(f"{BASE_URL}/{plan_id}")
            print(f"    Status: {response.status_code}")
            
        else:
            print(f"    Error: {response.text}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_planner_api())
