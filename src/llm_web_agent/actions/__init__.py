"""
Actions module - Browser action implementations.
"""

from llm_web_agent.actions.navigation import (
    NavigateAction,
    ReloadAction,
    GoBackAction,
    GoForwardAction,
)
from llm_web_agent.actions.interaction import (
    ClickAction,
    FillAction,
    TypeAction,
    SelectAction,
    HoverAction,
)

__all__ = [
    # Navigation
    "NavigateAction",
    "ReloadAction",
    "GoBackAction",
    "GoForwardAction",
    # Interaction
    "ClickAction",
    "FillAction",
    "TypeAction",
    "SelectAction",
    "HoverAction",
]


def _register_actions() -> None:
    """Register action implementations with the registry."""
    from llm_web_agent.registry import ComponentRegistry
    from llm_web_agent.interfaces.action import ActionType
    
    # Navigation actions
    ComponentRegistry.register_action(ActionType.NAVIGATE)(NavigateAction)
    ComponentRegistry.register_action(ActionType.RELOAD)(ReloadAction)
    ComponentRegistry.register_action(ActionType.GO_BACK)(GoBackAction)
    ComponentRegistry.register_action(ActionType.GO_FORWARD)(GoForwardAction)
    
    # Interaction actions
    ComponentRegistry.register_action(ActionType.CLICK)(ClickAction)
    ComponentRegistry.register_action(ActionType.FILL)(FillAction)
    ComponentRegistry.register_action(ActionType.TYPE)(TypeAction)
    ComponentRegistry.register_action(ActionType.SELECT)(SelectAction)
    ComponentRegistry.register_action(ActionType.HOVER)(HoverAction)


# Auto-register on import
_register_actions()
