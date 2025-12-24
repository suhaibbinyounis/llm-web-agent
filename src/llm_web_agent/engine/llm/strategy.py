"""
LLM Strategy - Unified interface for LLM interactions in the engine.

Provides:
- High-level methods for each LLM use case
- Response parsing and validation
- Error handling and retries
- Token management
- Caching for repeated queries
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import time
import json
import logging
import hashlib

from llm_web_agent.engine.llm.prompts import PromptBuilder
from llm_web_agent.engine.llm.schemas import (
    ParsedInstruction,
    ParsedStep,
    FoundElement,
    ActionPlan,
    ErrorRecovery,
    ExtractedValue,
    LLMResponse,
    LLMResponseStatus,
    get_instruction_parse_schema,
    get_element_find_schema,
    get_action_plan_schema,
)
from llm_web_agent.engine.llm.dom_simplifier import DOMSimplifier, SimplifiedDOM

if TYPE_CHECKING:
    from llm_web_agent.interfaces.llm import ILLMProvider, Message
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.engine.run_context import RunContext

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry for LLM responses."""
    response: LLMResponse
    timestamp: datetime
    hits: int = 0


class LLMStrategy:
    """
    Unified LLM interaction layer for the engine.
    
    This is the single point of contact between the engine and LLM.
    Handles all prompting, parsing, validation, and optimization.
    
    Example:
        >>> strategy = LLMStrategy(llm_provider)
        >>> 
        >>> # Parse instruction
        >>> result = await strategy.parse_instruction(
        ...     "Go to amazon and search for laptops"
        ... )
        >>> if result.success:
        ...     steps = result.parsed.steps
        >>> 
        >>> # Find element
        >>> result = await strategy.find_element(page, "the search button")
        >>> if result.is_found:
        ...     selector = result.selector
    """
    
    def __init__(
        self,
        llm_provider: "ILLMProvider",
        use_function_calling: bool = True,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 300,
        max_retries: int = 2,
    ):
        """
        Initialize the strategy.
        
        Args:
            llm_provider: LLM provider instance
            use_function_calling: Use function/tool calling if available
            cache_enabled: Cache repeated queries
            cache_ttl_seconds: Cache time-to-live
            max_retries: Retries on parse failure
        """
        self._llm = llm_provider
        self._use_functions = use_function_calling
        self._cache_enabled = cache_enabled
        self._cache_ttl = cache_ttl_seconds
        self._max_retries = max_retries
        
        self._prompt_builder = PromptBuilder()
        self._dom_simplifier = DOMSimplifier()
        self._cache: Dict[str, CacheEntry] = {}
        
        # Stats
        self._total_calls = 0
        self._cache_hits = 0
        self._total_tokens = 0
    
    # =========================================================================
    # INSTRUCTION PARSING
    # =========================================================================
    
    async def parse_instruction(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """
        Parse a natural language instruction into steps.
        
        Args:
            instruction: User's natural language instruction
            context: Optional context (current URL, available elements)
            
        Returns:
            LLMResponse with ParsedInstruction
        """
        # Check cache
        cache_key = self._cache_key("parse", instruction, context)
        cached = self._get_cached(cache_key)
        if cached:
            return cached
        
        # Build prompt
        system, user = self._prompt_builder.build_instruction_parse(
            instruction, context
        )
        
        # Call LLM
        response = await self._call_llm(
            system=system,
            user=user,
            schema_class=ParsedInstruction,
            function_schema=get_instruction_parse_schema() if self._use_functions else None,
        )
        
        # Cache on success
        if response.success:
            self._set_cached(cache_key, response)
        
        return response
    
    # =========================================================================
    # ELEMENT FINDING
    # =========================================================================
    
    async def find_element(
        self,
        page: "IPage",
        description: str,
        simplified_dom: Optional[SimplifiedDOM] = None,
    ) -> FoundElement:
        """
        Find an element matching a description.
        
        Args:
            page: Browser page
            description: Element description
            simplified_dom: Optional pre-simplified DOM
            
        Returns:
            FoundElement with match details
        """
        # Get DOM if not provided
        if simplified_dom is None:
            simplified_dom = await self._dom_simplifier.simplify(page)
        
        # Check cache (DOM-dependent, so include URL in key)
        cache_key = self._cache_key("find", description, {"url": simplified_dom.url})
        cached = self._get_cached(cache_key)
        if cached and cached.parsed:
            return cached.parsed
        
        # Build prompt
        system, user = self._prompt_builder.build_element_find(
            description=description,
            url=simplified_dom.url,
            elements=simplified_dom.to_elements_list(),
        )
        
        # Call LLM
        response = await self._call_llm(
            system=system,
            user=user,
            schema_class=FoundElement,
            function_schema=get_element_find_schema() if self._use_functions else None,
        )
        
        if response.success and response.parsed:
            result = response.parsed
            
            # Enrich with selector from DOM if index provided
            if result.found and result.index is not None:
                elem = simplified_dom.get_element(result.index)
                if elem:
                    result.selector = elem.selector
            
            self._set_cached(cache_key, response)
            return result
        
        # Return failed result
        return FoundElement(
            found=False,
            reasoning=response.error or "LLM call failed",
        )
    
    # =========================================================================
    # ACTION PLANNING
    # =========================================================================
    
    async def create_plan(
        self,
        page: "IPage",
        goal: str,
        context: Optional["RunContext"] = None,
    ) -> ActionPlan:
        """
        Create an action plan to achieve a goal.
        
        Args:
            page: Browser page
            goal: The goal to achieve
            context: Optional run context with variables
            
        Returns:
            ActionPlan with steps
        """
        # Get DOM
        simplified_dom = await self._dom_simplifier.simplify(page)
        
        # Get variables
        variables = context.get_all_stored() if context else {}
        
        # Build prompt
        system, user = self._prompt_builder.build_action_plan(
            goal=goal,
            url=simplified_dom.url,
            title=simplified_dom.title,
            elements=simplified_dom.to_elements_list(),
            variables=variables,
        )
        
        # Call LLM
        response = await self._call_llm(
            system=system,
            user=user,
            schema_class=ActionPlan,
            function_schema=get_action_plan_schema() if self._use_functions else None,
        )
        
        if response.success and response.parsed:
            return response.parsed
        
        # Return empty plan on failure
        return ActionPlan(plan=[])
    
    # =========================================================================
    # ERROR RECOVERY
    # =========================================================================
    
    async def suggest_recovery(
        self,
        page: "IPage",
        failed_action: str,
        error: str,
        context: Optional["RunContext"] = None,
    ) -> ErrorRecovery:
        """
        Suggest how to recover from a failed action.
        
        Args:
            page: Browser page
            failed_action: Description of what failed
            error: Error message
            context: Run context with history
            
        Returns:
            ErrorRecovery with suggestions
        """
        # Get DOM
        simplified_dom = await self._dom_simplifier.simplify(page)
        
        # Get history
        history = []
        if context:
            history = [
                f"{a.action_type}({a.target}) → {'✓' if a.success else '✗'}"
                for a in context.history[-5:]
            ]
        
        # Build prompt
        system, user = self._prompt_builder.build_error_recovery(
            action=failed_action,
            error=error,
            url=simplified_dom.url,
            title=simplified_dom.title,
            elements=simplified_dom.to_elements_list(),
            history=history,
        )
        
        # Call LLM
        response = await self._call_llm(
            system=system,
            user=user,
            schema_class=ErrorRecovery,
        )
        
        if response.success and response.parsed:
            return response.parsed
        
        return ErrorRecovery(
            diagnosis="Could not diagnose the issue",
            should_retry=True,
        )
    
    # =========================================================================
    # DATA EXTRACTION
    # =========================================================================
    
    async def extract_value(
        self,
        page: "IPage",
        what_to_extract: str,
        simplified_dom: Optional[SimplifiedDOM] = None,
    ) -> ExtractedValue:
        """
        Extract a specific value from the page.
        
        Args:
            page: Browser page
            what_to_extract: Description of what to extract
            simplified_dom: Optional pre-simplified DOM
            
        Returns:
            ExtractedValue with result
        """
        # Get DOM if not provided
        if simplified_dom is None:
            simplified_dom = await self._dom_simplifier.simplify(page)
        
        # Build prompt
        system, user = self._prompt_builder.build_dom_describe(
            what_to_extract=what_to_extract,
            elements=simplified_dom.to_elements_list(),
        )
        
        # Call LLM
        response = await self._call_llm(
            system=system,
            user=user,
            schema_class=ExtractedValue,
        )
        
        if response.success and response.parsed:
            result = response.parsed
            
            # If we have an index, try to get actual value from DOM
            if result.found and result.element_index is not None:
                elem = simplified_dom.get_element(result.element_index)
                if elem:
                    # Use text or value from element
                    result.value = elem.value or elem.text
            
            return result
        
        return ExtractedValue(found=False)
    
    # =========================================================================
    # SIMPLIFIED DOM ACCESS
    # =========================================================================
    
    async def get_simplified_dom(self, page: "IPage") -> SimplifiedDOM:
        """Get simplified DOM for a page."""
        return await self._dom_simplifier.simplify(page)
    
    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================
    
    async def _call_llm(
        self,
        system: str,
        user: str,
        schema_class: type,
        function_schema: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Make an LLM call with parsing and validation."""
        from llm_web_agent.interfaces.llm import Message
        
        start_time = time.time()
        self._total_calls += 1
        
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=user),
        ]
        
        try:
            # Try function calling if available
            if function_schema and self._use_functions:
                try:
                    from llm_web_agent.interfaces.llm import ToolDefinition
                    
                    tool = ToolDefinition(
                        name=function_schema["name"],
                        description=function_schema["description"],
                        parameters=function_schema["parameters"],
                    )
                    
                    response = await self._llm.complete(
                        messages=messages,
                        tools=[tool],
                    )
                    
                    # Check for tool calls
                    if response.tool_calls:
                        tool_call = response.tool_calls[0]
                        latency = (time.time() - start_time) * 1000
                        self._total_tokens += response.usage.total_tokens if response.usage else 0
                        
                        return LLMResponse.from_text(
                            text=json.dumps(tool_call.arguments),
                            schema_class=schema_class,
                            tokens=response.usage.total_tokens if response.usage else 0,
                            latency=latency,
                        )
                except Exception as e:
                    logger.debug(f"Function calling failed, falling back: {e}")
            
            # Regular completion
            response = await self._llm.complete(messages=messages)
            
            latency = (time.time() - start_time) * 1000
            tokens = response.usage.total_tokens if response.usage else 0
            self._total_tokens += tokens
            
            return LLMResponse.from_text(
                text=response.content,
                schema_class=schema_class,
                tokens=tokens,
                latency=latency,
            )
        
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return LLMResponse(
                status=LLMResponseStatus.ERROR,
                error=str(e),
                latency_ms=(time.time() - start_time) * 1000,
            )
    
    def _cache_key(
        self,
        operation: str,
        query: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate cache key."""
        data = f"{operation}:{query}:{json.dumps(context or {}, sort_keys=True)}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def _get_cached(self, key: str) -> Optional[LLMResponse]:
        """Get cached response if valid."""
        if not self._cache_enabled:
            return None
        
        entry = self._cache.get(key)
        if entry is None:
            return None
        
        # Check TTL
        age = (datetime.now() - entry.timestamp).total_seconds()
        if age > self._cache_ttl:
            del self._cache[key]
            return None
        
        entry.hits += 1
        self._cache_hits += 1
        return entry.response
    
    def _set_cached(self, key: str, response: LLMResponse) -> None:
        """Cache a response."""
        if not self._cache_enabled:
            return
        
        self._cache[key] = CacheEntry(
            response=response,
            timestamp=datetime.now(),
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_calls": self._total_calls,
            "cache_hits": self._cache_hits,
            "cache_hit_rate": self._cache_hits / max(self._total_calls, 1),
            "total_tokens": self._total_tokens,
            "cache_size": len(self._cache),
        }
    
    def clear_cache(self) -> None:
        """Clear the response cache."""
        self._cache.clear()
