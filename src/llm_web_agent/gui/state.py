"""
Agent State Management - Singleton for managing agent execution state.

This module provides a global state manager that tracks:
- Agent execution state (idle/running/paused/stopped)
- Current browser and page instances
- Event queue for real-time updates
- Screenshot buffer for live view
"""

import asyncio
import base64
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page
    from llm_web_agent.engine.adaptive_engine import AdaptiveEngine

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent execution states."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class StepEvent:
    """Event representing a single step in execution."""
    step_number: int
    action: str
    status: str  # pending, running, success, failed
    message: str
    timestamp: float = field(default_factory=time.time)
    screenshot: Optional[str] = None  # base64 encoded
    duration_ms: float = 0
    selector: Optional[str] = None


@dataclass
class RunState:
    """State of a single run."""
    run_id: str
    task: str
    status: AgentStatus
    started_at: datetime
    steps: List[StepEvent] = field(default_factory=list)
    current_step: int = 0
    total_steps: int = 0
    error: Optional[str] = None
    ended_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "run_id": self.run_id,
            "task": self.task,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "error": self.error,
            "steps": [
                {
                    "step_number": s.step_number,
                    "action": s.action,
                    "status": s.status,
                    "message": s.message,
                    "timestamp": s.timestamp,
                    "duration_ms": s.duration_ms,
                    "selector": s.selector,
                }
                for s in self.steps
            ],
        }


