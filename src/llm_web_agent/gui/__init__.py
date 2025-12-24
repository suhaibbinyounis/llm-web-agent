"""
GUI Module - Web-based control UI.

This module provides a FastAPI server and API routes for
controlling the agent through a web interface.
"""

from llm_web_agent.gui.server import create_app, run_server

__all__ = [
    "create_app",
    "run_server",
]
