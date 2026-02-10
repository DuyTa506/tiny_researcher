
from typing import Dict, Any

# Shared JSON output contract - prepended to all JSON-returning prompts.
_JSON_CONTRACT = """IMPORTANT OUTPUT RULES:
- Output must be valid JSON. No Markdown, no code fences, no comments.
- Use double quotes for all strings.
- If information is missing: use empty string "" for text fields, empty array [] for lists, and confidence 0. Do not guess.
- Never invent citations or snippets; snippets must be exact substrings from the provided content.
"""

# Shared language rule - appended to prompts that accept {language}.
_LANGUAGE_RULE = """
LANGUAGE RULES:
- Write all output text fields in {language}.
- Keep search queries, technical terms, dataset names, and metric names in English.
- Do not mix languages except for established technical terminology."""


class PromptManager:
    """
    Centralized manager for all LLM prompts.
    """

    # --- Planner Prompts ---
    PLANNER_RESEARCH_PLAN = _JSON_CONTRACT + """
    You are a research planning assistant. Create a detailed, step-by-step research plan for the topic: "{topic}"

    Available tools (you MUST choose `tool` from this list ONLY):
{available_tools}

    The plan should include 5-7 actionable steps covering:
    1. Initial research and definition gathering
    2. Deep dive into specific subtopics
    3. Analysis of methods/approaches
    4. Evaluation of benchmarks/datasets (if applicable)
    5. Identification of challenges and gaps

    CRITICAL RULES:
    - The `tool` field MUST be one of the tool names listed above. Do NOT invent tool names.
    - The `tool_args` field MUST only contain keys that match the tool's parameters listed above.
    - Steps with action "analyze" or "synthesize" do NOT need a tool — set tool to null and tool_args to {{}}.
    - Do NOT create search steps for synthesis/writing phases. Only create search steps for actual information gathering.

    For each step, return:
    {{
        "id": 1,
        "action": "<research|analyze|synthesize>",
        "title": "<Short title>",
        "description": "<What this step accomplishes>",
        "queries": ["query1", "query2"],
        "tool": "<tool_name from available tools, or null for analyze/synthesize>",
        "tool_args": {{"query": "...", "max_results": 20}},
        "expected_output": "<what this step produces: list_papers|study_cards|taxonomy|report|analysis>"
    }}

    Return ONLY a JSON object:
    {{
        "topic": "{topic}",
        "summary": "<Brief 1-2 sentence summary of the research plan>",
        "steps": [...]
    }}
    """ + _LANGUAGE_RULE

    # --- Analyzer Prompts ---
    ANALYZER_RELEVANCE = _JSON_CONTRACT + """
    You are a research assistant. Evaluate the relevance of the following paper to the topic: "{topic}".

    Paper Title: {title}
    Abstract: {abstract}

    Score 0-10 using this rubric:
    - 0-3: Out of scope, no connection to the topic
    - 4-6: Tangentially related, shares some keywords but different focus
    - 7-8: Directly relevant, addresses the topic or closely related methods
    - 9-10: Highly relevant, core contribution to the topic

    Return ONLY a JSON object:
    {{
        "score": <float between 0 and 10>,
        "reasoning": "<1-2 sentence explanation>"
    }}
    """

    ANALYZER_GAP_DETECTION = _JSON_CONTRACT + """
    Goal: "{goal}"

    Current Findings:
    {findings}

    Identify missing information or gaps. What else do we need to know to fully answer the goal?
    Generate 3 follow-up search queries to fill these gaps.

    Return ONLY a JSON object:
    {{
        "gaps": ["gap 1", "gap 2"],
        "queries": ["query 1", "query 2", "query 3"]
    }}

    IMPORTANT: Keep search queries in English for academic database compatibility.
    """

    # --- Summarizer Prompts ---
    SUMMARIZER_PAPER = _JSON_CONTRACT + """
    Analyze the following research paper content and extract key insights.

    Title: {title}
    Content:
    {content}

    Return ONLY a JSON object with the following fields:
    {{
        "problem": "<What problem is the paper trying to solve?>",
        "method": "<What method or approach did they use?>",
        "result": "<What were the key findings or results?>",
        "one_sentence_summary": "<A concise summary of the whole paper>"
    }}
    """ + _LANGUAGE_RULE

    # --- Clusterer Prompts ---
    CLUSTERER_LABELING = _JSON_CONTRACT + """
    Group the following research papers into a single research theme/direction.

    Papers:
    {titles}

    Return ONLY a JSON object:
    {{
        "name": "<Short Theme Name>",
        "description": "<Brief description of this research direction>"
    }}
    """ + _LANGUAGE_RULE

    # --- Planner Autofill Prompts ---
    PLANNER_EXPAND_KEYWORDS = _JSON_CONTRACT + """
    Given the research topic: "{topic}"
    And the user-provided seed keywords (if any): {seed_keywords}

    Generate a comprehensive list of 5-10 search keywords including:
    - Synonyms
    - Related technical terms
    - Abbreviations

    Return ONLY a JSON object:
    {{
        "keywords": ["keyword1", "keyword2", ...]
    }}

    IMPORTANT: Keep all keywords in English for academic database compatibility.
    """

    PLANNER_GENERATE_QUESTIONS = _JSON_CONTRACT + """
    Given the research topic: "{topic}"

    Generate 3-5 specific research questions that a comprehensive literature review should answer.
    Questions should cover: definitions, methods, benchmarks, challenges, and future directions.

    Return ONLY a JSON object:
    {{
        "research_questions": [
            "Question 1?",
            "Question 2?",
            ...
        ]
    }}
    """ + _LANGUAGE_RULE

    # --- Citation-First Workflow Prompts ---

    SCREENING_ABSTRACT = _JSON_CONTRACT + """
    You are a systematic research screener. Evaluate whether the following paper should be included in a literature review on the topic: "{topic}"

    Paper Title: {title}
    Abstract: {abstract}

    Assign a tier:
    - "core": Paper directly addresses the topic, presents relevant methods/results, or provides important new contributions. → Proceed to full-text analysis.
    - "background": Paper is a survey, provides useful context, or is indirectly relevant. Useful for taxonomy/benchmarks but not a core contribution. → Include for background only.
    - "exclude": Paper is clearly out of scope, lacks evaluation, has insufficient detail, or is a duplicate. → Skip.

    Reason codes: relevant, out_of_scope, survey_context, missing_eval, duplicate_work, insufficient_detail

    Return ONLY a JSON object:
    {{
        "tier": "<core|background|exclude>",
        "reason_code": "<one of the reason codes above>",
        "rationale_short": "<1-2 sentence explanation>",
        "scored_relevance": <float 0-10>
    }}
    """

    SCREENING_BATCH = _JSON_CONTRACT + """
    You are a systematic research screener. Evaluate each of the following papers for inclusion in a literature review on the topic: "{topic}"

    Papers:
    {papers_list}

    For each paper, assign a tier:
    - "core": Directly relevant, new contribution → full-text analysis
    - "background": Survey, context, indirect relevance → include for background
    - "exclude": Out of scope, missing eval, duplicate → skip

    Reason codes: relevant, out_of_scope, survey_context, missing_eval, duplicate_work, insufficient_detail

    IMPORTANT: Return results in the SAME ORDER as input papers. Use paper_id to identify each paper (not just paper_index, which can shift during merges).

    Return ONLY a JSON array:
    [
        {{
            "paper_index": 0,
            "paper_id": "<paper_id echoed from input>",
            "tier": "<core|background|exclude>",
            "reason_code": "...",
            "rationale_short": "...",
            "scored_relevance": <float 0-10>
        }},
        ...
    ]
    """

    EVIDENCE_EXTRACTION = _JSON_CONTRACT + """
    You are a research evidence extractor. Given the following paper, extract a structured study card with evidence.

    Title: {title}
    Content:
    {content}

    For each field, extract the relevant information AND a short verbatim quote (snippet, max 300 chars) from the paper that supports it.

    CRITICAL: Snippets MUST be exact substrings copied from the content above. Do NOT paraphrase or invent quotes. If you cannot find evidence for a field, set text to "" and snippet to "" with confidence 0.

    Return ONLY a JSON object:
    {{
        "problem": {{
            "text": "<what problem does this paper address?>",
            "snippet": "<verbatim quote from paper, max 300 chars>",
            "confidence": <float 0-1>
        }},
        "method": {{
            "text": "<what approach/technique is used?>",
            "snippet": "<verbatim quote>",
            "confidence": <float 0-1>
        }},
        "datasets": [
            {{"name": "<dataset name>", "snippet": "<verbatim quote>", "confidence": <float 0-1>}}
        ],
        "metrics": [
            {{"name": "<metric name>", "snippet": "<verbatim quote>", "confidence": <float 0-1>}}
        ],
        "results": [
            {{"text": "<key finding>", "snippet": "<verbatim quote>", "confidence": <float 0-1>}}
        ],
        "limitations": [
            {{"text": "<stated limitation>", "snippet": "<verbatim quote>", "confidence": <float 0-1>}}
        ]
    }}
    """ + _LANGUAGE_RULE

    CLAIM_GENERATION = _JSON_CONTRACT + """
    You are a research claim synthesizer. Given the following study cards from papers in the theme "{theme_name}", generate atomic citable claims.

    Each claim must be:
    - A single factual statement (1-3 sentences)
    - Backed by specific evidence from the study cards
    - Referenced by evidence_span_ids from the provided list

    Study Cards:
    {study_cards_json}

    Available Evidence Spans:
    {evidence_spans_json}

    Return ONLY a JSON array:
    [
        {{
            "claim_text": "<factual assertion>",
            "evidence_span_ids": ["<span_id_1>", "<span_id_2>"],
            "salience_score": <float 0-1, how important is this claim>,
            "uncertainty_flag": false
        }},
        ...
    ]

    Rules:
    - Every claim MUST reference at least 1 evidence_span_id from the provided list. Do NOT invent span IDs.
    - Only use span IDs that appear in the "Available Evidence Spans" section above.
    - If evidence is weak or contradictory, set uncertainty_flag to true.
    - Generate 3-8 claims per theme, covering key findings.
    """ + _LANGUAGE_RULE

    GROUNDED_SYNTHESIS = """
    You are a research report writer. Write a synthesis section for the theme "{theme_name}" using ONLY the provided claims. Every paragraph must cite claim IDs.

    Claims for this theme:
    {claims_json}

    Paper references (for inline citations):
    {papers_json}

    Write a coherent 2-4 paragraph synthesis in {language}. Format:
    - Use inline citations like [AuthorYear] or [paper_short_title] after each statement.
    - At the end of each key statement, add (claim: <claim_id>) for traceability.
    - If evidence is insufficient for an assertion, write: "[insufficient evidence in corpus]".
    - Do NOT make claims not backed by the provided evidence.

    Return ONLY the Markdown text (no JSON wrapper).
    """

    CITATION_AUDIT = _JSON_CONTRACT + """
    You are a citation auditor. Verify whether the cited evidence actually supports the claim.

    Claim: "{claim_text}"

    Cited evidence snippets:
    {evidence_snippets}

    Evaluate:
    1. Does the evidence semantically support the claim?
    2. Is the claim accurately representing what the evidence says?
    3. Is the claim making claims beyond what the evidence supports?

    Return ONLY a JSON object:
    {{
        "supported": true/false,
        "confidence": <float 0-1>,
        "severity": "<minor|major>",
        "issues": "<any issues found, or empty string>",
        "suggestion": "<suggested rewrite if not supported, or empty string>"
    }}

    Severity guide:
    - "minor": Claim is mostly correct but wording could be tighter or more precise.
    - "major": Claim is NOT supported by the evidence, overstates findings, or fabricates information.

    IMPORTANT: The "suggestion" field must ONLY use information present in the cited evidence snippets. Do NOT add new information.
    """

    GAP_MINING = _JSON_CONTRACT + """
    You are a research gap analyst. Given the following aggregated limitations and taxonomy of the research field on "{topic}", identify future research directions.

    Aggregated Limitations (from papers):
    {limitations_json}

    Taxonomy Matrix:
    - Themes: {themes}
    - Datasets: {datasets}
    - Metrics: {metrics}
    - Method families: {method_families}
    - Coverage gaps (empty cells): {taxonomy_holes}

    Contradictory results (if any):
    {contradictions}

    Generate future research directions grounded in the evidence. Each direction must cite at least one limitation evidence span.

    Return ONLY a JSON array:
    [
        {{
            "direction_type": "<open_problem|research_opportunity|next_experiment>",
            "title": "<short title>",
            "description": "<1-3 sentence description>",
            "evidence_span_ids": ["<limitation_span_id>"],
            "gap_source": "<limitation_cluster|contradictory_results|taxonomy_hole>"
        }},
        ...
    ]
    """ + _LANGUAGE_RULE

    @staticmethod
    def get_prompt(template_name: str, **kwargs) -> str:
        """
        Get a formatted prompt by name.
        Example: PromptManager.get_prompt('PLANNER_RESEARCH_PLAN', topic='AI')
        """
        template = getattr(PromptManager, template_name, None)
        if not template:
            raise ValueError(f"Prompt template '{template_name}' not found.")
        return template.format(**kwargs)

# Global instance not strictly needed if using static methods, but good for DI pattern if we want to change it later.
prompt_manager = PromptManager()
