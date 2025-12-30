"""
GUI API - API routes for agent control.
"""

from typing import Any


def register_routes(app: Any) -> None:
    """
    Register API routes with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    from llm_web_agent.gui.api.routes import agent, config, runs, recordings
    
    app.include_router(agent.router, prefix="/api/agent", tags=["agent"])
    app.include_router(config.router, prefix="/api/config", tags=["config"])
    app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
    app.include_router(recordings.router)
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "ok"}
