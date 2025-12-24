"""
Natural Language Mode - Execute tasks from natural language descriptions.

This is the primary mode where users describe what they want in plain English
and the agent figures out how to execute it using LLM-based planning.
"""

from typing import Any, Optional, TYPE_CHECKING
import logging

from llm_web_agent.modes.base import (
    IInteractionMode,
    ModeType,
    ModeConfig,
    ModeResult,
)

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


class NaturalLanguageMode(IInteractionMode):
    """
    Natural Language interaction mode.
    
    User describes a task in plain English, and the agent:
    1. Parses the intent using NLP
    2. Creates a plan using LLM
    3. Executes the plan step by step
    4. Handles errors and retries
    
    Example:
        >>> mode = NaturalLanguageMode(llm_provider)
        >>> await mode.start(page, config)
        >>> result = await mode.execute("Go to amazon.com and search for laptops")
    """
    
    @property
    def mode_type(self) -> ModeType:
        return ModeType.NATURAL_LANGUAGE
    
    @property
    def name(self) -> str:
        return "Natural Language"
    
    @property
    def description(self) -> str:
        return "Describe tasks in plain English and the agent will execute them"
    
    def __init__(self, llm_provider: "ILLMProvider"):
        """
        Initialize the mode.
        
        Args:
            llm_provider: LLM provider for task planning
        """
        self._llm = llm_provider
        self._page: Optional["IPage"] = None
        self._config: Optional[ModeConfig] = None
        self._is_running = False
    
    async def start(
        self,
        page: "IPage",
        config: ModeConfig,
        **kwargs: Any,
    ) -> None:
        """Start the natural language mode."""
        self._page = page
        self._config = config
        self._is_running = True
        logger.info("Natural Language mode started")
    
    async def execute(self, input_data: Any) -> ModeResult:
        """
        Execute a natural language task.
        
        Args:
            input_data: Task description string
            
        Returns:
            Execution result
        """
        if not self._page or not self._is_running:
            return ModeResult(
                success=False,
                error="Mode not started. Call start() first.",
            )
        
        task = str(input_data)
        logger.info(f"Executing task: {task}")
        
        # TODO: Implement the full pipeline:
        # 1. Parse intent
        # 2. Create plan with LLM
        # 3. Execute steps
        # 4. Verify results
        
        raise NotImplementedError("Natural language execution not yet implemented")
    
    async def stop(self) -> None:
        """Stop the mode."""
        self._is_running = False
        self._page = None
        logger.info("Natural Language mode stopped")
