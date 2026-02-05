
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock

# --- MOCKING ENV BEFORE IMPORTS ---
# Mock external heavy libs and DB drivers
sys.modules["qdrant_client"] = MagicMock()
sys.modules["qdrant_client.http"] = MagicMock()
sys.modules["sentence_transformers"] = MagicMock()
sys.modules["sklearn"] = MagicMock()
sys.modules["sklearn.cluster"] = MagicMock()

# Mock src.core.config
mock_config = MagicMock()
mock_config.settings.DATABASE_URL = "postgresql+asyncpg://mock:mock@localhost/mock"
mock_config.settings.ENVIRONMENT = "testing"
sys.modules["src.core.config"] = mock_config

# Mock src.core.database BEFORE it gets imported by models
from sqlalchemy.orm import DeclarativeBase
class MockBase(DeclarativeBase):
    pass
mock_db = MagicMock()
mock_db.Base = MockBase # Inject Base so models.py can inherit
sys.modules["src.core.database"] = mock_db

# Add src to pythonpath
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Now safe to import services
from src.adapters.llm import LLMFactory
from src.planner.service import PlannerService
from src.research.analysis.analyzer import AnalyzerService
from src.research.analysis.summarizer import SummarizerService
from src.research.analysis.clusterer import ClustererService
from src.research.synthesis.writer import WriterService
from src.storage.vector_store import VectorService
from src.core.models import Paper

async def main():
    print("--- Starting Debate Flow Test (Mocked Env) ---")
    
    # 1. Setup Services
    llm = LLMFactory.create_client(provider="gemini", api_key="test-key")
    
    # Mock VectorService methods since we didn't mock the class itself but its deps
    vector_service = VectorService()
    vector_service.embed_text = MagicMock(return_value=[0.1, 0.2, 0.3])
    
    planner = PlannerService(llm)
    analyzer = AnalyzerService(llm)
    summarizer = SummarizerService(llm)
    clusterer = ClustererService(llm, vector_service)
    writer = WriterService()
    
    topic = "Agentic AI Workflows"
    
    # 2. Plan
    print(f"\n[1] Planning research for: {topic}")
    plan = await planner.generate_research_plan(topic)
    print("Plan:", plan)
    
    # 3. Execution Loop (Mocked)
    print("\n[2] Executing Research Loop (Mocking Search/Ingestion)")
    
    # Mock papers that would be found
    mock_papers = [
        Paper(title="Agentic Patterns", abstract="Agents use tools and feedback loops. ReAct is popular.", url="http://p1", authors=["A"], published_date="2024-01-01"),
        Paper(title="Multi-Agent Debate", abstract="Agents debating improves factuality. Consensus is key.", url="http://p2", authors=["B"], published_date="2024-02-01"),
        Paper(title="Workflow Automation", abstract="Static workflows vs dynamic agentic limits.", url="http://p3", authors=["C"], published_date="2024-03-01")
    ]
    
    # Store findings strings for debate
    findings = [p.abstract for p in mock_papers]
    
    # 4. Critique / Gap Detection
    print("\n[3] Critiquing Findings & Detecting Gaps")
    gaps = await analyzer.detect_gaps(findings, topic)
    print("Identified Gaps/Follow-up Queries:", gaps)
    
    # 5. Summarize (Mocked Enrichment)
    print("\n[4] Summarizing Papers")
    for p in mock_papers:
        p.summary = await summarizer.summarize_paper(p)
        print(f"Summary for {p.title}: {p.summary.get('one_sentence_summary', 'N/A')}")
        
    # 6. Cluster
    print("\n[5] Clustering")
    clusters = await clusterer.cluster_papers(mock_papers)
    print(f"Formed {len(clusters)} clusters")
    for c in clusters:
        print(f" - Cluster {c.id}: {c.name} ({len(c.paper_indices)} papers)")
        
    # 7. Write Report
    print("\n[6] Writing Report")
    report = writer.format_report_with_papers(clusters, mock_papers, topic)
    print("\n--- Final Report Preview ---\n")
    print(report[:500] + "...")
    
    print("\n--- Test Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(main())
