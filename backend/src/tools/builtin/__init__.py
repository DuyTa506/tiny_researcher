"""
Built-in Tools

Auto-registered tools for research operations.
Import this module to register all built-in tools.
"""

# Import tool modules to trigger registration
from src.tools.builtin import search
from src.tools.builtin import huggingface
from src.tools.builtin import collector

__all__ = ["search", "huggingface", "collector"]
