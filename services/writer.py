
from typing import List, Dict
import logging
from src.core.models import Report, Paper
from src.services.clusterer import Cluster
from datetime import datetime

logger = logging.getLogger(__name__)

class WriterService:
    def __init__(self):
        pass

    def generate_report(self, clusters: List[Cluster], topic: str) -> str:
        """
        Generate a Markdown report from research clusters.
        """
        if not clusters:
            return f"# Research Report: {topic}\n\nNo relevant data found."

        report_lines = [f"# Research Report: {topic}", ""]
        report_lines.append(f"**Date**: {datetime.utcnow().strftime('%Y-%m-%d')}")
        report_lines.append(f"**Total Themes**: {len(clusters)}")
        report_lines.append("")

        for cluster in clusters:
            report_lines.append(f"## {cluster.name}")
            report_lines.append(f"{cluster.description}")
            report_lines.append("")
            
            # List papers
            # Assuming we can access paper details. 
            # In a real app, Cluster might only have indices, so we'd need the papers list passed in 
            # OR Cluster object should hold Paper objects (which I simplified in ClustererService to use indices).
            # Let's fix this in integration. For now, assuming Cluster has paper metadata or we skip details.
            # Wait, my ClustererService returns `Cluster` with `paper_indices`. 
            # I should probably pass the full `papers` list to `generate_report` OR `Cluster` should contain `Paper` objects.
            # Let's assume for this method we might need the papers list to look them up, 
            # BUT efficient design would be Cluster having the data. 
            # Let's stick to the simplest: I'll assume the caller passes papers map or I'll change Clusterer to include papers.
            # Re-reading ClustererService: `Cluster` has `paper_indices`. 
            # I will modify this method to accept `papers` list as context.
            pass

        return "\n".join(report_lines)

    def format_report_with_papers(self, clusters: List[Cluster], all_papers: List[Paper], topic: str) -> str:
        report_lines = [f"# Research Report: {topic}", ""]
        report_lines.append(f"**Generated**: {datetime.utcnow().strftime('%Y-%m-%d')}")
        report_lines.append("")
        
        for cluster in clusters:
            report_lines.append(f"## {cluster.name}")
            report_lines.append(f"_{cluster.description}_")
            report_lines.append("")
            
            report_lines.append("### Key Papers")
            for idx in cluster.paper_indices:
                if 0 <= idx < len(all_papers):
                    p = all_papers[idx]
                    report_lines.append(f"- **{p.title}** ({p.published_date})")
                    if p.summary:
                        # If summary is dict
                        if isinstance(p.summary, dict):
                            one_liner = p.summary.get('one_sentence_summary', '')
                            if one_liner:
                                report_lines.append(f"  - {one_liner}")
                        else:
                            report_lines.append(f"  - {str(p.summary)[:200]}...")
                    report_lines.append(f"  - [Link]({p.url})")
            report_lines.append("")
            
        return "\n".join(report_lines)
