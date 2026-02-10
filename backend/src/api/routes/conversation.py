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
from datetime import datetime
from typing import Optional, AsyncIterator
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.conversation.dialogue import DialogueManager, DialogueResponse
from src.conversation.context import ConversationContext, DialogueState
from src.research.pipeline import ResearchPipeline
from src.adapters.llm import LLMFactory
from src.core.config import settings
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
            gemini_key = settings.GEMINI_API_KEY
            openai_key = settings.OPENAI_API_KEY

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
        redis_url = settings.REDIS_URL
        try:
            await _memory_manager.connect(redis_url)
        except Exception as e:
            logger.warning(f"Redis not available: {e}")

        # Create dialogue manager
        _dialogue_manager = DialogueManager(
            llm_client=llm, pipeline=pipeline, memory=_memory_manager
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
    activity_log: list = field(default_factory=list)
    detailed_state: Optional[dict] = None


class MessageResponse(BaseModel):
    conversation_id: str
    state: str
    message: str
    plan: Optional[dict] = None
    result: Optional[dict] = None
    needs_input: bool = True


# --- Endpoints ---


@router.get("")
async def list_conversations(dialogue: DialogueManager = Depends(get_dialogue_manager)):
    """List all active conversations."""
    conversations = await dialogue.store.list_all()
    # Sort by most recent first (if created_at available)
    conversations.sort(key=lambda c: c.get("created_at", ""), reverse=True)
    return {"items": conversations, "total": len(conversations)}


@router.post("", response_model=ConversationResponse)
async def start_conversation(
    request: StartConversationRequest,
    dialogue: DialogueManager = Depends(get_dialogue_manager),
):
    """Start a new conversation."""
    context = await dialogue.start_conversation(user_id=request.user_id)

    return ConversationResponse(
        conversation_id=context.conversation_id,
        state=context.state.value,
        messages=[],
        current_topic=None,
        has_pending_plan=False,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str, dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """Get conversation state."""
    context = await dialogue.get_context(conversation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get detailed session info if available
    detailed_state = {}
    if context.research_session_id and dialogue.memory:
        session = await dialogue.memory.get_session(context.research_session_id)
        if session:
            detailed_state = {
                "phase_message": session.phase_message,
                "step_index": session.step_index,
                "total_steps": session.total_steps,
                "total_papers": session.total_papers,
                "current_phase": session.current_phase,
            }

    return ConversationResponse(
        conversation_id=context.conversation_id,
        state=context.state.value,
        messages=[m.to_dict() for m in context.get_recent_messages(50)], # Increase history limit
        current_topic=context.current_topic,
        has_pending_plan=context.pending_plan is not None,
        activity_log=context.activity_log,
        detailed_state=detailed_state,
    )


@router.post("/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    request: MessageRequest,
    background_tasks: BackgroundTasks,
    dialogue: DialogueManager = Depends(get_dialogue_manager),
):
    """Send a message to the conversation. Processing runs in background; results stream via SSE."""
    context = await dialogue.get_context(conversation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Ensure SSE queue exists before background processing starts
    _events.get_queue(conversation_id)

    # Define the background processing task
    async def process_in_background():
        try:
            with open("/tmp/tiny_researcher_debug.log", "a") as f:
                f.write(f"{datetime.utcnow()} - Starting background task for {conversation_id}\n")
        except:
            pass

        # Set up progress callback for SSE (including token_stream events)
        import uuid as import_uuid
        async def progress_callback(phase: str, message: str, data: dict):
            # 1. Publish to SSE
            await _events.publish(
                conversation_id, phase if phase == "token_stream" else "progress",
                {"phase": phase, "message": message, **data} if phase != "token_stream" else data
            )
            
            # 2. Persist to activity log (only for significant events, skip token stream)
            if phase != "token_stream":
                # Map phase to icon
                icon_map = {
                    "thinking": "🧠",
                    "plan": "📋",
                    "screening": "🔍",
                    "collect": "📄",
                    "evidence_extraction": "🔬",
                    "taxonomy": "📊",
                    "claims_gaps": "💡",
                    "hitl_gate": "🛡️",
                }
                icon = icon_map.get(phase, "⏳")
                
                # Create log entry
                import uuid
                entry = {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat(),
                    "phase": phase,
                    "icon": icon,
                    "text": message
                }
                
                # Append and save
                # Note: We need to reload context to avoid race conditions? 
                # Ideally DialogueManager handles save, but here we are outside.
                # Since DialogueManager saves at end of process_message, 
                # and this callback runs DURING execution...
                # We should append to context in memory. 
                # context object is shared reference if loaded via get_context?
                # Yes, _contexts cache in DialogueManager.
                context.activity_log.append(entry)
                
                # We optionally save to Redis here to be safe against crashes,
                # but valid concern about write contention. 
                # Let's trust DialogueManager's final save or intermediate saves if needed.
                # Actually, for long running processes, we WANT intermediate saves.
                # But simple append to memory is fine for now if we save regularly.
                # DialogueManager doesn't save automatically during execution unless we tell it.
                # Let's save context every time? Might be too heavy.
                # Let's trust that the final save will persist all logs.
                # BUT if we reload page mid-execution, we want logs.
                # So we SHOULD save.
                await dialogue.store.save(context)


        try:
            # Pass persistence-enabled callback
            response = await dialogue.process_message(
                conversation_id, request.message, progress_callback=progress_callback
            )
            # Remove global callback setting (it was deprecated/removed anyway)
            # dialogue.set_progress_callback(None)

            # Publish the assistant's message as an SSE event
            await _events.publish(
                conversation_id,
                "message",
                {"role": "assistant", "content": response.message},
            )
            context.activity_log.append({
                "id": str(import_uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "phase": "response",
                "icon": "🤖",
                "text": response.message[:100] if response.message else "Response"
            })

            # Publish state change
            await _events.publish(
                conversation_id,
                "state_change",
                {"state": response.state.value, "message": response.message},
            )
            context.activity_log.append({
                "id": str(import_uuid.uuid4()),
                "timestamp": datetime.utcnow().isoformat(),
                "phase": "state",
                "icon": "🔄",
                "text": f"State: {response.state.value}"
            })

            # Publish plan if present
            if response.plan:
                plan_dict = {
                    "query_type": response.plan.query_info.query_type.value,
                    "phases": response.plan.phase_config.active_phases,
                    "steps": [
                        {
                            "id": step.id,
                            "title": step.title,
                            "queries": step.queries[:5] if step.queries else [],
                        }
                        for step in response.plan.plan.steps
                    ],
                }
                await _events.publish(conversation_id, "plan", {"plan": plan_dict})
                context.activity_log.append({
                    "id": str(import_uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat(),
                    "phase": "plan",
                    "icon": "📋",
                    "text": f"Plan: {len(response.plan.plan.steps)} steps"
                })

            # Publish result if present
            if response.result:
                result_dict = {
                    "session_id": response.result.session_id,
                    "topic": response.result.topic,
                    "unique_papers": response.result.unique_papers,
                    "relevant_papers": response.result.relevant_papers,
                    "high_relevance_papers": response.result.high_relevance_papers,
                    "clusters_created": response.result.clusters_created,
                }
                await _events.publish(conversation_id, "result", {"result": result_dict})
                context.activity_log.append({
                    "id": str(import_uuid.uuid4()),
                    "timestamp": datetime.utcnow().isoformat(),
                    "phase": "complete",
                    "icon": "✅",
                    "text": f"Research complete. {response.result.unique_papers} papers."
                })

            # Save context with all new logs
            await dialogue.store.save(context)

            # Signal processing complete
            await _events.publish(
                conversation_id,
                "done",
                {"state": response.state.value},
            )

        except Exception as e:
            try:
                with open("/tmp/tiny_researcher_debug.log", "a") as f:
                    f.write(f"{datetime.utcnow()} - ERROR in background task: {e}\n")
            except:
                pass
            logger.error(f"Error processing message in background: {e}")
            await _events.publish(
                conversation_id,
                "error",
                {"message": str(e)},
            )

    # Run processing in background using FastAPI BackgroundTasks
    background_tasks.add_task(process_in_background)
    
    # Return immediately with 202 Accepted
    return {"status": "processing", "conversation_id": conversation_id}


@router.get("/{conversation_id}/stream")
async def stream_conversation(
    conversation_id: str, dialogue: DialogueManager = Depends(get_dialogue_manager)
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
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str, dialogue: DialogueManager = Depends(get_dialogue_manager)
):
    """Delete a conversation."""
    context = await dialogue.get_context(conversation_id)
    if not context:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await dialogue.store.delete(conversation_id)
    _events.remove_queue(conversation_id)

    return {"message": "Conversation deleted"}
