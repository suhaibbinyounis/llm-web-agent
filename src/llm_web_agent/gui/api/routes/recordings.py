"""
Recordings API routes for managing saved recordings.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

# Storage file path
RECORDINGS_FILE = Path("recordings.json")

# Active recording session
_active_recording = None


def _load_recordings() -> list:
    """Load recordings from JSON file."""
    if not RECORDINGS_FILE.exists():
        return []
    try:
        data = json.loads(RECORDINGS_FILE.read_text())
        return data.get("recordings", [])
    except Exception:
        return []


def _save_recordings(recordings: list) -> None:
    """Save recordings to JSON file."""
    RECORDINGS_FILE.write_text(json.dumps({"recordings": recordings}, indent=2))


class NewRecordingRequest(BaseModel):
    name: str
    url: str


class UpdateRecordingRequest(BaseModel):
    name: Optional[str] = None


@router.get("")
async def list_recordings():
    """List all saved recordings."""
    recordings = _load_recordings()
    return {"recordings": recordings}


@router.get("/{recording_id}")
async def get_recording(recording_id: str):
    """Get a specific recording by ID."""
    recordings = _load_recordings()
    for rec in recordings:
        if rec["id"] == recording_id:
            return rec
    raise HTTPException(status_code=404, detail="Recording not found")


@router.post("")
async def create_recording(data: dict):
    """Create a new recording from recorded actions."""
    recordings = _load_recordings()
    
    recording = {
        "id": str(uuid.uuid4()),
        "name": data.get("name", "Untitled Recording"),
        "start_url": data.get("start_url", ""),
        "actions": data.get("actions", []),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    
    recordings.append(recording)
    _save_recordings(recordings)
    
    return {"id": recording["id"], "message": "Recording saved"}


@router.put("/{recording_id}")
async def update_recording(recording_id: str, data: UpdateRecordingRequest):
    """Update a recording (rename)."""
    recordings = _load_recordings()
    
    for rec in recordings:
        if rec["id"] == recording_id:
            if data.name:
                rec["name"] = data.name
            rec["updated_at"] = datetime.now().isoformat()
            _save_recordings(recordings)
            return {"message": "Recording updated"}
    
    raise HTTPException(status_code=404, detail="Recording not found")


@router.delete("/{recording_id}")
async def delete_recording(recording_id: str):
    """Delete a recording."""
    recordings = _load_recordings()
    
    for i, rec in enumerate(recordings):
        if rec["id"] == recording_id:
            recordings.pop(i)
            _save_recordings(recordings)
            return {"message": "Recording deleted"}
    
    raise HTTPException(status_code=404, detail="Recording not found")


@router.post("/{recording_id}/run")
async def run_recording(recording_id: str, background_tasks: BackgroundTasks):
    """Run a saved recording."""
    recordings = _load_recordings()
    
    for rec in recordings:
        if rec["id"] == recording_id:
            # Run the recording in background
            background_tasks.add_task(_run_recording_task, rec)
            return {"message": f"Recording '{rec['name']}' started", "recording_id": recording_id}
    
    raise HTTPException(status_code=404, detail="Recording not found")


async def _run_recording_task(recording: dict):
    """Background task to run a recording."""
    try:
        from llm_web_agent.recorder.script_generator import ScriptGenerator
        from llm_web_agent.recorder.recorder import RecordedAction, RecordingSession, ActionType
        
        # Convert stored actions to RecordedAction objects
        actions = []
        for action_data in recording.get("actions", []):
            action = RecordedAction(
                action_type=ActionType(action_data.get("action_type", "navigate")),
                timestamp_ms=action_data.get("timestamp_ms", 0),
                selector=action_data.get("selector"),
                value=action_data.get("value"),
                url=action_data.get("url"),
                key=action_data.get("key"),
                x=action_data.get("x"),
                y=action_data.get("y"),
                element_info=action_data.get("element_info", {}),
                selectors=action_data.get("selectors", []),
            )
            actions.append(action)
        
        # Create session and generate script
        session = RecordingSession(
            name=recording["name"],
            start_url=recording.get("start_url", ""),
            started_at=datetime.now(),
            actions=actions,
        )
        
        generator = ScriptGenerator(timing=True, comments=True)
        script = generator.generate(session)
        
        # Execute the script
        exec_globals = {}
        exec(script, exec_globals)
        await exec_globals.get("main", lambda: None)()
        
        logger.info(f"Recording '{recording['name']}' completed successfully")
    except Exception as e:
        logger.error(f"Failed to run recording: {e}")


@router.post("/start")
async def start_recording(data: NewRecordingRequest, background_tasks: BackgroundTasks):
    """Start a new browser recording session."""
    global _active_recording
    
    recording_id = str(uuid.uuid4())
    _active_recording = {
        "id": recording_id,
        "name": data.name,
        "url": data.url,
        "status": "starting"
    }
    
    # Start recording in background
    background_tasks.add_task(_start_recording_task, recording_id, data.name, data.url)
    
    return {
        "message": f"Recording '{data.name}' started - browser opening...",
        "recording_id": recording_id,
        "url": data.url,
        "status": "recording"
    }


async def _start_recording_task(recording_id: str, name: str, url: str):
    """Background task to run the browser recorder."""
    global _active_recording
    
    try:
        from llm_web_agent.recorder.recorder import BrowserRecorder
        import traceback
        
        logger.info(f"Starting recording: {name} at {url}")
        
        # BrowserRecorder only takes show_panel parameter
        recorder = BrowserRecorder(show_panel=True)
        
        session = await recorder.start(url)
        
        if session:
            # Convert session to storable format
            actions = []
            for action in session.actions:
                actions.append({
                    "action_type": action.action_type.value,
                    "timestamp_ms": action.timestamp_ms,
                    "selector": action.selector,
                    "value": action.value,
                    "url": action.url,
                    "key": action.key,
                    "x": action.x,
                    "y": action.y,
                    "element_info": action.element_info,
                    "selectors": action.selectors,
                })
            
            # Save to recordings
            recordings = _load_recordings()
            recordings.append({
                "id": recording_id,
                "name": name,
                "start_url": url,
                "actions": actions,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            })
            _save_recordings(recordings)
            
            logger.info(f"Recording '{name}' saved with {len(actions)} actions")
        
        _active_recording = None
        
    except Exception as e:
        logger.error(f"Recording failed: {e}")
        _active_recording = None


@router.get("/status")
async def get_recording_status():
    """Get the status of any active recording."""
    if _active_recording:
        return {"active": True, "recording": _active_recording}
    return {"active": False}

