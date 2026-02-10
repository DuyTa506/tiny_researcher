"""
Tools Module

Lightweight tool registry for dynamic tool discovery and execution.
Tools are thin wrappers around actual implementations in research/ingestion/.

Usage:
    from src.tools import execute_tool, get_tools_for_llm, TOOL_REGISTRY
    
    # Execute a tool
    results = await execute_tool("search", query="LLM agents")
    
    # Get tools in OpenAI format for LLM
    tools_schema = get_tools_for_llm()
"""

from src.tools.registry import (
    TOOL_REGISTRY,
    ToolDefinition,
    register_tool,
    execute_tool,
    get_tools_for_llm,
    get_tools_description,
    get_tool,
    list_tools
)

# Import built-in tools to register them
from src.tools import builtin

__all__ = [
    "TOOL_REGISTRY",
    "ToolDefinition", 
    "register_tool",
    "execute_tool",
    "get_tools_for_llm",
    "get_tools_description",
    "get_tool",
    "list_tools"
]
