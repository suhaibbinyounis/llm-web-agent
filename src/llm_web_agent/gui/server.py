"""
GUI Server - FastAPI-based web server for agent control.

Provides:
- Static file serving for frontend assets
- Jinja2 template rendering
- API routes for agent control
- Health check endpoint
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Get the directory where this module is located
MODULE_DIR = Path(__file__).parent
TEMPLATES_DIR = MODULE_DIR / "templates"
STATIC_DIR = MODULE_DIR / "static"


def create_app(debug: bool = False) -> Any:
    """
    Create the FastAPI application.
    
    Args:
        debug: Enable debug mode
        
    Returns:
        FastAPI application instance
    """
    try:
        from fastapi import FastAPI, Request
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
        from fastapi.templating import Jinja2Templates
        from fastapi.responses import HTMLResponse
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
    
    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    
    # Templates
    templates = None
    if TEMPLATES_DIR.exists():
        templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    
    # Register API routes
    from llm_web_agent.gui.api import register_routes
    register_routes(app)
    
    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request):
        """Serve the main GUI page."""
        if templates:
            return templates.TemplateResponse(
                "index.html",
                {"request": request}
            )
        else:
            # Fallback if templates not found
            return HTMLResponse(
                content="""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>LLM Web Agent</title>
                    <style>
                        body { font-family: system-ui; background: #0f0f0f; color: #e5e5e5; 
                               display: flex; align-items: center; justify-content: center; 
                               height: 100vh; margin: 0; }
                        .error { text-align: center; }
                        code { background: #1a1a1a; padding: 0.5rem; border-radius: 4px; }
                    </style>
                </head>
                <body>
                    <div class="error">
                        <h1>⚠️ Templates not found</h1>
                        <p>The GUI templates directory is missing.</p>
                        <p>Expected at: <code>{}</code></p>
                    </div>
                </body>
                </html>
                """.format(TEMPLATES_DIR),
                status_code=500
            )
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        from llm_web_agent.gui.state import get_agent_state
        state = get_agent_state()
        return {
            "status": "ok",
            "agent_status": state.status.value,
        }
    
    return app


def run_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    debug: bool = False,
    open_browser: bool = True,
) -> None:
    """
    Run the web server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
        debug: Enable debug mode
        open_browser: Open browser automatically
    """
    try:
        import uvicorn
    except ImportError:
        raise ImportError(
            "Uvicorn not installed. Install with: pip install 'llm-web-agent[gui]'"
        )
    
    app = create_app(debug=debug)
    
    url = f"http://{host}:{port}"
    logger.info(f"Starting LLM Web Agent GUI at {url}")
    
    # Open browser if requested
    if open_browser:
        import webbrowser
        import threading
        
        def open_browser_delayed():
            import time
            time.sleep(1.5)  # Wait for server to start
            webbrowser.open(url)
        
        threading.Thread(target=open_browser_delayed, daemon=True).start()
    
    # Get local IP for LAN access
    local_ip = "your-ip"
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    
    # Print nice startup message
    print(f"""
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   🤖 LLM Web Agent GUI                                           ║
║                                                                  ║
║   Server running at: {url:<40} ║
║                                                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║   📡 Network Access:                                             ║
║      llm-web-agent gui --host 0.0.0.0                            ║
║      Then visit: http://{local_ip}:{port:<26} ║
║                                                                  ║
║   💻 CLI Mode (same features):                                   ║
║      llm-web-agent run-adaptive "your goal" --visible            ║
║      llm-web-agent run-file instructions.txt --report            ║
║                                                                  ║
║   📚 API Docs: {url}/docs{' ' * (41 - len(url))} ║
║                                                                  ║
║   Press Ctrl+C to stop                                           ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
""")
    
    uvicorn.run(app, host=host, port=port, log_level="info" if debug else "warning")

