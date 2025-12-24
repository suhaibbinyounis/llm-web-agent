"""
Pre-Analyzer - Parallel LLM analysis during browser startup.

Generates synonyms and selector hints that respect user's original instruction.
Key principle: Augment search, NEVER override user intent.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


# Prompt for extracting synonyms and hints
PRE_ANALYSIS_PROMPT = '''You are helping find elements on a web page.

User instruction: "{instruction}"

Extract the TARGET elements the user wants to interact with and generate:
1. SYNONYMS - alternative text that means THE SAME THING (not different actions)
2. SELECTOR_HINTS - CSS selector patterns that might match

IMPORTANT: The user's exact words are the source of truth. 
DO NOT suggest different actions. Only help FIND what they asked for.

Example:
Instruction: "Click Get started"
Response: {{
  "targets": ["Get started"],
  "synonyms": {{"Get started": ["Getting started", "Start here", "Begin", "Start now"]}},
  "selector_hints": ["button:has-text('start')", ".hero button", "a[href*=start]"]
}}

Respond with JSON only:'''


@dataclass
class PreAnalysisResult:
    """Result of pre-analysis."""
    targets: List[str] = field(default_factory=list)
    synonyms: Dict[str, List[str]] = field(default_factory=dict)
    selector_hints: List[str] = field(default_factory=list)
    
    def get_synonyms(self, target: str) -> List[str]:
        """Get synonyms for a target, case-insensitive."""
        target_lower = target.lower()
        for key, syns in self.synonyms.items():
            if key.lower() == target_lower:
                return syns
        return []


class PreAnalyzer:
    """
    Runs parallel LLM analysis during browser startup.
    
    Generates synonyms and selector hints that respect user intent.
    """
    
    def __init__(
        self,
        llm_provider: Optional["ILLMProvider"] = None,
        timeout_ms: int = 5000,
    ):
        self._llm = llm_provider
        self._timeout = timeout_ms / 1000  # Convert to seconds
        self._cache: Dict[str, PreAnalysisResult] = {}
    
    async def analyze(self, instruction: str) -> PreAnalysisResult:
        """
        Analyze instruction to extract synonyms and hints.
        
        Args:
            instruction: User's natural language instruction
            
        Returns:
            PreAnalysisResult with synonyms and selector hints
        """
        # Check cache first
        cache_key = instruction.lower().strip()
        if cache_key in self._cache:
            logger.debug(f"Pre-analysis cache hit for: {instruction[:50]}...")
            return self._cache[cache_key]
        
        if not self._llm:
            logger.debug("No LLM provider, skipping pre-analysis")
            return PreAnalysisResult()
        
        try:
            prompt = PRE_ANALYSIS_PROMPT.format(instruction=instruction)
            
            # Run with timeout
            response = await asyncio.wait_for(
                self._llm.generate(prompt),
                timeout=self._timeout,
            )
            
            # Parse JSON response
            result = self._parse_response(response)
            
            # Cache result
            self._cache[cache_key] = result
            
            logger.info(f"Pre-analysis: {len(result.targets)} targets, "
                       f"{sum(len(s) for s in result.synonyms.values())} synonyms")
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(f"Pre-analysis timed out after {self._timeout}s")
            return PreAnalysisResult()
            
        except Exception as e:
            logger.debug(f"Pre-analysis failed: {e}")
            return PreAnalysisResult()
    
    def _parse_response(self, response: str) -> PreAnalysisResult:
        """Parse LLM response into PreAnalysisResult."""
        import json
        
        # Try to extract JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                start = response.index("```json") + 7
                end = response.index("```", start)
                response = response[start:end]
            elif "```" in response:
                start = response.index("```") + 3
                end = response.index("```", start)
                response = response[start:end]
            
            data = json.loads(response.strip())
            
            return PreAnalysisResult(
                targets=data.get("targets", []),
                synonyms=data.get("synonyms", {}),
                selector_hints=data.get("selector_hints", []),
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Failed to parse pre-analysis response: {e}")
            return PreAnalysisResult()
    
    def clear_cache(self):
        """Clear the analysis cache."""
        self._cache.clear()


# Global instance
_pre_analyzer: Optional[PreAnalyzer] = None


def get_pre_analyzer(
    llm_provider: Optional["ILLMProvider"] = None,
    timeout_ms: int = 5000,
) -> PreAnalyzer:
    """Get or create global pre-analyzer instance."""
    global _pre_analyzer
    if _pre_analyzer is None or llm_provider is not None:
        _pre_analyzer = PreAnalyzer(llm_provider, timeout_ms)
    return _pre_analyzer
