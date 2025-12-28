"""
Tests for the actions module.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestActionsModuleImports:
    """Test action module imports."""
    
    def test_actions_module_imports(self):
        """Test that actions module can be imported."""
        from llm_web_agent import actions
        assert actions is not None
    
    def test_navigation_actions_import(self):
        """Test navigation actions import."""
        from llm_web_agent.actions import (
            NavigateAction, ReloadAction, GoBackAction, GoForwardAction
        )
        assert NavigateAction is not None
        assert ReloadAction is not None
        assert GoBackAction is not None
        assert GoForwardAction is not None
    
    def test_interaction_actions_import(self):
        """Test interaction actions import."""
        from llm_web_agent.actions import (
            ClickAction, FillAction, TypeAction, SelectAction, HoverAction
        )
        assert ClickAction is not None
        assert FillAction is not None
        assert TypeAction is not None
        assert SelectAction is not None
        assert HoverAction is not None


class TestNavigateAction:
    """Test the NavigateAction class."""
    
    def test_navigate_action_exists(self):
        """Test NavigateAction exists."""
        from llm_web_agent.actions import NavigateAction
        assert NavigateAction is not None
    
    @pytest.fixture
    def mock_page(self):
        """Create a mock page."""
        page = MagicMock()
        page.goto = AsyncMock()
        page.reload = AsyncMock()
        page.go_back = AsyncMock()
        page.go_forward = AsyncMock()
        return page


class TestClickAction:
    """Test the ClickAction class."""
    
    def test_click_action_exists(self):
        """Test ClickAction exists."""
        from llm_web_agent.actions import ClickAction
        assert ClickAction is not None


class TestFillAction:
    """Test the FillAction class."""
    
    def test_fill_action_exists(self):
        """Test FillAction exists."""
        from llm_web_agent.actions import FillAction
        assert FillAction is not None


class TestTypeAction:
    """Test the TypeAction class."""
    
    def test_type_action_exists(self):
        """Test TypeAction exists."""
        from llm_web_agent.actions import TypeAction
        assert TypeAction is not None


class TestSelectAction:
    """Test the SelectAction class."""
    
    def test_select_action_exists(self):
        """Test SelectAction exists."""
        from llm_web_agent.actions import SelectAction
        assert SelectAction is not None


class TestHoverAction:
    """Test the HoverAction class."""
    
    def test_hover_action_exists(self):
        """Test HoverAction exists."""
        from llm_web_agent.actions import HoverAction
        assert HoverAction is not None


class TestActionsRegistry:
    """Test action registration."""
    
    def test_actions_are_registered(self):
        """Test that actions are registered with the registry."""
        from llm_web_agent.registry import ComponentRegistry
        import llm_web_agent.actions  # Trigger registration
        
        actions = ComponentRegistry.list_actions()
        assert isinstance(actions, list)


class TestActionType:
    """Test ActionType enum."""
    
    def test_action_types_exist(self):
        """Test that action types exist."""
        from llm_web_agent.interfaces.action import ActionType
        assert ActionType.NAVIGATE
        assert ActionType.CLICK
        assert ActionType.FILL
        assert ActionType.SELECT
        assert ActionType.HOVER
