"""
WebSocket API Routes

Provides:
- Real-time bidirectional communication
- LLM streaming responses
- Pipeline progress updates
"""

import asyncio
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from src.conversation.dialogue import DialogueManager, DialogueResponse
from src.conversation.context import DialogueState
from src.research.pipeline import ResearchPipeline
from src.adapters.llm import LLMFactory
from src.memory import MemoryManager

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Connection Manager ---
class ConnectionManager:
    """Manages WebSocket connections."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, conversation_id: str):
        """Accept and register a connection."""
        await websocket.accept()
        self.active_connections[conversation_id] = websocket
        logger.info(f"WebSocket connected: {conversation_id}")

    def disconnect(self, conversation_id: str):
        """Remove a connection."""
        self.active_connections.pop(conversation_id, None)
        logger.info(f"WebSocket disconnected: {conversation_id}")

    async def send_json(self, conversation_id: str, data: dict):
        """Send JSON data to a connection."""
        if conversation_id in self.active_connections:
            await self.active_connections[conversation_id].send_json(data)

    async def broadcast(self, data: dict):
        """Send to all connections."""
        for connection in self.active_connections.values():
            await connection.send_json(data)


manager = ConnectionManager()


# --- Dependencies ---
_dialogue_manager: Optional[DialogueManager] = None


async def get_dialogue_manager() -> DialogueManager:
    """Get or create the dialogue manager singleton."""
    global _dialogue_manager

    if _dialogue_manager is None:
        try:
            gemini_key = os.getenv("GEMINI_API_KEY")
            openai_key = os.getenv("OPENAI_API_KEY")

            if gemini_key:
                llm = LLMFactory.create_client(provider="gemini", api_key=gemini_key)
            elif openai_key:
                llm = LLMFactory.create_client(provider="openai", api_key=openai_key)
            else:
                raise ValueError("No LLM API key found")
        except Exception as e:
            logger.error(f"Failed to create LLM client: {e}")
            raise

        pipeline = ResearchPipeline(llm, use_adaptive_planner=True)
        memory = MemoryManager()

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            await memory.connect(redis_url)
        except Exception as e:
            logger.warning(f"Redis not available: {e}")

        _dialogue_manager = DialogueManager(
            llm_client=llm,
            pipeline=pipeline,
            memory=memory
        )

        try:
            await _dialogue_manager.connect(redis_url)
        except Exception as e:
            logger.warning(f"Dialogue store Redis not available: {e}")

    return _dialogue_manager


@router.websocket("/{conversation_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    conversation_id: str
):
    """
    WebSocket endpoint for real-time conversation.

    Message format (client -> server):
    {
        "type": "message",
        "content": "user message here"
    }

    Response format (server -> client):
    {
        "type": "response|progress|stream|error",
        "data": {...}
    }
    """
    dialogue = await get_dialogue_manager()
    await manager.connect(websocket, conversation_id)

    # Get or create conversation context
    context = await dialogue.get_context(conversation_id)
    if not context:
        context = await dialogue.start_conversation(user_id="websocket_user")
        conversation_id = context.conversation_id

    # Send initial state
    await websocket.send_json({
        "type": "connected",
        "data": {
            "conversation_id": conversation_id,
            "state": context.state.value
        }
    })

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            msg_type = data.get("type", "message")
            content = data.get("content", "")

            if msg_type == "message" and content:
                # Set up progress callback
                async def progress_callback(phase: str, message: str, progress_data: dict):
                    await websocket.send_json({
                        "type": "progress",
                        "data": {
                            "phase": phase,
                            "message": message,
                            **progress_data
                        }
                    })

                dialogue.set_progress_callback(progress_callback)

                # Check if this is a /ask or /explain command for streaming
                if content.startswith("/ask ") or content.startswith("/explain "):
                    await handle_streaming_command(websocket, dialogue, content)
                else:
                    # Process regular message
                    response = await dialogue.process_message(conversation_id, content)
                    dialogue.set_progress_callback(None)

                    # Send response
                    response_data = {
                        "state": response.state.value,
                        "message": response.message,
                        "needs_input": response.needs_input
                    }

                    if response.plan:
                        response_data["plan"] = {
                            "query_type": response.plan.query_info.query_type.value,
                            "phases": response.plan.phase_config.active_phases,
                            "steps": [
                                {"id": s.id, "title": s.title, "queries": s.queries[:5]}
                                for s in response.plan.plan.steps
                            ]
                        }

                    if response.result:
                        response_data["result"] = {
                            "session_id": response.result.session_id,
                            "topic": response.result.topic,
                            "unique_papers": response.result.unique_papers,
                            "relevant_papers": response.result.relevant_papers,
                            "high_relevance_papers": response.result.high_relevance_papers
                        }

                    await websocket.send_json({
                        "type": "response",
                        "data": response_data
                    })

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(conversation_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass
        manager.disconnect(conversation_id)


async def handle_streaming_command(
    websocket: WebSocket,
    dialogue: DialogueManager,
    command: str
):
    """Handle /ask and /explain commands with LLM streaming."""
    if command.startswith("/ask "):
        question = command[5:].strip()
        system_instruction = "You are a helpful research assistant. Answer concisely."
    elif command.startswith("/explain "):
        topic = command[9:].strip()
        question = f"Explain '{topic}' in the context of academic research. Include what it is, why it matters, and key concepts."
        system_instruction = "You are a helpful research assistant explaining academic concepts."
    else:
        return

    # Stream the LLM response
    await websocket.send_json({
        "type": "stream_start",
        "data": {}
    })

    full_response = ""
    try:
        async for chunk in dialogue.llm.generate_stream(question, system_instruction):
            full_response += chunk
            await websocket.send_json({
                "type": "stream_chunk",
                "data": {"chunk": chunk}
            })
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        await websocket.send_json({
            "type": "error",
            "data": {"message": f"Streaming error: {e}"}
        })

    await websocket.send_json({
        "type": "stream_end",
        "data": {"full_response": full_response}
    })
