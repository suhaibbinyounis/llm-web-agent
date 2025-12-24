"""
Action Mapper - Map intents to browser actions.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Type
from llm_web_agent.interfaces.action import IAction, ActionType
from llm_web_agent.intelligence.nlp.intent_parser import IntentType


@dataclass
class ActionMapping:
    """
    Mapping from intent to action.
    
    Attributes:
        intent_type: Source intent type
        action_type: Target action type
        requires_target: Whether action requires a target element
        requires_value: Whether action requires a value
    """
    intent_type: IntentType
    action_type: ActionType
    requires_target: bool = False
    requires_value: bool = False


class ActionMapper:
    """
    Map intents to executable browser actions.
    
    Provides a translation layer between high-level user intents
    and low-level browser actions.
    
    Example:
        >>> mapper = ActionMapper()
        >>> action = mapper.map_intent(intent)
    """
    
    # Default mappings from intents to actions
    MAPPINGS: Dict[IntentType, ActionMapping] = {
        IntentType.NAVIGATE: ActionMapping(
            IntentType.NAVIGATE, ActionType.NAVIGATE, 
            requires_target=False, requires_value=True
        ),
        IntentType.CLICK: ActionMapping(
            IntentType.CLICK, ActionType.CLICK,
            requires_target=True, requires_value=False
        ),
        IntentType.FILL_FORM: ActionMapping(
            IntentType.FILL_FORM, ActionType.FILL,
            requires_target=True, requires_value=True
        ),
        IntentType.SEARCH: ActionMapping(
            IntentType.SEARCH, ActionType.FILL,
            requires_target=True, requires_value=True
        ),
        IntentType.SCROLL: ActionMapping(
            IntentType.SCROLL, ActionType.SCROLL,
            requires_target=False, requires_value=False
        ),
        IntentType.SCREENSHOT: ActionMapping(
            IntentType.SCREENSHOT, ActionType.SCREENSHOT,
            requires_target=False, requires_value=False
        ),
    }
    
    def __init__(self):
        """Initialize the mapper."""
        self._mappings = self.MAPPINGS.copy()
    
    def get_mapping(self, intent_type: IntentType) -> Optional[ActionMapping]:
        """
        Get the action mapping for an intent type.
        
        Args:
            intent_type: Intent type to map
            
        Returns:
            Action mapping or None if not found
        """
        return self._mappings.get(intent_type)
    
    def get_action_type(self, intent_type: IntentType) -> Optional[ActionType]:
        """
        Get the action type for an intent.
        
        Args:
            intent_type: Intent type
            
        Returns:
            Corresponding action type
        """
        mapping = self.get_mapping(intent_type)
        return mapping.action_type if mapping else None
    
    def register_mapping(self, mapping: ActionMapping) -> None:
        """
        Register a custom intent-to-action mapping.
        
        Args:
            mapping: The mapping to register
        """
        self._mappings[mapping.intent_type] = mapping
    
    def can_map(self, intent_type: IntentType) -> bool:
        """Check if an intent type can be mapped."""
        return intent_type in self._mappings
