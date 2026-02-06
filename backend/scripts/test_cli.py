#!/usr/bin/env python3
"""
Test script for CLI module.

Tests display components and basic CLI functionality.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.display import ResearchDisplay, StreamingDisplay
from src.cli.app import ResearchCLI


def test_display_components():
    """Test display utilities."""
    print("=" * 60)
    print("Testing Display Components")
    print("=" * 60)

    display = ResearchDisplay()

    # Test banner
    print("\n1. Testing banner...")
    display.print_banner()
    print("   ✅ Banner works")

    # Test messages
    print("\n2. Testing messages...")
    display.print_info("Info message test")
    display.print_success("Success message test")
    display.print_warning("Warning message test")
    print("   ✅ Messages work")

    # Test state
    print("\n3. Testing state indicator...")
    display.print_state("idle")
    display.print_state("clarifying")
    display.print_state("reviewing")
    display.print_state("executing")
    display.print_state("complete")
    print("   ✅ State indicator works")

    # Test divider
    print("\n4. Testing divider...")
    display.print_divider("Test Section")
    print("   ✅ Divider works")

    # Test help
    print("\n5. Testing help...")
    display.print_help()
    print("   ✅ Help works")

    return True


def test_streaming_display():
    """Test streaming display component."""
    print("\n" + "=" * 60)
    print("Testing Streaming Display")
    print("=" * 60)

    display = ResearchDisplay()
    streaming = StreamingDisplay(display.console)

    print("\n1. Testing streaming updates...")
    streaming.start()

    # Simulate updates
    phases = [
        ("Planning", "Generating plan...", 0),
        ("Execution", "Collecting papers...", 5),
        ("Analysis", "Scoring relevance...", 10),
        ("Complete", "Done!", 15),
    ]

    import time
    for phase, msg, papers in phases:
        streaming.update(phase=phase, message=msg, papers_collected=papers)
        time.sleep(0.3)

    streaming.stop()
    print("   ✅ Streaming display works")

    return True


async def test_cli_initialization():
    """Test CLI initialization with mock LLM."""
    print("\n" + "=" * 60)
    print("Testing CLI Initialization")
    print("=" * 60)

    class MockLLMClient:
        async def generate(self, prompt: str, **kwargs) -> str:
            return "Mock response"

    print("\n1. Creating CLI with mock LLM...")
    cli = ResearchCLI(llm_client=MockLLMClient(), user_id="test_user")
    print("   ✅ CLI created")

    print("\n2. Initializing CLI...")
    await cli.initialize()
    print(f"   Conversation ID: {cli.conversation_id[:8]}...")
    print("   ✅ CLI initialized")

    print("\n3. Cleaning up...")
    await cli.cleanup()
    print("   ✅ CLI cleanup complete")

    return True


async def main():
    """Run all CLI tests."""
    print("=" * 60)
    print("CLI Module Test Suite")
    print("=" * 60)

    results = []

    # Sync tests
    results.append(("Display Components", test_display_components()))
    results.append(("Streaming Display", test_streaming_display()))

    # Async tests
    results.append(("CLI Initialization", await test_cli_initialization()))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("✅ ALL CLI TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
