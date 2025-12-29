"""
Agent API Routes - Control the agent execution.

Provides endpoints for:
- Starting/stopping/pausing tasks
- Real-time status streaming via SSE
- Screenshot capture

This implementation mirrors the CLI's run-file command exactly.
"""

import asyncio
import base64
import json
import logging
import time
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, BackgroundTasks
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel, Field
except ImportError:
    # Stub for when FastAPI is not installed
    APIRouter = object
    HTTPException = Exception
    BaseModel = object
    BackgroundTasks = object
    StreamingResponse = object
    Field = lambda **kwargs: None

from llm_web_agent.gui.state import get_agent_state, AgentStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class RunTaskRequest(BaseModel):
    """Request to run a task."""
    task: str = Field(..., description="Instructions (one per line) or goal")
    url: Optional[str] = Field(None, description="Optional starting URL")
    use_websocket: bool = Field(True, description="Use WebSocket for LLM")
    visible: bool = Field(True, description="Show browser window")
    model: str = Field("gpt-4.1", description="LLM model to use")
    generate_report: bool = Field(True, description="Generate execution report")
    report_dir: str = Field("./reports", description="Output directory for reports")
    engine_mode: str = Field("instructions", description="'instructions' or 'goal'")


class TaskResponse(BaseModel):
    """Response from running a task."""
    run_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    """Agent status response."""
    status: str
    is_running: bool
    current_run: Optional[Dict[str, Any]] = None
    browser_connected: bool


