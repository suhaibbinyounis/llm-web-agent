"""
LLM Web Agent - CLI Entry Point.

Configuration Priority:
    1. CLI arguments (--model, --api-url, etc.)
    2. Environment variables (LLM_WEB_AGENT__LLM__MODEL, etc.)
    3. Config file (config.yaml)

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
from llm_web_agent.llm.copilot_provider import CopilotProvider
from llm_web_agent.engine.engine import Engine
from llm_web_agent.engine.adaptive_engine import AdaptiveEngine
from llm_web_agent.config import get_settings

# Create the CLI app
app = typer.Typer(
    name="llm-web-agent",
    help="Universal browser automation agent powered by LLMs",
    add_completion=False,
)

console = Console()


def setup_logging(verbose: bool = False):
    """Configure logging using settings."""
    settings = get_settings()
    
    # If verbose CLI flag is set, override to DEBUG
    if verbose:
        level = logging.DEBUG
    else:
        level = getattr(logging, settings.logging.level, logging.INFO)
    
    # Configure handlers
    handlers = [RichHandler(console=console, rich_tracebacks=True)]
    
    # Add file handler if configured
    if settings.logging.file:
        file_handler = logging.FileHandler(settings.logging.file)
        file_handler.setFormatter(logging.Formatter(settings.logging.format))
        handlers.append(file_handler)
    
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=handlers,
    )


@app.command()
def run(
    instruction: str = typer.Argument(..., help="Natural language instruction to execute"),
    visible: bool = typer.Option(False, "--visible", "-v", help="Run with visible browser"),
    browser: str = typer.Option("chromium", "--browser", "-b", help="Browser: chromium, chrome, msedge"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model (default: from config)"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="LLM API base URL (default: from config)"),
    websocket: bool = typer.Option(False, "--websocket", "--ws", help="Use WebSocket for low-latency LLM"),
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
    
    # Load settings from config/env, then override with CLI args
    settings = get_settings()
    
    # Use CLI args if provided, otherwise fall back to settings
    effective_model = model or settings.llm.model
    effective_api_url = api_url or settings.llm.base_url
    
    # Validate required settings
    if not effective_model:
        console.print("[red]Error: No model configured.[/red]")
        console.print("Set via CLI: --model gpt-4o")
        console.print("Or env var: LLM_WEB_AGENT__LLM__MODEL=gpt-4o")
        raise typer.Exit(1)
    
    if not effective_api_url:
        console.print("[red]Error: No API URL configured.[/red]")
        console.print("Set via CLI: --api-url https://api.openai.com/v1")
        console.print("Or env var: LLM_WEB_AGENT__LLM__BASE_URL=https://api.openai.com/v1")
        raise typer.Exit(1)
    
    # Parse browser option
    channel = None
    if browser in ("chrome", "chrome-beta", "msedge", "msedge-beta"):
        channel = browser
    
    browser_label = browser if browser != "chromium" else "Chromium"
    
    console.print(Panel.fit(
        f"[bold blue]🤖 LLM Web Agent[/bold blue]\n"
        f"[dim]Browser:[/dim] {browser_label}\n"
        f"[dim]Model:[/dim] {effective_model}\n"
        f"[dim]Instruction:[/dim] {instruction}"
        + (f"\n[dim]Mode:[/dim] WebSocket (Low Latency)" if websocket else ""),
        border_style="blue",
    ))
    
    asyncio.run(_run_async(
        instruction=instruction,
        headless=not visible,
        browser_channel=channel,
        model=effective_model,
        api_url=effective_api_url,
        timeout=timeout,
        use_websocket=websocket,
    ))


async def _run_async(
    instruction: str,
    headless: bool,
    model: str,
    api_url: str,
    timeout: int,
    browser_channel: Optional[str] = None,
    use_websocket: bool = False,
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
        
        # Load settings early for browser configuration
        settings = get_settings()
        
        browser = PlaywrightBrowser()
        await browser.launch(
            headless=headless,
            channel=browser_channel,
            slow_mo=settings.browser.slow_mo,
        )
        
        if use_websocket:
            from llm_web_agent.llm import HybridLLMProvider
            ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = ws_url.rstrip("/") + "/v1/realtime"
            llm = HybridLLMProvider(ws_url=ws_url, http_url=api_url, model=model)
            await llm.connect()
        else:
            llm = OpenAIProvider(base_url=api_url, model=model, timeout=float(settings.llm.timeout))
        
        # Check LLM health
        if not await llm.health_check():
            console.print(f"[yellow]Warning: LLM API at {api_url} may not be available[/yellow]")
        
        engine = Engine(
            llm_provider=llm,
            max_retries=settings.agent.retry_attempts,
            step_timeout_ms=settings.browser.timeout_ms,
            navigation_timeout_ms=settings.browser.navigation_timeout_ms,
            step_delay_ms=settings.agent.step_delay_ms,
            max_steps=settings.agent.max_steps,
        )
        
        # Get a page with configured viewport and user agent
        page_options = {
            "viewport": {"width": settings.browser.viewport_width, "height": settings.browser.viewport_height},
        }
        if settings.browser.user_agent:
            page_options["user_agent"] = settings.browser.user_agent
        page = await browser.new_page(**page_options)
        
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
    model: Optional[str] = typer.Option(None, "--model", "-m", help="LLM model to use"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="LLM API base URL"),
    websocket: bool = typer.Option(False, "--websocket", "--ws", help="Use WebSocket for low-latency LLM (persistent connection)"),
    report: bool = typer.Option(False, "--report", "-r", help="Generate detailed execution report"),
    report_dir: str = typer.Option("./reports", "--report-dir", help="Output directory for reports"),
    report_formats: str = typer.Option("json,md,html", "--report-formats", help="Report formats: json,md,html,pdf,docx"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Max execution time in seconds"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """
    Execute instructions from a file.
    
    Each line is executed as a separate instruction.
    
    Examples:
        llm-web-agent run-file instructions/mui_demo.txt --visible --browser chrome
        llm-web-agent run-file instructions/checkout.txt --report --report-formats json,md,html
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
    mode_info = "📄 Report Generation" if report else ""
    console.print(Panel.fit(
        f"[bold blue]🤖 LLM Web Agent[/bold blue]\n"
        f"[dim]Script:[/dim] {path.name}\n"
        f"[dim]Steps:[/dim] {len(instructions)}"
        + (f"\n[dim]Report:[/dim] {mode_info}" if report else "")
        + (f"\n[dim]Mode:[/dim] WebSocket (Low Latency)" if websocket else ""),
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
    
    formats_list = [f.strip() for f in report_formats.split(',')]
    
    # Run with sequential execution per line
    asyncio.run(_run_file_async(
        instructions=instructions,
        headless=not visible,
        browser_channel=channel,
        model=model,
        api_url=api_url,
        timeout=timeout,
        generate_report=report,
        report_dir=report_dir,
        report_formats=formats_list,
        use_websocket=websocket,
        script_name=path.stem,
    ))


async def _run_file_async(
    instructions: list,
    headless: bool,
    model: str,
    api_url: str,
    timeout: int,
    browser_channel: Optional[str] = None,
    generate_report: bool = False,
    report_dir: str = "./reports",
    report_formats: list = None,
    use_websocket: bool = False,
    script_name: str = "script",
):
    """Run instructions from file - each line separately."""
    import signal
    import uuid
    import time
    from pathlib import Path
    from datetime import datetime
    
    report_formats = report_formats or ['json', 'md', 'html']
    run_id = str(uuid.uuid4())[:8]
    
    browser = None
    llm = None
    cleanup_done = False
    screenshot_mgr = None
    step_data = []  # Collect step data for report
    
    # Initialize screenshot manager if reporting
    if generate_report:
        from llm_web_agent.reporting.screenshot_manager import ScreenshotManager
        screenshot_mgr = ScreenshotManager(output_dir=report_dir, run_id=run_id)
    
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
    
    start_time = time.time()
    
    try:
        # Load settings early for all configurations
        settings = get_settings()
        
        # Initialize LLM first (before browser)
        console.print("[dim]⏳ Connecting to LLM...[/dim]")
        
        if use_websocket:
            # Use hybrid provider with WebSocket support
            from llm_web_agent.llm import HybridLLMProvider
            
            ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = ws_url.rstrip("/") + "/v1/realtime"
            
            llm = HybridLLMProvider(
                ws_url=ws_url,
                http_url=api_url,
                model=model,
            )
            
            # Try to establish WebSocket connection
            connected = await llm.connect()
            if llm.active_transport == "websocket":
                console.print("[green]✓ WebSocket connected[/green]")
            else:
                console.print("[yellow]⚠ WebSocket unavailable, using HTTP[/yellow]")
        else:
            llm = OpenAIProvider(base_url=api_url, model=model, timeout=float(settings.llm.timeout))
        
        if not await llm.health_check():
            console.print(f"[yellow]⚠ LLM API at {api_url} may not be available[/yellow]")
        else:
            console.print(f"[green]✓ LLM connected[/green]")
        
        # NORMALIZE ALL INSTRUCTIONS WITH ONE LLM CALL
        console.print(f"[dim]⏳ Normalizing {len(instructions)} instructions (one LLM call)...[/dim]")
        from llm_web_agent.engine.instruction_normalizer import normalize_instructions, normalized_to_instruction
        
        normalized = await normalize_instructions(instructions, llm, timeout_seconds=120)
        
        if normalized:
            # Convert normalized actions back to simple instruction strings
            instructions = [normalized_to_instruction(action) for action in normalized]
            console.print(f"[green]✓ Normalized to {len(instructions)} actions (no more LLM calls needed!)[/green]")
        else:
            console.print("[yellow]⚠ Normalization failed, using original instructions (LLM may be called per step)[/yellow]")
        
        engine = Engine(
            llm_provider=llm,
            max_retries=settings.agent.retry_attempts,
            step_timeout_ms=settings.browser.timeout_ms,
            navigation_timeout_ms=settings.browser.navigation_timeout_ms,
            step_delay_ms=settings.agent.step_delay_ms,
            max_steps=settings.agent.max_steps,
        )
        
        # Now launch browser with settings
        console.print("[dim]⏳ Launching browser...[/dim]")
        browser = PlaywrightBrowser()
        await browser.launch(
            headless=headless,
            channel=browser_channel,
            slow_mo=settings.browser.slow_mo,
        )
        console.print(f"[green]✓ Browser ready[/green]")
        console.print()
        
        # Create page with configured viewport and user agent
        page_options = {
            "viewport": {"width": settings.browser.viewport_width, "height": settings.browser.viewport_height},
        }
        if settings.browser.user_agent:
            page_options["user_agent"] = settings.browser.user_agent
        page = await browser.new_page(**page_options)
        
        # Create a SHARED context that persists across all steps
        # This is critical for hover → click to work (stores _last_hover_selector)
        from llm_web_agent.engine.run_context import RunContext
        shared_context = RunContext()
        
        # Execute each instruction
        total = len(instructions)
        succeeded = 0
        failed = 0
        
        for i, instruction in enumerate(instructions, 1):
            step_start = time.time()
            console.print(f"[bold cyan]Step {i}/{total}:[/bold cyan] {instruction}")
            
            # Capture screenshot before if reporting
            if screenshot_mgr:
                try:
                    await screenshot_mgr.capture(page, i, f"Before: {instruction[:50]}")
                except:
                    pass
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                task = progress.add_task("Executing...", total=None)
                
                # Pass shared context to preserve hover state between steps
                result = await engine.run(page=page, task=instruction, context=shared_context)
                progress.update(task, completed=True)
            
            step_duration = (time.time() - step_start) * 1000
            
            # NEW TAB DETECTION: Check if a new tab opened and switch to it
            try:
                all_pages = page.get_all_pages()
                if len(all_pages) > 1:
                    # Switch to the newest page (last in list)
                    newest_page = all_pages[-1]
                    if newest_page.url != page.url:
                        logging.info(f"New tab detected: {newest_page.url} - switching to it")
                        console.print(f"  [dim]↳ New tab opened, switching to it[/dim]")
                        page = newest_page
            except Exception as e:
                logging.debug(f"Tab detection failed: {e}")
            
            if result.success:
                console.print(f"  [green]✓ Done[/green] ({result.duration_seconds:.1f}s)")
                succeeded += 1
                
                # Capture screenshot after if reporting
                screenshot_path = None
                if screenshot_mgr:
                    try:
                        ss = await screenshot_mgr.capture(page, i, f"After: {instruction[:50]}")
                        screenshot_path = str(ss.path)
                    except:
                        pass
                
                step_data.append({
                    "step_number": i,
                    "instruction": instruction,
                    "status": "success",
                    "duration_ms": step_duration,
                    "screenshot": screenshot_path,
                    "error": None,
                })
            else:
                console.print(f"  [red]✗ Failed:[/red] {result.error}")
                failed += 1
                
                # Capture error screenshot
                if screenshot_mgr:
                    try:
                        await screenshot_mgr.capture_on_error(page, i, result.error or "Unknown error")
                    except:
                        pass
                
                step_data.append({
                    "step_number": i,
                    "instruction": instruction,
                    "status": "failed",
                    "duration_ms": step_duration,
                    "screenshot": None,
                    "error": result.error,
                })
        
        total_duration = time.time() - start_time
        
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
        
        # Generate report if enabled
        if generate_report:
            console.print("\n[dim]📝 Generating reports...[/dim]")
            from llm_web_agent.reporting.execution_report import (
                ExecutionReportGenerator,
                ExecutionReport,
                StepDetail,
            )
            
            # Build step details
            steps = []
            for sd in step_data:
                steps.append(StepDetail(
                    step_number=sd["step_number"],
                    action="instruction",
                    target=sd["instruction"],
                    status=sd["status"],
                    duration_ms=sd["duration_ms"],
                    screenshot_after=sd["screenshot"],
                    error=sd["error"],
                ))
            
            # Create report
            report = ExecutionReport(
                run_id=run_id,
                created_at=datetime.now(),
                goal=f"Execute script: {script_name}",
                success=failed == 0,
                started_at=datetime.now(),
                completed_at=datetime.now(),
                duration_seconds=total_duration,
                steps_total=total,
                steps_completed=succeeded,
                steps_failed=failed,
                steps=steps,
            )
            
            # Generate AI summary
            try:
                report_gen = ExecutionReportGenerator(
                    output_dir=report_dir,
                    include_screenshots=True,
                )
                await report_gen.generate_ai_content(report, llm)
                
                # Export
                exported = report_gen.export_all(report, report_formats)
                
                console.print(f"[green]✓ Reports generated in: {report_dir}[/green]")
                for fmt, path in exported.items():
                    console.print(f"  - {Path(path).name}")
            except Exception as e:
                console.print(f"[yellow]⚠ Report generation error: {e}[/yellow]")
        
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


@app.command("run-adaptive")
def run_adaptive(
    goal: str = typer.Argument(..., help="Natural language goal (multi-step supported)"),
    visible: bool = typer.Option(False, "--visible", "-v", help="Run with visible browser"),
    browser: str = typer.Option("chromium", "--browser", "-b", help="Browser: chromium, chrome, msedge"),
    api_url: Optional[str] = typer.Option(None, "--api-url", help="LLM API base URL"),
    use_openai: bool = typer.Option(False, "--openai", help="Use OpenAI instead of Copilot Gateway"),
    websocket: bool = typer.Option(False, "--websocket", "--ws", help="Use WebSocket for low-latency LLM (persistent connection)"),
    report: bool = typer.Option(False, "--report", "-r", help="Generate detailed execution report"),
    report_dir: str = typer.Option("./reports", "--report-dir", help="Output directory for reports"),
    report_formats: str = typer.Option("json,md,html", "--report-formats", help="Report formats: json,md,html,pdf,docx"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Max execution time in seconds"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
):
    """
    Execute a goal using the NEW AdaptiveEngine (LLM-first planning).
    
    Features:
        - ONE LLM call plans complete task
        - Accessibility-first element resolution
        - Pattern learning for instant re-resolution
        - Speculative pre-resolution (lookahead)
        - Comprehensive report generation (--report)
    
    Examples:
        llm-web-agent run-adaptive "Login to saucedemo.com with standard_user" --visible
        llm-web-agent run-adaptive "Search for Python on Google" --openai
        llm-web-agent run-adaptive "Complete checkout" --report --report-formats json,md,html,pdf
        llm-web-agent run-adaptive "Fill form" --websocket  # Low-latency mode
    """
    setup_logging(verbose)
    
    channel = None
    if browser in ("chrome", "chrome-beta", "msedge", "msedge-beta"):
        channel = browser
    
    mode_desc = "LLM-First Planning + Learning"
    if websocket:
        mode_desc += " + WebSocket"
    if report:
        mode_desc += " + Report Generation"
    
    console.print(Panel.fit(
        f"[bold blue]🚀 Adaptive Engine[/bold blue]\n"
        f"[dim]Mode:[/dim] {mode_desc}\n"
        f"[dim]Goal:[/dim] {goal[:60]}{'...' if len(goal) > 60 else ''}",
        border_style="blue",
    ))
    
    formats_list = [f.strip() for f in report_formats.split(',')]
    
    asyncio.run(_run_adaptive_async(
        goal=goal,
        headless=not visible,
        browser_channel=channel,
        api_url=api_url,
        use_openai=use_openai,
        use_websocket=websocket,
        timeout=timeout,
        generate_report=report,
        report_dir=report_dir,
        report_formats=formats_list,
    ))


async def _run_adaptive_async(
    goal: str,
    headless: bool,
    api_url: str,
    use_openai: bool,
    timeout: int,
    browser_channel: Optional[str] = None,
    use_websocket: bool = False,
    generate_report: bool = False,
    report_dir: str = "./reports",
    report_formats: list = None,
):
    """Run with AdaptiveEngine."""
    import signal
    from playwright.async_api import async_playwright
    
    report_formats = report_formats or ['json', 'md', 'html']
    playwright_ctx = None
    browser_obj = None
    llm = None
    cleanup_done = False
    
    async def cleanup():
        nonlocal cleanup_done
        if cleanup_done:
            return
        cleanup_done = True
        if browser_obj:
            try:
                await browser_obj.close()
            except Exception:
                pass
        if playwright_ctx:
            try:
                await playwright_ctx.stop()
            except Exception:
                pass
        if llm and hasattr(llm, 'close'):
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
        # Load settings early for all configurations
        settings = get_settings()
        
        # Initialize LLM
        console.print("[dim]⏳ Initializing LLM provider...[/dim]")
        
        if use_websocket:
            # Use hybrid provider with WebSocket support
            from llm_web_agent.llm import HybridLLMProvider
            
            ws_url = api_url.replace("http://", "ws://").replace("https://", "wss://")
            ws_url = ws_url.rstrip("/") + "/v1/realtime"
            
            llm = HybridLLMProvider(
                ws_url=ws_url,
                http_url=api_url,
            )
            
            # Try to establish WebSocket connection
            connected = await llm.connect()
            if llm.active_transport == "websocket":
                llm_name = "WebSocket (Hybrid)"
                console.print("[green]✓ WebSocket connected[/green]")
            else:
                llm_name = "HTTP (WebSocket unavailable)"
                console.print("[yellow]⚠ WebSocket unavailable, using HTTP[/yellow]")
        elif use_openai:
            llm = OpenAIProvider(base_url=api_url, timeout=float(settings.llm.timeout))
            llm_name = "OpenAI"
        else:
            llm = CopilotProvider(base_url=api_url)
            if await llm.health_check():
                llm_name = "Copilot Gateway"
            else:
                console.print("[yellow]Copilot Gateway not available, falling back to OpenAI[/yellow]")
                llm = OpenAIProvider(base_url=api_url, timeout=float(settings.llm.timeout))
                llm_name = "OpenAI"
        
        console.print(f"[green]✓ {llm_name} connected[/green]")
        
        # Initialize AdaptiveEngine
        engine = AdaptiveEngine(llm_provider=llm, lookahead_steps=2)
        
        # Launch browser with Playwright directly
        console.print("[dim]⏳ Launching browser...[/dim]")
        playwright_ctx = await async_playwright().start()
        
        launch_options = {
            "headless": headless,
            "slow_mo": settings.browser.slow_mo,
        }
        if browser_channel:
            launch_options["channel"] = browser_channel
            
        browser_obj = await playwright_ctx.chromium.launch(**launch_options)
        
        # Create page with configured viewport and user agent
        page_options = {
            "viewport": {"width": settings.browser.viewport_width, "height": settings.browser.viewport_height},
        }
        if settings.browser.user_agent:
            page_options["user_agent"] = settings.browser.user_agent
        page = await browser_obj.new_page(**page_options)
        
        console.print(f"[green]✓ Browser ready[/green]")
        console.print()
        
        # Check if goal starts with navigation
        goal_lower = goal.lower()
        if not any(goal_lower.startswith(x) for x in ['go to', 'navigate to', 'open', 'visit']):
            # Default to about:blank
            pass
        else:
            # Extract URL and navigate first
            import re
            url_match = re.search(r'(?:go to|navigate to|open|visit)\s+(\S+)', goal_lower)
            if url_match:
                url = url_match.group(1)
                if not url.startswith('http'):
                    url = 'https://' + url
                console.print(f"[dim]🌐 Navigating to {url}...[/dim]")
                await page.goto(url)
                await asyncio.sleep(1)
        
        # Run with progress
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task_desc = "Planning and executing..."
            if generate_report:
                task_desc += " (capturing screenshots)"
            task = progress.add_task(task_desc, total=None)
            
            # Use run_with_report if report flag is set
            if generate_report:
                result = await engine.run_with_report(
                    page=page,
                    goal=goal,
                    output_dir=report_dir,
                    formats=report_formats,
                    capture_screenshots=True,
                    generate_ai_summary=True,
                )
            else:
                result = await engine.run(page=page, goal=goal)
            
            progress.update(task, completed=True)
        
        # Display results
        console.print()
        if result.success:
            console.print(Panel.fit(
                f"[bold green]✓ Success![/bold green]\n"
                f"Steps: {result.steps_completed}/{result.steps_total}\n"
                f"Duration: {result.duration_seconds:.1f}s\n"
                f"Framework: {result.framework_detected or 'unknown'}",
                border_style="green",
            ))
        else:
            console.print(Panel.fit(
                f"[bold red]✗ Failed[/bold red]\n"
                f"Steps: {result.steps_completed}/{result.steps_total}\n"
                f"Error: {result.error or 'Unknown'}",
                border_style="red",
            ))
        
        # Step details
        if result.step_results:
            console.print("\n[bold]Step Details:[/bold]")
            for i, sr in enumerate(result.step_results, 1):
                status = "[green]✓[/green]" if sr.success else "[red]✗[/red]"
                loc = f"[{sr.locator_type.value}]" if sr.locator_type else ""
                console.print(f"  {i}. {status} {sr.step.action.value}: {sr.step.target[:40]} {loc} ({sr.duration_ms:.0f}ms)")
        
        # Report info
        if generate_report:
            console.print(f"\n[dim]📄 Reports generated in: {report_dir}[/dim]")
            from pathlib import Path
            report_path = Path(report_dir)
            if report_path.exists():
                for f in report_path.glob(f"{result.run_id}*"):
                    console.print(f"  - {f.name}")
        
        # Keep open if visible
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
def gui(
    port: int = typer.Option(8000, "--port", "-p", help="Port to run the GUI server on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to (use 0.0.0.0 for LAN)"),
    no_browser: bool = typer.Option(False, "--no-browser", help="Don't open browser automatically"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
):
    """
    Launch the GUI control panel in your browser.
    
    This starts a web server that provides a visual interface for:
      - Starting/stopping/pausing agent tasks
      - Viewing live browser preview
      - Configuring settings
      - Viewing execution logs in real-time
      - Browsing run history
    
    Examples:
        llm-web-agent gui                    # Start on localhost:8000
        llm-web-agent gui --port 3000        # Custom port
        llm-web-agent gui --host 0.0.0.0     # Allow LAN access
        llm-web-agent gui --no-browser       # Don't auto-open browser
    """
    try:
        from llm_web_agent.gui.server import run_server
    except ImportError as e:
        console.print("[red]✗ GUI dependencies not installed.[/red]")
        console.print("Install with: [cyan]pip install 'llm-web-agent[gui]'[/cyan]")
        console.print(f"\n[dim]Missing: {e}[/dim]")
        raise typer.Exit(1)
    
    setup_logging(debug)
    
    console.print(Panel.fit(
        "[bold blue]🎛️  LLM Web Agent GUI[/bold blue]\n"
        f"[dim]Starting control panel...[/dim]",
        border_style="blue",
    ))
    
    try:
        run_server(
            host=host,
            port=port,
            debug=debug,
            open_browser=not no_browser,
        )
    except KeyboardInterrupt:
        console.print("\n[dim]Shutting down...[/dim]")
    except Exception as e:
        console.print(f"[red]✗ Server error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def version():
    """Show version information."""
    console.print("[bold]LLM Web Agent[/bold] v0.1.0")
    console.print("[dim]Actively maintained and developed by Suhaib Bin Younis[/dim]")
    console.print("[dim]https://github.com/suhaibbinyounis/llm-web-agent[/dim]")


@app.command()
def health(
    api_url: Optional[str] = typer.Option(None, "--api-url", help="LLM API base URL"),
):
    """Check if LLM API is available."""
    async def check():
        settings = get_settings()
        llm = OpenAIProvider(base_url=api_url, timeout=float(settings.llm.timeout))
        try:
            if await llm.health_check():
                console.print(f"[green]✓ LLM API at {api_url} is healthy[/green]")
            else:
                console.print(f"[red]✗ LLM API at {api_url} is not responding[/red]")
        finally:
            await llm.close()
    
    asyncio.run(check())


@app.command()
def record(
    url: Optional[str] = typer.Argument(None, help="Starting URL (optional)"),
    output: str = typer.Option("recording.py", "--output", "-o", help="Output file path"),
    name: str = typer.Option("recording", "--name", "-n", help="Recording name"),
    format: str = typer.Option("python", "--format", "-f", help="Output format: python, json, instructions"),
    browser_channel: Optional[str] = typer.Option(None, "--browser", "-b", help="Browser channel (chrome, msedge)"),
):
    """
    Record browser actions and generate a Playwright script.
    
    Opens a browser window where you can perform actions manually.
    All actions are recorded and converted to a replayable script.
    
    Examples:
        llm-web-agent record --output login_flow.py
        llm-web-agent record https://example.com --name login_flow
        llm-web-agent record --format json --output actions.json
    """
    from playwright.async_api import async_playwright
    from llm_web_agent.recorder import BrowserRecorder, PlaywrightScriptGenerator
    from llm_web_agent.recorder.script_generator import generate_instruction_file
    from pathlib import Path
    import signal
    
    # Track state
    stop_requested = False
    recorder = None
    browser = None
    
    async def run_recording():
        nonlocal stop_requested, recorder, browser
        settings = get_settings()
        
        console.print(Panel.fit(
            "[bold cyan]🎬 Browser Recording Mode[/bold cyan]\n\n"
            "A browser window will open. Perform your actions, then:\n"
            "• Press [bold]Ctrl+C[/bold] in terminal to stop recording\n"
            "• Or close the browser window",
            title="Recording",
        ))
        
        async with async_playwright() as p:
            # Launch visible browser
            browser = await p.chromium.launch(
                headless=False,
                slow_mo=settings.browser.slow_mo,
                channel=browser_channel,
            )
            
            page = await browser.new_page(
                viewport={"width": settings.browser.viewport_width, "height": settings.browser.viewport_height}
            )
            
            # Navigate to starting URL if provided
            if url:
                await page.goto(url)
                console.print(f"[dim]Navigated to {url}[/dim]")
            
            # Start recording
            recorder = BrowserRecorder()
            
            # Show action feedback
            def on_action(action):
                # Skip displaying wait/assert actions if they are too frequent or internal
                val = action.selector or action.url or action.value or ''
                console.print(f"[dim]  📝 {action.action_type.value}: {val}[/dim]")
            
            # Handle stop request from panel
            def on_stop_request():
                nonlocal stop_requested
                stop_requested = True
                console.print("\n[yellow]Stop requested from control panel...[/yellow]")
            
            recorder.on_action(on_action)
            recorder.on_stop(on_stop_request)
            await recorder.start(page, name=name, start_url=url)
            
            console.print("\n[green]✓ Recording started![/green]")
            console.print("[dim]Perform actions in the browser...[/dim]\n")
            
            # Wait for browser to close
            while browser.is_connected() and not stop_requested:
                await asyncio.sleep(0.2)
            
            if stop_requested:
                console.print("\n[yellow]Stopping recording...[/yellow]")
            
            # Stop recording and save
            session = await recorder.stop()
            
            if not session or len(session.actions) == 0:
                console.print("[yellow]No actions recorded.[/yellow]")
                try:
                    await browser.close()
                except Exception:
                    pass
                return
            
            console.print(f"\n[green]✓ Recorded {len(session.actions)} actions[/green]")
            
            # Generate output
            output_path = Path(output)
            
            if format == "json":
                content = session.to_json()
            elif format == "instructions":
                content = generate_instruction_file(session)
            else:  # python
                generator = PlaywrightScriptGenerator(
                    async_mode=True,
                    include_comments=True,
                    headless=False,
                )
                content = generator.generate(session)
            
            output_path.write_text(content)
            console.print(f"[green]✓ Saved to {output_path}[/green]")
            
            # Show preview
            if format == "python":
                console.print("\n[dim]Preview (first 20 lines):[/dim]")
                lines = content.split("\n")[:20]
                for line in lines:
                    console.print(f"  [dim]{line}[/dim]")
                if len(content.split("\n")) > 20:
                    console.print("  [dim]...[/dim]")
            
            try:
                await browser.close()
            except Exception:
                pass
    
    def signal_handler(sig, frame):
        nonlocal stop_requested
        stop_requested = True
    
    # Set up signal handler
    original_handler = signal.signal(signal.SIGINT, signal_handler)
    
    try:
        asyncio.run(run_recording())
    finally:
        # Restore original handler
        signal.signal(signal.SIGINT, original_handler)



@app.command()
def replay(
    script_file: str = typer.Argument(..., help="Path to script file (.py, .json)"),
    visible: bool = typer.Option(True, "--visible/--headless", help="Show browser window"),
    browser_channel: Optional[str] = typer.Option(None, "--browser", "-b", help="Browser channel"),
):
    """
    Replay a recorded script.
    
    Supports both Playwright Python scripts and JSON recordings.
    
    Examples:
        llm-web-agent replay login_flow.py
        llm-web-agent replay actions.json --headless
    """
    from pathlib import Path
    import subprocess
    
    script_path = Path(script_file)
    
    if not script_path.exists():
        console.print(f"[red]Error: File not found: {script_file}[/red]")
        raise typer.Exit(1)
    
    if script_path.suffix == ".py":
        # Execute as Python script
        console.print(f"[cyan]▶ Running {script_file}...[/cyan]")
        result = subprocess.run([sys.executable, str(script_path)])
        if result.returncode == 0:
            console.print("[green]✓ Replay completed successfully[/green]")
        else:
            console.print(f"[red]✗ Replay failed with code {result.returncode}[/red]")
            
    elif script_path.suffix == ".json":
        # Load and replay JSON recording
        from playwright.async_api import async_playwright
        from llm_web_agent.recorder import RecordingSession
        
        async def run_replay():
            settings = get_settings()
            
            with open(script_path) as f:
                session = RecordingSession.from_json(f.read())
            
            console.print(f"[cyan]▶ Replaying: {session.name} ({len(session.actions)} actions)[/cyan]")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=not visible,
                    channel=browser_channel,
                )
                page = await browser.new_page()
                
                from llm_web_agent.recorder.recorder import ActionType
                
                for i, action in enumerate(session.actions, 1):
                    console.print(f"[dim]  Step {i}: {action.action_type.value}[/dim]")
                    
                    try:
                        if action.action_type == ActionType.NAVIGATE and action.url:
                            await page.goto(action.url)
                        elif action.action_type == ActionType.CLICK and action.selector:
                            await page.click(action.selector)
                        elif action.action_type == ActionType.FILL and action.selector:
                            await page.fill(action.selector, action.value or "")
                        elif action.action_type == ActionType.SELECT and action.selector:
                            await page.select_option(action.selector, action.value or "")
                        elif action.action_type == ActionType.PRESS and action.key:
                            await page.keyboard.press(action.key)
                        elif action.action_type == ActionType.CHECK and action.selector:
                            await page.check(action.selector)
                        elif action.action_type == ActionType.UNCHECK and action.selector:
                            await page.uncheck(action.selector)
                    except Exception as e:
                        console.print(f"[yellow]  ⚠ Step {i} failed: {e}[/yellow]")
                
                console.print("[green]✓ Replay completed[/green]")
                
                if visible:
                    console.print("[dim]Press Enter to close browser...[/dim]")
                    input()
                
                await browser.close()
        
        asyncio.run(run_replay())
    else:
        console.print(f"[red]Error: Unknown file format: {script_path.suffix}[/red]")
        console.print("[dim]Supported formats: .py, .json[/dim]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

