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
        language = self._detect_language_from_context(context)

        # Store any URLs found in the message
        if intent.extracted_urls:
            context.pending_urls.extend(intent.extracted_urls)

        if intent.intent == UserIntent.NEW_TOPIC:
            return await self._analyze_and_maybe_clarify(context, intent.original_message)

        if intent.intent == UserIntent.CHAT:
            return await self._handle_chat(context, intent)

        if intent.intent == UserIntent.OTHER:
            # Treat as potential research topic if long enough
            if len(intent.original_message.split()) >= 3:
                return await self._analyze_and_maybe_clarify(context, intent.original_message)

            return await self._handle_chat(context, intent)

        return DialogueResponse(
            message=self._get_localized_message("ask_topic", language),
            state=DialogueState.IDLE
        )

    def _get_localized_message(self, key: str, language: str = "English") -> str:
        """Get localized message based on detected language."""
        messages = {
            "cancel_research": {
                "English": "No problem. What else would you like to research?",
                "Vietnamese": "Không sao cả. Bạn muốn tìm hiểu về gì nữa?",
                "Spanish": "No hay problema. ¿Qué más te gustaría investigar?",
                "French": "Pas de problème. Qu'aimeriez-vous rechercher d'autre?",
                "German": "Kein Problem. Was möchten Sie sonst noch recherchieren?"
            },
            "plan_cancelled": {
                "English": "Cancelled. What else would you like to research?",
                "Vietnamese": "Đã hủy. Bạn muốn tìm hiểu về gì khác?",
                "Spanish": "Cancelado. ¿Qué más te gustaría investigar?",
                "French": "Annulé. Qu'aimeriez-vous rechercher d'autre?",
                "German": "Abgebrochen. Was möchten Sie sonst noch recherchieren?"
            },
            "proceed_or_edit": {
                "English": "Say 'ok' to proceed, 'cancel' to stop, or describe changes.",
                "Vietnamese": "Nói 'ok' để tiếp tục, 'hủy' để dừng, hoặc mô tả thay đổi.",
                "Spanish": "Di 'ok' para continuar, 'cancelar' para detener, o describe los cambios.",
                "French": "Dites 'ok' pour continuer, 'annuler' pour arrêter, ou décrivez les modifications.",
                "German": "Sagen Sie 'ok' zum Fortfahren, 'abbrechen' zum Stoppen oder beschreiben Sie Änderungen."
            },
            "still_working": {
                "English": "Still working on the research...",
                "Vietnamese": "Vẫn đang nghiên cứu...",
                "Spanish": "Todavía trabajando en la investigación...",
                "French": "Toujours en train de rechercher...",
                "German": "Arbeite noch an der Recherche..."
            },
            "ask_topic": {
                "English": "What topic would you like to research?",
                "Vietnamese": "Bạn muốn tìm hiểu về chủ đề gì?",
                "Spanish": "¿Qué tema te gustaría investigar?",
                "French": "Quel sujet aimeriez-vous rechercher?",
                "German": "Welches Thema möchten Sie recherchieren?"
            },
            "try_again": {
                "English": "Let's try again. What would you like to research?",
                "Vietnamese": "Thử lại nhé. Bạn muốn tìm hiểu về gì?",
                "Spanish": "Intentémoslo de nuevo. ¿Qué te gustaría investigar?",
                "French": "Essayons à nouveau. Qu'aimeriez-vous rechercher?",
                "German": "Versuchen wir es noch einmal. Was möchten Sie recherchieren?"
            },
            "no_plan": {
                "English": "No plan to execute. What would you like to research?",
                "Vietnamese": "Không có kế hoạch nào để thực hiện. Bạn muốn tìm hiểu về gì?",
                "Spanish": "No hay plan para ejecutar. ¿Qué te gustaría investigar?",
                "French": "Aucun plan à exécuter. Qu'aimeriez-vous rechercher?",
                "German": "Kein Plan zum Ausführen. Was möchten Sie recherchieren?"
            },
            "proceed_with_understanding": {
                "English": "(Or say 'ok' to proceed with my understanding)",
                "Vietnamese": "(Hoặc nói 'ok' để tiếp tục với hiểu biết của tôi)",
                "Spanish": "(O di 'ok' para continuar con mi comprensión)",
                "French": "(Ou dites 'ok' pour continuer avec ma compréhension)",
                "German": "(Oder sagen Sie 'ok', um mit meinem Verständnis fortzufahren)"
            },
        }

        return messages.get(key, {}).get(language, messages.get(key, {}).get("English", ""))

    def _detect_language_from_context(self, context: ConversationContext) -> str:
        """Detect language from conversation context."""
        # Check recent messages for language indicators
        recent_messages = context.messages[-3:] if context.messages else []

        for msg in reversed(recent_messages):
            if msg.role == MessageRole.USER:
                # Use clarifier's language detection
                detected = self.clarifier._detect_language(msg.content)
                if detected != "English":
                    return detected

        return "English"

    async def _handle_clarifying(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages during clarification phase."""
        language = self._detect_language_from_context(context)

        # User wants to cancel
        if intent.intent == UserIntent.CANCEL:
            context.pending_clarification = None
            context.transition_to(DialogueState.IDLE)
            return DialogueResponse(
                message=self._get_localized_message("cancel_research", language),
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
        language = self._detect_language_from_context(context)

        if intent.intent == UserIntent.CONFIRM:
            return await self._execute_plan(context)

        elif intent.intent == UserIntent.CANCEL:
            context.clear_pending_plan()
            context.transition_to(DialogueState.IDLE)
            return DialogueResponse(
                message=self._get_localized_message("plan_cancelled", language),
                state=DialogueState.IDLE
            )

        elif intent.intent == UserIntent.EDIT:
            return await self._edit_plan(context, intent.edit_text)

        elif intent.intent == UserIntent.NEW_TOPIC:
            return await self._analyze_and_maybe_clarify(context, intent.original_message)

        return DialogueResponse(
            message=self._get_localized_message("proceed_or_edit", language),
            state=DialogueState.REVIEWING,
            plan=context.pending_plan
        )

    async def _handle_executing(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle messages while executing."""
        language = self._detect_language_from_context(context)
        return DialogueResponse(
            message=self._get_localized_message("still_working", language),
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

        if intent.intent == UserIntent.CHAT:
            return await self._handle_chat(context, intent)

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
        language = self._detect_language_from_context(context)

        if intent.intent == UserIntent.NEW_TOPIC:
            return await self._analyze_and_maybe_clarify(context, intent.original_message)

        if intent.intent == UserIntent.CHAT:
            return await self._handle_chat(context, intent)

        context.transition_to(DialogueState.IDLE)
        return DialogueResponse(
            message=self._get_localized_message("try_again", language),
            state=DialogueState.IDLE
        )

    async def _handle_chat(
        self,
        context: ConversationContext,
        intent: IntentResult
    ) -> DialogueResponse:
        """Handle casual conversation - greetings, questions about the agent, etc."""
        language = self._detect_language_from_context(context)
        message = intent.original_message

        if self.llm:
            try:
                prompt = f"""You are a friendly research assistant. The user is chatting casually with you.

User's message: "{message}"

Respond naturally and conversationally in {language}. Keep it brief (1-3 sentences).

Guidelines:
- If they greet you, greet back warmly and ask what topic they'd like to research
- If they ask your name, say you're a research assistant (trợ lý nghiên cứu) - you don't have a personal name
- If they ask what you can do, briefly explain: you help find and analyze academic papers on any topic
- If they thank you, respond naturally
- If it's unclear, gently guide them to tell you a research topic
- Be natural and friendly, like a colleague
- ALWAYS respond in {language}"""

                response = await self.llm.generate(prompt)
                return DialogueResponse(
                    message=response.strip(),
                    state=context.state
                )
            except Exception as e:
                logger.warning(f"Chat LLM failed: {e}")

        # Fallback without LLM
        fallback = {
            "English": "Hi! I'm a research assistant. Tell me a topic and I'll help you find and analyze papers on it.",
            "Vietnamese": "Chào bạn! Tôi là trợ lý nghiên cứu. Hãy cho tôi biết chủ đề bạn muốn tìm hiểu, tôi sẽ giúp bạn tìm và phân tích các bài báo khoa học.",
            "Spanish": "¡Hola! Soy un asistente de investigación. Dime un tema y te ayudaré a encontrar y analizar artículos.",
            "French": "Bonjour! Je suis un assistant de recherche. Dites-moi un sujet et je vous aiderai à trouver des articles.",
            "German": "Hallo! Ich bin ein Forschungsassistent. Nennen Sie mir ein Thema und ich helfe Ihnen, Artikel zu finden."
        }

        return DialogueResponse(
            message=fallback.get(language, fallback["English"]),
            state=context.state
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
                if clarification.detected_language == "Vietnamese":
                    message += "\n\nTừ lịch sử của bạn:"
                elif clarification.detected_language == "Spanish":
                    message += "\n\nDe tu historial:"
                elif clarification.detected_language == "French":
                    message += "\n\nDe votre historique:"
                elif clarification.detected_language == "German":
                    message += "\n\nAus Ihrer Historie:"
                else:
                    message += "\n\nFrom your history:"

                for session in memory_context.similar_sessions[:2]:
                    message += f"\n  - {session}"

            message += "\n\n" + self._get_localized_message("proceed_with_understanding", clarification.detected_language)

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

            # Add user-provided URLs extracted from messages
            if context.pending_urls:
                request.sources = list(set(context.pending_urls))
                context.pending_urls = []  # Clear after use

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
        language = self._detect_language_from_context(context)

        if not context.pending_plan or not context.current_request:
            return DialogueResponse(
                message=self._get_localized_message("no_plan", language),
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
