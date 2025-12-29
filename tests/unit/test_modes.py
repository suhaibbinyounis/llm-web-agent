"""
Tests for the interaction modes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestModeType:
    """Test the ModeType enum."""
    
    def test_mode_types_exist(self):
        """Test that all expected mode types exist."""
        from llm_web_agent.modes.base import ModeType
        assert ModeType.NATURAL_LANGUAGE
        assert ModeType.RECORD_REPLAY
        assert ModeType.GUIDED
    
    def test_mode_type_values(self):
        """Test mode type string values."""
        from llm_web_agent.modes.base import ModeType
        assert ModeType.NATURAL_LANGUAGE.value == "natural_language"
        assert ModeType.RECORD_REPLAY.value == "record_replay"
        assert ModeType.GUIDED.value == "guided"


class TestModeConfig:
    """Test the ModeConfig dataclass."""
    
    def test_create_config(self):
        """Test creating a mode config."""
        from llm_web_agent.modes.base import ModeConfig, ModeType
        config = ModeConfig(mode_type=ModeType.NATURAL_LANGUAGE)
        assert config.mode_type == ModeType.NATURAL_LANGUAGE
        assert config.options == {}
    
    def test_config_with_options(self):
        """Test config with custom options."""
        from llm_web_agent.modes.base import ModeConfig, ModeType
        config = ModeConfig(
            mode_type=ModeType.GUIDED,
            options={"max_steps": 10}
        )
        assert config.options["max_steps"] == 10


class TestModeResult:
    """Test the ModeResult dataclass."""
    
    def test_success_result(self):
        """Test creating a success result."""
        from llm_web_agent.modes.base import ModeResult
        result = ModeResult(success=True, steps_executed=5)
        assert result.success is True
        assert result.steps_executed == 5
        assert result.error is None
    
    def test_failure_result(self):
        """Test creating a failure result."""
        from llm_web_agent.modes.base import ModeResult
        result = ModeResult(success=False, error="Element not found")
        assert result.success is False
        assert result.error == "Element not found"


class TestRecording:
    """Test the Recording dataclass."""
    
    def test_create_recording(self):
        """Test creating a recording."""
        from llm_web_agent.modes.base import Recording
        recording = Recording(name="test_recording")
        assert recording.name == "test_recording"
        assert recording.actions == []
    
    def test_recording_to_dict(self):
        """Test converting recording to dict."""
        from llm_web_agent.modes.base import Recording
        recording = Recording(name="test", metadata={"url": "https://example.com"})
        data = recording.to_dict()
        assert data["name"] == "test"
        assert data["metadata"]["url"] == "https://example.com"
    
    def test_recording_from_dict(self):
        """Test creating recording from dict."""
        from llm_web_agent.modes.base import Recording
        data = {"name": "test", "actions": [], "metadata": {}}
        recording = Recording.from_dict(data)
        assert recording.name == "test"


class TestRecordedAction:
    """Test the RecordedAction dataclass."""
    
    def test_create_action(self):
        """Test creating a recorded action."""
        from llm_web_agent.modes.base import RecordedAction
        action = RecordedAction(
            action_type="click",
            selector="#submit",
            timestamp_ms=1000
        )
        assert action.action_type == "click"
        assert action.selector == "#submit"
    
    def test_action_to_dict(self):
        """Test converting action to dict."""
        from llm_web_agent.modes.base import RecordedAction
        action = RecordedAction(action_type="fill", selector="#email", value="test@test.com")
        data = action.to_dict()
        assert data["action_type"] == "fill"
        assert data["value"] == "test@test.com"


class TestNaturalLanguageMode:
    """Test the NaturalLanguageMode class."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        llm = MagicMock()
        llm.complete = AsyncMock()
        return llm
    
    @pytest.fixture
    def mode(self, mock_llm):
        """Create a NaturalLanguageMode instance."""
        from llm_web_agent.modes.natural_language import NaturalLanguageMode
        return NaturalLanguageMode(mock_llm)
    
    def test_mode_type(self, mode):
        """Test mode_type property."""
        from llm_web_agent.modes.base import ModeType
        assert mode.mode_type == ModeType.NATURAL_LANGUAGE
    
    def test_name(self, mode):
        """Test name property."""
        assert mode.name == "Natural Language"
    
    def test_description(self, mode):
        """Test description property."""
        assert "plain English" in mode.description
    
    @pytest.mark.asyncio
    async def test_execute_without_start(self, mode):
        """Test execute fails if not started."""
        result = await mode.execute("test task")
        assert result.success is False
        assert "not started" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_stop(self, mode):
        """Test stop method."""
        await mode.stop()
        # Should not raise


