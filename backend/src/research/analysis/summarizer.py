from typing import Dict, Optional, Any
import logging
import json
from src.core.models import Paper
from src.adapters.llm import LLMClientInterface
from src.core.prompts import PromptManager

logger = logging.getLogger(__name__)


class SummarizerService:
    def __init__(self, llm_client: LLMClientInterface):
        self.llm = llm_client

    async def summarize_paper(
        self, paper: Paper, language: str = "en"
    ) -> Dict[str, str]:
        """
        Generate a structured summary for the paper.
        Returns a dictionary with keys: "problem", "method", "result", "one_sentence_summary".
        """
        if not paper.abstract and not paper.full_text:
            return {}

        text_to_summarize = paper.abstract
        if (
            paper.full_text and len(paper.full_text) < 10000
        ):  # Simple truncation for context window
            text_to_summarize += (
                "\n\n" + paper.full_text[:5000]
            )  # Take first 5k chars if full text exists

        prompt = PromptManager.get_prompt(
            "SUMMARIZER_PAPER",
            title=paper.title,
            content=text_to_summarize,
            language=language,
        )

        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            if "Mock" in response_text:
                return {
                    "problem": "Mock Problem",
                    "method": "Mock Method",
                    "result": "Mock Result",
                    "one_sentence_summary": "This is a mock summary.",
                }

            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Error summarizing paper {paper.title}: {e}")
            return {}
