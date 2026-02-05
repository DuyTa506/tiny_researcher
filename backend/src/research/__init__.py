"""
Research Module

This module handles the research pipeline:
- ingestion/: Data collection (ArxivSearcher, HuggingFaceSearcher, Collectors)
- analysis/: AI processing (Analyzer, Summarizer, Clusterer)
- synthesis/: Output generation (Writer)

Import submodules directly to avoid circular imports:
  from src.research.ingestion import ArxivSearcher
  from src.research.analysis import AnalyzerService
"""

# Lazy imports to avoid circular dependencies
__all__ = [
    "ingestion",
    "analysis", 
    "synthesis"
]
