"""
Record & Replay Mode - Record user actions and replay them.

⚠️ STATUS: Coming Soon

This mode will allow users to:
1. Start recording browser actions
2. Perform actions manually
3. Save the recording as a replayable script
4. Replay saved scripts

Currently not implemented. Use `run-file` with instruction files instead.
"""

from typing import Any, Optional, TYPE_CHECKING
import logging

from llm_web_agent.modes.base import (
    IInteractionMode,
    ModeType,
    ModeConfig,
    ModeResult,
)

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


class RecordReplayMode(IInteractionMode):
    """
    Record & Replay interaction mode.
    
    ⚠️ STATUS: Coming Soon
    
    This mode will allow recording user actions and replaying them.
    Currently not implemented.
    """
    
    @property
    def mode_type(self) -> ModeType:
        return ModeType.RECORD_REPLAY
    
    @property
    def name(self) -> str:
        return "Record & Replay"
    
    @property
    def description(self) -> str:
        return "Record browser actions and replay them (Coming Soon)"
    
    def __init__(self):
        """Initialize the mode."""
        self._page: Optional["IPage"] = None
        self._config: Optional[ModeConfig] = None
        self._is_running = False
        self._is_recording = False
        self._recorded_actions: list = []
    
    async def start(
        self,
        page: "IPage",
        config: ModeConfig,
        **kwargs: Any,
    ) -> None:
        """Start the record/replay mode."""
        self._page = page
        self._config = config
        self._is_running = True
        logger.info("Record & Replay mode started (feature coming soon)")
    
    async def execute(self, input_data: Any) -> ModeResult:
        """
        Execute a record/replay action.
        
        Args:
            input_data: Command dict with 'action': 'record' | 'stop' | 'replay'
            
        Returns:
            Execution result
        """
        if not self._is_running:
            return ModeResult(
                success=False,
                error="Mode not started. Call start() first.",
            )
        
        # Feature not yet implemented
        return ModeResult(
            success=False,
            error="Record & Replay mode is coming soon. Use 'run-file' with instruction files instead.",
        )
    
    async def stop(self) -> None:
        """Stop the mode."""
        self._is_running = False
        self._is_recording = False
        self._recorded_actions.clear()
        self._page = None
        logger.info("Record & Replay mode stopped")