async def execute_task(
    task: str,
    url: Optional[str] = None,
    use_websocket: bool = True,
    visible: bool = True,
    model: str = "gpt-4.1",
    generate_report: bool = True,
    report_dir: str = "./reports",
    api_url: str = "http://127.0.0.1:3030",
    engine_mode: str = "instructions",
) -> None:
    """
    Execute a task in the background.
    
    Supports two modes:
    - instructions: Step-by-step instructions (like CLI run-file)
    - goal: High-level goal for AI to plan (like CLI run-adaptive)
    """
    state = get_agent_state()
    browser = None
    llm = None
    playwright_ctx = None
    
    try:
        # Imports
        from llm_web_agent.engine.engine import Engine
        from llm_web_agent.engine.adaptive_engine import AdaptiveEngine
        from llm_web_agent.engine.run_context import RunContext
        from llm_web_agent.engine.instruction_normalizer import normalize_instructions, normalized_to_instruction
        from llm_web_agent.llm.openai_provider import OpenAIProvider
        from llm_web_agent.browsers.playwright_browser import PlaywrightBrowser
        from llm_web_agent.config import load_config
        
        mode_name = "goal" if engine_mode == "goal" else "instructions"
        logger.info(f"Starting task execution ({mode_name} mode): {task[:100]}...")
        
        config = load_config()
        effective_api_url = config.llm.base_url or api_url
        
        # Connect to LLM
        logger.info("Connecting to LLM...")
        
        if use_websocket:
            try:
                from llm_web_agent.llm import HybridLLMProvider
                
                ws_url = effective_api_url.replace("http://", "ws://").replace("https://", "wss://")
                ws_url = ws_url.rstrip("/") + "/v1/realtime"
                
                llm = HybridLLMProvider(
                    ws_url=ws_url,
                    http_url=effective_api_url,
                    model=model,
                )
                
                await llm.connect()
                if llm.active_transport == "websocket":
                    logger.info("WebSocket connected")
                else:
                    logger.warning("WebSocket unavailable, using HTTP")
            except Exception as e:
                logger.warning(f"HybridLLMProvider failed: {e}")
                llm = OpenAIProvider(base_url=effective_api_url, model=model)
        else:
            llm = OpenAIProvider(base_url=effective_api_url, model=model)
        
        # Health check
        if not await llm.health_check():
            logger.warning(f"LLM API at {effective_api_url} may not be available")
        
        # Launch browser
        logger.info("Launching browser...")
        browser = PlaywrightBrowser()
        
        # Try browsers in priority order: Chrome > Edge > Chromium
        browser_channels = [
            ("chrome", "Google Chrome"),
            ("msedge", "Microsoft Edge"),
            (None, "Chromium (bundled)"),
        ]
        
        launched = False
        for channel, name in browser_channels:
            try:
                await browser.launch(headless=not visible, channel=channel)
                logger.info(f"Browser launched: {name}")
                launched = True
                break
            except Exception as e:
                logger.debug(f"{name} not available: {e}")
                continue
        
        if not launched:
            raise RuntimeError("No browser available. Please install Chrome, Edge, or Chromium.")
        
        page = await browser.new_page()
        
        # Store for state (get underlying playwright objects)
        state.set_browser(browser._browser, page._page if hasattr(page, '_page') else page)
        
        # Take initial screenshot
        try:
            screenshot_bytes = await page.screenshot()
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
            await state.update_screenshot(screenshot_b64)
        except Exception as e:
            logger.warning(f"Failed to take initial screenshot: {e}")
        
        # ================================================================
        # EXECUTION: Branch based on engine_mode
        # ================================================================
        
        if engine_mode == "goal":
            # ============================================================
            # GOAL MODE: Use AdaptiveEngine (like CLI run-adaptive)
            # ============================================================
            logger.info("Using AdaptiveEngine for goal-based execution")
            
            engine = AdaptiveEngine(llm_provider=llm, lookahead_steps=2)
            state.set_engine(engine)
            
            await state.set_running()
            
            # Execute using AdaptiveEngine
            if generate_report:
                result = await engine.run_with_report(
                    page=page._page if hasattr(page, '_page') else page,
                    goal=task,
                    output_dir=report_dir,
                    formats=["json", "md", "html"],
                    capture_screenshots=True,
                    generate_ai_summary=True,
                )
            else:
                result = await engine.run(
                    page=page._page if hasattr(page, '_page') else page,
                    goal=task,
                )
            
            # Update state with step results from AdaptiveEngine
            for i, step_result in enumerate(result.step_results, 1):
                if state.should_stop():
                    break
                
                await state.update_step(
                    step_number=i,
                    action=step_result.step.action.value if step_result.step else "done",
                    status="success" if step_result.success else "failed",
                    message=step_result.step.target[:100] if step_result.step else "",
                    duration_ms=step_result.duration_ms,
                )
                
                # Take screenshot
                try:
                    actual_page = page._page if hasattr(page, '_page') else page
                    screenshot_bytes = await actual_page.screenshot()
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                    await state.update_screenshot(screenshot_b64)
                except Exception:
                    pass
            
            # Complete the run
            await state.complete_run(
                success=result.success,
                error=result.error,
            )
            
            logger.info(f"Goal mode completed: success={result.success}, steps={result.steps_completed}/{result.steps_total}")
        
        else:
            # ============================================================
            # INSTRUCTIONS MODE: Use Engine (like CLI run-file)
            # ============================================================
            logger.info("Using Engine for instruction-based execution")
            
            # Parse instructions
            instructions = []
            for line in task.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    instructions.append(line)
            
            if not instructions:
                raise ValueError("No instructions found. Enter one instruction per line.")
            
            logger.info(f"Parsed {len(instructions)} instruction(s)")
            await state.set_running(total_steps=len(instructions))
            
            # Normalize instructions
            logger.info(f"Normalizing {len(instructions)} instructions (one LLM call)...")
            try:
                normalized = await normalize_instructions(instructions, llm, timeout_seconds=120)
                if normalized:
                    instructions = [normalized_to_instruction(action) for action in normalized]
                    logger.info(f"Normalized to {len(instructions)} actions")
            except Exception as e:
                logger.warning(f"Normalization error: {e}, using original instructions")
            
            # Create Engine with settings configuration
            from llm_web_agent.config import get_settings
            settings = get_settings()
            engine = Engine(
                llm_provider=llm,
                max_retries=settings.agent.retry_attempts,
                step_timeout_ms=settings.browser.timeout_ms,
                navigation_timeout_ms=settings.browser.navigation_timeout_ms,
                step_delay_ms=settings.agent.step_delay_ms,
                max_steps=settings.agent.max_steps,
            )
            state.set_engine(engine)
            
            # Shared context for hover → click
            shared_context = RunContext()
            
            # Execute each instruction
            total = len(instructions)
            succeeded = 0
            failed = 0
            
            for i, instruction in enumerate(instructions, 1):
                step_start = time.time()
                
                if state.should_stop():
                    logger.info("Stop requested, breaking execution loop")
                    break
                
                if not await state.wait_if_paused():
                    break
                
                logger.info(f"Step {i}/{total}: {instruction}")
                
                await state.update_step(
                    step_number=i,
                    action="executing",
                    status="running",
                    message=instruction[:100],
                )
                
                result = await engine.run(page=page, task=instruction, context=shared_context)
                step_duration = (time.time() - step_start) * 1000
                
                if result.success:
                    succeeded += 1
                    logger.info(f"Step {i} succeeded ({step_duration:.0f}ms)")
                    await state.update_step(
                        step_number=i,
                        action="done",
                        status="success",
                        message=instruction[:100],
                        duration_ms=step_duration,
                    )
                else:
                    failed += 1
                    logger.error(f"Step {i} failed: {result.error}")
                    await state.update_step(
                        step_number=i,
                        action="failed",
                        status="failed",
                        message=f"{instruction[:50]}: {result.error or 'Unknown error'}",
                        duration_ms=step_duration,
                    )
                
                # Screenshot after each step
                try:
                    screenshot_bytes = await page.screenshot()
                    screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                    await state.update_screenshot(screenshot_b64)
                except Exception:
                    pass
            
            # Final screenshot
            try:
                screenshot_bytes = await page.screenshot()
                screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
                await state.update_screenshot(screenshot_b64)
            except Exception:
                pass
            
            # Complete the run
            overall_success = failed == 0 and succeeded > 0
            await state.complete_run(
                success=overall_success,
                error=None if overall_success else f"{failed} step(s) failed",
            )
            
            logger.info(f"Instructions mode completed: {succeeded}/{total} succeeded, {failed} failed")
        
    except asyncio.CancelledError:
        logger.info("Task was cancelled")
        await state.complete_run(success=False, error="Task was cancelled")
        
    except Exception as e:
        logger.exception(f"Task failed: {e}")
        await state.complete_run(success=False, error=str(e))
        
    finally:
        # Cleanup
        if llm and hasattr(llm, 'close'):
            try:
                await llm.close()
            except Exception:
                pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass
        
        try:
            await state.cleanup()
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")


