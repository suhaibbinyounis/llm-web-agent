"""
Component Registry - Central registry for pluggable components.

This module provides a registry pattern for dynamically registering
browser engines, LLM providers, actions, and other pluggable components.

Example:
    >>> from llm_web_agent.registry import register_browser, get_browser
    >>> 
    >>> @register_browser("playwright")
    >>> class PlaywrightBrowser(IBrowser):
    ...     pass
    >>> 
    >>> browser_class = get_browser("playwright")
"""

from typing import Callable, Dict, List, Optional, Type, TypeVar, Any
from llm_web_agent.interfaces.browser import IBrowser
from llm_web_agent.interfaces.llm import ILLMProvider
from llm_web_agent.interfaces.action import IAction, ActionType
from llm_web_agent.interfaces.extractor import IDataExtractor


T = TypeVar("T")


class ComponentRegistry:
    """
    Central registry for pluggable components.
    
    This class maintains registries for each type of pluggable component
    and provides methods for registration, discovery, and instantiation.
    
    Components are registered by name and can be retrieved for instantiation.
    This enables a plugin architecture where new implementations can be
    added without modifying core code.
    """
    
    # Type registries
    _browsers: Dict[str, Type[IBrowser]] = {}
    _llm_providers: Dict[str, Type[ILLMProvider]] = {}
    _actions: Dict[ActionType, Type[IAction]] = {}
    _extractors: Dict[str, Type[IDataExtractor]] = {}
    
    # Factory functions for lazy loading
    _browser_factories: Dict[str, Callable[[], Type[IBrowser]]] = {}
    _llm_factories: Dict[str, Callable[[], Type[ILLMProvider]]] = {}
    
    # ==================== Browser Registration ====================
    
    @classmethod
    def register_browser(cls, name: str) -> Callable[[Type[IBrowser]], Type[IBrowser]]:
        """
        Decorator to register a browser implementation.
        
        Args:
            name: Unique name for the browser (e.g., 'playwright', 'selenium')
            
        Returns:
            Decorator function
            
        Example:
            >>> @ComponentRegistry.register_browser("playwright")
            >>> class PlaywrightBrowser(IBrowser):
            ...     pass
        """
        def decorator(browser_class: Type[IBrowser]) -> Type[IBrowser]:
            if name in cls._browsers:
                raise ValueError(f"Browser '{name}' is already registered")
            cls._browsers[name] = browser_class
            return browser_class
        return decorator
    
    @classmethod
    def register_browser_factory(
        cls,
        name: str,
        factory: Callable[[], Type[IBrowser]],
    ) -> None:
        """
        Register a factory function for lazy-loading a browser.
        
        Useful for avoiding import overhead when the browser might not be used.
        """
        cls._browser_factories[name] = factory
    
    @classmethod
    def get_browser(cls, name: str) -> Type[IBrowser]:
        """
        Get a registered browser class by name.
        
        Args:
            name: The registered name of the browser
            
        Returns:
            The browser class
            
        Raises:
            ValueError: If the browser is not registered
        """
        # Check direct registrations first
        if name in cls._browsers:
            return cls._browsers[name]
        
        # Try factory (lazy loading)
        if name in cls._browser_factories:
            browser_class = cls._browser_factories[name]()
            cls._browsers[name] = browser_class
            return browser_class
        
        available = list(cls._browsers.keys()) + list(cls._browser_factories.keys())
        raise ValueError(
            f"Unknown browser: '{name}'. Available browsers: {available}"
        )
    
    @classmethod
    def list_browsers(cls) -> List[str]:
        """List all registered browser names."""
        return list(set(cls._browsers.keys()) | set(cls._browser_factories.keys()))
    
    # ==================== LLM Provider Registration ====================
    
    @classmethod
    def register_llm(cls, name: str) -> Callable[[Type[ILLMProvider]], Type[ILLMProvider]]:
        """
        Decorator to register an LLM provider implementation.
        
        Args:
            name: Unique name for the provider (e.g., 'openai', 'anthropic')
            
        Returns:
            Decorator function
        """
        def decorator(provider_class: Type[ILLMProvider]) -> Type[ILLMProvider]:
            if name in cls._llm_providers:
                raise ValueError(f"LLM provider '{name}' is already registered")
            cls._llm_providers[name] = provider_class
            return provider_class
        return decorator
    
    @classmethod
    def register_llm_factory(
        cls,
        name: str,
        factory: Callable[[], Type[ILLMProvider]],
    ) -> None:
        """Register a factory function for lazy-loading an LLM provider."""
        cls._llm_factories[name] = factory
    
    @classmethod
    def get_llm_provider(cls, name: str) -> Type[ILLMProvider]:
        """
        Get a registered LLM provider class by name.
        
        Args:
            name: The registered name of the provider
            
        Returns:
            The provider class
            
        Raises:
            ValueError: If the provider is not registered
        """
        if name in cls._llm_providers:
            return cls._llm_providers[name]
        
        if name in cls._llm_factories:
            provider_class = cls._llm_factories[name]()
            cls._llm_providers[name] = provider_class
            return provider_class
        
        available = list(cls._llm_providers.keys()) + list(cls._llm_factories.keys())
        raise ValueError(
            f"Unknown LLM provider: '{name}'. Available providers: {available}"
        )
    
    @classmethod
    def list_llm_providers(cls) -> List[str]:
        """List all registered LLM provider names."""
        return list(set(cls._llm_providers.keys()) | set(cls._llm_factories.keys()))
    
    # ==================== Action Registration ====================
    
    @classmethod
    def register_action(
        cls,
        action_type: ActionType,
    ) -> Callable[[Type[IAction]], Type[IAction]]:
        """
        Decorator to register an action implementation.
        
        Args:
            action_type: The ActionType this action handles
            
        Returns:
            Decorator function
        """
        def decorator(action_class: Type[IAction]) -> Type[IAction]:
            if action_type in cls._actions:
                raise ValueError(f"Action '{action_type.value}' is already registered")
            cls._actions[action_type] = action_class
            return action_class
        return decorator
    
    @classmethod
    def get_action(cls, action_type: ActionType) -> Type[IAction]:
        """
        Get a registered action class by type.
        
        Args:
            action_type: The ActionType to get
            
        Returns:
            The action class
        """
        if action_type not in cls._actions:
            raise ValueError(
                f"Unknown action type: '{action_type.value}'. "
                f"Available actions: {[a.value for a in cls._actions.keys()]}"
            )
        return cls._actions[action_type]
    
    @classmethod
    def list_actions(cls) -> List[ActionType]:
        """List all registered action types."""
        return list(cls._actions.keys())
    
    # ==================== Extractor Registration ====================
    
    @classmethod
    def register_extractor(
        cls,
        name: str,
    ) -> Callable[[Type[IDataExtractor]], Type[IDataExtractor]]:
        """
        Decorator to register a data extractor implementation.
        
        Args:
            name: Unique name for the extractor
            
        Returns:
            Decorator function
        """
        def decorator(extractor_class: Type[IDataExtractor]) -> Type[IDataExtractor]:
            if name in cls._extractors:
                raise ValueError(f"Extractor '{name}' is already registered")
            cls._extractors[name] = extractor_class
            return extractor_class
        return decorator
    
    @classmethod
    def get_extractor(cls, name: str) -> Type[IDataExtractor]:
        """Get a registered extractor class by name."""
        if name not in cls._extractors:
            raise ValueError(
                f"Unknown extractor: '{name}'. Available: {list(cls._extractors.keys())}"
            )
        return cls._extractors[name]
    
    # ==================== Utility Methods ====================
    
    @classmethod
    def clear_all(cls) -> None:
        """Clear all registries. Useful for testing."""
        cls._browsers.clear()
        cls._llm_providers.clear()
        cls._actions.clear()
        cls._extractors.clear()
        cls._browser_factories.clear()
        cls._llm_factories.clear()


