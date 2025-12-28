"""
Runs API Routes - Run history and management.

Provides endpoints for:
- Listing past runs
- Getting run details
- Exporting run reports
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import APIRouter, HTTPException, Query
    from fastapi.responses import FileResponse
    from pydantic import BaseModel, Field
except ImportError:
    APIRouter = object
    HTTPException = Exception
    Query = lambda *args, **kwargs: None
    FileResponse = object
    BaseModel = object
    Field = lambda **kwargs: None

from llm_web_agent.gui.state import get_agent_state

router = APIRouter()


class RunSummary(BaseModel):
    """Summary of a run."""
    run_id: str
    task: str
    status: str
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: float = 0
    steps_completed: int = 0
    total_steps: int = 0
    error: Optional[str] = None


class StepDetail(BaseModel):
    """Detail of a single step."""
    step_number: int
    action: str
    status: str
    message: str
    timestamp: float
    duration_ms: float = 0
    selector: Optional[str] = None


class RunDetail(BaseModel):
    """Full details of a run."""
    run_id: str
    task: str
    status: str
    started_at: str
    ended_at: Optional[str] = None
    duration_seconds: float = 0
    steps: List[StepDetail] = Field(default_factory=list)
    error: Optional[str] = None


@router.get("/", response_model=List[RunSummary])
async def list_runs(
    limit: int = Query(default=20, le=100, ge=1),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
) -> List[RunSummary]:
    """
    List recent runs.
    
    Returns runs from memory. For persistent history,
    run reports are saved to disk.
    """
    state = get_agent_state()
    
    # Filter by status if provided
    runs = state.run_history
    if status:
        runs = [r for r in runs if r.status.value == status]
    
    # Apply pagination
    paginated = runs[offset:offset + limit]
    
    summaries = []
    for run in paginated:
        duration = 0
        if run.ended_at and run.started_at:
            duration = (run.ended_at - run.started_at).total_seconds()
        
        completed = sum(1 for s in run.steps if s.status == "success")
        
        summaries.append(RunSummary(
            run_id=run.run_id,
            task=run.task[:100] + "..." if len(run.task) > 100 else run.task,
            status=run.status.value,
            started_at=run.started_at.isoformat(),
            ended_at=run.ended_at.isoformat() if run.ended_at else None,
            duration_seconds=duration,
            steps_completed=completed,
            total_steps=run.total_steps,
            error=run.error,
        ))
    
    return summaries


@router.get("/current")
async def get_current_run() -> Dict[str, Any]:
    """Get the current running task details."""
    state = get_agent_state()
    
    if not state.current_run:
        return {
            "running": False,
            "run": None,
        }
    
    return {
        "running": True,
        "run": state.current_run.to_dict(),
    }


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str) -> RunDetail:
    """Get details of a specific run."""
    state = get_agent_state()
    
    # Check current run
    if state.current_run and state.current_run.run_id == run_id:
        run = state.current_run
    else:
        # Search history
        run = next((r for r in state.run_history if r.run_id == run_id), None)
    
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found"
        )
    
    duration = 0
    if run.ended_at and run.started_at:
        duration = (run.ended_at - run.started_at).total_seconds()
    
    return RunDetail(
        run_id=run.run_id,
        task=run.task,
        status=run.status.value,
        started_at=run.started_at.isoformat(),
        ended_at=run.ended_at.isoformat() if run.ended_at else None,
        duration_seconds=duration,
        steps=[
            StepDetail(
                step_number=s.step_number,
                action=s.action,
                status=s.status,
                message=s.message,
                timestamp=s.timestamp,
                duration_ms=s.duration_ms,
                selector=s.selector,
            )
            for s in run.steps
        ],
        error=run.error,
    )


@router.get("/{run_id}/logs")
async def get_run_logs(run_id: str) -> Dict[str, Any]:
    """Get logs for a run as plain text."""
    state = get_agent_state()
    
    # Find run
    run = None
    if state.current_run and state.current_run.run_id == run_id:
        run = state.current_run
    else:
        run = next((r for r in state.run_history if r.run_id == run_id), None)
    
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found"
        )
    
    # Format logs
    logs = []
    logs.append(f"Run ID: {run.run_id}")
    logs.append(f"Task: {run.task}")
    logs.append(f"Status: {run.status.value}")
    logs.append(f"Started: {run.started_at.isoformat()}")
    if run.ended_at:
        logs.append(f"Ended: {run.ended_at.isoformat()}")
    logs.append("")
    logs.append("Steps:")
    
    for step in run.steps:
        status_icon = "✓" if step.status == "success" else "✗" if step.status == "failed" else "•"
        logs.append(f"  {status_icon} Step {step.step_number}: {step.action}")
        logs.append(f"    {step.message}")
        if step.selector:
            logs.append(f"    Selector: {step.selector}")
        if step.duration_ms:
            logs.append(f"    Duration: {step.duration_ms:.0f}ms")
    
    if run.error:
        logs.append("")
        logs.append(f"Error: {run.error}")
    
    return {
        "run_id": run_id,
        "logs": "\n".join(logs),
    }


@router.get("/{run_id}/screenshots")
async def get_run_screenshots(run_id: str) -> Dict[str, Any]:
    """Get screenshots for a run."""
    state = get_agent_state()
    
    # Find run
    run = None
    if state.current_run and state.current_run.run_id == run_id:
        run = state.current_run
    else:
        run = next((r for r in state.run_history if r.run_id == run_id), None)
    
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found"
        )
    
    # Collect screenshots from steps
    screenshots = []
    for step in run.steps:
        if step.screenshot:
            screenshots.append({
                "step_number": step.step_number,
                "action": step.action,
                "screenshot": step.screenshot,
            })
    
    return {
        "run_id": run_id,
        "count": len(screenshots),
        "screenshots": screenshots,
    }


@router.delete("/{run_id}")
async def delete_run(run_id: str) -> Dict[str, str]:
    """Delete a run from history."""
    state = get_agent_state()
    
    # Can't delete current run
    if state.current_run and state.current_run.run_id == run_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the current running task"
        )
    
    # Find and remove from history
    original_len = len(state.run_history)
    state._run_history = [r for r in state.run_history if r.run_id != run_id]
    
    if len(state.run_history) == original_len:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found"
        )
    
    return {"status": "deleted", "run_id": run_id}


@router.delete("/")
async def clear_history() -> Dict[str, Any]:
    """Clear all run history."""
    state = get_agent_state()
    
    count = len(state.run_history)
    state._run_history = []
    
    return {"status": "cleared", "deleted_count": count}


@router.get("/{run_id}/export")
async def export_run(
    run_id: str,
    format: str = Query(default="json", pattern="^(json|md|html)$"),
) -> Dict[str, Any]:
    """Export a run report in the specified format."""
    state = get_agent_state()
    
    # Find run
    run = None
    if state.current_run and state.current_run.run_id == run_id:
        run = state.current_run
    else:
        run = next((r for r in state.run_history if r.run_id == run_id), None)
    
    if not run:
        raise HTTPException(
            status_code=404,
            detail=f"Run {run_id} not found"
        )
    
    run_dict = run.to_dict()
    
    if format == "json":
        return {
            "format": "json",
            "content": run_dict,
        }
    
    elif format == "md":
        # Generate markdown report
        md_lines = [
            f"# Run Report: {run_id}",
            "",
            f"**Task:** {run.task}",
            f"**Status:** {run.status.value}",
            f"**Started:** {run.started_at.isoformat()}",
        ]
        if run.ended_at:
            md_lines.append(f"**Ended:** {run.ended_at.isoformat()}")
        md_lines.extend([
            "",
            "## Steps",
            "",
        ])
        
        for step in run.steps:
            status = "✅" if step.status == "success" else "❌" if step.status == "failed" else "⏳"
            md_lines.append(f"### Step {step.step_number}: {step.action} {status}")
            md_lines.append(f"{step.message}")
            if step.duration_ms:
                md_lines.append(f"*Duration: {step.duration_ms:.0f}ms*")
            md_lines.append("")
        
        if run.error:
            md_lines.extend([
                "## Error",
                "",
                f"```\n{run.error}\n```",
            ])
        
        return {
            "format": "md",
            "content": "\n".join(md_lines),
        }
    
    elif format == "html":
        # Generate simple HTML report
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Run Report: {run_id}</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 0 1rem; }}
        .success {{ color: #22c55e; }}
        .failed {{ color: #ef4444; }}
        .step {{ padding: 1rem; margin: 0.5rem 0; background: #f5f5f5; border-radius: 8px; }}
    </style>
</head>
<body>
    <h1>Run Report: {run_id}</h1>
    <p><strong>Task:</strong> {run.task}</p>
    <p><strong>Status:</strong> <span class="{run.status.value}">{run.status.value}</span></p>
    <p><strong>Started:</strong> {run.started_at.isoformat()}</p>
    <h2>Steps</h2>
"""
        for step in run.steps:
            status_class = "success" if step.status == "success" else "failed"
            html += f"""
    <div class="step">
        <strong>Step {step.step_number}: {step.action}</strong>
        <span class="{status_class}">[{step.status}]</span>
        <p>{step.message}</p>
    </div>
"""
        html += "</body></html>"
        
        return {
            "format": "html",
            "content": html,
        }
    
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported format: {format}"
    )
