"""
Test Tool Registry

Verifies the lightweight tool registry works correctly.
"""

import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

async def main():
    print("=" * 60)
    print("  Testing Tool Registry")
    print("=" * 60)
    
    # Import tools module (this registers all built-in tools)
    from src.tools import (
        TOOL_REGISTRY,
        get_tools_for_llm,
        get_tools_description,
        execute_tool,
        list_tools
    )
    
    # --- 1. List registered tools ---
    print("\n[1] Registered Tools:")
    tools = list_tools()
    for tool in tools:
        print(f"    - {tool.name}: {tool.description[:50]}...")
        print(f"      Tags: {tool.tags}")
    
    print(f"\n    Total: {len(tools)} tools")
    
    # --- 2. Get OpenAI-compatible schema ---
    print("\n[2] OpenAI Function Schema:")
    schemas = get_tools_for_llm()
    for schema in schemas[:2]:  # Show first 2
        print(f"    {schema['function']['name']}:")
        params = schema['function']['parameters']
        print(f"      Required: {params.get('required', [])}")
    
    # --- 3. Get description for prompts ---
    print("\n[3] Tools Description (for LLM prompts):")
    desc = get_tools_description()
    print(desc)
    
    # --- 4. Execute a tool ---
    print("\n[4] Execute Tool: arxiv_search")
    try:
        results = await execute_tool(
            "arxiv_search",
            query="transformer attention",
            max_results=3
        )
        print(f"    Found {len(results)} papers")
        if results:
            print(f"    First: {results[0]['title'][:50]}...")
    except Exception as e:
        print(f"    Error: {e}")
    
    # --- 5. Test error handling ---
    print("\n[5] Test Error Handling:")
    try:
        await execute_tool("nonexistent_tool", query="test")
    except Exception as e:
        print(f"    Caught expected error: {type(e).__name__}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(main())
