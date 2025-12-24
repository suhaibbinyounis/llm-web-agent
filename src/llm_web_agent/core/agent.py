"""
Agent - Main orchestrator for web automation tasks.

This module contains the Agent class which coordinates between the LLM,
browser, and action execution to complete natural language tasks.

Example:
    >>> from llm_web_agent import Agent
    >>> agent = Agent()
    >>> result = await agent.run("Search for Python tutorials on Google")
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from llm_web_agent.config.settings import Settings
    from llm_web_agent.interfaces.browser import IBrowser, IPage
    from llm_web_agent.interfaces.llm import ILLMProvider
    from llm_web_agent.core.planner import Planner, TaskPlan
    from llm_web_agent.core.executor import Executor

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """
    Result of an agent task execution.
    
    Attributes:
        success: Whether the task completed successfully
        task: The original task description
        steps_executed: Number of steps executed
        final_url: The final URL after task completion
        final_screenshot: Screenshot of the final state
        extracted_data: Any data extracted during the task
        error: Error message if the task failed
        history: List of all steps and their results
        duration_seconds: Total execution time
    """
    success: bool
    task: str
    steps_executed: int = 0
    final_url: Optional[str] = None
    final_screenshot: Optional[bytes] = None
    extracted_data: Optional[Any] = None
    error: Optional[str] = None
    history: List[Dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0


class Agent:
    """
    Main agent class for executing web automation tasks.
    
    The Agent coordinates between:
    - Browser: For executing actions on web pages
    - LLM Provider: For understanding tasks and deciding actions
    - Planner: For breaking down tasks into steps
    - Executor: For executing individual steps with error handling
    
    Example:
        >>> from llm_web_agent import Agent
        >>> from llm_web_agent.config import load_config
        >>> 
        >>> settings = load_config()
        >>> agent = Agent(settings=settings)
        >>> 
        >>> async with agent:
        ...     result = await agent.run("Go to google.com and search for 'Python'")
        ...     print(f"Success: {result.success}")
    """
    
    def __init__(
        self,
        settings: Optional["Settings"] = None,
        browser: Optional["IBrowser"] = None,
        llm_provider: Optional["ILLMProvider"] = None,
    ):
        """
        Initialize the Agent.
        
        Args:
            settings: Configuration settings (loads defaults if None)
            browser: Browser instance (creates from settings if None)
            llm_provider: LLM provider instance (creates from settings if None)
        """
        self._settings = settings
        self._browser = browser
        self._llm_provider = llm_provider
        self._page: Optional["IPage"] = None
        self._planner: Optional["Planner"] = None
        self._executor: Optional["Executor"] = None
        self._is_initialized = False
    
    @property
    def settings(self) -> "Settings":
        """Get the current settings, loading defaults if needed."""
        if self._settings is None:
            from llm_web_agent.config import load_config
            self._settings = load_config()
        return self._settings
    
    @property
    def browser(self) -> "IBrowser":
        """Get the browser instance."""
        if self._browser is None:
            raise RuntimeError("Agent not initialized. Use 'async with agent:' or call 'await agent.initialize()'")
        return self._browser
    
    @property
    def llm_provider(self) -> "ILLMProvider":
        """Get the LLM provider instance."""
        if self._llm_provider is None:
            raise RuntimeError("Agent not initialized. Use 'async with agent:' or call 'await agent.initialize()'")
        return self._llm_provider
    
    @property
    def page(self) -> Optional["IPage"]:
        """Get the current page, if any."""
        return self._page
    
    async def initialize(self) -> None:
        """
        Initialize the agent's components.
        
        This creates and launches the browser, initializes the LLM provider,
        and sets up the planner and executor.
        """
        if self._is_initialized:
            return
        
        logger.info("Initializing agent...")
        
        # Create browser if not provided
        if self._browser is None:
            from llm_web_agent.registry import get_browser
            browser_class = get_browser(self.settings.browser.engine)
            self._browser = browser_class()
        
        # Launch browser
        await self._browser.launch(
            headless=self.settings.browser.headless,
        )
        
        # Create LLM provider if not provided
        if self._llm_provider is None:
            from llm_web_agent.registry import get_llm_provider
            provider_class = get_llm_provider(self.settings.llm.provider)
            self._llm_provider = provider_class(
                api_key=self.settings.llm.api_key.get_secret_value() if self.settings.llm.api_key else None,
                model=self.settings.llm.model,
            )
        
        # Create page
        self._page = await self._browser.new_page()
        
        # Initialize planner and executor
        from llm_web_agent.core.planner import Planner
        from llm_web_agent.core.executor import Executor
        
        self._planner = Planner(self._llm_provider, self.settings)
        self._executor = Executor(self.settings)
        
        self._is_initialized = True
        logger.info("Agent initialized successfully")
    
    async def close(self) -> None:
        """Close the agent and cleanup resources."""
        if self._page:
            await self._page.close()
            self._page = None
        
        if self._browser:
            await self._browser.close()
            self._browser = None
        
        self._is_initialized = False
        logger.info("Agent closed")
    
    async def __aenter__(self) -> "Agent":
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()
    
    async def run(self, task: str) -> AgentResult:
        """
        Execute a natural language task.
        
        Args:
            task: Natural language description of the task to perform
            
        Returns:
            AgentResult with the outcome of the task
            
        Example:
            >>> result = await agent.run("Go to github.com and search for 'llm-web-agent'")
        """
        # TODO: Implement task execution
        # 1. Use planner to break down the task
        # 2. Use executor to run each step
        # 3. Handle errors and retries
        # 4. Return result
        
        logger.info(f"Running task: {task}")
        
        return AgentResult(
            success=False,
            task=task,
            error="Agent execution not yet implemented",
        )
    
    async def step(self, instruction: str) -> Dict[str, Any]:
        """
        Execute a single step with a natural language instruction.
        
        This is useful for interactive/REPL-style usage.
        
        Args:
            instruction: Natural language instruction for this step
            
        Returns:
            Dictionary with step result
        """
        # TODO: Implement single step execution
        raise NotImplementedError("Single step execution not yet implemented")
    
    async def goto(self, url: str) -> None:
        """
        Navigate to a URL.
        
        Convenience method for direct navigation.
        
        Args:
            url: URL to navigate to
        """
        if self._page is None:
            raise RuntimeError("No page available. Initialize the agent first.")
        await self._page.goto(url)
    
    async def screenshot(self) -> bytes:
        """
        Take a screenshot of the current page.
        
        Returns:
            PNG screenshot bytes
        """
        if self._page is None:
            raise RuntimeError("No page available. Initialize the agent first.")
        return await self._page.screenshot()
