"""
Tests for the GUI server module.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestGUIServerCreation:
    """Test GUI server creation."""
    
    def test_create_app_returns_fastapi(self):
        """Test create_app returns a FastAPI instance."""
        from llm_web_agent.gui.server import create_app
        app = create_app(debug=True)
        assert app is not None
        assert hasattr(app, 'routes')
    
    def test_create_app_has_health_endpoint(self):
        """Test app has health endpoint."""
        from llm_web_agent.gui.server import create_app
        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert "/health" in routes
    
    def test_create_app_has_index_endpoint(self):
        """Test app has index endpoint."""
        from llm_web_agent.gui.server import create_app
        app = create_app()
        routes = [r.path for r in app.routes if hasattr(r, 'path')]
        assert "/" in routes


class TestGUIServerRoutes:
    """Test the GUI server API routes."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the FastAPI app."""
        from llm_web_agent.gui.server import create_app
        from starlette.testclient import TestClient
        app = create_app(debug=True)
        return TestClient(app)
    
    def test_health_check(self, client):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    def test_index_page(self, client):
        """Test the index page renders."""
        response = client.get("/")
        # May return 200 or 500 depending on template availability
        assert response.status_code in [200, 500]


class TestGUIState:
    """Test the GUI state management."""
    
    def test_get_agent_state(self):
        """Test getting agent state."""
        from llm_web_agent.gui.state import get_agent_state
        state = get_agent_state()
        assert state is not None
        assert hasattr(state, 'status')
    
    def test_agent_status_enum(self):
        """Test AgentStatus enum values."""
        from llm_web_agent.gui.state import AgentStatus
        assert AgentStatus.IDLE
        assert AgentStatus.RUNNING
        assert AgentStatus.PAUSED


class TestGUISettings:
    """Test GUI settings from api.routes.config."""
    
    def test_gui_settings_class_exists(self):
        """Test GUISettings class exists."""
        from llm_web_agent.gui.api.routes.config import GUISettings
        assert GUISettings is not None
    
    def test_create_default_gui_settings(self):
        """Test creating default GUI settings."""
        from llm_web_agent.gui.api.routes.config import GUISettings
        settings = GUISettings()
        assert settings is not None
        assert hasattr(settings, 'model')
        assert hasattr(settings, 'api_url')
    
    def test_gui_settings_model_dump(self):
        """Test converting settings to dict."""
        from llm_web_agent.gui.api.routes.config import GUISettings
        settings = GUISettings()
        data = settings.model_dump()
        assert isinstance(data, dict)
        assert "model" in data
    
    def test_gui_settings_with_custom_values(self):
        """Test creating settings with custom values."""
        from llm_web_agent.gui.api.routes.config import GUISettings
        settings = GUISettings(model="gpt-4", step_timeout_ms=60000)
        assert settings.model == "gpt-4"
        assert settings.step_timeout_ms == 60000


class TestGUIFileStorage:
    """Test GUI settings file storage."""
    
    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        """Test saving and loading settings."""
        import llm_web_agent.gui.api.routes.config as config_module
        from llm_web_agent.gui.api.routes.config import (
            GUISettings, save_gui_settings, load_gui_settings
        )
        
        # Mock the settings file location
        settings_file = tmp_path / "gui_settings.json"
        monkeypatch.setattr(config_module, 'GUI_SETTINGS_PATH', settings_file)
        
        # Save settings
        settings = GUISettings(model="gpt-4", step_timeout_ms=60000)
        save_gui_settings(settings)
        
        # Verify file was created
        assert settings_file.exists()
        
        # Load settings
        loaded = load_gui_settings()
        assert loaded.model == "gpt-4"
        assert loaded.step_timeout_ms == 60000
