# Phase 5: API Integration - Implementation Guide

## Overview

Phase 5 adds REST API and WebSocket endpoints for the Research Assistant, enabling frontend integration with real-time streaming capabilities.

## Implementation Summary

### Components Implemented

#### 1. Conversation REST API (`src/api/routes/conversation.py`)

**Endpoints:**
- `POST /api/v1/conversations` - Start a new conversation
- `GET /api/v1/conversations/{id}` - Get conversation state
- `POST /api/v1/conversations/{id}/messages` - Send a message
- `DELETE /api/v1/conversations/{id}` - Delete conversation
- `GET /api/v1/conversations/{id}/stream` - SSE stream for real-time updates

**Key Features:**
- DialogueManager integration for conversation orchestration
- Progress callbacks for pipeline phase notifications
- Server-Sent Events (SSE) for streaming
- In-memory event queue (can be replaced with Redis pub/sub)
- LLM and Memory manager initialization with dependency injection

**Request/Response Models:**
```python
# Start conversation
POST /api/v1/conversations
{
  "user_id": "test_user"
}
→ Returns: conversation_id, state, messages

# Send message
POST /api/v1/conversations/{id}/messages
{
  "message": "transformer models"
}
→ Returns: state, message, plan (if any), result (if complete)
```

#### 2. WebSocket API (`src/api/routes/websocket.py`)

**Endpoints:**
- `WS /api/v1/ws/{conversation_id}` - Real-time bidirectional communication

**Message Types (Client → Server):**
```json
{
  "type": "message",
  "content": "user message here"
}
```

**Message Types (Server → Client):**
- `connected` - Initial connection established
- `response` - Message processing response
- `progress` - Pipeline phase updates
- `stream_start` - LLM streaming started
- `stream_chunk` - LLM response chunk
- `stream_end` - LLM streaming complete
- `error` - Error occurred
- `pong` - Keepalive response

**Special Commands:**
- `/ask <question>` - Direct LLM question with streaming
- `/explain <topic>` - Explain topic with streaming

#### 3. CORS Middleware

Added to `src/api/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Architecture

### Event Flow

```
Client → REST API → DialogueManager → ResearchPipeline
                         ↓
                  Progress Callback
                         ↓
                  Event Queue (SSE)
                         ↓
                  Client (streaming)
```

### SSE Event System

**ConversationEvents Class:**
- Manages event queues per conversation
- Publishes events: `progress`, `state_change`, `complete`, `error`
- Clients subscribe via SSE endpoint
- Keepalive: sends heartbeat every 30s

**Event Format:**
```
data: {"type": "progress", "data": {"phase": "execution", "message": "Collecting papers...", "papers": 10}}

data: {"type": "state_change", "data": {"state": "reviewing", "message": "Plan ready for approval"}}
```

### WebSocket Connection Manager

**ConnectionManager Class:**
- Tracks active WebSocket connections
- Handles connect/disconnect
- Supports broadcast and targeted send

## Dependencies

**New packages installed:**
```bash
pip install fastapi uvicorn httpx websockets
```

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - Async HTTP client (for testing)
- `websockets` - WebSocket library (for testing)

## Testing

### Running Tests

```bash
# 1. Start the API server
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
uvicorn src.api.main:app --reload

# 2. Run tests in another terminal
source .venv/bin/activate
export $(grep -v '^#' .env | xargs)
python scripts/test_api.py
```

### Test Coverage

**test_api.py covers:**
- ✅ Health endpoint
- ✅ Conversation CRUD
- ✅ Message sending
- ✅ SSE streaming
- ✅ WebSocket connection
- ✅ LLM response handling

**Test Results (2026-02-06):**
```
✅ Health check passed
✅ Created conversation
✅ Get conversation passed
✅ Send message passed
✅ SSE stream connection works
✅ WebSocket test passed
✅ Delete conversation passed
```

## Usage Examples

### Example 1: REST API - Start Research

```python
import httpx

async def research_example():
    async with httpx.AsyncClient() as client:
        # 1. Start conversation
        resp = await client.post(
            "http://localhost:8000/api/v1/conversations",
            json={"user_id": "researcher1"}
        )
        conv_id = resp.json()["conversation_id"]

        # 2. Send research topic
        resp = await client.post(
            f"http://localhost:8000/api/v1/conversations/{conv_id}/messages",
            json={"message": "transformer models"}
        )
        data = resp.json()
        print(f"State: {data['state']}")  # reviewing
        print(f"Plan: {data['plan']}")    # research plan

        # 3. Approve plan
        resp = await client.post(
            f"http://localhost:8000/api/v1/conversations/{conv_id}/messages",
            json={"message": "yes"}
        )
        # This triggers execution
