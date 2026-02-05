"""
Schema Generator

Generates OpenAI-compatible JSON Schema from Python function signatures.
Supports type hints for automatic schema generation.
"""

from typing import Callable, Dict, Any, get_type_hints, get_origin, get_args
import inspect


# Python type to JSON Schema type mapping
TYPE_MAP = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
    type(None): "null"
}


def python_type_to_json_schema(py_type: type) -> Dict[str, Any]:
    """
    Convert Python type hint to JSON Schema.
    
    Examples:
        str -> {"type": "string"}
        list[str] -> {"type": "array", "items": {"type": "string"}}
        Optional[int] -> {"type": "integer"}
    """
    origin = get_origin(py_type)
    
    # Handle generic types (list[str], dict[str, int], etc.)
    if origin is list:
        args = get_args(py_type)
        item_type = args[0] if args else str
        return {
            "type": "array",
            "items": python_type_to_json_schema(item_type)
        }
    
    if origin is dict:
        return {"type": "object"}
    
    # Handle Optional[T] (Union[T, None])
    if origin is type(None) or py_type is type(None):
        return {"type": "null"}
    
    # Handle basic types
    if py_type in TYPE_MAP:
        return {"type": TYPE_MAP[py_type]}
    
    # Default to string for unknown types
    return {"type": "string"}


def generate_parameters_schema(func: Callable) -> Dict[str, Any]:
    """
    Generate OpenAI-compatible parameters schema from function signature.
    
    Args:
        func: Function to analyze
        
    Returns:
        JSON Schema for function parameters
        
    Example:
        def search(query: str, max_results: int = 20):
            ...
            
        Returns:
        {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": ""},
                "max_results": {"type": "integer", "description": ""}
            },
            "required": ["query"]
        }
    """
    sig = inspect.signature(func)
    
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}
    
    properties = {}
    required = []
    
    for param_name, param in sig.parameters.items():
        # Skip self, cls, *args, **kwargs
        if param_name in ("self", "cls"):
            continue
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
        
        # Get type hint
        py_type = hints.get(param_name, str)
        
        # Handle Optional types
        origin = get_origin(py_type)
        if origin is type(None):
            py_type = str
        
        # Build property schema
        prop_schema = python_type_to_json_schema(py_type)
        prop_schema["description"] = ""  # Could extract from docstring
        
        properties[param_name] = prop_schema
        
        # Check if required (no default value)
        if param.default is inspect.Parameter.empty:
            required.append(param_name)
    
    return {
        "type": "object",
        "properties": properties,
        "required": required
    }
