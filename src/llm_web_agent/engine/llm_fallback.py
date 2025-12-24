"""
LLM Fallback - Adaptive LLM-assisted element resolution.

Uses LLM for disambiguation when:
- Severity is HIGH (no candidates found)
- Multiple candidates found but none match well
- Page looks different than expected

Severity Levels:
- LOW: Similar elements found, retry might work
- MEDIUM: Fuzzy found candidates with low confidence
- HIGH: No candidates at all
- CRITICAL: Page state unexpected
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Resolution difficulty severity."""
    LOW = "low"           # Found similar elements
    MEDIUM = "medium"     # Fuzzy found something
    HIGH = "high"         # No candidates
    CRITICAL = "critical" # Page state wrong


@dataclass
class ResolutionContext:
    """Context about the resolution attempt."""
    target: str
    candidates: List[str] = field(default_factory=list)
    best_score: float = 0.0
    page_title: str = ""
    visible_buttons: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class DisambiguationResult:
    """Result of LLM disambiguation."""
    success: bool
    selector: Optional[str] = None
    matched_text: Optional[str] = None
    reasoning: str = ""


# Prompt for element disambiguation
DISAMBIGUATION_PROMPT = '''You are helping find a web element.

User wants to interact with: "{target}"

Available elements on the page:
{elements}

Page title: {page_title}

Which element BEST matches the user's intent?
The user's exact words matter - don't substitute with a different action.

Respond with JSON:
{{
  "match": "exact text of matching element or null if none match",
  "confidence": 0.0-1.0,
  "reasoning": "why this matches the user's intent"
}}'''


class LLMFallback:
    """
    Adaptive LLM fallback for element resolution.
    
    Uses LLM only when necessary, based on resolution severity.
    """
    
    def __init__(
        self,
        llm_provider: Optional["ILLMProvider"] = None,
        timeout_ms: int = 8000,
    ):
        self._llm = llm_provider
        self._timeout = timeout_ms / 1000
    
    def assess_severity(self, context: ResolutionContext) -> Severity:
        """
        Assess the severity of a failed resolution.
        
        Args:
            context: Information about the resolution attempt
            
        Returns:
            Severity level
        """
        # Critical: Something really wrong (e.g., auth wall, error page)
        if context.page_title and any(
            x in context.page_title.lower() 
            for x in ["error", "404", "login", "sign in", "access denied"]
        ):
            return Severity.CRITICAL
        
        # Low: Found good candidates, just picked wrong one
        if context.best_score >= 0.7:
            return Severity.LOW
        
        # Medium: Found some candidates with moderate confidence
        if context.candidates and context.best_score >= 0.4:
            return Severity.MEDIUM
        
        # High: No candidates or very low confidence
        if not context.candidates or context.best_score < 0.4:
            return Severity.HIGH
        
        return Severity.MEDIUM
    
    def should_use_llm(self, severity: Severity, retry_count: int = 0) -> bool:
        """
        Decide whether to use LLM based on severity and retry count.
        
        Args:
            severity: Current severity level
            retry_count: How many retries have occurred
            
        Returns:
            True if LLM should be used
        """
        if not self._llm:
            return False
        
        # Always use LLM for critical situations
        if severity == Severity.CRITICAL:
            return True
        
        # High severity: use LLM immediately
        if severity == Severity.HIGH:
            return True
        
        # Medium severity: use LLM after 1 retry
        if severity == Severity.MEDIUM and retry_count >= 1:
            return True
        
        # Low severity: only use LLM after 2 retries
        if severity == Severity.LOW and retry_count >= 2:
            return True
        
        return False
    
    async def disambiguate(
        self,
        page: "IPage",
        context: ResolutionContext,
    ) -> DisambiguationResult:
        """
        Use LLM to disambiguate between candidates or find the right element.
        
        Args:
            page: Browser page
            context: Resolution context with candidates
            
        Returns:
            DisambiguationResult with best match
        """
        if not self._llm:
            return DisambiguationResult(success=False, reasoning="No LLM provider")
        
        try:
            # Gather visible interactive elements if not provided
            if not context.visible_buttons:
                context.visible_buttons = await self._get_visible_elements(page)
            
            # Get page title if not provided
            if not context.page_title:
                try:
                    context.page_title = await page.title()
                except Exception:
                    context.page_title = "Unknown"
            
            # Format elements for prompt
            elements_text = "\n".join(
                f"- {elem}" for elem in context.visible_buttons[:15]  # Limit to 15
            )
            
            prompt = DISAMBIGUATION_PROMPT.format(
                target=context.target,
                elements=elements_text or "(no elements found)",
                page_title=context.page_title,
            )
            
            # Call LLM with timeout
            response = await asyncio.wait_for(
                self._llm.generate(prompt),
                timeout=self._timeout,
            )
            
            # Parse response
            return self._parse_response(response, context.visible_buttons)
            
        except asyncio.TimeoutError:
            logger.warning(f"LLM disambiguation timed out after {self._timeout}s")
            return DisambiguationResult(success=False, reasoning="Timeout")
            
        except Exception as e:
            logger.debug(f"LLM disambiguation failed: {e}")
            return DisambiguationResult(success=False, reasoning=str(e))
    
    async def _get_visible_elements(self, page: "IPage") -> List[str]:
        """Get text of visible interactive elements."""
        try:
            selector = "button, a, input[type='submit'], [role='button']"
            elements = await page.query_selector_all(selector)
            
            texts = []
            for elem in elements[:20]:  # Limit to 20
                try:
                    if await elem.is_visible():
                        text = await elem.text_content()
                        if text and text.strip():
                            texts.append(text.strip()[:50])  # Limit length
                except Exception:
                    continue
            
            return texts
            
        except Exception as e:
            logger.debug(f"Failed to get visible elements: {e}")
            return []
    
    def _parse_response(
        self,
        response: str,
        available_elements: List[str],
    ) -> DisambiguationResult:
        """Parse LLM response into DisambiguationResult."""
        import json
        
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
            
            matched = data.get("match")
            confidence = data.get("confidence", 0.0)
            reasoning = data.get("reasoning", "")
            
            if not matched or confidence < 0.6:
                return DisambiguationResult(
                    success=False,
                    reasoning=reasoning or "Low confidence match",
                )
            
            # Find the actual element text (case-insensitive)
            matched_lower = matched.lower()
            for elem_text in available_elements:
                if elem_text.lower() == matched_lower or matched_lower in elem_text.lower():
                    logger.info(f"LLM matched: '{matched}' (confidence={confidence})")
                    return DisambiguationResult(
                        success=True,
                        matched_text=elem_text,
                        reasoning=reasoning,
                    )
            
            # LLM returned something not in our list
            return DisambiguationResult(
                success=False,
                reasoning=f"LLM suggested '{matched}' but not found in elements",
            )
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"Failed to parse LLM response: {e}")
            return DisambiguationResult(success=False, reasoning="Parse error")


# Global instance
_llm_fallback: Optional[LLMFallback] = None


def get_llm_fallback(
    llm_provider: Optional["ILLMProvider"] = None,
    timeout_ms: int = 8000,
) -> LLMFallback:
    """Get or create global LLM fallback instance."""
    global _llm_fallback
    if _llm_fallback is None or llm_provider is not None:
        _llm_fallback = LLMFallback(llm_provider, timeout_ms)
    return _llm_fallback