```

### Example 2: SSE Streaming

```python
async def stream_progress():
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "GET",
            f"http://localhost:8000/api/v1/conversations/{conv_id}/stream"
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    event = json.loads(line[5:])
                    print(f"{event['type']}: {event['data']}")
```

### Example 3: WebSocket

```python
import websockets
import json

async def websocket_example():
    async with websockets.connect(
        "ws://localhost:8000/api/v1/ws/my-conversation-123"
    ) as ws:
        # Receive connected message
        msg = await ws.recv()
        print(json.loads(msg))  # {'type': 'connected', ...}

        # Send message
        await ws.send(json.dumps({
            "type": "message",
            "content": "transformer models"
        }))

        # Receive response
        msg = await ws.recv()
        data = json.loads(msg)
        print(f"{data['type']}: {data['data']['state']}")

        # Stream LLM response
        await ws.send(json.dumps({
            "type": "message",
            "content": "/ask What are transformers?"
        }))

        # Receive streaming chunks
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data['type'] == 'stream_chunk':
                print(data['data']['chunk'], end='')
            elif data['type'] == 'stream_end':
                break
```

## Production Considerations

### 1. Authentication
Currently no authentication. Add API key middleware:
```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key
```

### 2. Rate Limiting
Use `slowapi` or similar:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@limiter.limit("10/minute")
@router.post("/messages")
async def send_message(...):
    ...
```

### 3. Redis Pub/Sub for Events
Replace in-memory `ConversationEvents` with Redis:
```python
import redis.asyncio as redis

class RedisPubSub:
    def __init__(self, redis_url):
        self.redis = redis.from_url(redis_url)

    async def publish(self, channel, data):
        await self.redis.publish(channel, json.dumps(data))

    async def subscribe(self, channel):
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        async for message in pubsub.listen():
            if message['type'] == 'message':
                yield json.loads(message['data'])
```

### 4. Load Balancing
For horizontal scaling:
- Use Redis for conversation storage (already implemented)
- Use Redis pub/sub for SSE events
- Run multiple API instances behind nginx/HAProxy
- Session affinity for WebSocket connections

### 5. Monitoring
Add metrics:
```python
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator().instrument(app).expose(app)
```

## Known Limitations

1. **Qdrant Lock Issue**: Cannot run API and CLI simultaneously due to Qdrant embedded mode file lock. Solution: Use Qdrant server mode or disable vector store.

2. **In-Memory Events**: SSE events use in-memory queues. For production, migrate to Redis pub/sub.

3. **No Authentication**: API is open. Add API keys or OAuth for production.

4. **WebSocket Session Recovery**: No automatic reconnection. Client must handle reconnects.

## Files Created/Modified

**New Files:**
- `src/api/routes/conversation.py` - Conversation REST + SSE
- `src/api/routes/websocket.py` - WebSocket endpoints
- `scripts/test_api.py` - API test suite
- `docs/phase_5_api_integration.md` - This file

**Modified Files:**
- `src/api/main.py` - Added CORS, new routers
- `src/api/routes/__init__.py` - Export new routers
- `docs/checklist.md` - Phase 5 complete
- `docs/process_track.md` - Updated status to v3.4
- `docs/system_design.md` - API endpoints section

## Next Steps

### Immediate (Production Hardening)
- [ ] Add authentication (API keys)
- [ ] Add rate limiting
- [ ] Migrate to Redis pub/sub for SSE
- [ ] Add request/response logging
- [ ] Add error monitoring (Sentry)
- [ ] Configure CORS properly
- [ ] Add health checks for dependencies (Redis, MongoDB)

### Future Enhancements
- [ ] Frontend web app (React/Vue)
- [ ] Report download endpoints (PDF, DOCX)
- [ ] Batch research API
- [ ] User management
- [ ] Research history dashboard
- [ ] Vector search API
- [ ] Paper recommendation engine

## API Documentation

FastAPI automatically generates OpenAPI docs:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Conclusion

Phase 5 successfully integrates REST and WebSocket APIs with the Research Assistant, providing:
- Full conversation flow via HTTP
- Real-time streaming via SSE and WebSocket
- LLM response streaming
- Pipeline progress notifications
- Ready for frontend integration

All tests pass. System is ready for production hardening and frontend development.

---
**Version**: v3.4
**Date**: 2026-02-06
**Status**: ✅ Complete
