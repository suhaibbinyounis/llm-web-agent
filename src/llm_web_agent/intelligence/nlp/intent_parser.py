"""
Intent Parser - Parse user intents from natural language.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.llm import ILLMProvider


class IntentType(Enum):
    """Types of user intents."""
    NAVIGATE = "navigate"
    SEARCH = "search"
    CLICK = "click"
    FILL_FORM = "fill_form"
    EXTRACT = "extract"
    SCREENSHOT = "screenshot"
    SCROLL = "scroll"
    WAIT = "wait"
    LOGIN = "login"
    DOWNLOAD = "download"
    UPLOAD = "upload"
    COMPLEX = "complex"  # Multi-step intent
    UNKNOWN = "unknown"


@dataclass
class Intent:
    """
    A parsed user intent.
    
    Attributes:
        intent_type: Type of intent
        confidence: Confidence score (0-1)
        target: Target of the intent (URL, element, etc.)
        value: Value for the intent (text to type, etc.)
        parameters: Additional parameters
        sub_intents: Child intents for complex tasks
    """
    intent_type: IntentType
    confidence: float
    target: Optional[str] = None
    value: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    sub_intents: List["Intent"] = field(default_factory=list)


class IntentParser:
    """
    Parse user intents from natural language instructions.
    
    Uses LLM to understand user instructions and extract
    structured intents that can be executed.
    
    Example:
        >>> parser = IntentParser(llm_provider)
        >>> intent = await parser.parse("Go to google and search for cats")
        >>> print(intent.intent_type)  # IntentType.SEARCH
    """
    
    # Keywords that indicate specific intents
    INTENT_KEYWORDS = {
        IntentType.NAVIGATE: ["go to", "open", "visit", "navigate"],
        IntentType.SEARCH: ["search", "find", "look for", "query"],
        IntentType.CLICK: ["click", "press", "tap", "select", "choose"],
        IntentType.FILL_FORM: ["fill", "enter", "type", "input", "write"],
        IntentType.EXTRACT: ["get", "extract", "copy", "read", "scrape"],
        IntentType.SCREENSHOT: ["screenshot", "capture", "snap"],
        IntentType.SCROLL: ["scroll", "page down", "page up"],
        IntentType.LOGIN: ["login", "log in", "sign in", "authenticate"],
        IntentType.DOWNLOAD: ["download", "save", "export"],
        IntentType.UPLOAD: ["upload", "attach", "import"],
    }
    
    def __init__(self, llm_provider: Optional["ILLMProvider"] = None):
        """
        Initialize the parser.
        
        Args:
            llm_provider: LLM provider for complex parsing
        """
        self._llm = llm_provider
    
    async def parse(self, instruction: str) -> Intent:
        """
        Parse an instruction into an intent.
        
        Args:
            instruction: Natural language instruction
            
        Returns:
            Parsed intent
        """
        # Try simple keyword matching first
        intent = self._parse_simple(instruction)
        if intent.confidence > 0.8:
            return intent
        
        # Use LLM for complex parsing
        if self._llm:
            return await self._parse_with_llm(instruction)
        
        return intent
    
    def _parse_simple(self, instruction: str) -> Intent:
        """Simple keyword-based intent parsing."""
        instruction_lower = instruction.lower()
        
        for intent_type, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in instruction_lower:
                    return Intent(
                        intent_type=intent_type,
                        confidence=0.7,
                    )
        
        return Intent(
            intent_type=IntentType.UNKNOWN,
            confidence=0.3,
        )
    
    async def _parse_with_llm(self, instruction: str) -> Intent:
        """Use LLM for intent parsing."""
        # TODO: Implement LLM-based parsing
        raise NotImplementedError("LLM intent parsing not yet implemented")
