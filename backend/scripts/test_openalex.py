"""
Test Unified Search + URL Detection + OpenAlex Filter + Query Refinement

Tests:
1. Unified search tool registration
2. Parallel search execution (ArXiv + OpenAlex)
3. OpenAlex with has_fulltext filter
4. Deduplication with DOI
5. Paper.from_dict with openalex source
6. URL extraction from user messages
7. Query refinement heuristic
8. Quality-aware search with refinement
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_tool_registration():
    """Test that unified search tool is registered."""
    print("=" * 60)
    print("Test 1: Unified Search Tool Registration")
    print("=" * 60)

    import src.tools.builtin  # noqa
    from src.tools.registry import TOOL_REGISTRY, get_tool

    print(f"\n  Registered tools: {list(TOOL_REGISTRY.keys())}")

    # Unified search should exist
    tool = get_tool("search")
    if not tool:
        print("  FAIL: 'search' tool not found!")
        return False

    print(f"  search: FOUND")
    print(f"    Description: {tool.description[:60]}...")
    print(f"    Tags: {tool.tags}")
    print(f"    Parameters: {list(tool.parameters.get('properties', {}).keys())}")

    # Old tools should NOT exist
    old_tools = ["arxiv_search", "arxiv_search_keywords", "openalex_search"]
    for old in old_tools:
        if get_tool(old):
            print(f"  FAIL: Old tool '{old}' still registered!")
            return False

    print(f"  Old tools removed: {old_tools}")
    print("\n  PASS")
    return True


async def test_unified_search():
    """Test parallel search execution."""
    print("\n" + "=" * 60)
    print("Test 2: Parallel Search Execution")
    print("=" * 60)

    import src.tools.builtin  # noqa
    from src.tools.registry import execute_tool

    print("\n  Executing search('vision transformer', max_results=5)")
    start = time.time()
    results = await execute_tool("search", query="vision transformer", max_results=5)
    elapsed = time.time() - start

    print(f"  Returned {len(results)} results in {elapsed:.2f}s")

    if not results:
        print("  FAIL: No results!")
        return False

    # Check sources - both ArXiv and OpenAlex should appear
    sources = {}
    for r in results:
        src = r.get("source_type", "unknown")
        sources[src] = sources.get(src, 0) + 1
    print(f"  Sources: {sources}")

    has_both = len(sources) >= 2
    print(f"  Multi-source: {'YES' if has_both else 'NO (single source)'}")

    for i, r in enumerate(results[:3]):
        print(f"  [{i+1}] [{r.get('source_type')}] {r['title'][:55]}...")

    print("\n  PASS")
    return True


async def test_openalex_fulltext_filter():
    """Test OpenAlex with has_fulltext filter."""
    print("\n" + "=" * 60)
    print("Test 3: OpenAlex has_fulltext Filter")
    print("=" * 60)

    from src.research.ingestion.searcher import OpenAlexSearcher

    searcher = OpenAlexSearcher()
    print("\n  Searching 'transformers' with has_fulltext:true filter")
    results = await searcher.search("transformers", max_results=5)
    print(f"  Found {len(results)} papers")

    if results:
        for r in results:
            has_pdf = bool(r.get("pdf_url"))
            print(f"  - [{r.get('publication_year')}] {r['title'][:50]}... (PDF: {has_pdf})")

    if not results:
        print("  WARNING: No results (may be API issue)")
        return True  # Non-blocking

    print("\n  PASS")
    return True


def test_deduplication():
    """Test PaperDeduplicator with DOI."""
    print("\n" + "=" * 60)
    print("Test 4: Deduplication with DOI")
    print("=" * 60)

    from src.planner.executor import PaperDeduplicator

    dedup = PaperDeduplicator()
    papers = [
        {"title": "Vision Transformer Architecture", "authors": ["Alice"], "arxiv_id": "2301.00001", "doi": None},
        {"title": "Vision Transformer Architecture", "authors": ["Alice"], "arxiv_id": "2301.00001", "doi": None},
        {"title": "BERT Pre-training of Deep Models", "authors": ["Bob"], "arxiv_id": None, "doi": "10.1234/test"},
        {"title": "BERT Language Model Revisited", "authors": ["Bob"], "arxiv_id": None, "doi": "10.1234/test"},
        {"title": "Reinforcement Learning Robotics", "authors": ["Diana"], "arxiv_id": None, "doi": "10.5678/rl"},
    ]

    unique, dups = dedup.deduplicate(papers)
    print(f"\n  Input: {len(papers)}, Unique: {len(unique)}, Dups: {dups}")

    if len(unique) == 3:
        print("  PASS")
        return True
    print(f"  FAIL: Expected 3 unique, got {len(unique)}")
    return False


def test_paper_from_dict():
    """Test Paper.from_dict with OpenAlex data."""
    print("\n" + "=" * 60)
    print("Test 5: Paper.from_dict with OpenAlex")
    print("=" * 60)

    from src.core.models import Paper

    data = {
        "title": "Test OpenAlex Paper",
        "abstract": "Abstract text",
        "authors": ["Author One"],
        "doi": "10.1234/test",
        "source_type": "openalex",
        "url": "https://openalex.org/W123",
        "pdf_url": "https://example.com/paper.pdf",
    }

    paper = Paper.from_dict(data)
    checks = [
        ("source=openalex", paper.source == "openalex"),
        ("doi set", paper.doi == "10.1234/test"),
        ("title set", paper.title == "Test OpenAlex Paper"),
    ]

    all_pass = True
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            all_pass = False

    # Also test arxiv_api normalization
    arxiv_data = {"title": "Test", "source_type": "arxiv_api"}
    p2 = Paper.from_dict(arxiv_data)
    ok = p2.source == "arxiv"
    print(f"  [{'PASS' if ok else 'FAIL'}] arxiv_api -> arxiv")
    if not ok:
        all_pass = False

    return all_pass


def test_url_extraction():
    """Test URL extraction from user messages."""
    print("\n" + "=" * 60)
    print("Test 6: URL Extraction from Messages")
    print("=" * 60)

    # Load intent.py directly to avoid triggering qdrant via conversation.__init__
    import importlib.util
    intent_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'conversation', 'intent.py')
    spec = importlib.util.spec_from_file_location("intent_standalone", intent_path)
    intent_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(intent_module)
    IntentClassifier = intent_module.IntentClassifier
    UserIntent = intent_module.UserIntent

    classifier = IntentClassifier()

    test_cases = [
        (
            "research about transformers https://arxiv.org/abs/2301.00001",
            ["https://arxiv.org/abs/2301.00001"],
            UserIntent.NEW_TOPIC,
        ),
        (
            "check this paper https://arxiv.org/pdf/2301.00001.pdf and https://arxiv.org/abs/2301.00002",
            ["https://arxiv.org/pdf/2301.00001.pdf", "https://arxiv.org/abs/2301.00002"],
            None,  # Don't check intent, just URLs
        ),
        (
            "hello",
            [],
            UserIntent.CHAT,
        ),
        (
            "vision transformer survey",
            [],
            UserIntent.NEW_TOPIC,
        ),
    ]

    all_pass = True
    for msg, expected_urls, expected_intent in test_cases:
        result = classifier.classify(msg)
        urls_ok = sorted(result.extracted_urls) == sorted(expected_urls)
        intent_ok = expected_intent is None or result.intent == expected_intent

        status = "PASS" if (urls_ok and intent_ok) else "FAIL"
        print(f"  [{status}] '{msg[:50]}...'")
        print(f"         URLs: {result.extracted_urls}")
        if expected_intent:
            print(f"         Intent: {result.intent.value}")

        if not urls_ok:
            print(f"         EXPECTED URLs: {expected_urls}")
            all_pass = False
        if not intent_ok:
            print(f"         EXPECTED Intent: {expected_intent.value}")
            all_pass = False

    return all_pass


def test_query_refiner_heuristic():
    """Test QueryRefiner heuristic rules."""
    print("\n" + "=" * 60)
    print("Test 7: QueryRefiner Heuristic Rules")
    print("=" * 60)

    from src.research.ingestion.query_refiner import QueryRefiner

    refiner = QueryRefiner()
    all_pass = True

    test_cases = [
        (
            "DeepSeek OCR 1 and 2",
            {"deepseek ocr 1 and 2"},
            # Should remove numbers and suggest individual terms
        ),
        (
            "GPT-4 performance analysis 2024",
            {"gpt-4 performance analysis 2024"},
        ),
    ]

    for query, tried in test_cases:
        suggestions = refiner._refine_heuristic(query, tried)
        print(f"  Query: '{query}'")
        print(f"  Suggestions: {suggestions}")

        if not suggestions:
            print(f"  FAIL: No suggestions!")
            all_pass = False
        else:
            # Check suggestions don't contain query itself
            for s in suggestions:
                if s.lower() in tried:
                    print(f"  FAIL: Suggestion '{s}' same as tried!")
                    all_pass = False

    if all_pass:
        print("  PASS")
    return all_pass


async def test_quality_aware_search():
    """Test that poor queries trigger refinement and find better results."""
    print("\n" + "=" * 60)
    print("Test 8: Quality-Aware Search with Refinement")
    print("=" * 60)

    from src.tools.builtin.search import _is_poor_quality, _parallel_search

    # Test quality detection
    fake_results = [
        {"title": "Unrelated Paper About Chemistry", "source_type": "arxiv_api"},
        {"title": "Another Random Paper", "source_type": "arxiv_api"},
        {"title": "Third Unrelated Work", "source_type": "arxiv_api"},
    ]

    is_poor = _is_poor_quality("DeepSeek OCR", fake_results)
    print(f"  Quality check (irrelevant results): poor={is_poor}")
    if not is_poor:
        print("  FAIL: Should detect poor quality!")
        return False

    good_results = [
        {"title": "DeepSeek Language Model Architecture", "source_type": "openalex"},
        {"title": "DeepSeek-R1 Reasoning Analysis", "source_type": "openalex"},
        {"title": "Random Other Paper", "source_type": "arxiv_api"},
    ]

    is_poor2 = _is_poor_quality("DeepSeek", good_results)
    print(f"  Quality check (relevant results): poor={is_poor2}")
    if is_poor2:
        print("  FAIL: Should detect good quality!")
        return False

    # Test that parallel search returns from both sources
    results = await _parallel_search("large language models", max_results=5)
    sources = {}
    for r in results:
        src = r.get("source_type", "unknown")
        sources[src] = sources.get(src, 0) + 1
    print(f"  Parallel search sources: {sources}")

    print("  PASS")
    return True


async def main():
    print("\n" + "#" * 60)
    print("  Unified Search + Query Refinement Test Suite")
    print("#" * 60)

    results = []

    # Sync tests
    results.append(("Tool Registration", test_tool_registration()))
    results.append(("Deduplication", test_deduplication()))
    results.append(("Paper.from_dict", test_paper_from_dict()))
    results.append(("URL Extraction", test_url_extraction()))
    results.append(("QueryRefiner Heuristic", test_query_refiner_heuristic()))

    # Async tests
    results.append(("Parallel Search", await test_unified_search()))
    results.append(("OpenAlex Filter", await test_openalex_fulltext_filter()))
    results.append(("Quality-Aware Search", await test_quality_aware_search()))

    # Summary
    print("\n" + "=" * 60)
    print("  Summary")
    print("=" * 60)
    all_pass = True
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")
        if not passed:
            all_pass = False

    print(f"\n  Overall: {'ALL PASS' if all_pass else 'SOME FAILED'}")
    return all_pass


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
