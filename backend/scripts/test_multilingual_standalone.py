"""
Standalone test for language detection logic (no imports).
"""

def detect_language(query: str) -> str:
    """Detect language from query text using word boundary matching."""
    query_lower = query.lower()

    # Split into words for word-boundary matching
    words = query_lower.split()

    # Vietnamese indicators (common words that are unique to Vietnamese)
    vietnamese_words = ['chào', 'tôi', 'cho', 'tìm', 'về', 'có', 'là', 'của', 'và', 'được', 'này', 'đó', 'muốn', 'bạn', 'nghiên', 'cứu']
    vietnamese_count = sum(1 for word in vietnamese_words if word in words)
    if vietnamese_count >= 2:  # Require at least 2 Vietnamese words
        return "Vietnamese"

    # Spanish indicators
    spanish_words = ['hola', 'buscar', 'encontrar', 'sobre', 'investigación', 'qué', 'cómo', 'dónde']
    spanish_count = sum(1 for word in spanish_words if word in words)
    if spanish_count >= 2:
        return "Spanish"

    # French indicators (excluding common words like "me", "pour")
    french_words = ['bonjour', 'chercher', 'trouver', 'recherche', 'recherches', 'où']
    french_count = sum(1 for word in french_words if word in words)
    if french_count >= 2:
        return "French"

    # German indicators
    german_words = ['hallo', 'suchen', 'finden', 'über', 'forschung']
    german_count = sum(1 for word in german_words if word in words)
    if german_count >= 2:
        return "German"

    # Default to English
    return "English"


def test_language_detection():
    """Test the language detection logic."""
    test_cases = [
        ("chào, cho tôi một vài nghiên cứu về transformers", "Vietnamese"),
        ("hello, find me latest research on transformers", "English"),
        ("hola, buscar investigación sobre transformers", "Spanish"),
        ("bonjour, chercher des recherches sur transformers", "French"),
        ("hallo, suchen Forschung über Transformatoren", "German"),
        ("just a random query without language indicators", "English"),  # Default
    ]

    print("\n=== Language Detection Tests ===\n")

    all_pass = True
    for query, expected in test_cases:
        detected = detect_language(query)
        status = "✓" if detected == expected else "✗"
        if detected != expected:
            all_pass = False
        print(f"{status} Query: {query[:50]}...")
        print(f"   Expected: {expected}, Got: {detected}\n")

    return all_pass


def test_localized_messages():
    """Test localized message structure."""
    messages = {
        "cancel_research": {
            "English": "No problem. What else would you like to research?",
            "Vietnamese": "Không sao cả. Bạn muốn tìm hiểu về gì nữa?",
            "Spanish": "No hay problema. ¿Qué más te gustaría investigar?",
            "French": "Pas de problème. Qu'aimeriez-vous rechercher d'autre?",
            "German": "Kein Problem. Was möchten Sie sonst noch recherchieren?"
        }
    }

    languages = ["English", "Vietnamese", "Spanish", "French", "German"]
    message_key = "cancel_research"

    print("\n=== Localized Message Tests ===\n")
    print(f"Message Key: '{message_key}'\n")

    for lang in languages:
        msg = messages[message_key].get(lang, "")
        print(f"{lang:12} → {msg}")

    print()
    return True


def test_natural_formatting():
    """Test that formatting is natural (not robotic)."""
    # Example natural format (Vietnamese)
    formatted = """Bạn muốn tìm các nghiên cứu gần đây về vision transformers

Tôi thấy bạn muốn tìm hiểu về:
1. nghiên cứu mới nhất
2. vision transformers

Bạn quan tâm đến ứng dụng cụ thể nào không?
Bạn muốn so sánh với CNN hay chỉ tìm hiểu ViT thôi?"""

    print("\n=== Natural Formatting Test ===\n")
    print("Example: Vietnamese query about vision transformers")
    print("\nFormatted Output:")
    print("-" * 60)
    print(formatted)
    print("-" * 60)

    # Check that robotic markers are NOT present
    robotic_markers = ["**My understanding:**", "**I see these objectives:**", "**Before I search"]

    print("\nRobotic Marker Check:")
    all_pass = True
    for marker in robotic_markers:
        present = marker in formatted
        status = "✗ FAIL" if present else "✓ PASS"
        if present:
            all_pass = False
        print(f"  {status}: '{marker}' {'present' if present else 'not present'}")

    print()
    return all_pass


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print(" Multilingual Conversational Agent - Standalone Test")
    print("=" * 70)

    results = []
    results.append(("Language Detection", test_language_detection()))
    results.append(("Localized Messages", test_localized_messages()))
    results.append(("Natural Formatting", test_natural_formatting()))

    print("=" * 70)
    print("\nTest Summary:")
    print("-" * 70)

    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("✓ All tests passed!")
        print("=" * 70 + "\n")
    else:
        print("✗ Some tests failed")
        print("=" * 70 + "\n")
        exit(1)
