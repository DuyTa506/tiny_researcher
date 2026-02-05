
import asyncio
import sys
import os
from unittest.mock import MagicMock

# Mock external dependencies
sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()

mock_config = MagicMock()
mock_config.settings.DATABASE_URL = "postgresql+asyncpg://mock:mock@localhost/mock"
mock_config.settings.ENVIRONMENT = "testing"
sys.modules["src.core.config"] = mock_config

from sqlalchemy.orm import DeclarativeBase
class MockBase(DeclarativeBase):
    pass
mock_db = MagicMock()
mock_db.Base = MockBase
sys.modules["src.core.database"] = mock_db

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from src.adapters.llm import LLMFactory
from src.planner.service import PlannerService
from src.core.schema import ResearchRequest, TimeWindow, OutputConfig
from datetime import date

async def main():
    print("=== Test: Planner with ResearchRequest ===\n")
    
    llm = LLMFactory.create_client(provider="gemini", api_key="test-key")
    planner = PlannerService(llm)
    
    # --- Test 1: Minimal Input (Only Topic) ---
    print("[1] Minimal Input (Topic only)")
    request1 = ResearchRequest(topic="Network Intrusion Detection")
    plan1 = await planner.generate_research_plan(request1)
    print(f"  Topic: {plan1.topic}")
    print(f"  Keywords (Autofilled): {plan1.keywords}")
    print(f"  Questions (Autofilled): {plan1.research_questions}")
    print(f"  Sources (Default): {plan1.sources}")
    print()
    
    # --- Test 2: Full Input ---
    print("[2] Full Input (User provides everything)")
    request2 = ResearchRequest(
        topic="Large Language Models",
        keywords=["LLM", "GPT", "Transformer"],
        research_questions=["What are SOTA LLMs?", "Scaling laws?"],
        sources=["https://arxiv.org/rss/cs.CL"],
        time_window=TimeWindow(start=date(2023, 1, 1), end=date(2024, 1, 1)),
        output_config=OutputConfig(max_papers=50, language="en")
    )
    plan2 = await planner.generate_research_plan(request2)
    print(f"  Topic: {plan2.topic}")
    print(f"  Keywords (Expanded): {plan2.keywords}")
    print(f"  Questions: {plan2.research_questions}")
    print(f"  Time Window: {plan2.time_window.start} to {plan2.time_window.end}")
    print(f"  Max Papers: {plan2.max_papers}")
    print()
    
    print("=== All Tests Passed ===")

if __name__ == "__main__":
    asyncio.run(main())
