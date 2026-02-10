from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Any
from src.planner.service import PlannerService
from src.research.ingestion.collector import IngestionFactory
from src.research.ingestion.searcher import HuggingFaceSearcher
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


class InputRequest(BaseModel):
    items: List[str]


@router.post("/process")
async def process_inputs(request: InputRequest):
    """
    Process a list of inputs (URLs or Keywords).
    """
    plan = PlannerService.plan(request.items)
    results = {"collected_papers": [], "search_results": [], "errors": []}

    # Process URLs
    for url in plan["urls"]:
        try:
            collector = IngestionFactory.get_collector(url)
            papers = await collector.collect(url)
            results["collected_papers"].extend(papers)
        except Exception as e:
            results["errors"].append(f"Failed to collect {url}: {str(e)}")

    # Process Keywords
    if plan["keywords"]:
        searcher = HuggingFaceSearcher()
        for keyword in plan["keywords"]:
            try:
                # Playwright search
                papers = await searcher.search(keyword)
                results["search_results"].extend(papers)
            except Exception as e:
                results["errors"].append(f"Failed to search {keyword}: {str(e)}")

    return results
