"""
Tests for the reporting module.
"""

import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock


class TestScreenshot:
    """Test the Screenshot dataclass."""
    
    def test_create_screenshot(self):
        """Test creating a screenshot."""
        from llm_web_agent.reporting.screenshot_manager import Screenshot
        screenshot = Screenshot(
            path=Path("/tmp/screenshot.png"),
            step_number=1,
            timestamp=datetime.now()
        )
        assert screenshot.step_number == 1
        assert screenshot.path == Path("/tmp/screenshot.png")
    
    def test_screenshot_with_description(self):
        """Test screenshot with description."""
        from llm_web_agent.reporting.screenshot_manager import Screenshot
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            step_number=2,
            timestamp=datetime.now(),
            description="After login"
        )
        assert screenshot.description == "After login"
    
    def test_screenshot_error_flag(self):
        """Test screenshot error flag."""
        from llm_web_agent.reporting.screenshot_manager import Screenshot
        screenshot = Screenshot(
            path=Path("/tmp/error.png"),
            step_number=3,
            timestamp=datetime.now(),
            is_error=True
        )
        assert screenshot.is_error is True


class TestScreenshotManager:
    """Test the ScreenshotManager class."""
    
    @pytest.fixture
    def manager(self, tmp_path):
        """Create a ScreenshotManager instance."""
        from llm_web_agent.reporting.screenshot_manager import ScreenshotManager
        return ScreenshotManager(output_dir=str(tmp_path), run_id="test123")
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock page."""
        page = MagicMock()
        page.screenshot = AsyncMock(return_value=b"fake_image_data")
        return page
    
    def test_manager_creates_output_dir(self, tmp_path):
        """Test manager creates output directory."""
        from llm_web_agent.reporting.screenshot_manager import ScreenshotManager
        manager = ScreenshotManager(output_dir=str(tmp_path), run_id="newrun")
        assert manager.output_dir.exists()
    
    @pytest.mark.asyncio
    async def test_capture_screenshot(self, manager, mock_page):
        """Test capturing a screenshot."""
        result = await manager.capture(mock_page, step_number=1)
        assert result is not None
        assert result.step_number == 1
        mock_page.screenshot.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_capture_with_description(self, manager, mock_page):
        """Test capturing screenshot with description."""
        result = await manager.capture(mock_page, step_number=1, description="Before click")
        assert result.description == "Before click"
    
    @pytest.mark.asyncio
    async def test_capture_on_error(self, manager, mock_page):
        """Test capturing screenshot on error."""
        result = await manager.capture_on_error(mock_page, step_number=5, error="Element not found")
        assert result.is_error is True
        assert "Error" in result.description
    
    @pytest.mark.asyncio
    async def test_get_screenshots(self, manager, mock_page):
        """Test getting all screenshots."""
        await manager.capture(mock_page, step_number=1)
        await manager.capture(mock_page, step_number=2)
        screenshots = manager.get_screenshots()
        assert len(screenshots) == 2
    
    @pytest.mark.asyncio
    async def test_get_screenshot_for_step(self, manager, mock_page):
        """Test getting screenshot for specific step."""
        await manager.capture(mock_page, step_number=1)
        await manager.capture(mock_page, step_number=2)
        step1_shots = manager.get_screenshot_for_step(1)
        assert len(step1_shots) == 1
        assert step1_shots[0].step_number == 1


class TestRunReport:
    """Test the RunReport class."""
    
    def test_run_report_exists(self):
        """Test RunReport class exists."""
        from llm_web_agent.reporting.run_report import RunReport
        assert RunReport is not None


class TestExecutionReport:
    """Test the ExecutionReport module."""
    
    def test_execution_report_module_exists(self):
        """Test execution_report module can be imported."""
        import llm_web_agent.reporting.execution_report
        assert llm_web_agent.reporting.execution_report is not None


class TestStepLogger:
    """Test the StepLogger class."""
    
    def test_step_logger_exists(self):
        """Test StepLogger can be imported."""
        from llm_web_agent.reporting.step_logger import StepLogger
        assert StepLogger is not None


class TestArtifacts:
    """Test the artifacts module."""
    
    def test_artifacts_module_exists(self):
        """Test artifacts module can be imported."""
        import llm_web_agent.reporting.artifacts
        assert llm_web_agent.reporting.artifacts is not None
