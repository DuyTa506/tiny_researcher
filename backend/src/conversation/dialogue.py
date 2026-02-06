"""
DialogueManager - Orchestrates the conversation flow.

Humanoid approach:
1. CLARIFYING - Ask questions before planning (like a real researcher)
2. PLANNING - Generate research plan
3. REVIEWING - Human approves/edits
4. EXECUTING - Run the research
5. COMPLETE - Present results

Memory-enhanced:
- Uses episodic memory to recall similar past sessions
- Uses preferences to personalize behavior
- Records sessions for future learning
"""

import uuid
import time
import logging
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass, asdict

from src.adapters.llm import LLMClientInterface
from src.core.schema import ResearchRequest
from src.planner.adaptive_planner import AdaptivePlan
from src.research.pipeline import ResearchPipeline, PipelineResult, ProgressCallback
from src.conversation.context import (
    ConversationContext,
    ConversationStore,
    DialogueState,
    MessageRole
)
from src.conversation.intent import IntentClassifier, UserIntent, IntentResult
from src.conversation.clarifier import QueryClarifier, ClarificationResult
from src.memory import MemoryManager, MemoryContext, SessionOutcome

logger = logging.getLogger(__name__)


@dataclass
class DialogueResponse:
    """Response from the dialogue manager."""
    message: str
    state: DialogueState
    plan: Optional[AdaptivePlan] = None
    result: Optional[PipelineResult] = None
    needs_input: bool = True


