from typing import Generic, TypeVar, Type, Optional, List, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from src.core.models import Base, Paper, Source

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def get(self, id: Any) -> Optional[ModelType]:
        result = await self.session.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def list(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        result = await self.session.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, attributes: dict) -> ModelType:
        db_obj = self.model(**attributes)
        self.session.add(db_obj)
        await self.session.flush()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: Any) -> bool:
        result = await self.session.execute(delete(self.model).where(self.model.id == id))
        return result.rowcount > 0

class PaperRepository(BaseRepository[Paper]):
    def __init__(self, session: AsyncSession):
        super().__init__(Paper, session)

    async def get_by_arxiv_id(self, arxiv_id: str) -> Optional[Paper]:
        result = await self.session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id))
        return result.scalars().first()

    async def upsert(self, paper_data: dict) -> Paper:
        """
        Create or Update paper based on ArXiv ID.
        """
        # We can use postgres ON CONFLICT logic or manual check.
        # Manual check is safer for complex logic (like not overwriting existing embeddings if any)
        
        arxiv_id = paper_data.get("arxiv_id")
        existing = await self.get_by_arxiv_id(arxiv_id)
        
        if existing:
            # Update fields
            for key, value in paper_data.items():
                setattr(existing, key, value)
            # session.add(existing) is not strictly needed if attached, but good for clarity
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        else:
            return await self.create(paper_data)

class SourceRepository(BaseRepository[Source]):
    def __init__(self, session: AsyncSession):
        super().__init__(Source, session)
