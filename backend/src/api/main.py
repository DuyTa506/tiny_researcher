from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import settings
from src.api.routes import (
    auth,
    sources,
    planner,
    conversation,
    websocket,
    papers,
    reports,
)
import logging

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API for AI Research Assistant",
)

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(sources.router, prefix="/api/v1/sources", tags=["Sources"])
app.include_router(planner.router, prefix="/api/v1/plan", tags=["Planner"])
app.include_router(
    conversation.router, prefix="/api/v1/conversations", tags=["Conversations"]
)
app.include_router(websocket.router, prefix="/api/v1/ws", tags=["WebSocket"])
app.include_router(papers.router, prefix="/api/v1/papers", tags=["Papers"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["Reports"])


@app.on_event("startup")
async def startup():
    # Connect MongoDB and create indexes
    try:
        from src.core.database import connect_mongodb

        await connect_mongodb()
        logger.info("MongoDB connected on startup")

        # Create auth indexes
        from src.auth.service import AuthService

        auth_service = AuthService()
        await auth_service.ensure_indexes()
    except Exception as e:
        logger.warning(f"Startup DB init skipped: {e}")


@app.on_event("shutdown")
async def shutdown():
    try:
        from src.core.database import close_mongodb

        await close_mongodb()
        logger.info("MongoDB connection closed")
    except Exception:
        pass


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.VERSION}


@app.get("/")
async def root():
    return {"message": "Welcome to Research Assistant API"}
