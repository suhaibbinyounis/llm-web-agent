
import pytest
from llm_web_agent.recorder.recorder import RecordingSession, RecordedAction, ActionType
from llm_web_agent.recorder.script_generator import PlaywrightScriptGenerator

def test_script_generator_parametrization():
    """Test that input values are extracted and parametrized."""
    actions = [
        RecordedAction(
            action_type=ActionType.NAVIGATE,
            timestamp_ms=0,
            url="http://example.com"
        ),
        RecordedAction(
            action_type=ActionType.FILL,
            timestamp_ms=1000,
            selector="#search",
            selectors=["#search", "input[name='q']"],
            value="hello world",
            element_info={"placeholder": "Search"}
        ),
        RecordedAction(
            action_type=ActionType.TYPE,
            timestamp_ms=2000,
            selector="#email",
            selectors=["#email"],
            value="user@example.com",
            element_info={"name": "email"}
        )
    ]
    
    session = RecordingSession(name="test_session", actions=actions)
    generator = PlaywrightScriptGenerator(async_mode=True)
    script = generator.generate(session)
    
    # Assert INPUT_DATA presence
    assert "INPUT_DATA = {" in script
    assert '"step_2_search": "hello world",' in script
    assert '"step_3_email": "user@example.com",' in script
    
    # Assert variable usage
    assert 'INPUT_DATA["step_2_search"]' in script
    assert 'INPUT_DATA["step_3_email"]' in script

def test_script_generator_smart_selectors():
    """Test that multiple selectors generate perform_action calls."""
    actions = [
        RecordedAction(
            action_type=ActionType.CLICK,
            timestamp_ms=1000,
            selector="#btn",
            selectors=["#btn", "text=Submit", "//button"]
        )
    ]
    
    session = RecordingSession(name="test_session", actions=actions)
    generator = PlaywrightScriptGenerator(async_mode=True)
    script = generator.generate(session)
    
    # Assert helper definition
    assert "async def perform_action" in script
    
    # Assert usage
    # perform_action(page, 'click', ["#btn", "text=Submit", "//button"])
    assert "perform_action(page, 'click', [" in script
    assert '"#btn"' in script
    assert '"text=Submit"' in script
    assert '"//button"' in script

def test_script_generator_single_selector_optimization():
    """Test that single selector still uses simple try/except logic."""
    actions = [
        RecordedAction(
            action_type=ActionType.CLICK,
            timestamp_ms=1000,
            selector="#simple",
            selectors=["#simple"]
        )
    ]
    
    session = RecordingSession(name="test_session", actions=actions)
    generator = PlaywrightScriptGenerator(async_mode=True)
    script = generator.generate(session)
    
    # Should NOT use perform_action for single selector
    assert "perform_action(page, 'click'" not in script
    assert 'page.locator("#simple").first.click' in script
