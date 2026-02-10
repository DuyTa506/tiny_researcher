
from typing import List, Dict, Any
import logging
import numpy as np
import json
# Try importing clustering algos, fallback if not available
try:
    from sklearn.cluster import KMeans
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    
from src.core.models import Paper
from src.adapters.llm import LLMClientInterface
from src.storage.vector_store import VectorService
from src.core.prompts import PromptManager

logger = logging.getLogger(__name__)

class Cluster:
    def __init__(self, id: int, name: str, paper_indices: List[int], description: str = ""):
        self.id = id
        self.name = name
        self.paper_indices = paper_indices
        self.description = description

class ClustererService:
    def __init__(self, llm_client: LLMClientInterface, vector_service: VectorService):
        self.llm = llm_client
        self.vector_service = vector_service

    async def cluster_papers(self, papers: List[Paper], language: str = "en") -> List[Cluster]:
        """
        Group papers into clusters and name them.
        """
        if not papers:
            return []
            
        embeddings = []
        for p in papers:
            # We assume we can get embedding on the fly or it's cached.
            # ideally paper.embedding is stored, but model might not have it loaded.
            # For this MVP, let's re-embed or use VectorService logic.
            # VectorService.embed_text gives us the float list.
            text = f"{p.title}. {p.abstract}"
            emb = self.vector_service.embed_text(text)
            embeddings.append(emb)
            
        if not embeddings:
            return []
            
        X = np.array(embeddings)
        n_clusters = min(len(papers) // 2 + 1, 5) # Heuristic: roughly 2-3 papers per cluster, max 5
        if n_clusters < 1: 
            n_clusters = 1

        labels = []
        if SKLEARN_AVAILABLE:
            kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init="auto")
            kmeans.fit(X)
            labels = kmeans.labels_
        else:
            logger.warning("sklearn not found, returning single cluster")
            labels = [0] * len(papers)

        # Group papers by label
        clusters_map = {} # label -> list of paper indices
        for idx, label in enumerate(labels):
            if label not in clusters_map:
                clusters_map[label] = []
            clusters_map[label].append(idx)
            
        # Create Cluster objects and Label them
        results = []
        for label, indices in clusters_map.items():
            cluster_papers = [papers[i] for i in indices]
            name, desc = await self._generate_cluster_label(cluster_papers, language)
            results.append(Cluster(id=int(label), name=name, paper_indices=indices, description=desc))
            
        return results

    async def _generate_cluster_label(self, papers: List[Paper], language: str = "en") -> (str, str):
        titles = "\n".join([f"- {p.title}" for p in papers])
        prompt = PromptManager.get_prompt("CLUSTERER_LABELING", titles=titles, language=language)
        try:
            response_text = await self.llm.generate(prompt, json_mode=True)
            if "Mock" in response_text:
                return "Mock Theme", "Mock Description"
            
            data = json.loads(response_text)
            return data.get("name", "Unknown Theme"), data.get("description", "")
        except Exception as e:
            logger.error(f"Error labeling cluster: {e}")
            return "Unlabeled Cluster", ""
