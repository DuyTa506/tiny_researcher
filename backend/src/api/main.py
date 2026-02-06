from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.routes import sources, planner, conversation, websocket
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for AI Research Assistant"
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sources.router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(planner.router, prefix="/api/v1/plan", tags=["Planner"])
app.include_router(conversation.router, prefix="/api/v1/conversations", tags=["Conversations"])
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["WebSocket"])

@app.on_event("startup")
async def startup():
    # Database initialization is optional for development
    if settings.ENVIRONMENT == "development":
        try:
            from src.core.database import engine, Base
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created")
        except Exception as e:
            logger.warning(f"Database not available, running without DB: {e}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}

@app.get("/")
async def root():
    return {"message": "Welcome to Research Assistant API"}
