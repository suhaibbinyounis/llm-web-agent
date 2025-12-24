"""
Agent API Routes - Control the agent.
"""

from typing import Any, Optional
from dataclasses import dataclass

try:
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel
except ImportError:
    # Stub for when FastAPI is not installed
    APIRouter = object
    HTTPException = Exception
    BaseModel = object

router = APIRouter()


class RunTaskRequest(BaseModel):
    """Request to run a task."""
    task: str
    url: Optional[str] = None
    options: dict = {}


class TaskResponse(BaseModel):
    """Response from running a task."""
    run_id: str
    status: str
    message: str


@router.post("/run", response_model=TaskResponse)
async def run_task(request: RunTaskRequest) -> TaskResponse:
    """
    Run a task.
    
    Start the agent to execute a natural language task.
    """
    # TODO: Implement task execution
    raise HTTPException(
        status_code=501,
        detail="Task execution not yet implemented"
    )


@router.post("/stop")
async def stop_task() -> dict:
    """Stop the currently running task."""
    # TODO: Implement task stopping
    return {"status": "stopped", "message": "No task running"}


@router.get("/status")
async def get_status() -> dict:
    """Get current agent status."""
    return {
        "status": "idle",
        "current_task": None,
        "browser_connected": False,
    }


@router.post("/screenshot")
async def take_screenshot() -> dict:
    """Take a screenshot of the current page."""
    # TODO: Implement screenshot
    raise HTTPException(
        status_code=501,
        detail="Screenshot not yet implemented"
    )
