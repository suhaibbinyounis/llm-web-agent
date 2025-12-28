"""
Integration tests for end-to-end workflows.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestFullWorkflow:
    """Test complete execution workflows."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        from llm_web_agent.interfaces.llm import Message, MessageRole, LLMResponse
        
        llm = MagicMock()
        llm.name = "mock"
        llm.default_model = "mock-model"
        llm.supports_vision = False
        llm.supports_tools = True
        llm.supports_streaming = False
        llm.complete = AsyncMock(return_value=LLMResponse(
            content="Click the button",
            model="mock-model"
        ))
        llm.health_check = AsyncMock(return_value=True)
        llm.close = AsyncMock()
        return llm
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock page with elements."""
        page = MagicMock()
        page.url = "https://example.com"
        page.goto = AsyncMock()
        page.title = AsyncMock(return_value="Example")
        page.content = AsyncMock(return_value="<html><body><button id='submit'>Submit</button></body></html>")
        
        mock_element = AsyncMock()
        mock_element.click = AsyncMock()
        mock_element.fill = AsyncMock()
        mock_element.text_content = AsyncMock(return_value="Submit")
        mock_element.is_visible = AsyncMock(return_value=True)
        
        page.query_selector = AsyncMock(return_value=mock_element)
        page.query_selector_all = AsyncMock(return_value=[mock_element])
        page.wait_for_selector = AsyncMock(return_value=mock_element)
        page.wait_for_load_state = AsyncMock()
        page.evaluate = AsyncMock(return_value=[])
        page.screenshot = AsyncMock(return_value=b"image")
        
        return page
    
    @pytest.mark.asyncio
    async def test_engine_workflow_navigation(self, mock_page, mock_llm):
        """Test complete engine navigation workflow."""
        from llm_web_agent.engine.engine import Engine
        
        engine = Engine(llm_provider=mock_llm)
        result = await engine.run(mock_page, "go to https://google.com")
        
        assert result.success is True
        assert result.steps_total >= 1
        mock_page.goto.assert_called_with("https://google.com")
    
    @pytest.mark.asyncio
    async def test_engine_workflow_multi_step(self, mock_page, mock_llm):
        """Test multi-step workflow."""
        from llm_web_agent.engine.engine import Engine
        
        engine = Engine(llm_provider=mock_llm)
        result = await engine.run(
            mock_page,
            "go to example.com, click the button"
        )
        
        assert result.steps_total >= 2
    
    @pytest.mark.asyncio
    async def test_adaptive_engine_workflow(self, mock_page, mock_llm):
        """Test AdaptiveEngine workflow."""
        from llm_web_agent.engine.adaptive_engine import AdaptiveEngine
        
        engine = AdaptiveEngine(llm_provider=mock_llm)
        result = await engine.run(mock_page, "Click the submit button")
        
        # Should succeed or partially succeed
        assert result.run_id is not None


class TestReportingWorkflow:
    """Test execution with reporting."""
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock page."""
        page = MagicMock()
        page.url = "https://example.com"
        page.goto = AsyncMock()
        page.title = AsyncMock(return_value="Example")
        page.screenshot = AsyncMock(return_value=b"image_data")
        page.wait_for_load_state = AsyncMock()
        page.evaluate = AsyncMock(return_value=[])
        page.query_selector = AsyncMock(return_value=None)
        page.query_selector_all = AsyncMock(return_value=[])
        return page
    
    @pytest.mark.asyncio
    async def test_generates_report(self, mock_page, tmp_path):
        """Test report generation during execution."""
        from llm_web_agent.engine.engine import Engine
        from llm_web_agent.reporting.execution_report import ExecutionReportGenerator
        
        engine = Engine()
        result = await engine.run(mock_page, "go to example.com")
        
        generator = ExecutionReportGenerator(output_dir=str(tmp_path))
        report = generator.create_report(
            run_id=result.run_id or "test",
            goal="go to example.com",
            success=result.success,
            step_results=[],
            duration_seconds=result.duration_seconds
        )
        
        json_path = generator.export_json(report)
        assert Path(json_path).exists()


class TestSettingsPersistence:
    """Test settings save/load workflow."""
    
    def test_gui_settings_roundtrip(self, tmp_path, monkeypatch):
        """Test saving and loading GUI settings."""
        from llm_web_agent.gui.config import GUISettings, save_gui_settings, load_gui_settings
        
        # Mock the settings file location
        settings_file = tmp_path / "gui_settings.json"
        monkeypatch.setattr("llm_web_agent.gui.config.SETTINGS_FILE", settings_file)
        
        # Save settings
        original = GUISettings(
            model="gpt-4",
            api_url="http://localhost:8080",
            timeout=120,
            websocket=True
        )
        save_gui_settings(original)
        
        # Load settings
        loaded = load_gui_settings()
        
        assert loaded.model == "gpt-4"
        assert loaded.api_url == "http://localhost:8080"
        assert loaded.timeout == 120


