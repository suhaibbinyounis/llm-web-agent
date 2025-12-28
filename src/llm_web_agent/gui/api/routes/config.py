"""
Config API Routes - Configuration management.

Provides endpoints for:
- Reading and updating configuration
- Listing available providers
- Uploading instruction files
- GUI settings persistence
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import logging

try:
    from fastapi import APIRouter, HTTPException, UploadFile, File
    from pydantic import BaseModel, Field
except ImportError:
    APIRouter = object
    HTTPException = Exception
    BaseModel = object
    UploadFile = object
    File = lambda: None
    Field = lambda **kwargs: None

logger = logging.getLogger(__name__)
router = APIRouter()

# GUI Settings file path
GUI_SETTINGS_PATH = Path.home() / ".llm-web-agent" / "gui_settings.json"


class GUISettings(BaseModel):
    """GUI-specific settings that persist across sessions."""
    # Mode
    engine_mode: str = Field("instructions", description="instructions | goal")
    
    # LLM
    model: str = Field("gpt-4.1", description="LLM model to use")
    api_url: str = Field("http://127.0.0.1:3030", description="API URL")
    use_websocket: bool = Field(True, description="Use WebSocket for LLM")
    
    # Browser
    visible_browser: bool = Field(True, description="Show browser window")
    browser_channel: Optional[str] = Field("chrome", description="chrome | msedge | chromium")
    
    # Execution
    max_steps: int = Field(50, description="Maximum steps per run")
    step_timeout_ms: int = Field(30000, description="Timeout per step in ms")
    retry_attempts: int = Field(3, description="Retry attempts on failure")
    
    # Reports
    generate_report: bool = Field(True, description="Generate execution reports")
    report_dir: str = Field("./reports", description="Report output directory")
    report_formats: List[str] = Field(["json", "md", "html"], description="Report formats")


def load_gui_settings() -> GUISettings:
    """Load GUI settings from file, or return defaults."""
    if GUI_SETTINGS_PATH.exists():
        try:
            with open(GUI_SETTINGS_PATH, "r") as f:
                data = json.load(f)
            return GUISettings(**data)
        except Exception as e:
            logger.warning(f"Failed to load GUI settings: {e}")
    return GUISettings()


def save_gui_settings(settings: GUISettings) -> None:
    """Save GUI settings to file."""
    GUI_SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(GUI_SETTINGS_PATH, "w") as f:
        json.dump(settings.model_dump(), f, indent=2)
    logger.info(f"GUI settings saved to {GUI_SETTINGS_PATH}")


class BrowserConfig(BaseModel):
    """Browser configuration."""
    headless: bool = True
    timeout_ms: int = 30000
    viewport_width: int = 1280
    viewport_height: int = 720
    browser_channel: Optional[str] = None
    show_overlay: bool = False
    highlight_elements: bool = False


class LLMConfig(BaseModel):
    """LLM configuration."""
    provider: str = "openai"
    model: str = "gpt-4o"
    base_url: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 4096
    use_vision: bool = True


class AgentConfig(BaseModel):
    """Agent configuration."""
    max_steps: int = 20
    retry_attempts: int = 3
    step_delay_ms: int = 500
    screenshot_on_error: bool = True
    verbose: bool = False


class FullConfig(BaseModel):
    """Complete configuration."""
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    browser: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = None
    agent: Optional[Dict[str, Any]] = None


class InstructionFile(BaseModel):
    """Instruction file info."""
    name: str
    path: str
    lines: int


@router.get("/", response_model=FullConfig)
async def get_config() -> FullConfig:
    """Get current configuration."""
    from llm_web_agent.config import load_config
    
    try:
        settings = load_config()
        return FullConfig(
            browser=BrowserConfig(
                headless=settings.browser.headless,
                timeout_ms=settings.browser.timeout_ms,
                viewport_width=settings.browser.viewport_width,
                viewport_height=settings.browser.viewport_height,
                browser_channel=settings.browser.browser_channel,
                show_overlay=settings.browser.show_overlay,
                highlight_elements=settings.browser.highlight_elements,
            ),
            llm=LLMConfig(
                provider=settings.llm.provider,
                model=settings.llm.model,
                base_url=settings.llm.base_url,
                temperature=settings.llm.temperature,
                max_tokens=settings.llm.max_tokens,
                use_vision=settings.llm.use_vision,
            ),
            agent=AgentConfig(
                max_steps=settings.agent.max_steps,
                retry_attempts=settings.agent.retry_attempts,
                step_delay_ms=settings.agent.step_delay_ms,
                screenshot_on_error=settings.agent.screenshot_on_error,
                verbose=settings.agent.verbose,
            ),
        )
    except Exception as e:
        # Return defaults if config can't be loaded
        return FullConfig()


@router.patch("/")
async def update_config(update: ConfigUpdate) -> Dict[str, Any]:
    """
    Update configuration.
    
    Updates are applied to the current session.
    To persist, use /env endpoint.
    """
    from llm_web_agent.gui.state import get_agent_state
    
    state = get_agent_state()
    
    # Merge updates into state config
    if update.browser:
        state._config.setdefault("browser", {}).update(update.browser)
    if update.llm:
        state._config.setdefault("llm", {}).update(update.llm)
    if update.agent:
        state._config.setdefault("agent", {}).update(update.agent)
    
    return {
        "status": "updated",
        "config": state._config,
    }


@router.get("/providers")
async def list_providers() -> Dict[str, List[str]]:
    """List available LLM providers and browser engines."""
    return {
        "llm_providers": ["openai", "anthropic", "copilot", "custom"],
        "browsers": ["chromium", "chrome", "msedge", "firefox"],
        "models": [
            "gpt-4o",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
    }


@router.get("/instructions", response_model=List[InstructionFile])
async def list_instruction_files() -> List[InstructionFile]:
    """List available instruction files."""
    # Look in standard locations
    instruction_dirs = [
        Path("instructions"),
        Path.home() / ".llm-web-agent" / "instructions",
    ]
    
    files = []
    for dir_path in instruction_dirs:
        if dir_path.exists() and dir_path.is_dir():
            for file_path in dir_path.glob("*.txt"):
                try:
                    with open(file_path, "r") as f:
                        line_count = len(f.readlines())
                    files.append(InstructionFile(
                        name=file_path.name,
                        path=str(file_path.absolute()),
                        lines=line_count,
                    ))
                except Exception:
                    pass
    
    return files


@router.post("/instructions/upload")
async def upload_instruction_file(
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    """Upload an instruction file."""
    # Create instructions directory if it doesn't exist
    instructions_dir = Path("instructions")
    instructions_dir.mkdir(exist_ok=True)
    
    # Save file
    file_path = instructions_dir / file.filename
    
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
        
        # Count lines
        lines = content.decode("utf-8").splitlines()
        
        return {
            "status": "uploaded",
            "file": InstructionFile(
                name=file.filename,
                path=str(file_path.absolute()),
                lines=len(lines),
            ).model_dump(),
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload file: {e}"
        )


@router.get("/instructions/{filename}")
async def get_instruction_file(filename: str) -> Dict[str, Any]:
    """Get contents of an instruction file."""
    # Search in standard locations
    instruction_dirs = [
        Path("instructions"),
        Path.home() / ".llm-web-agent" / "instructions",
    ]
    
    for dir_path in instruction_dirs:
        file_path = dir_path / filename
        if file_path.exists():
            try:
                with open(file_path, "r") as f:
                    content = f.read()
                return {
                    "name": filename,
                    "path": str(file_path.absolute()),
                    "content": content,
                    "lines": content.splitlines(),
                }
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to read file: {e}"
                )
    
    raise HTTPException(
        status_code=404,
        detail=f"Instruction file not found: {filename}"
    )


@router.get("/env")
async def get_env_vars() -> Dict[str, Any]:
    """Get relevant environment variables (masked)."""
    env_vars = {}
    
    # List of relevant env vars
    relevant = [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "COPILOT_API_URL",
        "LLM_WEB_AGENT__LLM__PROVIDER",
        "LLM_WEB_AGENT__LLM__MODEL",
        "LLM_WEB_AGENT__BROWSER__HEADLESS",
    ]
    
    for var in relevant:
        value = os.environ.get(var, "")
        if value:
            # Mask API keys
            if "KEY" in var or "SECRET" in var:
                if len(value) > 8:
                    env_vars[var] = value[:4] + "****" + value[-4:]
                else:
                    env_vars[var] = "****"
            else:
                env_vars[var] = value
        else:
            env_vars[var] = None
    
    return {
        "variables": env_vars,
        "env_file_exists": Path(".env").exists(),
    }


@router.patch("/env")
async def update_env_var(
    updates: Dict[str, str],
) -> Dict[str, str]:
    """
    Update environment variables.
    
    This updates the current process environment.
    Does NOT modify .env file.
    """
    for key, value in updates.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    
    return {"status": "updated", "count": len(updates)}


# ============================================
# GUI Settings Endpoints
# ============================================

@router.get("/gui", response_model=GUISettings)
async def get_gui_settings() -> GUISettings:
    """
    Get GUI settings.
    
    Settings are persisted to ~/.llm-web-agent/gui_settings.json
    and survive server restarts.
    """
    return load_gui_settings()


@router.post("/gui", response_model=GUISettings)
async def save_gui_settings_endpoint(settings: GUISettings) -> GUISettings:
    """
    Save GUI settings.
    
    Settings are persisted to ~/.llm-web-agent/gui_settings.json
    and survive server restarts.
    """
    save_gui_settings(settings)
    return settings


@router.patch("/gui", response_model=GUISettings)
async def update_gui_settings(updates: Dict[str, Any]) -> GUISettings:
    """
    Partially update GUI settings.
    
    Only provided fields are updated, others remain unchanged.
    """
    current = load_gui_settings()
    current_dict = current.model_dump()
    current_dict.update(updates)
    updated = GUISettings(**current_dict)
    save_gui_settings(updated)
    return updated

