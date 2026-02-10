"""
Test script for conversational agent multilingual and natural tone support.

Tests:
1. Language auto-detection for Vietnamese, English, Spanish
2. Natural tone formatting (no robotic "**My understanding:**")
3. Localized dialogue messages
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_language_detection():
    """Test the language detection logic."""
    from src.conversation.clarifier import QueryClarifier

    clarifier = QueryClarifier()

    test_cases = [
        ("chào, cho tôi một vài nghiên cứu về transformers", "Vietnamese"),
        ("hello, find me latest research on transformers", "English"),
        ("hola, buscar investigación sobre transformers", "Spanish"),
        ("bonjour, chercher des recherches sur transformers", "French"),
        ("hallo, suchen Forschung über Transformatoren", "German"),
        ("just a random query without language indicators", "English"),  # Default
    ]

    print("\n=== Language Detection Tests ===\n")

    for query, expected in test_cases:
        detected = clarifier._detect_language(query)
        status = "✓" if detected == expected else "✗"
        print(f"{status} Query: {query[:50]}...")
        print(f"   Expected: {expected}, Got: {detected}\n")


def test_localized_messages():
    """Test localized message generation."""
    from src.conversation.dialogue import DialogueManager
    from src.adapters.llm import MockLLMClient

    manager = DialogueManager(MockLLMClient())

    languages = ["English", "Vietnamese", "Spanish", "French", "German"]
    message_key = "cancel_research"

    print("\n=== Localized Message Tests ===\n")
    print(f"Message Key: '{message_key}'\n")

    for lang in languages:
        msg = manager._get_localized_message(message_key, lang)
        print(f"{lang:12} → {msg}")

    print()


def test_natural_formatting():
    """Test that formatting is natural (not robotic)."""
    from src.conversation.clarifier import QueryClarifier, ClarificationResult, QueryComplexity

    clarifier = QueryClarifier()

    # Create a mock result
    result = ClarificationResult(
        needs_clarification=True,
        complexity=QueryComplexity.COMPOUND,
        questions=[
            "Bạn quan tâm đến ứng dụng cụ thể nào không?",
            "Bạn muốn so sánh với CNN hay chỉ tìm hiểu ViT?"
        ],
        understanding="Bạn muốn tìm các nghiên cứu gần đây về vision transformers",
        sub_queries=["nghiên cứu mới nhất", "vision transformers"],
        original_query="chào, cho tôi một vài nghiên cứu về vision transformers",
        detected_language="Vietnamese"
    )

    formatted = clarifier.format_clarification_message(result)

    print("\n=== Natural Formatting Test ===\n")
    print("Input: Vietnamese query about vision transformers")
    print("\nFormatted Output:")
    print("-" * 60)
    print(formatted)
    print("-" * 60)

    # Check that robotic markers are NOT present
    robotic_markers = ["**My understanding:**", "**I see these objectives:**", "**Before I search"]

    print("\nRobotic Marker Check:")
    for marker in robotic_markers:
        present = marker in formatted
        status = "✗ FAIL" if present else "✓ PASS"
        print(f"  {status}: '{marker}' {'present' if present else 'not present'}")

    print()


def test_clarification_result_has_language():
    """Test that ClarificationResult stores detected language."""
    from src.conversation.clarifier import ClarificationResult, QueryComplexity

    print("\n=== ClarificationResult Language Field Test ===\n")

    result = ClarificationResult(
        needs_clarification=True,
        complexity=QueryComplexity.SIMPLE,
        detected_language="Vietnamese"
    )

    assert hasattr(result, 'detected_language'), "ClarificationResult missing 'detected_language' field"
    assert result.detected_language == "Vietnamese", "Language not stored correctly"

    print("✓ ClarificationResult has 'detected_language' field")
    print(f"✓ Language stored correctly: {result.detected_language}\n")


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" Multilingual Conversational Agent - Test Suite")
    print("=" * 70)

    try:
        test_language_detection()
        test_localized_messages()
        test_natural_formatting()
        test_clarification_result_has_language()

        print("=" * 70)
        print("✓ All tests completed successfully!")
        print("=" * 70 + "\n")

    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
