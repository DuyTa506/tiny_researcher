"""
Tool Registry

Core registry for tool registration and execution.
Uses decorator pattern for clean tool definition.
"""

from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field
import asyncio
import logging
import inspect

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Definition of a registered tool."""
    name: str
    description: str
    fn: Callable
    parameters: Dict[str, Any] = field(default_factory=dict)
    is_async: bool = True
    tags: List[str] = field(default_factory=list)


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in registry."""
    def __init__(self, tool_name: str):
        self.tool_name = tool_name
        super().__init__(f"Tool not found: {tool_name}")


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""
    def __init__(self, tool_name: str, error: Exception):
        self.tool_name = tool_name
        self.original_error = error
        super().__init__(f"Tool '{tool_name}' failed: {error}")


# Global registry
TOOL_REGISTRY: Dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    description: str,
    tags: List[str] = None
):
    """
    Decorator to register a function as a tool.
    
    Usage:
        @register_tool("arxiv_search", "Search ArXiv papers")
        async def arxiv_search(query: str, max_results: int = 20):
            ...
    """
    def decorator(func: Callable):
        # Generate parameter schema from function signature
        from src.tools.schema import generate_parameters_schema
        
        parameters = generate_parameters_schema(func)
        is_async = asyncio.iscoroutinefunction(func)
        
        tool_def = ToolDefinition(
            name=name,
            description=description,
            fn=func,
            parameters=parameters,
            is_async=is_async,
            tags=tags or []
        )
        
        TOOL_REGISTRY[name] = tool_def
        logger.info(f"Registered tool: {name}")
        
        return func
    
    return decorator


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Get a tool definition by name."""
    return TOOL_REGISTRY.get(name)


def list_tools(tag: str = None) -> List[ToolDefinition]:
    """List all registered tools, optionally filtered by tag."""
    tools = list(TOOL_REGISTRY.values())
    if tag:
        tools = [t for t in tools if tag in t.tags]
    return tools


async def execute_tool(name: str, **kwargs) -> Any:
    """
    Execute a registered tool by name.
    
    Args:
        name: Tool name
        **kwargs: Arguments to pass to the tool
        
    Returns:
        Tool execution result
        
    Raises:
        ToolNotFoundError: If tool not registered
        ToolExecutionError: If execution fails
    """
    tool = TOOL_REGISTRY.get(name)
    if not tool:
        raise ToolNotFoundError(name)
    
    try:
        logger.info(f"Executing tool: {name}", extra={"args": kwargs})
        
        if tool.is_async:
            result = await tool.fn(**kwargs)
        else:
            result = tool.fn(**kwargs)
        
        logger.info(f"Tool completed: {name}")
        return result
        
    except Exception as e:
        logger.error(f"Tool failed: {name}", exc_info=True)
        raise ToolExecutionError(name, e)


def get_tools_for_llm() -> List[Dict[str, Any]]:
    """
    Export tools in OpenAI function-calling format.
    
    Returns:
        List of tool definitions compatible with OpenAI API
    """
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            }
        }
        for tool in TOOL_REGISTRY.values()
    ]


def get_tools_description() -> str:
    """
    Get human-readable description of all tools.
    Used for including in prompts.
    """
    lines = ["Available tools:"]
    for tool in TOOL_REGISTRY.values():
        params = ", ".join(tool.parameters.get("required", []))
        lines.append(f"  - {tool.name}({params}): {tool.description}")
    return "\n".join(lines)
