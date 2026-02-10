"""
API Routes

Available routers:
- auth: Authentication endpoints (register, login, OAuth)
- sources: Source processing endpoints
- planner: Plan CRUD endpoints
- conversation: Conversation management with SSE
- websocket: WebSocket for real-time streaming
- papers: Paper CRUD endpoints
- reports: Report CRUD and export endpoints
"""

from src.api.routes import (
    auth,
    sources,
    planner,
    conversation,
    websocket,
    papers,
    reports,
)

__all__ = [
    "auth",
    "sources",
    "planner",
    "conversation",
    "websocket",
    "papers",
    "reports",
]