class TestPolicyWorkflow:
    """Test policy enforcement workflow."""
    
    def test_policy_blocks_domain(self):
        """Test policy blocking a domain."""
        from llm_web_agent.control.policies.policy_engine import (
            PolicyEngine, Policy, PolicyType, PolicyAction
        )
        
        engine = PolicyEngine()
        engine.add_policy(Policy(
            name="block-gambling",
            policy_type=PolicyType.DOMAIN,
            pattern=r".*gambling\.com",
            action=PolicyAction.DENY
        ))
        
        result = engine.evaluate_domain("https://gambling.com/slots")
        
        assert result.allowed is False
        assert result.policy.name == "block-gambling"
    
    def test_policy_allows_whitelisted(self):
        """Test policy allowing whitelisted domain."""
        from llm_web_agent.control.policies.policy_engine import (
            PolicyEngine, Policy, PolicyType, PolicyAction
        )
        
        engine = PolicyEngine()
        engine.add_policy(Policy(
            name="allow-google",
            policy_type=PolicyType.DOMAIN,
            pattern=r".*google\.com",
            action=PolicyAction.ALLOW,
            priority=10
        ))
        
        result = engine.evaluate_domain("https://google.com")
        
        assert result.allowed is True


class TestModeWorkflow:
    """Test mode switching workflow."""
    
    @pytest.mark.asyncio
    async def test_guided_mode_with_hints(self):
        """Test guided mode with locator hints."""
        from llm_web_agent.modes.guided import GuidedMode, GuidedTaskInput, LocatorHint
        from llm_web_agent.modes.base import ModeConfig, ModeType
        
        mode = GuidedMode()
        mock_page = MagicMock()
        
        await mode.start(mock_page, ModeConfig(mode_type=ModeType.GUIDED))
        
        task_input = GuidedTaskInput(
            task="Fill the login form",
            hints=[
                LocatorHint(name="username", selector="#user"),
                LocatorHint(name="password", selector="#pass"),
            ],
            data={"username": "admin", "password": "secret"}
        )
        
        result = await mode.execute(task_input)
        # May fail due to stub, but shouldn't crash
        assert result is not None


class TestComponentRegistryWorkflow:
    """Test component registration workflow."""
    
    def test_register_and_get_browser(self):
        """Test registering and retrieving a browser."""
        from llm_web_agent.registry import ComponentRegistry
        from llm_web_agent.interfaces.browser import IBrowser
        
        @ComponentRegistry.register_browser("test-browser")
        class TestBrowser(IBrowser):
            @property
            def is_connected(self):
                return False
            async def launch(self, **kwargs): pass
            async def new_page(self, **kwargs): pass
            async def new_context(self, **kwargs): pass
            async def close(self): pass
        
        assert "test-browser" in ComponentRegistry.list_browsers()
        assert ComponentRegistry.get_browser("test-browser") == TestBrowser
        
        ComponentRegistry.clear_all()
    
    def test_register_and_get_llm(self):
        """Test registering and retrieving an LLM provider."""
        from llm_web_agent.registry import ComponentRegistry
        from llm_web_agent.interfaces.llm import ILLMProvider
        
        @ComponentRegistry.register_llm("test-llm")
        class TestLLM(ILLMProvider):
            @property
            def name(self): return "test"
            @property
            def default_model(self): return "test"
            @property
            def supports_vision(self): return False
            @property
            def supports_tools(self): return False
            @property
            def supports_streaming(self): return False
            async def complete(self, messages, **kwargs): pass
            async def stream(self, messages, **kwargs): pass
            async def count_tokens(self, messages, **kwargs): return 0
            async def health_check(self): return True
        
        assert "test-llm" in ComponentRegistry.list_llm_providers()
        
        ComponentRegistry.clear_all()


class TestErrorRecoveryWorkflow:
    """Test error handling and recovery."""
    
    @pytest.mark.asyncio
    async def test_engine_recovers_from_errors(self):
        """Test engine recovers from step errors."""
        from llm_web_agent.engine.engine import Engine
        
        page = MagicMock()
        page.url = "https://example.com"
        page.goto = AsyncMock(side_effect=Exception("Network error"))
        page.title = AsyncMock(return_value="Test")
        page.wait_for_load_state = AsyncMock()
        page.evaluate = AsyncMock(return_value=[])
        page.query_selector = AsyncMock(return_value=None)
        page.query_selector_all = AsyncMock(return_value=[])
        
        engine = Engine()
        result = await engine.run(page, "go to example.com")
        
        # Should not crash, should return error
        assert result.success is False
        assert result.error is not None