class DialogueManager:
    """
    Manages conversation flow for research assistant.

    Humanoid state machine:
    IDLE → CLARIFYING → PLANNING → REVIEWING → EXECUTING → COMPLETE

    Key insight: A real researcher ASKS before searching.

    Memory-enhanced:
    - Recalls similar past sessions to improve planning
    - Learns user preferences over time
    - Records sessions for future reference
    """

    def __init__(
        self,
        llm_client: LLMClientInterface,
        pipeline: Optional[ResearchPipeline] = None,
        memory: Optional[MemoryManager] = None
    ):
        self.llm = llm_client
        self.pipeline = pipeline or ResearchPipeline(llm_client, use_adaptive_planner=True)
        self.intent_classifier = IntentClassifier(llm_client)
        self.clarifier = QueryClarifier(llm_client)
        self.memory = memory or MemoryManager()  # NEW: Memory manager
        self.store = ConversationStore()
        self._contexts: dict[str, ConversationContext] = {}
        self._session_start_times: dict[str, float] = {}  # Track session durations
        self._progress_callback: Optional[ProgressCallback] = None  # For streaming updates

    def set_progress_callback(self, callback: ProgressCallback):
        """Set callback for execution progress updates."""
        self._progress_callback = callback

    async def connect(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize connections."""
        await self.store.connect(redis_url)
        await self.memory.connect(redis_url)  # NEW

    async def close(self):
        """Cleanup."""
        await self.store.close()
        await self.memory.close()  # NEW

    async def start_conversation(self, user_id: str = "default") -> ConversationContext:
        """Start a new conversation."""
        conversation_id = str(uuid.uuid4())
        context = ConversationContext(conversation_id=conversation_id)
        context.user_id = user_id  # Track user for memory
        self._contexts[conversation_id] = context
        self._session_start_times[conversation_id] = time.time()
        await self.store.save(context)
        logger.info(f"Started conversation {conversation_id} for user {user_id}")
        return context

    async def get_context(self, conversation_id: str) -> Optional[ConversationContext]:
        """Get or load a conversation context."""
        if conversation_id in self._contexts:
            return self._contexts[conversation_id]

        context = await self.store.load(conversation_id)
        if context:
            self._contexts[conversation_id] = context
            return context
        return None

    async def process_message(
        self,
        conversation_id: str,
        user_message: str
    ) -> DialogueResponse:
        """Process a user message and generate response."""
        context = await self.get_context(conversation_id)
        if not context:
            context = await self.start_conversation()
            conversation_id = context.conversation_id

        context.add_user_message(user_message)

        # Build context hint for intent classification based on current state
        state_context = self._get_state_context(context)

        # Classify intent using LLM with state context
        intent_result = await self.intent_classifier.classify_with_llm(
            user_message,
            context=state_context
        )
        logger.info(f"Intent: {intent_result.intent.value}")

        # Handle based on state
        response = await self._handle_message(context, intent_result)

        context.add_assistant_message(response.message)
        await self.store.save(context)

        return response

    def _get_state_context(self, context: ConversationContext) -> str:
        """Get context hint for intent classification based on current state."""
        state = context.state

        if state == DialogueState.REVIEWING:
            return "User was just shown a research plan and asked 'Proceed with this plan? (yes/no/edit)'"
        elif state == DialogueState.CLARIFYING:
            return "User was asked clarifying questions about their research topic"
        elif state == DialogueState.EXECUTING:
            return "Research is currently being executed"
        elif state == DialogueState.COMPLETE:
            return "Research just completed, user might want to start a new topic"
        else:
            return ""

    async def _handle_message(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle message based on current state and intent."""
        state = context.state

        if state == DialogueState.IDLE:
            return await self._handle_idle(context, intent)
        elif state == DialogueState.CLARIFYING:
            return await self._handle_clarifying(context, intent)
        elif state == DialogueState.REVIEWING:
            return await self._handle_reviewing(context, intent)
        elif state == DialogueState.EXECUTING:
            return await self._handle_executing(context, intent)
        elif state == DialogueState.COMPLETE:
            return await self._handle_complete(context, intent)
        elif state == DialogueState.ERROR:
            return await self._handle_error(context, intent)
        else:
            return DialogueResponse(
                message="What would you like to research?",
                state=DialogueState.IDLE
            )

    async def _handle_idle(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages when idle."""

        if intent.intent == UserIntent.NEW_TOPIC:
            return await self._analyze_and_maybe_clarify(context, intent.original_message)

        if intent.intent == UserIntent.OTHER:
            # Treat as potential research topic if long enough
            if len(intent.original_message.split()) >= 2:
                return await self._analyze_and_maybe_clarify(context, intent.original_message)

            return DialogueResponse(
                message=self._get_help_text(),
                state=DialogueState.IDLE
            )

        return DialogueResponse(
            message="What topic would you like to research?",
            state=DialogueState.IDLE
        )

    async def _handle_clarifying(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages during clarification phase."""

        # User wants to cancel
        if intent.intent == UserIntent.CANCEL:
            context.pending_clarification = None
            context.transition_to(DialogueState.IDLE)
            return DialogueResponse(
                message="No problem. What else would you like to research?",
                state=DialogueState.IDLE
            )

        # User provides clarification or says "proceed anyway"
        if intent.intent == UserIntent.CONFIRM:
            # User wants to proceed without answering questions
            return await self._proceed_to_planning(context)

        # User provides additional context - incorporate and proceed
        if context.pending_clarification:
            clarification = context.pending_clarification
            original_query = clarification.get("original_query", "")

            # Combine original query with user's clarification
            enriched_topic = f"{original_query} ({intent.original_message})"
            context.current_topic = enriched_topic
            context.pending_clarification = None

            return await self._create_plan(context, enriched_topic)

        return await self._proceed_to_planning(context)

    async def _handle_reviewing(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages when reviewing a plan."""

        if intent.intent == UserIntent.CONFIRM:
            return await self._execute_plan(context)

        elif intent.intent == UserIntent.CANCEL:
            context.clear_pending_plan()
            context.transition_to(DialogueState.IDLE)
            return DialogueResponse(
                message="Cancelled. What else would you like to research?",
                state=DialogueState.IDLE
            )

        elif intent.intent == UserIntent.EDIT:
            return await self._edit_plan(context, intent.edit_text)

        elif intent.intent == UserIntent.NEW_TOPIC:
            return await self._analyze_and_maybe_clarify(context, intent.original_message)

        return DialogueResponse(
            message="Say 'ok' to proceed, 'cancel' to stop, or describe changes.",
            state=DialogueState.REVIEWING,
            plan=context.pending_plan
        )

    async def _handle_executing(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages while executing."""
        return DialogueResponse(
            message="Still working on the research...",
            state=DialogueState.EXECUTING,
            needs_input=False
        )

    async def _handle_complete(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages after research is complete."""

        if intent.intent == UserIntent.NEW_TOPIC:
            return await self._analyze_and_maybe_clarify(context, intent.original_message)

        return DialogueResponse(
            message=context.result_summary or "Research complete. Start a new topic?",
            state=DialogueState.COMPLETE
        )

    async def _handle_error(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages after an error."""
        if intent.intent == UserIntent.NEW_TOPIC:
            return await self._analyze_and_maybe_clarify(context, intent.original_message)

        context.transition_to(DialogueState.IDLE)
        return DialogueResponse(
            message="Let's try again. What would you like to research?",
            state=DialogueState.IDLE
        )

    async def _analyze_and_maybe_clarify(
        self,
        context: ConversationContext,
        topic: str
    ) -> DialogueResponse:
        """
        Analyze the query and decide: clarify or plan directly.

        This is the "Think Before Plan" step.
        Uses memory to enrich context and decide if clarification is needed.
        """
        context.current_topic = topic
        user_id = getattr(context, 'user_id', 'default')

        # Get memory context for this user/topic
        memory_context = await self.memory.get_context(user_id, topic)

        # Check if we should skip clarification based on memory
        should_skip = await self.memory.should_skip_clarification(user_id, topic)

        # Analyze the query
        clarification = await self.clarifier.analyze(topic)

        # Note: Don't append memory context to clarification.understanding
        # as it causes nested history in stored sessions. Memory context is
        # shown separately in the clarification message.

        if clarification.needs_clarification and not should_skip:
            # Store clarification context
            context.pending_clarification = {
                "original_query": clarification.original_query,
                "understanding": clarification.understanding,  # Keep clean
                "sub_queries": clarification.sub_queries,
                "questions": clarification.questions,
                "memory_context": memory_context.to_prompt_context(),
            }
            context.transition_to(DialogueState.CLARIFYING)

            # Format message
            message = self.clarifier.format_clarification_message(clarification)

            # Add memory hints if available
            if memory_context.similar_sessions:
                message += "\n\n**From your history:**"
                for session in memory_context.similar_sessions[:2]:
                    message += f"\n  - {session}"

            message += "\n\n(Or say 'ok' to proceed with my understanding)"

            return DialogueResponse(
                message=message,
                state=DialogueState.CLARIFYING
            )

        # Query is clear (or user is experienced), proceed to planning
        return await self._create_plan(context, topic, memory_context)

    async def _proceed_to_planning(
        self,
        context: ConversationContext
    ) -> DialogueResponse:
        """Proceed to planning with current understanding."""
        topic = context.current_topic or ""
        user_id = getattr(context, 'user_id', 'default')

        # If we have clarification context, use the enriched understanding
        if context.pending_clarification:
            understanding = context.pending_clarification.get("understanding", topic)
            sub_queries = context.pending_clarification.get("sub_queries", [])

            # Create a more structured topic from clarification
            if sub_queries:
                topic = f"{understanding} (Focus: {'; '.join(sub_queries)})"
            else:
                topic = understanding

            context.pending_clarification = None

        # Get memory context for planning
        memory_context = await self.memory.get_context(user_id, topic)

        return await self._create_plan(context, topic, memory_context)

    async def _create_plan(
        self,
        context: ConversationContext,
        topic: str,
        memory_context: Optional[MemoryContext] = None
    ) -> DialogueResponse:
        """Create a research plan, enriched with memory context."""
        context.transition_to(DialogueState.PLANNING)

        try:
            # Build request with memory hints
            request = ResearchRequest(topic=topic)

            # Enrich request with memory context if available
            if memory_context:
                # Add preferred sources if user has history
                if memory_context.preferred_sources:
                    request.sources = memory_context.preferred_sources

                # Adjust paper limits based on preferences
                if memory_context.min_papers:
                    request.min_papers = memory_context.min_papers
                if memory_context.max_papers:
                    request.max_papers = memory_context.max_papers

            plan = await self.pipeline.generate_adaptive_plan(request)

            context.set_pending_plan(plan, request)

            plan_display = self._format_plan(plan)
            return DialogueResponse(
                message=f"**Research Plan:**\n\n{plan_display}\n\nProceed?",
                state=DialogueState.REVIEWING,
                plan=plan
            )

        except Exception as e:
            logger.error(f"Failed to create plan: {e}")
            context.transition_to(DialogueState.ERROR)
            return DialogueResponse(
                message=f"Error creating plan: {e}",
                state=DialogueState.ERROR
            )

    async def _execute_plan(self, context: ConversationContext) -> DialogueResponse:
        """Execute the approved plan and record to memory."""
        if not context.pending_plan or not context.current_request:
            return DialogueResponse(
                message="No plan to execute. What would you like to research?",
                state=DialogueState.IDLE
            )

        context.transition_to(DialogueState.EXECUTING)
        user_id = getattr(context, 'user_id', 'default')
        start_time = time.time()

        try:
            result = await self.pipeline.execute_plan(
                context.current_request,
                adaptive_plan=context.pending_plan,
                progress_callback=self._progress_callback
            )

            duration = time.time() - start_time
            context.research_session_id = result.session_id
            context.result_summary = self._format_result(result)

            # Record successful session to episodic memory
            # Use original_query for topic to avoid nested history in summaries
            original_query = context.current_request.topic if context.current_request else ""
            await self.memory.record_session(
                user_id=user_id,
                session_id=result.session_id,
                topic=original_query,  # Use clean original query, not enriched topic
                original_query=original_query,
                papers_found=result.unique_papers,
                relevant_papers=result.relevant_papers,
                high_relevance_papers=result.high_relevance_papers,
                sources_used=getattr(result, 'sources_used', []),
                outcome=SessionOutcome.SUCCESS,
                duration_seconds=duration
            )

            # Learn from this interaction
            await self.memory.learn_from_interaction(
                user_id=user_id,
                topic=original_query,
                sources=getattr(result, 'sources_used', [])
            )

            context.clear_pending_plan()
            context.transition_to(DialogueState.COMPLETE)

            return DialogueResponse(
                message=f"Done!\n\n{context.result_summary}",
                state=DialogueState.COMPLETE,
                result=result
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Execution failed: {e}")

            # Record failed session - use original query for clean topic
            original_query = context.current_request.topic if context.current_request else ""
            await self.memory.record_session(
                user_id=user_id,
                session_id=context.conversation_id,
                topic=original_query,  # Use clean original query
                original_query=original_query,
                outcome=SessionOutcome.FAILED,
                duration_seconds=duration
            )

            context.transition_to(DialogueState.ERROR)
            return DialogueResponse(
                message=f"Research failed: {e}",
                state=DialogueState.ERROR
            )

    async def _edit_plan(
        self,
        context: ConversationContext,
        edit_text: str
    ) -> DialogueResponse:
        """Edit the pending plan."""
        if not context.pending_plan:
            return DialogueResponse(
                message="No plan to edit.",
                state=DialogueState.IDLE
            )

        plan = context.pending_plan.plan
        edit_lower = edit_text.lower()

        if "add" in edit_lower or "thêm" in edit_lower:
            for keyword in ["add", "thêm"]:
                if keyword in edit_lower:
                    to_add = edit_lower.split(keyword, 1)[-1].strip()
                    if to_add and plan.steps:
                        for step in plan.steps:
                            if step.action == "research":
                                step.queries.append(to_add)
                                break
                    break

        elif "remove" in edit_lower or "xóa" in edit_lower:
            for keyword in ["remove", "xóa"]:
                if keyword in edit_lower:
                    to_remove = edit_lower.split(keyword, 1)[-1].strip()
                    for step in plan.steps:
                        step.queries = [q for q in step.queries if to_remove not in q.lower()]
                    break

        plan_display = self._format_plan(context.pending_plan)
        return DialogueResponse(
            message=f"Updated:\n\n{plan_display}\n\nProceed?",
            state=DialogueState.REVIEWING,
            plan=context.pending_plan
        )

    def _format_plan(self, plan: AdaptivePlan) -> str:
        """Format plan for display."""
        lines = [
            f"**Mode:** {plan.query_info.query_type.value.upper()}",
            f"**Phases:** {', '.join(plan.phase_config.active_phases)}",
            "",
            "**Steps:**"
        ]
        for step in plan.plan.steps:
            queries = ", ".join(step.queries[:3]) if step.queries else "N/A"
            lines.append(f"  {step.id}. {step.title}")
            lines.append(f"     Queries: {queries}")
        return "\n".join(lines)

    def _format_result(self, result: PipelineResult) -> str:
        """Format result for display."""
        lines = [
            f"**Topic:** {result.topic}",
            f"**Papers found:** {result.unique_papers}",
            f"**Relevant:** {result.relevant_papers}",
            f"**High relevance:** {result.high_relevance_papers}",
        ]
        if result.clusters:
            lines.append(f"**Clusters:** {len(result.clusters)}")
        if result.report_markdown:
            lines.append(f"**Report:** Generated")
        return "\n".join(lines)

    def _get_help_text(self) -> str:
        """Get help text."""
        return """Research assistant - just tell me a topic!

I'll ask clarifying questions if your query is complex, then create a plan for your approval.

Examples:
- "transformer models"
- "find attention-free methods and adapt to linear transformers"
- "compare BERT vs GPT architectures"

During conversation:
- Answer my questions to help me understand your goal
- "ok" to proceed with my understanding
- "cancel" to start over"""