class TestGuidedMode:
    """Test the GuidedMode class."""
    
    @pytest.fixture
    def mode(self):
        """Create a GuidedMode instance."""
        from llm_web_agent.modes.guided import GuidedMode
        return GuidedMode()
    
    def test_mode_type(self, mode):
        """Test mode_type property."""
        from llm_web_agent.modes.base import ModeType
        assert mode.mode_type == ModeType.GUIDED
    
    def test_name(self, mode):
        """Test name property."""
        assert mode.name == "Guided"
    
    @pytest.mark.asyncio
    async def test_execute_without_start(self, mode):
        """Test execute fails if not started."""
        result = await mode.execute({"task": "test"})
        assert result.success is False


class TestRecordReplayMode:
    """Test the RecordReplayMode class."""
    
    @pytest.fixture
    def mode(self):
        """Create a RecordReplayMode instance."""
        from llm_web_agent.modes.record_replay import RecordReplayMode
        return RecordReplayMode()
    
    def test_mode_type(self, mode):
        """Test mode_type property."""
        from llm_web_agent.modes.base import ModeType
        assert mode.mode_type == ModeType.RECORD_REPLAY
    
    def test_name(self, mode):
        """Test name property."""
        assert mode.name == "Record & Replay"
    
    def test_description_mentions_record(self, mode):
        """Test description mentions recording functionality."""
        # Now that it's implemented, it should describe the feature
        assert "Record" in mode.description or "record" in mode.description.lower()
    
    @pytest.mark.asyncio
    async def test_execute_without_start_fails(self, mode):
        """Test execute fails if not started."""
        result = await mode.execute({"action": "record"})
        assert result.success is False
        assert "not started" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_execute_unknown_action(self, mode):
        """Test execute with unknown action."""
        from llm_web_agent.modes.base import ModeConfig, ModeType
        mock_page = MagicMock()
        await mode.start(mock_page, ModeConfig(mode_type=ModeType.RECORD_REPLAY))
        result = await mode.execute({"action": "invalid"})
        assert result.success is False
        assert "unknown action" in result.error.lower()


class TestLocatorHint:
    """Test the LocatorHint dataclass."""
    
    def test_create_hint(self):
        """Test creating a locator hint."""
        from llm_web_agent.modes.guided import LocatorHint
        hint = LocatorHint(name="username", selector="#email")
        assert hint.name == "username"
        assert hint.selector == "#email"
    
    def test_hint_to_dict(self):
        """Test converting hint to dict."""
        from llm_web_agent.modes.guided import LocatorHint
        hint = LocatorHint(name="submit", selector="button[type='submit']", role="button")
        data = hint.to_dict()
        assert data["name"] == "submit"
        assert data["role"] == "button"


class TestGuidedTaskInput:
    """Test the GuidedTaskInput dataclass."""
    
    def test_create_task_input(self):
        """Test creating a task input."""
        from llm_web_agent.modes.guided import GuidedTaskInput, LocatorHint
        hints = [LocatorHint(name="email", selector="#email")]
        task_input = GuidedTaskInput(
            task="Login to the app",
            hints=hints,
            data={"email": "test@test.com"}
        )
        assert task_input.task == "Login to the app"
        assert len(task_input.hints) == 1
    
    def test_get_hint(self):
        """Test get_hint method."""
        from llm_web_agent.modes.guided import GuidedTaskInput, LocatorHint
        hints = [
            LocatorHint(name="email", selector="#email"),
            LocatorHint(name="password", selector="#password"),
        ]
        task_input = GuidedTaskInput(task="Test", hints=hints)
        
        email_hint = task_input.get_hint("email")
        assert email_hint is not None
        assert email_hint.selector == "#email"
        
        unknown = task_input.get_hint("unknown")
        assert unknown is None
    
    def test_get_selector(self):
        """Test get_selector method."""
        from llm_web_agent.modes.guided import GuidedTaskInput, LocatorHint
        hints = [LocatorHint(name="submit", selector="#submit")]
        task_input = GuidedTaskInput(task="Test", hints=hints)
        
        selector = task_input.get_selector("submit")
        assert selector == "#submit"
        
        unknown = task_input.get_selector("unknown")
        assert unknown is None
