"""
Recorder Module - Record browser actions for replay.

This module provides functionality to record user actions in a browser
and generate replayable Playwright scripts.
"""

from llm_web_agent.recorder.recorder import BrowserRecorder, RecordingSession
from llm_web_agent.recorder.script_generator import PlaywrightScriptGenerator

__all__ = [
    "BrowserRecorder",
    "RecordingSession",
    "PlaywrightScriptGenerator",
]
