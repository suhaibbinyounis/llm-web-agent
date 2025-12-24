"""
GUI Server - FastAPI-based web server for agent control.
"""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def create_app(debug: bool = False) -> Any:
    """
    Create the FastAPI application.
    
    Args:
        debug: Enable debug mode
        
    Returns:
        FastAPI application instance
    """
    try:
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
    except ImportError:
        raise ImportError(
            "FastAPI not installed. Install with: pip install 'llm-web-agent[gui]'"
        )
    
    app = FastAPI(
        title="LLM Web Agent",
        description="Web automation agent powered by LLMs",
        version="0.1.0",
        debug=debug,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routes
    from llm_web_agent.gui.api import register_routes
    register_routes(app)
    
    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    debug: bool = False,
) -> None:
    """
    Run the web server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
    """
    try:
        import uvicorn
    except ImportError:
        raise ImportError(
            "Uvicorn not installed. Install with: pip install 'llm-web-agent[gui]'"
        )
    
    app = create_app(debug=debug)
    
    logger.info(f"Starting server at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
