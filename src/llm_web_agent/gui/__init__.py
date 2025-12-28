"""
GUI Module - Web-based control UI.

This module provides a FastAPI server and API routes for
controlling the agent through a web interface.

Usage:
    from llm_web_agent.gui import run_server
    run_server(port=8000)
    
Or via CLI:
    llm-web-agent gui --port 8000
"""

from llm_web_agent.gui.server import create_app, run_server
from llm_web_agent.gui.state import AgentState, AgentStatus, get_agent_state

__all__ = [
    "create_app",
    "run_server",
    "AgentState",
    "AgentStatus",
    "get_agent_state",
]
