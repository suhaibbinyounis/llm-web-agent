"""
LLM Web Agent - CLI Entry Point.

Usage:
    llm-web-agent run "go to google.com and search for cats"
    llm-web-agent run "login to example.com" --visible
"""

import asyncio
import logging
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from llm_web_agent.browsers.playwright_browser import PlaywrightBrowser
from llm_web_agent.llm.openai_provider import OpenAIProvider
from llm_web_agent.engine.engine import Engine

# Create the CLI app
app = typer.Typer(
    name="llm-web-agent",
    help="Universal browser automation agent powered by LLMs",
    add_completion=False,
)

console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


@app.command()
def run(
    instruction: str = typer.Argument(..., help="Natural language instruction to execute"),
    visible: bool = typer.Option(False, "--visible", "-v", help="Run with visible browser"),
    model: str = typer.Option("gpt-4.1", "--model", "-m", help="LLM model to use"),
    api_url: str = typer.Option("http://127.0.0.1:3030", "--api-url", help="LLM API base URL"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Max execution time in seconds"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """
    Execute a natural language instruction in the browser.
    
    Examples:
        llm-web-agent run "go to google.com"
        llm-web-agent run "search for cats on google" --visible
        llm-web-agent run "login to twitter" -v --model gpt-4.1
    """
    setup_logging(verbose)
    
    console.print(Panel.fit(
        f"[bold blue]LLM Web Agent[/bold blue]\n"
        f"[dim]Instruction:[/dim] {instruction}",
        border_style="blue",
    ))
    
    asyncio.run(_run_async(
        instruction=instruction,
        headless=not visible,
        model=model,
        api_url=api_url,
        timeout=timeout,
    ))


async def _run_async(
    instruction: str,
    headless: bool,
    model: str,
    api_url: str,
    timeout: int,
):
    """Run the agent asynchronously with proper cleanup."""
    import signal
    
    browser = None
    llm = None
    cleanup_done = False
    
    async def cleanup():
        """Ensure browser and LLM are properly closed."""
        nonlocal cleanup_done
        if cleanup_done:
            return
        cleanup_done = True
        
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        if llm:
            try:
                await llm.close()
            except Exception:
                pass
    
    def signal_handler(sig, frame):
        """Handle Ctrl+C and other signals."""
        console.print("\n[dim]Cleaning up...[/dim]")
        # Schedule cleanup in the event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(cleanup())
        raise KeyboardInterrupt
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize components
        console.print("\n[dim]Initializing...[/dim]")
        
        browser = PlaywrightBrowser()
        await browser.launch(headless=headless)
        
        llm = OpenAIProvider(base_url=api_url, model=model)
        
        # Check LLM health
        if not await llm.health_check():
            console.print(f"[yellow]Warning: LLM API at {api_url} may not be available[/yellow]")
        
        engine = Engine(llm_provider=llm)
        
        # Get a page
        page = await browser.new_page()
        
        # Run with progress indicator
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Executing...", total=None)
            
            result = await engine.run(
                page=page,
                task=instruction,
            )
            
            progress.update(task, completed=True)
        
        # Display results
        if result.success:
            console.print(f"\n[green]✓ Success![/green]")
            console.print(f"  Steps completed: {result.steps_completed}/{result.steps_total}")
            console.print(f"  Duration: {result.duration_seconds:.1f}s")
            
            if result.extracted_data:
                console.print("\n[bold]Extracted Data:[/bold]")
                for key, value in result.extracted_data.items():
                    console.print(f"  {key}: {value}")
        else:
            console.print(f"\n[red]✗ Failed[/red]")
            if result.error:
                console.print(f"  Error: {result.error}")
            console.print(f"  Steps completed: {result.steps_completed}/{result.steps_total}")
        
        # Keep browser open if visible
        if not headless:
            console.print("\n[dim]Browser is open. Press Ctrl+C to close.[/dim]")
            try:
                await asyncio.sleep(3600)  # Keep open for 1 hour
            except KeyboardInterrupt:
                pass
    
    except KeyboardInterrupt:
        console.print("[dim]Interrupted[/dim]")
    
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        logging.exception("Execution failed")
        raise typer.Exit(1)
    
    finally:
        await cleanup()


@app.command()
def version():
    """Show version information."""
    console.print("[bold]LLM Web Agent[/bold] v0.1.0")


@app.command()
def health(
    api_url: str = typer.Option("http://127.0.0.1:3030", "--api-url", help="LLM API base URL"),
):
    """Check if LLM API is available."""
    async def check():
        llm = OpenAIProvider(base_url=api_url)
        try:
            if await llm.health_check():
                console.print(f"[green]✓ LLM API at {api_url} is healthy[/green]")
            else:
                console.print(f"[red]✗ LLM API at {api_url} is not responding[/red]")
        finally:
            await llm.close()
    
    asyncio.run(check())


if __name__ == "__main__":
    app()
