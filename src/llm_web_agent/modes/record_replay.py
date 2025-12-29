"""
Record & Replay Mode - Record user actions and replay them.

This mode allows users to:
1. Start recording browser actions
2. Perform actions manually in the browser
3. Stop and save the recording
4. Replay saved recordings
5. Export as Playwright scripts
"""

import json
import logging
from pathlib import Path
from typing import Any, Optional, Union, TYPE_CHECKING

from llm_web_agent.modes.base import (
    IInteractionMode,
    ModeType,
    ModeConfig,
    ModeResult,
    Recording,
    RecordedAction as BaseRecordedAction,
)
from llm_web_agent.recorder.recorder import BrowserRecorder, RecordingSession
from llm_web_agent.recorder.script_generator import (
    PlaywrightScriptGenerator,
    generate_instruction_file,
)

if TYPE_CHECKING:
    from playwright.async_api import Page
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


class RecordReplayMode(IInteractionMode):
    """
    Record & Replay interaction mode.
    
    Allows recording user actions and replaying them.
    
    Usage:
        >>> mode = RecordReplayMode()
        >>> await mode.start(page, config)
        >>> 
        >>> # Start recording
        >>> result = await mode.execute({"action": "record", "name": "my_flow"})
        >>> 
        >>> # User performs actions in browser...
        >>> 
        >>> # Stop and get recording
        >>> result = await mode.execute({"action": "stop"})
        >>> print(result.data["script"])  # Playwright script
        >>> 
        >>> # Or replay a saved recording
        >>> result = await mode.execute({"action": "replay", "recording": session_dict})
    """
    
    @property
    def mode_type(self) -> ModeType:
        return ModeType.RECORD_REPLAY
    
    @property
    def name(self) -> str:
        return "Record & Replay"
    
    @property
    def description(self) -> str:
        return "Record browser actions and replay them as Playwright scripts"
    
    def __init__(self):
        """Initialize the mode."""
        self._page: Optional["Page"] = None
        self._config: Optional[ModeConfig] = None
        self._is_running = False
        self._recorder: Optional[BrowserRecorder] = None
        self._current_session: Optional[RecordingSession] = None
    
    async def start(
        self,
        page: Union["IPage", "Page"],
        config: ModeConfig,
        **kwargs: Any,
    ) -> None:
        """
        Start the record/replay mode.
        
        Args:
            page: Browser page (Playwright page or IPage wrapper)
            config: Mode configuration
        """
        # Get the underlying Playwright page if wrapped
        if hasattr(page, "_page"):
            self._page = page._page
        else:
            self._page = page
            
        self._config = config
        self._is_running = True
        self._recorder = BrowserRecorder()
        
        logger.info("Record & Replay mode started")
    
    async def execute(self, input_data: Any) -> ModeResult:
        """
        Execute a record/replay action.
        
        Args:
            input_data: Command dict with:
                - action: 'record' | 'stop' | 'replay' | 'status' | 'export'
                - name: Recording name (for 'record')
                - url: Optional start URL (for 'record')
                - recording: Recording session dict (for 'replay')
                - format: 'python' | 'json' | 'instructions' (for 'export')
                - output_path: File path to save (for 'export')
                
        Returns:
            Execution result with recording data
        """
        if not self._is_running:
            return ModeResult(
                success=False,
                error="Mode not started. Call start() first.",
            )
        
        if not isinstance(input_data, dict):
            return ModeResult(
                success=False,
                error="Input must be a dict with 'action' key.",
            )
        
        action = input_data.get("action", "").lower()
        
        if action == "record":
            return await self._start_recording(
                name=input_data.get("name", "recording"),
                url=input_data.get("url"),
            )
            
        elif action == "stop":
            return await self._stop_recording(
                export_format=input_data.get("format", "python"),
            )
            
        elif action == "replay":
            return await self._replay_recording(
                recording=input_data.get("recording"),
            )
            
        elif action == "status":
            return self._get_status()
            
        elif action == "export":
            return self._export_recording(
                format=input_data.get("format", "python"),
                output_path=input_data.get("output_path"),
            )
            
        else:
            return ModeResult(
                success=False,
                error=f"Unknown action: {action}. Valid actions: record, stop, replay, status, export",
            )
    
    async def _start_recording(
        self,
        name: str = "recording",
        url: Optional[str] = None,
    ) -> ModeResult:
        """Start recording user actions."""
        if not self._page:
            return ModeResult(success=False, error="No page available")
        
        if self._recorder and self._recorder.is_recording:
            return ModeResult(success=False, error="Already recording")
        
        try:
            self._recorder = BrowserRecorder()
            await self._recorder.start(self._page, name=name, start_url=url)
            
            return ModeResult(
                success=True,
                data={
                    "status": "recording",
                    "name": name,
                    "message": "Recording started. Perform actions in the browser, then call with action='stop'.",
                },
            )
            
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return ModeResult(success=False, error=str(e))
    
    async def _stop_recording(self, export_format: str = "python") -> ModeResult:
        """Stop recording and return the result."""
        if not self._recorder or not self._recorder.is_recording:
            return ModeResult(success=False, error="Not currently recording")
        
        try:
            session = await self._recorder.stop()
            self._current_session = session
            
            # Generate output
            generator = PlaywrightScriptGenerator(
                async_mode=True,
                include_comments=True,
                headless=False,
            )
            
            script = generator.generate(session)
            
            return ModeResult(
                success=True,
                steps_executed=len(session.actions),
                data={
                    "status": "stopped",
                    "name": session.name,
                    "action_count": len(session.actions),
                    "duration_ms": session.duration_ms,
                    "script": script,
                    "session": session.to_dict(),
                },
            )
            
        except Exception as e:
            logger.error(f"Failed to stop recording: {e}")
            return ModeResult(success=False, error=str(e))
    
    async def _replay_recording(
        self,
        recording: Optional[dict],
    ) -> ModeResult:
        """Replay a recorded session."""
        if not self._page:
            return ModeResult(success=False, error="No page available")
        
        if not recording:
            # Use current session if available
            if self._current_session:
                recording = self._current_session.to_dict()
            else:
                return ModeResult(
                    success=False,
                    error="No recording provided and no current session available",
                )
        
        try:
            session = RecordingSession.from_dict(recording)
            steps_executed = 0
            
            for action in session.actions:
                await self._execute_action(action)
                steps_executed += 1
            
            return ModeResult(
                success=True,
                steps_executed=steps_executed,
                data={
                    "status": "completed",
                    "name": session.name,
                    "actions_replayed": steps_executed,
                },
            )
            
        except Exception as e:
            logger.error(f"Replay failed: {e}")
            return ModeResult(success=False, error=str(e))
    
    async def _execute_action(self, action) -> None:
        """Execute a single recorded action."""
        from llm_web_agent.recorder.recorder import ActionType
        
        if not self._page:
            return
        
        if action.action_type == ActionType.NAVIGATE and action.url:
            await self._page.goto(action.url)
            
        elif action.action_type == ActionType.CLICK and action.selector:
            await self._page.click(action.selector)
            
        elif action.action_type == ActionType.FILL and action.selector and action.value:
            await self._page.fill(action.selector, action.value)
            
        elif action.action_type == ActionType.TYPE and action.selector and action.value:
            await self._page.type(action.selector, action.value)
            
        elif action.action_type == ActionType.SELECT and action.selector and action.value:
            await self._page.select_option(action.selector, action.value)
            
        elif action.action_type == ActionType.CHECK and action.selector:
            await self._page.check(action.selector)
            
        elif action.action_type == ActionType.UNCHECK and action.selector:
            await self._page.uncheck(action.selector)
            
        elif action.action_type == ActionType.PRESS and action.key:
            if action.selector:
                await self._page.press(action.selector, action.key)
            else:
                await self._page.keyboard.press(action.key)
                
        elif action.action_type == ActionType.HOVER and action.selector:
            await self._page.hover(action.selector)
    
    def _get_status(self) -> ModeResult:
        """Get current recording status."""
        if self._recorder and self._recorder.is_recording:
            session = self._recorder.current_session
            return ModeResult(
                success=True,
                data={
                    "status": "recording",
                    "name": session.name if session else "unknown",
                    "action_count": len(session.actions) if session else 0,
                },
            )
        elif self._current_session:
            return ModeResult(
                success=True,
                data={
                    "status": "stopped",
                    "name": self._current_session.name,
                    "action_count": len(self._current_session.actions),
                },
            )
        else:
            return ModeResult(
                success=True,
                data={"status": "idle"},
            )
    
    def _export_recording(
        self,
        format: str = "python",
        output_path: Optional[str] = None,
    ) -> ModeResult:
        """Export the current recording."""
        if not self._current_session:
            return ModeResult(
                success=False,
                error="No recording available. Record something first.",
            )
        
        try:
            if format == "json":
                content = self._current_session.to_json()
                suffix = ".json"
            elif format == "instructions":
                content = generate_instruction_file(self._current_session)
                suffix = ".txt"
            else:  # python
                generator = PlaywrightScriptGenerator(async_mode=True)
                content = generator.generate(self._current_session)
                suffix = ".py"
            
            if output_path:
                path = Path(output_path)
                path.write_text(content)
                logger.info(f"Exported recording to {path}")
            
            return ModeResult(
                success=True,
                data={
                    "format": format,
                    "content": content,
                    "saved_to": output_path,
                },
            )
            
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return ModeResult(success=False, error=str(e))
    
    async def stop(self) -> None:
        """Stop the mode and cleanup."""
        if self._recorder and self._recorder.is_recording:
            await self._recorder.stop()
        
        self._is_running = False
        self._recorder = None
        self._current_session = None
        self._page = None
        logger.info("Record & Replay mode stopped")