@router.post("/run", response_model=TaskResponse)
async def run_task(
    request: RunTaskRequest,
    background_tasks: BackgroundTasks,
) -> TaskResponse:
    """
    Start a new task.
    
    Supports two modes:
    - instructions: Step-by-step instructions (one per line), uses Engine
    - goal: High-level goal, uses AdaptiveEngine with dynamic planning
    """
    state = get_agent_state()
    
    if state.is_running:
        raise HTTPException(
            status_code=409,
            detail="Agent is already running. Stop the current task first."
        )
    
    try:
        run_id = await state.start_run(request.task)
        
        background_tasks.add_task(
            execute_task,
            task=request.task,
            url=request.url,
            use_websocket=request.use_websocket,
            visible=request.visible,
            model=request.model,
            generate_report=request.generate_report,
            report_dir=request.report_dir,
            engine_mode=request.engine_mode,
        )
        
        return TaskResponse(
            run_id=run_id,
            status="started",
            message=f"Task started with run_id: {run_id}"
        )
        
    except Exception as e:
        logger.exception("Failed to start task")
        raise HTTPException(status_code=500, detail=f"Failed to start task: {e}")


@router.post("/stop")
async def stop_task() -> Dict[str, str]:
    """Stop the currently running task."""
    state = get_agent_state()
    
    if not state.is_running:
        if state.status != AgentStatus.IDLE:
            await state.force_reset()
            return {"status": "reset", "message": "State was stuck, forced reset to idle"}
        return {"status": "idle", "message": "No task is running"}
    
    await state.request_stop()
    await asyncio.sleep(0.5)
    
    if state.is_running:
        await state.cleanup()
    
    return {"status": "stopped", "message": "Task stopped"}


