"""
Conversation API Routes

Endpoints:
- POST /api/v1/conversations - Start a new conversation
- GET /api/v1/conversations/{id} - Get conversation state
- POST /api/v1/conversations/{id}/messages - Send a message
- GET /api/v1/conversations/{id}/stream - SSE stream for real-time updates
"""

import asyncio
import json
import logging
import os
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.conversation.dialogue import DialogueManager, DialogueResponse
from src.conversation.context import ConversationContext, DialogueState
from src.research.pipeline import ResearchPipeline
from src.adapters.llm import LLMFactory
from src.memory import MemoryManager

router = APIRouter()
logger = logging.getLogger(__name__)


# --- Event Queue for SSE ---
@dataclass
class ConversationEvents:
    """Manages SSE events for a conversation."""
    queues: dict = field(default_factory=dict)  # conversation_id -> asyncio.Queue

    def get_queue(self, conversation_id: str) -> asyncio.Queue:
        """Get or create event queue for a conversation."""
        if conversation_id not in self.queues:
            self.queues[conversation_id] = asyncio.Queue()
        return self.queues[conversation_id]

    async def publish(self, conversation_id: str, event_type: str, data: dict):
        """Publish an event to a conversation's queue."""
        if conversation_id in self.queues:
            event = {"type": event_type, "data": data}
            await self.queues[conversation_id].put(event)

    def remove_queue(self, conversation_id: str):
        """Remove a conversation's queue."""
        self.queues.pop(conversation_id, None)


# Global event manager (in production, use Redis pub/sub)
_events = ConversationEvents()


# --- Dependencies ---
_dialogue_manager: Optional[DialogueManager] = None
_memory_manager: Optional[MemoryManager] = None


async def get_dialogue_manager() -> DialogueManager:
    """Get or create the dialogue manager singleton."""
    global _dialogue_manager, _memory_manager

    if _dialogue_manager is None:
        # Create LLM client
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
            raise HTTPException(status_code=500, detail="LLM service unavailable")

        # Create pipeline
        pipeline = ResearchPipeline(llm, use_adaptive_planner=True)

        # Create memory manager
        _memory_manager = MemoryManager()
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            await _memory_manager.connect(redis_url)
        except Exception as e:
            logger.warning(f"Redis not available: {e}")

        # Create dialogue manager
        _dialogue_manager = DialogueManager(
            llm_client=llm,
            pipeline=pipeline,
            memory=_memory_manager
        )

        # Connect to Redis for conversation storage
        try:
            await _dialogue_manager.connect(redis_url)
        except Exception as e:
            logger.warning(f"Dialogue store Redis not available: {e}")

        logger.info("DialogueManager initialized")

    return _dialogue_manager


# --- Request/Response Models ---

class StartConversationRequest(BaseModel):
    user_id: str = Field("anonymous", description="User identifier")


class MessageRequest(BaseModel):
    message: str = Field(..., description="User message", min_length=1)


class ConversationResponse(BaseModel):
    conversation_id: str
    state: str
    messages: list
    current_topic: Optional[str] = None
    has_pending_plan: bool = False


class MessageResponse(BaseModel):
    conversation_id: str
    state: str
    message: str
    plan: Optional[dict] = None
    result: Optional[dict] = None
    needs_input: bool = True


# --- Endpoints ---

@router.get("")
async def list_conversations(
    dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """List all active conversations."""
    conversations = await dialogue.store.list_all()
    # Sort by most recent first (if created_at available)
    conversations.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return {"items": conversations, "total": len(conversations)}


@router.post("", response_model=ConversationResponse)
async def start_conversation(
    request: StartConversationRequest,
    dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """Start a new conversation."""
    context = await dialogue.start_conversation(user_id=request.user_id)

    return ConversationResponse(
        conversation_id=context.conversation_id,
        state=context.state.value,
        messages=[],
        current_topic=None,
        has_pending_plan=False
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """Get conversation state."""
    context = await dialogue.get_context(conversation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        conversation_id=context.conversation_id,
        state=context.state.value,
        messages=[m.to_dict() for m in context.get_recent_messages(20)],
        current_topic=context.current_topic,
        has_pending_plan=context.pending_plan is not None
    )


@router.post("/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: str,
    request: MessageRequest,
    background_tasks: BackgroundTasks,
    dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """Send a message to the conversation."""
    context = await dialogue.get_context(conversation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Set up progress callback for SSE
    async def progress_callback(phase: str, message: str, data: dict):
        await _events.publish(conversation_id, "progress", {
            "phase": phase,
            "message": message,
            **data
        })

    # Set the callback
    dialogue.set_progress_callback(progress_callback)

    try:
        # Process the message
        response = await dialogue.process_message(conversation_id, request.message)

        # Clear callback
        dialogue.set_progress_callback(None)

        # Publish state change event
        await _events.publish(conversation_id, "state_change", {
            "state": response.state.value,
            "message": response.message
        })

        # Format response
        result_dict = None
        if response.result:
            result_dict = {
                "session_id": response.result.session_id,
                "topic": response.result.topic,
                "unique_papers": response.result.unique_papers,
                "relevant_papers": response.result.relevant_papers,
                "high_relevance_papers": response.result.high_relevance_papers,
                "clusters_created": response.result.clusters_created,
                "report_preview": (response.result.report_markdown[:500] + "...")
                    if response.result.report_markdown and len(response.result.report_markdown) > 500
                    else response.result.report_markdown
            }

        plan_dict = None
        if response.plan:
            plan_dict = {
                "query_type": response.plan.query_info.query_type.value,
                "phases": response.plan.phase_config.active_phases,
                "steps": [
                    {
                        "id": step.id,
                        "title": step.title,
                        "queries": step.queries[:5] if step.queries else []
                    }
                    for step in response.plan.plan.steps
                ]
            }

        return MessageResponse(
            conversation_id=conversation_id,
            state=response.state.value,
            message=response.message,
            plan=plan_dict,
            result=result_dict,
            needs_input=response.needs_input
        )

    except Exception as e:
        dialogue.set_progress_callback(None)
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{conversation_id}/stream")
async def stream_conversation(
    conversation_id: str,
    dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """
    Server-Sent Events stream for real-time updates.

    Events:
    - progress: Pipeline phase updates
    - state_change: Dialogue state transitions
    - message: New messages
    - complete: Research complete
    - error: Error occurred
    """
    context = await dialogue.get_context(conversation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events."""
        queue = _events.get_queue(conversation_id)

        # Send initial state
        yield f"data: {json.dumps({'type': 'connected', 'data': {'state': context.state.value}})}\n\n"

        try:
            while True:
                try:
                    # Wait for events with timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"

                    # Check if conversation is complete
                    if event.get("type") == "complete" or event.get("type") == "error":
                        break

                except asyncio.TimeoutError:
                    # Send keepalive
                    yield f": keepalive\n\n"

        except asyncio.CancelledError:
            pass
        finally:
            _events.remove_queue(conversation_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """Delete a conversation."""
    context = await dialogue.get_context(conversation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await dialogue.store.delete(conversation_id)
    _events.remove_queue(conversation_id)

    return {"message": "Conversation deleted"}