class AgentState:
    """
    Global state manager for agent execution.
    
    Thread-safe singleton that manages:
    - Browser and page instances
    - Execution state
    - Event subscribers for real-time updates
    - Screenshot buffer
    """
    
    _instance: Optional["AgentState"] = None
    
    def __new__(cls) -> "AgentState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self._status = AgentStatus.IDLE
        self._current_run: Optional[RunState] = None
        self._browser: Optional["Browser"] = None
        self._page: Optional["Page"] = None
        self._engine: Optional["AdaptiveEngine"] = None
        self._task: Optional[asyncio.Task] = None
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially
        self._stop_requested = False
        
        # Event subscribers for SSE
        self._subscribers: List[asyncio.Queue] = []
        
        # Screenshot buffer
        self._last_screenshot: Optional[str] = None
        self._screenshot_lock = asyncio.Lock()
        
        # Run history
        self._run_history: List[RunState] = []
        self._max_history = 100
        
        # Configuration
        self._config: Dict[str, Any] = {}
        
        logger.info("AgentState initialized")
    
    @property
    def status(self) -> AgentStatus:
        """Current agent status."""
        return self._status
    
    @property
    def current_run(self) -> Optional[RunState]:
        """Current run state."""
        return self._current_run
    
    @property
    def is_running(self) -> bool:
        """Whether agent is currently running or in a transitional state."""
        return self._status in (
            AgentStatus.RUNNING, 
            AgentStatus.PAUSED, 
            AgentStatus.STARTING,
            AgentStatus.STOPPING,
        )
    
    @property
    def run_history(self) -> List[RunState]:
        """List of past runs."""
        return self._run_history
    
    async def subscribe(self) -> asyncio.Queue:
        """Subscribe to state events. Returns a queue that receives events."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        
        # Send current state immediately
        await queue.put({
            "type": "state",
            "status": self._status.value,
            "run": self._current_run.to_dict() if self._current_run else None,
        })
        
        return queue
    
    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Unsubscribe from state events."""
        if queue in self._subscribers:
            self._subscribers.remove(queue)
    
    async def _broadcast(self, event: Dict[str, Any]) -> None:
        """Broadcast event to all subscribers."""
        for queue in self._subscribers:
            try:
                await queue.put(event)
            except Exception as e:
                logger.warning(f"Failed to broadcast to subscriber: {e}")
    
    async def start_run(
        self,
        task: str,
        options: Dict[str, Any] = None,
    ) -> str:
        """
        Start a new agent run.
        
        Args:
            task: The task/goal to execute
            options: Optional configuration overrides
            
        Returns:
            Run ID
            
        Raises:
            RuntimeError: If agent is already running
        """
        if self.is_running:
            raise RuntimeError("Agent is already running")
        
        run_id = str(uuid.uuid4())[:8]
        self._current_run = RunState(
            run_id=run_id,
            task=task,
            status=AgentStatus.STARTING,
            started_at=datetime.now(),
        )
        self._status = AgentStatus.STARTING
        self._stop_requested = False
        self._pause_event.set()
        
        await self._broadcast({
            "type": "run_started",
            "run_id": run_id,
            "task": task,
            "status": self._status.value,
        })
        
        logger.info(f"Starting run {run_id}: {task[:50]}...")
        return run_id
    
    async def update_step(
        self,
        step_number: int,
        action: str,
        status: str,
        message: str,
        screenshot: Optional[str] = None,
        duration_ms: float = 0,
        selector: Optional[str] = None,
    ) -> None:
        """Update step progress."""
        if not self._current_run:
            return
        
        event = StepEvent(
            step_number=step_number,
            action=action,
            status=status,
            message=message,
            screenshot=screenshot,
            duration_ms=duration_ms,
            selector=selector,
        )
        
        # Update or add step (step_number is 1-indexed)
        step_index = step_number - 1
        if step_index >= 0 and step_index < len(self._current_run.steps):
            self._current_run.steps[step_index] = event
        else:
            self._current_run.steps.append(event)
        
        self._current_run.current_step = step_number
        
        await self._broadcast({
            "type": "step",
            "step": {
                "step_number": step_number,
                "action": action,
                "status": status,
                "message": message,
                "duration_ms": duration_ms,
                "selector": selector,
            },
        })
    
    async def set_running(self, total_steps: int = 0) -> None:
        """Mark agent as running."""
        self._status = AgentStatus.RUNNING
        if self._current_run:
            self._current_run.status = AgentStatus.RUNNING
            self._current_run.total_steps = total_steps
        
        await self._broadcast({
            "type": "state",
            "status": self._status.value,
        })
    
    async def pause(self) -> None:
        """Pause execution."""
        if self._status == AgentStatus.RUNNING:
            self._status = AgentStatus.PAUSED
            self._pause_event.clear()
            if self._current_run:
                self._current_run.status = AgentStatus.PAUSED
            
            await self._broadcast({
                "type": "state",
                "status": self._status.value,
            })
            logger.info("Agent paused")
    
    async def resume(self) -> None:
        """Resume paused execution."""
        if self._status == AgentStatus.PAUSED:
            self._status = AgentStatus.RUNNING
            self._pause_event.set()
            if self._current_run:
                self._current_run.status = AgentStatus.RUNNING
            
            await self._broadcast({
                "type": "state",
                "status": self._status.value,
            })
            logger.info("Agent resumed")
    
    async def wait_if_paused(self) -> bool:
        """
        Wait if execution is paused.
        
        Returns:
            False if stop was requested while paused, True otherwise
        """
        await self._pause_event.wait()
        return not self._stop_requested
    
    def should_stop(self) -> bool:
        """Check if stop has been requested."""
        return self._stop_requested
    
    async def request_stop(self) -> None:
        """Request stop of current execution."""
        if self.is_running:
            self._stop_requested = True
            self._status = AgentStatus.STOPPING
            self._pause_event.set()  # Unblock if paused
            
            if self._current_run:
                self._current_run.status = AgentStatus.STOPPING
            
            await self._broadcast({
                "type": "state",
                "status": self._status.value,
            })
            logger.info("Stop requested")
    
    async def complete_run(
        self,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Mark current run as complete."""
        if self._current_run:
            self._current_run.ended_at = datetime.now()
            self._current_run.status = AgentStatus.STOPPED if success else AgentStatus.ERROR
            self._current_run.error = error
            
            # Add to history
            self._run_history.insert(0, self._current_run)
            if len(self._run_history) > self._max_history:
                self._run_history.pop()
        
        self._status = AgentStatus.IDLE
        
        await self._broadcast({
            "type": "run_completed",
            "success": success,
            "error": error,
            "run": self._current_run.to_dict() if self._current_run else None,
        })
        
        self._current_run = None
        logger.info(f"Run completed: success={success}")
    
    async def update_screenshot(self, screenshot_base64: str) -> None:
        """Update the current screenshot buffer."""
        async with self._screenshot_lock:
            self._last_screenshot = screenshot_base64
    
    async def get_screenshot(self) -> Optional[str]:
        """Get the current screenshot."""
        async with self._screenshot_lock:
            return self._last_screenshot
    
    def set_browser(self, browser: "Browser", page: "Page") -> None:
        """Set the browser and page instances."""
        self._browser = browser
        self._page = page
    
    def set_engine(self, engine: "AdaptiveEngine") -> None:
        """Set the engine instance."""
        self._engine = engine
    
    def set_task(self, task: asyncio.Task) -> None:
        """Set the current execution task."""
        self._task = task
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        if self._page:
            try:
                await self._page.close()
            except Exception:
                pass
            self._page = None
        
        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None
        
        self._engine = None
        self._task = None
        self._stop_requested = False  # Reset stop flag
        self._current_run = None  # Clear current run
        self._status = AgentStatus.IDLE
        self._pause_event.set()  # Ensure not blocked
        
        # Broadcast state change to frontend
        await self._broadcast({
            "type": "state",
            "status": self._status.value,
        })
        
        logger.info("AgentState cleanup complete")
    
    async def force_reset(self) -> None:
        """
        Force reset state when stuck.
        
        This can be called if the agent gets into an inconsistent state,
        for example if cleanup fails or a task hangs.
        """
        logger.warning("Force resetting agent state")
        
        # Cancel any running task
        if self._task:
            self._task.cancel()
        
        # Close browser without waiting
        if self._browser:
            try:
                await asyncio.wait_for(self._browser.close(), timeout=5.0)
            except Exception:
                pass
        
        # Reset all state
        self._browser = None
        self._page = None
        self._engine = None
        self._task = None
        self._stop_requested = False
        self._current_run = None
        self._status = AgentStatus.IDLE
        self._pause_event.set()
        self._last_screenshot = None
        
        await self._broadcast({
            "type": "state",
            "status": self._status.value,
        })
        
        logger.info("Agent state force reset complete")
    
    def get_status_dict(self) -> Dict[str, Any]:
        """Get current status as dictionary."""
        return {
            "status": self._status.value,
            "is_running": self.is_running,
            "current_run": self._current_run.to_dict() if self._current_run else None,
            "browser_connected": self._browser is not None,
        }


# Global singleton instance
def get_agent_state() -> AgentState:
    """Get the global agent state instance."""
    return AgentState()
