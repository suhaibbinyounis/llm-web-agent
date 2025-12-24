"""
LLM Web Agent - CLI Entry Point

This module provides the command-line interface for the LLM Web Agent.
"""

import typer
from rich.console import Console

app = typer.Typer(
    name="llm-web-agent",
    help="A universal browser automation agent powered by large language models.",
    add_completion=False,
)
console = Console()


@app.command()
def run(
    task: str = typer.Argument(..., help="Natural language task to execute"),
    config: str = typer.Option(None, "--config", "-c", help="Path to config file"),
    headless: bool = typer.Option(True, "--headless/--no-headless", help="Run browser in headless mode"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
) -> None:
    """Execute a web automation task using natural language instructions."""
    # TODO: Implement agent execution
    console.print(f"[bold blue]Task:[/bold blue] {task}")
    console.print("[yellow]Agent execution not yet implemented[/yellow]")


@app.command()
def interactive() -> None:
    """Start an interactive session with the agent."""
    # TODO: Implement interactive mode
    console.print("[yellow]Interactive mode not yet implemented[/yellow]")


@app.command()
def version() -> None:
    """Show the version of llm-web-agent."""
    from llm_web_agent import __version__
    console.print(f"llm-web-agent version {__version__}")


if __name__ == "__main__":
    app()