@router.post("/reset")
async def force_reset() -> Dict[str, str]:
    """Force reset the agent state when stuck."""
    state = get_agent_state()
    await state.force_reset()
    return {"status": "idle", "message": "Agent state reset to idle"}


@router.post("/pause")
async def pause_task() -> Dict[str, str]:
    """Pause the currently running task."""
    state = get_agent_state()
    
    if state.status != AgentStatus.RUNNING:
        raise HTTPException(status_code=400, detail=f"Cannot pause: agent is {state.status.value}")
    
    await state.pause()
    return {"status": "paused", "message": "Task paused"}


@router.post("/resume")
async def resume_task() -> Dict[str, str]:
    """Resume a paused task."""
    state = get_agent_state()
    
    if state.status != AgentStatus.PAUSED:
        raise HTTPException(status_code=400, detail=f"Cannot resume: agent is {state.status.value}")
    
    await state.resume()
    return {"status": "running", "message": "Task resumed"}


@router.get("/status", response_model=StatusResponse)
async def get_status() -> StatusResponse:
    """Get current agent status."""
    state = get_agent_state()
    status_dict = state.get_status_dict()
    
    return StatusResponse(
        status=status_dict["status"],
        is_running=status_dict["is_running"],
        current_run=status_dict["current_run"],
        browser_connected=status_dict["browser_connected"],
    )


@router.get("/screenshot")
async def get_screenshot() -> Dict[str, Any]:
    """Get the current browser screenshot."""
    state = get_agent_state()
    screenshot = await state.get_screenshot()
    
    if not screenshot:
        raise HTTPException(status_code=404, detail="No screenshot available")
    
    return {"screenshot": screenshot, "format": "base64", "mime_type": "image/png"}


@router.get("/models")
async def get_models() -> Dict[str, Any]:
    """Fetch available models from the LLM API."""
    import httpx
    from llm_web_agent.config import load_config
    
    config = load_config()
    api_url = config.llm.base_url or "http://127.0.0.1:3030"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{api_url}/v1/models")
            if response.status_code == 200:
                data = response.json()
                models = [{"id": m.get("id"), "name": m.get("id")} for m in data.get("data", [])]
                return {"models": models, "source": api_url}
    except Exception as e:
        logger.warning(f"Failed to fetch models: {e}")
    
    return {
        "models": [
            {"id": "gpt-4.1", "name": "GPT-4.1"},
            {"id": "gpt-4o", "name": "GPT-4o"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo"},
        ],
        "source": "fallback",
    }


@router.get("/stream")
async def stream_events() -> StreamingResponse:
    """Server-Sent Events stream for real-time updates."""
    state = get_agent_state()
    
    async def event_generator():
        queue = await state.subscribe()
        
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    event_type = event.get("type", "message")
                    yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            state.unsubscribe(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.post("/screenshot/take")
async def take_screenshot() -> Dict[str, Any]:
    """Take a new screenshot of the current page."""
    state = get_agent_state()
    
    if not state._page:
        raise HTTPException(status_code=400, detail="No browser page available")
    
    try:
        screenshot_bytes = await state._page.screenshot()
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode()
        await state.update_screenshot(screenshot_b64)
        return {"screenshot": screenshot_b64, "format": "base64", "mime_type": "image/png"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to take screenshot: {e}")
