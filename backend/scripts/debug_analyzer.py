"""
Debug Analyzer - Test LLM scoring directly
"""

import asyncio
import sys
import os
import logging
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

from src.adapters.llm import LLMFactory
from src.core.models import Paper
from src.research.analysis.analyzer import AnalyzerService

async def main():
    print("=" * 60)
    print("  Debug: Analyzer Relevance Scoring")
    print("=" * 60)
    
    # Setup
    llm = LLMFactory.create_client(provider="openai")
    analyzer = AnalyzerService(llm)
    
    # Create test papers
    papers = [
        Paper(
            id="test_1",
            arxiv_id="2401.00001",
            title="Defending Against Prompt Injection in Large Language Models",
            abstract="We propose a novel defense mechanism against prompt injection attacks in LLMs. Our method uses input sanitization and output filtering to prevent malicious prompts from affecting model behavior."
        ),
        Paper(
            id="test_2", 
            arxiv_id="2401.00002",
            title="A Survey on Machine Translation",
            abstract="This paper surveys recent advances in machine translation using neural networks. We cover encoder-decoder architectures and attention mechanisms."
        ),
        Paper(
            id="test_3",
            arxiv_id="2401.00003",
            title="Jailbreak Attacks and Defenses for Large Language Models",
            abstract="We systematically study jailbreak attacks that bypass safety guardrails in LLMs and propose defensive measures including prompt filtering and response monitoring."
        )
    ]
    
    topic = "Prompt Injection Defense Mechanisms"
    
    print(f"\nTopic: {topic}")
    print(f"Papers: {len(papers)}")
    print("-" * 60)
    
    # Test batch analysis
    print("\n[1] Testing batch analysis...")
    evaluations = await analyzer._analyze_batch_llm(papers, topic)
    
    print(f"\n[2] Results ({len(evaluations)} evaluations):")
    for eval in evaluations:
        print(f"    Paper {eval.paper_id}: score={eval.score}, relevant={eval.is_relevant}")
        print(f"    Reasoning: {eval.reasoning[:100]}...")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
