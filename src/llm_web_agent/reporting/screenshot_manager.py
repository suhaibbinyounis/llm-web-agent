"""
Screenshot Manager - Capture and organize screenshots during runs.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


@dataclass
class Screenshot:
    """
    A captured screenshot.
    
    Attributes:
        path: File path to the screenshot
        step_number: Associated step number
        timestamp: When the screenshot was taken
        description: Description of what the screenshot shows
        is_error: Whether this is an error screenshot
    """
    path: Path
    step_number: int
    timestamp: datetime
    description: str = ""
    is_error: bool = False


class ScreenshotManager:
    """
    Manage screenshot capture and organization.
    
    Example:
        >>> manager = ScreenshotManager(output_dir="./screenshots", run_id="run_123")
        >>> screenshot = await manager.capture(page, step_number=1, description="After login")
    """
    
    def __init__(
        self,
        output_dir: str | Path,
        run_id: str,
        format: str = "png",
    ):
        """
        Initialize the screenshot manager.
        
        Args:
            output_dir: Directory to save screenshots
            run_id: Unique run identifier
            format: Image format (png, jpeg)
        """
        self.output_dir = Path(output_dir) / run_id
        self.run_id = run_id
        self.format = format
        self._screenshots: list[Screenshot] = []
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def capture(
        self,
        page: "IPage",
        step_number: int,
        description: str = "",
        full_page: bool = False,
        is_error: bool = False,
    ) -> Screenshot:
        """
        Capture a screenshot.
        
        Args:
            page: Browser page to capture
            step_number: Current step number
            description: Description of the screenshot
            full_page: Whether to capture full scrollable page
            is_error: Whether this is an error screenshot
            
        Returns:
            Screenshot object with path and metadata
        """
        timestamp = datetime.now()
        prefix = "error_" if is_error else ""
        filename = f"{prefix}step_{step_number:03d}_{timestamp.strftime('%H%M%S')}.{self.format}"
        path = self.output_dir / filename
        
        # Capture screenshot
        await page.screenshot(path=path, full_page=full_page)
        
        screenshot = Screenshot(
            path=path,
            step_number=step_number,
            timestamp=timestamp,
            description=description,
            is_error=is_error,
        )
        self._screenshots.append(screenshot)
        
        logger.debug(f"Captured screenshot: {path}")
        return screenshot
    
    async def capture_on_error(
        self,
        page: "IPage",
        step_number: int,
        error: str,
    ) -> Screenshot:
        """Capture an error screenshot."""
        return await self.capture(
            page=page,
            step_number=step_number,
            description=f"Error: {error}",
            full_page=True,
            is_error=True,
        )
    
    def get_screenshots(self) -> list[Screenshot]:
        """Get all captured screenshots."""
        return self._screenshots.copy()
    
    def get_screenshot_for_step(self, step_number: int) -> list[Screenshot]:
        """Get all screenshots for a specific step."""
        return [s for s in self._screenshots if s.step_number == step_number]
