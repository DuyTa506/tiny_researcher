"""
Display utilities for CLI using Rich library.

Provides:
- Themed console output
- Progress indicators
- Streaming status updates
- Formatted tables and panels
"""

from typing import Optional, List, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.style import Style
from rich.theme import Theme

# Custom theme for the research assistant
RESEARCH_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green bold",
        "agent": "blue bold",
        "user": "magenta bold",
        "phase": "yellow",
        "paper": "cyan",
        "highlight": "bold white on blue",
    }
)


class ResearchDisplay:
    """
    Rich-based display manager for the research CLI.

    Provides themed output, progress tracking, and streaming updates.
    """

    def __init__(self):
        self.console = Console(theme=RESEARCH_THEME)
        self._live: Optional[Live] = None

    def clear(self):
        """Clear the console."""
        self.console.clear()

    def print_banner(self):
        """Print the application banner."""
        banner = """
╔══════════════════════════════════════════════════════════════════╗
║                  🔬 RESEARCH ASSISTANT                           ║
║                   Intelligent Paper Discovery                    ║
╚══════════════════════════════════════════════════════════════════╝
        """
        self.console.print(
            Panel(
                Text(banner.strip(), justify="center"),
                style="bold cyan",
                border_style="cyan",
            )
        )

    def print_help(self):
        """Print help text."""
        help_text = """
[bold]Research Commands:[/bold]
  • Type your research topic to start
  • [cyan]ok[/cyan] / [cyan]yes[/cyan] - Confirm and proceed
  • [cyan]cancel[/cyan] / [cyan]no[/cyan] - Cancel current operation
  • [cyan]add <text>[/cyan] - Add to current plan
  • [cyan]remove <text>[/cyan] - Remove from plan

[bold]Chat Commands (streaming):[/bold]
  • [cyan]/ask <question>[/cyan] - Ask any question (streams response)
  • [cyan]/explain <topic>[/cyan] - Get explanation of a topic

[bold]General:[/bold]
  • [cyan]help[/cyan] - Show this help
  • [cyan]quit[/cyan] / [cyan]exit[/cyan] - Exit the application

[bold]Tips:[/bold]
  • Be specific in your queries for better results
  • Complex queries will trigger clarifying questions
  • Use /ask for general questions outside research flow
        """
        self.console.print(Panel(help_text.strip(), title="Help", border_style="dim"))

    def print_agent(self, message: str):
        """Print agent message."""
        self.console.print()
        self.console.print(
            Panel(
                Markdown(message),
                title="🤖 Agent",
                title_align="left",
                border_style="blue",
                padding=(1, 2),
            )
        )

    def print_agent_streaming_start(self):
        """Start streaming agent message."""
        self.console.print()
        self.console.print("[blue bold]🤖 Agent:[/blue bold]")
        self.console.print()

    def print_agent_chunk(self, chunk: str):
        """Print a chunk of streaming agent response."""
        self.console.print(chunk, end="")

    def print_agent_streaming_end(self):
        """End streaming agent message."""
        self.console.print()
        self.console.print()

    def print_user_prompt(self) -> str:
        """Print user prompt and get input."""
        self.console.print()
        return self.console.input("[magenta bold]You:[/magenta bold] ")

    def print_state(self, state: str):
        """Print current state indicator."""
        state_colors = {
            "idle": "dim",
            "clarifying": "yellow",
            "planning": "cyan",
            "reviewing": "blue",
            "executing": "green",
            "complete": "green bold",
            "error": "red bold",
        }
        color = state_colors.get(state, "white")
        self.console.print(
            f"[{color}]◉ State: {state.upper()}[/{color}]", justify="right"
        )

    def print_phase(self, phase: str, status: str = "running"):
        """Print phase status."""
        icons = {
            "running": "⏳",
            "complete": "✅",
            "error": "❌",
            "skipped": "⏭️",
        }
        icon = icons.get(status, "•")
        if status == "running":
            self.console.print(f"  {icon} [phase]{phase}[/phase]...")
        elif status == "complete":
            self.console.print(f"  {icon} [success]{phase}[/success]")
        elif status == "error":
            self.console.print(f"  {icon} [error]{phase}[/error]")
        else:
            self.console.print(f"  {icon} [dim]{phase}[/dim]")

    def print_plan(self, plan: Any):
        """Print research plan in a table format."""
        from src.planner.adaptive_planner import AdaptivePlan

        if not isinstance(plan, AdaptivePlan):
            self.console.print("[warning]Invalid plan format[/warning]")
            return

        # Plan info
        self.console.print()
        info_table = Table(show_header=False, box=None, padding=(0, 2))
        info_table.add_column("Key", style="dim")
        info_table.add_column("Value")
        info_table.add_row(
            "Mode", f"[bold]{plan.query_info.query_type.value.upper()}[/bold]"
        )
        info_table.add_row("Phases", ", ".join(plan.phase_config.active_phases))
        self.console.print(info_table)

        # Steps table
        self.console.print()
        steps_table = Table(title="Research Steps", show_lines=True)
        steps_table.add_column("#", style="dim", width=3)
        steps_table.add_column("Step", style="bold")
        steps_table.add_column("Queries", style="cyan")

        for step in plan.plan.steps:
            queries = ", ".join(step.queries[:3]) if step.queries else "N/A"
            if len(step.queries) > 3:
                queries += f" (+{len(step.queries) - 3} more)"
            steps_table.add_row(str(step.id), step.title, queries)

        self.console.print(steps_table)

    def print_papers(self, papers: List[Any], title: str = "Papers Found"):
        """Print papers in a table."""
        if not papers:
            self.console.print("[dim]No papers found[/dim]")
            return

        table = Table(title=title, show_lines=True)
        table.add_column("#", style="dim", width=3)
        table.add_column("Title", style="bold", max_width=50)
        table.add_column("Score", style="cyan", width=6)
        table.add_column("Source", style="dim", width=10)

        for i, paper in enumerate(papers[:10], 1):
            title_text = (
                paper.title[:47] + "..." if len(paper.title) > 50 else paper.title
            )
            score = (
                f"{paper.relevance_score:.1f}"
                if hasattr(paper, "relevance_score") and paper.relevance_score
                else "N/A"
            )
            source = getattr(paper, "source", "unknown")
            table.add_row(str(i), title_text, score, source)

        if len(papers) > 10:
            self.console.print(f"[dim](Showing 10 of {len(papers)} papers)[/dim]")

        self.console.print(table)

    def print_result(self, result: Any):
        """Print pipeline result summary."""
        self.console.print()
        self.console.print(
            Panel(
                f"""
[bold]Research Complete![/bold]

[cyan]Topic:[/cyan] {result.topic}
[cyan]Papers Found:[/cyan] {result.unique_papers}
[cyan]Relevant:[/cyan] {result.relevant_papers}
[cyan]High Relevance:[/cyan] {result.high_relevance_papers}
[cyan]Clusters:[/cyan] {result.clusters_created}
[cyan]Cache Hit Rate:[/cyan] {result.cache_hit_rate:.1%}
            """.strip(),
                title="📊 Results",
                border_style="green",
            )
        )

    def print_error(self, message: str):
        """Print error message."""
        self.console.print(
            Panel(f"[error]{message}[/error]", title="❌ Error", border_style="red")
        )

    def print_warning(self, message: str):
        """Print warning message."""
        self.console.print(f"[warning]⚠️ {message}[/warning]")

    def print_success(self, message: str):
        """Print success message."""
        self.console.print(f"[success]✅ {message}[/success]")

    def print_info(self, message: str):
        """Print info message."""
        self.console.print(f"[info]ℹ️ {message}[/info]")

    def create_progress(self) -> Progress:
        """Create a progress context for multi-step operations."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console,
        )

    def print_markdown(self, md_text: str):
        """Print markdown content."""
        self.console.print(Markdown(md_text))

    def print_divider(self, title: str = ""):
        """Print a divider line."""
        if title:
            self.console.rule(f"[bold]{title}[/bold]")
        else:
            self.console.rule()


class StreamingDisplay:
    """
    Manages live streaming updates during research execution.

    Shows real-time progress of:
    - Current phase
    - Papers being collected
    - Analysis progress
    - Synthesis status
    """

    def __init__(self, console: Console):
        self.console = console
        self.live: Optional[Live] = None
        self.current_phase = ""
        self.papers_collected = 0
        self.papers_analyzed = 0
        self.status_message = ""

    def start(self):
        """Start live display."""
        self.live = Live(self._render(), console=self.console, refresh_per_second=4)
        self.live.start()

    def stop(self):
        """Stop live display."""
        if self.live:
            self.live.stop()
            self.live = None

    def update(
        self,
        phase: str = None,
        papers_collected: int = None,
        papers_analyzed: int = None,
        message: str = None,
    ):
        """Update the display."""
        if phase is not None:
            self.current_phase = phase
        if papers_collected is not None:
            self.papers_collected = papers_collected
        if papers_analyzed is not None:
            self.papers_analyzed = papers_analyzed
        if message is not None:
            self.status_message = message

        if self.live:
            self.live.update(self._render())

    def _render(self) -> Panel:
        """Render the current status."""
        content = Table.grid(padding=1)
        content.add_column(justify="left")
        content.add_column(justify="right")

        content.add_row(
            f"[bold]Phase:[/bold] [phase]{self.current_phase or 'Starting...'}[/phase]",
            f"[dim]Papers: {self.papers_collected}[/dim]",
        )

        if self.status_message:
            content.add_row(f"[dim]{self.status_message}[/dim]", "")

        return Panel(content, title="🔄 Processing", border_style="cyan")
