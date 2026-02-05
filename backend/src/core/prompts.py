
from typing import Dict, Any

class PromptManager:
    """
    Centralized manager for all LLM prompts.
    """
    
    # --- Planner Prompts ---
    PLANNER_RESEARCH_PLAN = """
    You are a research planning assistant. Create a detailed, step-by-step research plan for the topic: "{topic}"
    
    Available tools for research:
{available_tools}
    
    The plan should include 5-7 actionable steps covering:
    1. Initial research and definition gathering
    2. Deep dive into specific subtopics
    3. Analysis of methods/approaches
    4. Evaluation of benchmarks/datasets (if applicable)
    5. Identification of challenges and gaps
    6. Synthesis and report writing
    
    For each step:
    - Provide specific search queries
    - Select the most appropriate tool from the available list
    - Include tool_args with the required parameters
    
    Return ONLY a JSON object:
    {{
        "topic": "{topic}",
        "summary": "<Brief 1-2 sentence summary of the research plan>",
        "steps": [
            {{
                "id": 1,
                "action": "research",
                "title": "<Short title>",
                "description": "<What this step accomplishes>",
                "queries": ["query1", "query2"],
                "tool": "<tool_name from available tools>",
                "tool_args": {{"query": "...", "max_results": 20}}
            }},
            ...
        ]
    }}
    """

    # --- Analyzer Prompts ---
    ANALYZER_RELEVANCE = """
    You are a research assistant. Evaluate the relevance of the following paper to the topic: "{topic}".
    
    Paper Title: {title}
    Abstract: {abstract}
    
    Return ONLY a JSON object with the following format:
    {{
        "score": <float between 0 and 10>,
        "reasoning": "<short explanation>"
    }}
    """

    ANALYZER_GAP_DETECTION = """
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
    """

    # --- Summarizer Prompts ---
    SUMMARIZER_PAPER = """
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
    """

    # --- Clusterer Prompts ---
    CLUSTERER_LABELING = """
    Group the following research papers into a single research theme/direction.
    
    Papers:
    {titles}
    
    Return ONLY a JSON object:
    {{
        "name": "<Short Theme Name>",
        "description": "<Brief description of this research direction>"
    }}
    """

    # --- Planner Autofill Prompts ---
    PLANNER_EXPAND_KEYWORDS = """
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
    """

    PLANNER_GENERATE_QUESTIONS = """
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
    """

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
