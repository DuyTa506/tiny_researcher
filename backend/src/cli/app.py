"""
ResearchCLI - Interactive command-line interface for the research assistant.

Features:
- Full conversation flow with clarification
- Streaming progress during execution
- Colorful Rich-based output
- Memory-enhanced personalization
"""

import asyncio
import sys
import os
from typing import Optional
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from src.cli.display import ResearchDisplay, StreamingDisplay
from src.conversation.dialogue import DialogueManager, DialogueResponse
from src.conversation.context import DialogueState
from src.memory import MemoryManager
from src.adapters.llm import LLMClientInterface


class ResearchCLI:
    """
    Interactive CLI for the research assistant.

    Manages the conversation loop with streaming output.
    """

    def __init__(
        self,
        llm_client: LLMClientInterface,
        user_id: str = "cli_user",
        redis_url: Optional[str] = None,
        enable_streaming: bool = True,
    ):
        self.llm = llm_client
        self.user_id = user_id
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.enable_streaming = enable_streaming

        self.display = ResearchDisplay()
        self.memory: Optional[MemoryManager] = None
        self.dialogue: Optional[DialogueManager] = None
        self.conversation_id: Optional[str] = None
        self._running = False

    async def initialize(self):
        """Initialize the CLI components."""
        self.display.print_info("Initializing research assistant...")

        # Initialize memory
        self.memory = MemoryManager()
        try:
            await self.memory.connect(self.redis_url)
            self.display.print_success("Connected to Redis")
        except Exception as e:
            self.display.print_warning(f"Redis not available: {e}")
            self.display.print_info("Running in memory-only mode")

        # Initialize dialogue manager with streaming pipeline
        from src.research.pipeline import ResearchPipeline

        pipeline = ResearchPipeline(self.llm, use_adaptive_planner=True)

        self.dialogue = DialogueManager(
            llm_client=self.llm, pipeline=pipeline, memory=self.memory
        )

        # Connect DialogueManager to Redis (for ConversationStore)
        try:
            await self.dialogue.connect(self.redis_url)
        except Exception as e:
            self.display.print_warning(f"Conversation store not available: {e}")

        # Start conversation
        context = await self.dialogue.start_conversation(user_id=self.user_id)
        self.conversation_id = context.conversation_id

        self.display.print_success("Ready!")

    async def cleanup(self):
        """Cleanup resources."""
        if self.memory:
            await self.memory.close()
        if self.dialogue:
            await self.dialogue.close()

    async def run(self):
        """Main CLI loop."""
        self.display.clear()
        self.display.print_banner()
        self.display.print_help()

        await self.initialize()

        self._running = True
        while self._running:
            try:
                # Get user input
                user_input = self.display.print_user_prompt()

                if not user_input.strip():
                    continue

                # Check for exit commands
                if user_input.lower() in ("quit", "exit", "q"):
                    self.display.print_info("Goodbye!")
                    break

                # Check for help command
                if user_input.lower() in ("help", "?"):
                    self.display.print_help()
                    continue

                # Process the message
                await self._process_message(user_input)

            except KeyboardInterrupt:
                self.display.print_info("\nInterrupted. Type 'quit' to exit.")
            except EOFError:
                # End of input (e.g., piped input)
                self.display.print_info("\nEnd of input. Goodbye!")
                break
            except Exception as e:
                self.display.print_error(f"Error: {e}")

        await self.cleanup()

    async def _show_results(self, response: DialogueResponse):
        """Show research results."""
        if response.result:
            self.display.print_result(response.result)

            # Show report preview if available
            if response.result.report_markdown:
                # Save report to file
                report_path = await self._save_report(response.result)

                self.display.print_divider("Report Preview")
                preview = response.result.report_markdown[:1000]
                if len(response.result.report_markdown) > 1000:
                    preview += f"\n\n[dim]... (truncated, full report saved to {report_path})[/dim]"
                self.display.print_markdown(preview)

            # Show papers summary
            if response.result.papers:
                self.display.print_divider("Top Papers")
                self.display.print_papers(response.result.papers[:5])

        self.display.console.print(
            "\n[bold]Research complete![/bold] Start a new topic or type 'quit' to exit."
        )

    async def _save_report(self, result) -> str:
        """Save report to markdown file."""
        from datetime import datetime
        import re

        # Create reports directory
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)

        # Generate filename from topic
        topic = result.topic if hasattr(result, "topic") else "research"

        # Extract English terms for filename (strip non-ASCII characters)
        # This handles Vietnamese/Chinese input by keeping only ASCII words
        ascii_words = re.findall(r"[a-zA-Z][a-zA-Z0-9-]+", topic)
        if ascii_words:
            safe_topic = "_".join(ascii_words)[:60]
        else:
            safe_topic = "research_report"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_topic}_{timestamp}.md"
        filepath = reports_dir / filename

        # Write report
        filepath.write_text(result.report_markdown, encoding="utf-8")

        self.display.print_success(f"Report saved to: {filepath}")
        return str(filepath)

    async def _process_message(self, message: str):
        """Process a user message and display the response."""
        if not self.dialogue or not self.conversation_id:
            self.display.print_error("Not initialized")
            return

        # Check for special commands
        if message.startswith("/ask "):
            # Direct LLM question with streaming
            question = message[5:].strip()
            if question:
                await self.ask_with_streaming(question)
            return

        if message.startswith("/explain "):
            # Explain a topic with streaming
            topic = message[9:].strip()
            if topic:
                await self._explain_with_streaming(topic)
            return

        # Check if this might trigger execution (confirming in REVIEWING state)
        context = await self.dialogue.get_context(self.conversation_id)
        is_confirming_plan = (
            context
            and context.state == DialogueState.REVIEWING
            and message.lower() in ("yes", "ok", "y", "proceed", "go", "đồng ý", "có")
        )

        if is_confirming_plan:
            # Execute with streaming display
            await self._execute_with_streaming(message)
        else:
            # Normal processing with status indicator
            with self.display.console.status("[bold cyan]Thinking...[/bold cyan]"):
                response = await self.dialogue.process_message(
                    self.conversation_id, message
                )

            # Display state
            self.display.print_state(response.state.value)

            # Handle response based on state
            if response.state == DialogueState.CLARIFYING:
                # Stream the clarification message if enabled
                if self.enable_streaming:
                    await self._stream_clarification(response.message)
                else:
                    self.display.print_agent(response.message)

            elif response.state == DialogueState.REVIEWING:
                self.display.print_agent("Here's my research plan:")
                if response.plan:
                    self.display.print_plan(response.plan)
                self.display.console.print(
                    "\n[bold]Proceed with this plan?[/bold] (yes/no/edit)"
                )

            elif response.state == DialogueState.COMPLETE:
                await self._show_results(response)

            elif response.state == DialogueState.ERROR:
                self.display.print_error(response.message)

            elif response.state == DialogueState.IDLE:
                self.display.print_agent(response.message)

            else:
                self.display.print_agent(response.message)

    async def _stream_clarification(self, message: str):
        """Stream clarification message with typewriter effect."""
        self.display.print_agent_streaming_start()

        # Simulate streaming for pre-generated message
        words = message.split()
        for i, word in enumerate(words):
            self.display.print_agent_chunk(word)
            if i < len(words) - 1:
                self.display.print_agent_chunk(" ")
            await asyncio.sleep(0.02)  # Small delay for effect

        self.display.print_agent_streaming_end()

    async def _explain_with_streaming(self, topic: str):
        """Explain a topic using streaming LLM response."""
        prompt = f"""Explain '{topic}' in the context of academic research.

Be concise but informative. Include:
1. What it is
2. Why it matters in research
3. Key papers or concepts to know

Use markdown formatting."""

        await self._stream_llm_response(prompt)

    async def _execute_with_streaming(self, confirm_message: str):
        """Execute research with streaming progress display."""
        streaming = StreamingDisplay(self.display.console)
        papers_count = 0

        async def progress_callback(phase: str, message: str, data: dict):
            """Callback for pipeline progress updates."""
            nonlocal papers_count
            papers_count = data.get("papers", papers_count)
            streaming.update(
                phase=phase.replace("_", " ").title(),
                papers_collected=papers_count,
                message=message,
            )

        # Set the callback on the dialogue manager
        self.dialogue.set_progress_callback(progress_callback)

        try:
            streaming.start()
            self.display.print_info("Starting research...")

            # Process the confirmation message (will trigger execution)
            response = await self.dialogue.process_message(
                self.conversation_id, confirm_message
            )

            streaming.stop()

            # Clear the callback
            self.dialogue.set_progress_callback(None)

            # Show results
            self.display.print_state(response.state.value)
            await self._show_results(response)

        except Exception as e:
            streaming.stop()
            self.dialogue.set_progress_callback(None)
            self.display.print_error(f"Execution failed: {e}")

    async def _stream_llm_response(self, prompt: str, system_instruction: str = None):
        """Stream an LLM response directly to the console."""
        self.display.print_agent_streaming_start()

        full_response = ""
        try:
            async for chunk in self.llm.generate_stream(prompt, system_instruction):
                self.display.print_agent_chunk(chunk)
                full_response += chunk
        except Exception as e:
            self.display.print_error(f"Streaming error: {e}")

        self.display.print_agent_streaming_end()
        return full_response

    async def ask_with_streaming(self, question: str) -> str:
        """
        Ask a question and stream the response.

        Use this for direct LLM interactions in the CLI.
        """
        system_instruction = """You are a helpful research assistant.
Answer concisely and helpfully. Use markdown formatting when appropriate."""

        return await self._stream_llm_response(question, system_instruction)


async def create_cli_with_gemini() -> ResearchCLI:
    """Create CLI with Gemini LLM client."""
    from src.adapters.llm import GeminiClient

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    llm = GeminiClient(api_key=api_key)
    return ResearchCLI(llm_client=llm)


async def create_cli_with_openai() -> ResearchCLI:
    """Create CLI with OpenAI LLM client."""
    from src.adapters.llm import OpenAIClient

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    llm = OpenAIClient(api_key=api_key)
    return ResearchCLI(llm_client=llm)


async def main():
    """Main entry point for the CLI."""
    from dotenv import load_dotenv

    load_dotenv()

    # Try Gemini first, then OpenAI
    try:
        cli = await create_cli_with_gemini()
    except ValueError:
        try:
            cli = await create_cli_with_openai()
        except ValueError:
            print("Error: No API key found. Set GEMINI_API_KEY or OPENAI_API_KEY")
            sys.exit(1)

    await cli.run()


if __name__ == "__main__":
    asyncio.run(main())
