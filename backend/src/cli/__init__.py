"""
CLI Module - Interactive command-line interface for the research assistant.

Features:
- Colorful output using Rich
- Streaming display during research
- Interactive conversation flow
- Progress indicators for each phase
"""

from src.cli.app import ResearchCLI, main
from src.cli.display import ResearchDisplay, StreamingDisplay

__all__ = ["ResearchCLI", "main", "ResearchDisplay", "StreamingDisplay"]
