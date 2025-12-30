"""
Recordings API routes for managing saved recordings.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/recordings", tags=["recordings"])

# Storage file path
RECORDINGS_FILE = Path("recordings.json")


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
async def run_recording(recording_id: str):
    """Run a saved recording."""
    recordings = _load_recordings()
    
    for rec in recordings:
        if rec["id"] == recording_id:
            # In a real implementation, this would:
            # 1. Generate a script from the recording actions
            # 2. Execute it via the replay system
            # For now, return success
            return {"message": f"Recording '{rec['name']}' started", "recording": rec}
    
    raise HTTPException(status_code=404, detail="Recording not found")


@router.post("/start")
async def start_recording(data: NewRecordingRequest):
    """Start a new browser recording session."""
    # This would integrate with the BrowserRecorder
    # For now, return a placeholder response
    return {
        "message": f"Recording '{data.name}' session started",
        "url": data.url,
        "status": "recording"
    }
