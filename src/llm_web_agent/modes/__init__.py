"""
Modes Module - Different interaction modes for the agent.

Supports 3 primary ways of using the agent:
1. Natural Language Mode - User describes task, agent executes
2. Record & Replay Mode - User performs actions, system records and replays
3. Guided Mode - Natural language + explicit locator hints
"""

from llm_web_agent.modes.base import IInteractionMode, ModeType
from llm_web_agent.modes.natural_language import NaturalLanguageMode
from llm_web_agent.modes.record_replay import RecordReplayMode
from llm_web_agent.modes.guided import GuidedMode

__all__ = [
    "IInteractionMode",
    "ModeType",
    "NaturalLanguageMode",
    "RecordReplayMode",
    "GuidedMode",
]