# ==================== Convenience Decorators ====================

def register_browser(name: str) -> Callable[[Type[IBrowser]], Type[IBrowser]]:
    """Convenience decorator for registering browsers."""
    return ComponentRegistry.register_browser(name)


def register_llm(name: str) -> Callable[[Type[ILLMProvider]], Type[ILLMProvider]]:
    """Convenience decorator for registering LLM providers."""
    return ComponentRegistry.register_llm(name)


def register_action(
    action_type: ActionType,
) -> Callable[[Type[IAction]], Type[IAction]]:
    """Convenience decorator for registering actions."""
    return ComponentRegistry.register_action(action_type)


def register_extractor(name: str) -> Callable[[Type[IDataExtractor]], Type[IDataExtractor]]:
    """Convenience decorator for registering extractors."""
    return ComponentRegistry.register_extractor(name)


# ==================== Convenience Getters ====================

def get_browser(name: str) -> Type[IBrowser]:
    """Get a browser class by name."""
    return ComponentRegistry.get_browser(name)


def get_llm_provider(name: str) -> Type[ILLMProvider]:
    """Get an LLM provider class by name."""
    return ComponentRegistry.get_llm_provider(name)


def get_action(action_type: ActionType) -> Type[IAction]:
    """Get an action class by type."""
    return ComponentRegistry.get_action(action_type)
