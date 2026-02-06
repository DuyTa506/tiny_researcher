from typing import List, Optional, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from src.core.config import settings
import structlog

logger = structlog.get_logger()

class VectorService:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if VectorService._client is not None:
            self.client = VectorService._client
            self.collection_name = "papers"
            self._model = None
            return

        # Use local embedded storage instead of Docker
        # self.client = QdrantClient(url=settings.VECTOR_DB_URL, api_key=settings.VECTOR_DB_API_KEY)
        self.client = QdrantClient(path="qdrant_storage")
        VectorService._client = self.client
        logger.info("vector_db_init", mode="embedded", path="qdrant_storage")

        self.collection_name = "papers"
        self._model = None # Lazy load
        
    @property
    def model(self):
        if self._model is None:
            logger.info("loading_embedding_model", model="all-MiniLM-L6-v2")
            self._model = SentenceTransformer('all-MiniLM-L6-v2')
        return self._model

    def ensure_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            logger.info("creating_collection", name=self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE)
            )

    def embed_text(self, text: str) -> List[float]:
        if not text:
            return [0.0] * 384
        return self.model.encode(text).tolist()

    def upsert_paper(self, paper: dict):
        """
        Index a paper. 
        Paper dict should have: arxiv_id, title, abstract, published_date, source_type
        """
        self.ensure_collection()
        
        # Combine title and abstract for embedding
        text_to_embed = f"{paper.get('title', '')}. {paper.get('abstract', '')}"
        vector = self.embed_text(text_to_embed)
        
        payload = {
            "title": paper.get("title"),
            "url": paper.get("url"),
            "published_date": str(paper.get("published_date")) if paper.get("published_date") else None,
            "source_type": paper.get("source_type"),
            "arxiv_id": paper.get("arxiv_id")
        }
        
        # Use arxiv_id as point ID (hashing it or using strictly UUID?)
        # Qdrant supports UUID or integer. Let's create a UUID from arxiv_id to be safe.
        import uuid
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, paper.get("arxiv_id")))
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                models.PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            ]
        )
        logger.info("paper_indexed", arxiv_id=paper.get("arxiv_id"))

    def search(self, query: str, limit: int = 10) -> List[dict]:
        self.ensure_collection()
        query_vector = self.embed_text(query)
        
    def search(self, query: str, limit: int = 10) -> List[dict]:
        self.ensure_collection()
        query_vector = self.embed_text(query)

        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit
        )

        return [
            {
                "score": hit.score,
                "payload": hit.payload
            }
            for hit in results.points
        ]

    def close(self):
        """Close the Qdrant client and release the lock."""
        if VectorService._client:
            try:
                VectorService._client.close()
                logger.info("vector_db_closed")
            except Exception as e:
                logger.warning("vector_db_close_failed", error=str(e))
            finally:
                VectorService._client = None

# Global instance
vector_service = VectorService()
