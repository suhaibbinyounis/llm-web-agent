"""
Config API Routes - Configuration management.
"""

from typing import Any, Dict

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except ImportError:
    APIRouter = object
    HTTPException = Exception
    BaseModel = object

router = APIRouter()


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    settings: Dict[str, Any]


@router.get("/")
async def get_config() -> dict:
    """Get current configuration."""
    from llm_web_agent.config import load_config
    
    settings = load_config()
    return {
        "browser": {
            "engine": settings.browser.engine,
            "headless": settings.browser.headless,
            "timeout_ms": settings.browser.timeout_ms,
        },
        "llm": {
            "provider": settings.llm.provider,
            "model": settings.llm.model,
        },
        "agent": {
            "max_steps": settings.agent.max_steps,
            "verbose": settings.agent.verbose,
        },
    }


@router.patch("/")
async def update_config(update: ConfigUpdate) -> dict:
    """Update configuration."""
    # TODO: Implement config update
    raise HTTPException(
        status_code=501,
        detail="Config update not yet implemented"
    )


@router.get("/providers")
async def list_providers() -> dict:
    """List available LLM providers."""
    from llm_web_agent.registry import ComponentRegistry
    
    # Import to trigger registrations
    try:
        import llm_web_agent.llm
        import llm_web_agent.browsers
    except Exception:
        pass
    
    return {
        "llm_providers": ComponentRegistry.list_llm_providers(),
        "browsers": ComponentRegistry.list_browsers(),
    }
