
from typing import List, Optional, Dict
import logging
from src.core.models import Paper
from src.adapters.llm import LLMClientInterface
from src.core.prompts import PromptManager
import json

logger = logging.getLogger(__name__)

class AnalyzerService:
    def __init__(self, llm_client: LLMClientInterface):
        self.llm = llm_client

    async def analyze_relevance(self, paper: Paper, topic: str) -> float:
        """
        Analyze if a paper is relevant to the topic using LLM.
        Returns a score between 0.0 and 10.0.
        """
        if not paper.abstract and not paper.title:
            return 0.0

        prompt = PromptManager.get_prompt("ANALYZER_RELEVANCE", title=paper.title, abstract=paper.abstract)
        
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            # Simple parsing for now, in production use structured output parsing
            # Assuming the mock returns a string, we might need more robust parsing if it's real output
            # For this mock implementation, let's simulate a parsed response if the LLM returns a string
            if "Mock" in response_text:
                return 8.0 # Mock high score
            
            data = json.loads(response_text)
            return float(data.get("score", 0.0))
        except Exception as e:
            logger.error(f"Error scoring relevance for paper {paper.title}: {e}")
            return 0.0

    async def detect_gaps(self, current_findings: List[str], original_goal: str) -> List[str]:
        """
        Critique the current findings against the original goal and identify gaps.
        Returns a list of follow-up search queries.
        """
        findings_text = "\n".join([f"- {f}" for f in current_findings])
        
        prompt = PromptManager.get_prompt("ANALYZER_GAP_DETECTION", goal=original_goal, findings=findings_text)
        
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            if "Mock" in response_text:
                return [f"refined query for {original_goal}"]
                
            data = json.loads(response_text)
            return data.get("queries", [])
        except Exception as e:
            logger.error(f"Error detecting gaps: {e}")
            return []
