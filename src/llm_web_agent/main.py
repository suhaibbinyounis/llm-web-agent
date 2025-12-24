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
    browser: str = typer.Option("chromium", "--browser", "-b", help="Browser: chromium, chrome, msedge"),
    model: str = typer.Option("gpt-4.1", "--model", "-m", help="LLM model to use"),
    api_url: str = typer.Option("http://127.0.0.1:3030", "--api-url", help="LLM API base URL"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Max execution time in seconds"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """
    Execute a natural language instruction in the browser.
    
    Browser options:
        --browser chromium  (default, bundled)
        --browser chrome    (Google Chrome)
        --browser msedge    (Microsoft Edge)
    
    Examples:
        llm-web-agent run "go to google.com" --browser chrome
        llm-web-agent run "search for cats" --visible -b msedge
    """
    setup_logging(verbose)
    
    # Parse browser option
    channel = None
    if browser in ("chrome", "chrome-beta", "msedge", "msedge-beta"):
        channel = browser
    
    browser_label = browser if browser != "chromium" else "Chromium"
    
    console.print(Panel.fit(
        f"[bold blue]🤖 LLM Web Agent[/bold blue]\n"
        f"[dim]Browser:[/dim] {browser_label}\n"
        f"[dim]Instruction:[/dim] {instruction}",
        border_style="blue",
    ))
    
    asyncio.run(_run_async(
        instruction=instruction,
        headless=not visible,
        browser_channel=channel,
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
    browser_channel: Optional[str] = None,
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
        await browser.launch(headless=headless, channel=browser_channel)
        
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


@app.command("run-file")
def run_file(
    file_path: str = typer.Argument(..., help="Path to instruction file (.txt)"),
    visible: bool = typer.Option(False, "--visible", "-v", help="Run with visible browser"),
    browser: str = typer.Option("chromium", "--browser", "-b", help="Browser: chromium, chrome, msedge"),
    model: str = typer.Option("gpt-4.1", "--model", "-m", help="LLM model to use"),
    api_url: str = typer.Option("http://127.0.0.1:3030", "--api-url", help="LLM API base URL"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Max execution time in seconds"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """
    Execute instructions from a file.
    
    Each line is executed as a separate instruction.
    
    Examples:
        llm-web-agent run-file instructions/mui_demo.txt --visible --browser chrome
    """
    import pathlib
    from rich.table import Table
    from rich.live import Live
    from rich.layout import Layout
    
    setup_logging(verbose)
    
    path = pathlib.Path(file_path)
    if not path.exists():
        console.print(f"[red]✗ File not found: {file_path}[/red]")
        raise typer.Exit(1)
    
    # Read and parse file
    lines = path.read_text().strip().split("\n")
    instructions = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            instructions.append(line)
    
    if not instructions:
        console.print(f"[yellow]⚠ No instructions found in {file_path}[/yellow]")
        raise typer.Exit(1)
    
    # Display script info
    console.print()
    console.print(Panel.fit(
        f"[bold blue]🤖 LLM Web Agent[/bold blue]\n"
        f"[dim]Script:[/dim] {path.name}\n"
        f"[dim]Steps:[/dim] {len(instructions)}",
        border_style="blue",
    ))
    
    # Show instructions table
    table = Table(show_header=True, header_style="bold cyan", box=None)
    table.add_column("#", width=3)
    table.add_column("Instruction", style="dim")
    table.add_column("Status", width=10)
    
    for i, instr in enumerate(instructions, 1):
        table.add_row(str(i), instr[:60] + ("..." if len(instr) > 60 else ""), "[dim]pending[/dim]")
    
    console.print(table)
    console.print()
    
    # Parse browser option
    channel = None
    if browser in ("chrome", "chrome-beta", "msedge", "msedge-beta"):
        channel = browser
    
    # Run with sequential execution per line
    asyncio.run(_run_file_async(
        instructions=instructions,
        headless=not visible,
        browser_channel=channel,
        model=model,
        api_url=api_url,
        timeout=timeout,
    ))


async def _run_file_async(
    instructions: list,
    headless: bool,
    model: str,
    api_url: str,
    timeout: int,
    browser_channel: Optional[str] = None,
):
    """Run instructions from file - each line separately."""
    import signal
    
    browser = None
    llm = None
    cleanup_done = False
    
    async def cleanup():
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
        console.print("\n[dim]Cleaning up...[/dim]")
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(cleanup())
        raise KeyboardInterrupt
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize LLM first (before browser)
        console.print("[dim]⏳ Connecting to LLM...[/dim]")
        llm = OpenAIProvider(base_url=api_url, model=model)
        
        if not await llm.health_check():
            console.print(f"[yellow]⚠ LLM API at {api_url} may not be available[/yellow]")
        else:
            console.print(f"[green]✓ LLM connected[/green]")
        
        engine = Engine(llm_provider=llm)
        
        # Now launch browser
        console.print("[dim]⏳ Launching browser...[/dim]")
        browser = PlaywrightBrowser()
        await browser.launch(headless=headless, channel=browser_channel)
        console.print(f"[green]✓ Browser ready[/green]")
        console.print()
        
        page = await browser.new_page()
        
        # Execute each instruction
        total = len(instructions)
        succeeded = 0
        failed = 0
        
        for i, instruction in enumerate(instructions, 1):
            console.print(f"[bold cyan]Step {i}/{total}:[/bold cyan] {instruction}")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Executing...", total=None)
                
                result = await engine.run(page=page, task=instruction)
                progress.update(task, completed=True)
            
            if result.success:
                console.print(f"  [green]✓ Done[/green] ({result.duration_seconds:.1f}s)")
                succeeded += 1
            else:
                console.print(f"  [red]✗ Failed:[/red] {result.error}")
                failed += 1
                # Continue to next instruction
        
        # Summary
        console.print()
        if failed == 0:
            console.print(Panel.fit(
                f"[bold green]✓ All {total} steps completed successfully[/bold green]",
                border_style="green",
            ))
        else:
            console.print(Panel.fit(
                f"[bold yellow]⚠ Completed: {succeeded}/{total} steps ({failed} failed)[/bold yellow]",
                border_style="yellow",
            ))
        
        # Keep browser open if visible
        if not headless:
            console.print("\n[dim]Browser is open. Press Ctrl+C to close.[/dim]")
            try:
                await asyncio.sleep(3600)
            except KeyboardInterrupt:
                pass
    
    except KeyboardInterrupt:
        console.print("[dim]Interrupted[/dim]")
    
    except Exception as e:
        console.print(f"\n[red]✗ Error: {e}[/red]")
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
