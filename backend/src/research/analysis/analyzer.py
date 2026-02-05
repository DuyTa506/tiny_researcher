"""
Analyzer Service

Relevance scoring and gap detection for research papers.
Uses abstract-only analysis (no full text) for efficiency.
"""

import logging
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from src.core.models import Paper, PaperStatus
from src.adapters.llm import LLMClientInterface
from src.core.prompts import PromptManager
from src.storage.repositories import PaperRepository

logger = logging.getLogger(__name__)


@dataclass
class PaperEvaluation:
    """Result of analyzing a paper's relevance."""
    paper_id: str
    score: float
    reasoning: str
    is_relevant: bool


class AnalyzerService:
    """
    Analyzer for research papers.
    
    Features:
    - Batch relevance scoring (abstract-only)
    - MongoDB integration
    - Gap detection for follow-up queries
    """
    
    RELEVANCE_THRESHOLD = 7.0
    BATCH_SIZE = 10
    
    def __init__(
        self, 
        llm_client: LLMClientInterface,
        paper_repo: PaperRepository = None
    ):
        self.llm = llm_client
        self.paper_repo = paper_repo or PaperRepository()
    
    async def analyze_relevance(self, paper: Paper, topic: str) -> float:
        """
        Analyze if a paper is relevant to the topic using LLM.
        Returns a score between 0.0 and 10.0.
        
        Uses abstract only - no full text loading.
        """
        if not paper.abstract and not paper.title:
            return 0.0

        prompt = PromptManager.get_prompt(
            "ANALYZER_RELEVANCE", 
            topic=topic,
            title=paper.title, 
            abstract=paper.abstract[:3000]  # Truncate for efficiency
        )
        
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            data = json.loads(response_text)
            return float(data.get("score", 0.0))
        except Exception as e:
            logger.error(f"Error scoring paper {paper.title[:50]}: {e}")
            return 0.0
    
    async def analyze_batch(
        self, 
        papers: List[Paper], 
        topic: str
    ) -> List[PaperEvaluation]:
        """
        Analyze multiple papers in batches.
        Updates MongoDB with scores.
        """
        evaluations = []
        
        for i in range(0, len(papers), self.BATCH_SIZE):
            batch = papers[i:i + self.BATCH_SIZE]
            batch_results = await self._analyze_batch_llm(batch, topic)
            evaluations.extend(batch_results)
            
            logger.info(f"Analyzed batch {i//self.BATCH_SIZE + 1}, "
                       f"papers {i+1}-{min(i+self.BATCH_SIZE, len(papers))}")
        
        return evaluations
    
    async def _analyze_batch_llm(
        self, 
        papers: List[Paper], 
        topic: str
    ) -> List[PaperEvaluation]:
        """Analyze a batch of papers with a single LLM call."""
        # Build batch prompt
        papers_text = "\n\n".join([
            f"Paper {i+1}:\n"
            f"Title: {p.title}\n"
            f"Abstract: {p.abstract[:500] if p.abstract else 'No abstract'}..."
            for i, p in enumerate(papers)
        ])
        
        prompt = f"""
Analyze the relevance of these {len(papers)} papers to the research topic: "{topic}"

{papers_text}

Return a JSON array with one object per paper:
[
    {{"paper_index": 1, "score": 8.5, "reasoning": "Directly addresses..."}},
    {{"paper_index": 2, "score": 3.0, "reasoning": "Tangentially related..."}}
]

Score meanings:
- 9-10: Core paper, directly addresses the topic
- 7-8: Highly relevant, provides important context
- 5-6: Moderately relevant, some useful information
- 3-4: Tangentially related
- 0-2: Not relevant
"""
        
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            
            # DEBUG: Log response
            logger.debug(f"LLM response (first 500 chars): {response_text[:500]}")
            
            # Parse JSON - handle various formats
            results = self._parse_json_response(response_text)
            
            # DEBUG: Log parsed results
            logger.debug(f"Parsed results type: {type(results)}, count: {len(results) if isinstance(results, list) else 'N/A'}")
            
            if not isinstance(results, list):
                # Handle wrapped format: {"results": [...]} or {"papers": [...]}
                if isinstance(results, dict):
                    # Try common keys first
                    for key in ["results", "papers", "evaluations", "data"]:
                        if key in results and isinstance(results[key], list):
                            results = results[key]
                            break
                    else:
                        # Fallback: find first list value in dict
                        for v in results.values():
                            if isinstance(v, list):
                                results = v
                                break
                        else:
                            results = [results] if results else []
                elif results:
                    results = [results]
                else:
                    results = []
            
            evaluations = []
            for result in results:
                if not isinstance(result, dict):
                    continue
                    
                idx = result.get("paper_index", 1) - 1
                if 0 <= idx < len(papers):
                    paper = papers[idx]
                    score = float(result.get("score", 5.0))
                    
                    eval_result = PaperEvaluation(
                        paper_id=paper.id or str(idx),
                        score=score,
                        reasoning=result.get("reasoning", ""),
                        is_relevant=score >= self.RELEVANCE_THRESHOLD
                    )
                    evaluations.append(eval_result)
                    
                    # Update paper score in memory
                    paper.relevance_score = score
                    paper.status = PaperStatus.SCORED
            
            # Fill in missing evaluations
            evaluated_indices = {e.paper_id for e in evaluations}
            for i, p in enumerate(papers):
                pid = p.id or str(i)
                if pid not in evaluated_indices:
                    evaluations.append(PaperEvaluation(
                        paper_id=pid,
                        score=5.0,
                        reasoning="Not evaluated",
                        is_relevant=False
                    ))
            
            return evaluations
            
        except Exception as e:
            logger.error(f"Batch analysis failed: {e}")
            # Fallback: return neutral scores
            return [
                PaperEvaluation(
                    paper_id=p.id or str(i),
                    score=5.0,
                    reasoning="Analysis failed, assigned neutral score",
                    is_relevant=False
                )
                for i, p in enumerate(papers)
            ]
    
    def _parse_json_response(self, response_text: str) -> Any:
        """Parse JSON from LLM response, handling various formats."""
        import re
        
        # Try direct parse first
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON array from text
        match = re.search(r'\[[\s\S]*\]', response_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        # Try to extract JSON object from text
        match = re.search(r'\{[\s\S]*\}', response_text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        
        logger.warning(f"Could not parse JSON from response: {response_text[:200]}")
        return []
    
    async def score_and_persist(
        self, 
        papers: List[Paper], 
        topic: str
    ) -> tuple[List[Paper], List[Paper]]:
        """
        Score papers and persist to MongoDB.
        
        Returns:
            Tuple of (relevant_papers, irrelevant_papers)
        """
        logger.info(f"Scoring {len(papers)} papers for topic: {topic[:50]}...")
        
        # Analyze in batches
        evaluations = await self.analyze_batch(papers, topic)
        
        # Create evaluation lookup
        eval_map = {e.paper_id: e for e in evaluations}
        
        relevant = []
        irrelevant = []
        
        for paper in papers:
            eval_result = eval_map.get(paper.id)
            if eval_result:
                paper.relevance_score = eval_result.score
                paper.status = PaperStatus.SCORED
                
                if eval_result.is_relevant:
                    relevant.append(paper)
                else:
                    irrelevant.append(paper)
            else:
                irrelevant.append(paper)
        
        logger.info(f"Scoring complete: {len(relevant)} relevant, "
                   f"{len(irrelevant)} irrelevant")
        
        return relevant, irrelevant
    
    async def detect_gaps(
        self, 
        current_findings: List[str], 
        original_goal: str
    ) -> List[str]:
        """
        Identify gaps in current research and suggest follow-up queries.
        """
        findings_text = "\n".join([f"- {f}" for f in current_findings])
        
        prompt = PromptManager.get_prompt(
            "ANALYZER_GAP_DETECTION", 
            goal=original_goal, 
            findings=findings_text
        )
        
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            data = json.loads(response_text)
            return data.get("queries", [])
        except Exception as e:
            logger.error(f"Gap detection failed: {e}")
            return []
    
    def filter_relevant(self, papers: List[Paper]) -> List[Paper]:
        """Filter papers that meet relevance threshold."""
        return [
            p for p in papers 
            if p.relevance_score and p.relevance_score >= self.RELEVANCE_THRESHOLD
        ]
