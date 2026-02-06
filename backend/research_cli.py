#!/usr/bin/env python3
"""
Research Assistant CLI

Usage:
    python research_cli.py [--mock] [--user USER_ID]

Options:
    --mock      Use mock LLM for testing (no API key needed)
    --user      Set user ID for memory personalization

Examples:
    python research_cli.py                    # Run with Gemini/OpenAI
    python research_cli.py --mock             # Run with mock LLM
    python research_cli.py --user researcher1 # Custom user ID
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()


class MockLLMClient:
    """Mock LLM for testing without API keys."""

    async def generate(self, prompt: str, json_mode: bool = False, **kwargs) -> str:
        prompt_lower = prompt.lower()

        # Plan generation
        if "research plan" in prompt_lower or "available_tools" in prompt_lower:
            return '''{
                "topic": "Test Topic",
                "summary": "Test research plan",
                "steps": [
                    {
                        "id": 1,
                        "action": "research",
                        "title": "Search arXiv",
                        "description": "Find papers on arXiv",
                        "queries": ["test query"],
                        "sources": ["arxiv"],
                        "tool": "arxiv_search",
                        "tool_args": {"query": "test", "max_results": 5}
                    }
                ]
            }'''

        # Query clarification
        if "analyze" in prompt_lower and "query" in prompt_lower:
            if "and" in prompt_lower or "," in prompt_lower:
                return """UNDERSTANDING: User wants to research a compound topic
SUBQUERIES: first objective | second objective
QUESTIONS: What's your primary focus? | Are you looking for existing research or exploring new ideas?"""
            return """UNDERSTANDING: Simple research query
SUBQUERIES: none
QUESTIONS: none"""

        # Query type detection
        if "query type" in prompt_lower or ("analyze" in prompt_lower and "research" in prompt_lower):
            return """TYPE: full
COMPLEXITY: moderate
TOPIC: research topic"""

        return "Mock response"

    async def generate_stream(self, prompt: str, system_instruction: str = None):
        """Mock streaming - yields response word by word."""
        response = await self.generate(prompt)
        words = response.split()
        for i, word in enumerate(words):
            yield word
            if i < len(words) - 1:
                yield " "


async def run_cli(mock: bool = False, user_id: str = "cli_user"):
    """Run the CLI with specified configuration."""
    from src.cli.app import ResearchCLI
    from src.cli.display import ResearchDisplay

    display = ResearchDisplay()

    # Select LLM client
    if mock:
        display.print_info("Running in MOCK mode (no API calls)")
        llm = MockLLMClient()
    else:
        # Try Gemini first
        gemini_key = os.getenv("GEMINI_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")

        if gemini_key:
            from src.adapters.llm import GeminiClient
            llm = GeminiClient(api_key=gemini_key)
            display.print_info("Using Gemini API")
        elif openai_key:
            from src.adapters.llm import OpenAIClient
            llm = OpenAIClient(api_key=openai_key)
            display.print_info("Using OpenAI API")
        else:
            display.print_error("No API key found!")
            display.console.print("""
[bold]Setup required:[/bold]

1. Create a .env file with your API key:
   [cyan]GEMINI_API_KEY=your_key_here[/cyan]
   or
   [cyan]OPENAI_API_KEY=your_key_here[/cyan]

2. Or run in mock mode for testing:
   [cyan]python research_cli.py --mock[/cyan]
            """)
            sys.exit(1)

    # Create and run CLI
    cli = ResearchCLI(llm_client=llm, user_id=user_id, enable_streaming=not mock)
    await cli.run()


def main():
    """Parse arguments and run CLI."""
    parser = argparse.ArgumentParser(
        description="Research Assistant CLI - Intelligent Paper Discovery"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock LLM for testing"
    )
    parser.add_argument(
        "--user",
        default="cli_user",
        help="User ID for memory personalization"
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming output"
    )

    args = parser.parse_args()

    try:
        asyncio.run(run_cli(mock=args.mock, user_id=args.user))
    except KeyboardInterrupt:
        print("\nGoodbye!")


if __name__ == "__main__":
    main()
