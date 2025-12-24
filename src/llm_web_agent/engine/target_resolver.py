"""
Target Resolver - Fast, reliable element resolution.

Simplified approach that works:
1. Try direct selector first
2. Try smart text-based selectors
3. Try common patterns
4. Skip LLM - too slow, use simpler heuristics
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import re
import logging

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage, IElement
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


class ResolutionLayer(Enum):
    """Which layer resolved the target."""
    EXACT = "exact"
    TEXT = "text"
    SMART = "smart"
    FAILED = "failed"


@dataclass
class ResolvedTarget:
    """A resolved target element."""
    selector: str
    element: Optional["IElement"] = None
    layer: ResolutionLayer = ResolutionLayer.EXACT
    confidence: float = 1.0
    alternatives: List[str] = field(default_factory=list)
    
    @property
    def is_resolved(self) -> bool:
        return self.layer != ResolutionLayer.FAILED and bool(self.selector)


class TargetResolver:
    """
    Fast element resolution.
    
    Priority order:
    1. Direct CSS selectors
    2. Text-based Playwright selectors  
    3. Role + text combinations
    4. Common UI patterns
    """
    
    def __init__(
        self,
        llm_provider: Optional["ILLMProvider"] = None,
        fuzzy_threshold: float = 0.6,
    ):
        self._llm = llm_provider
        self._fuzzy_threshold = fuzzy_threshold
    
    async def resolve(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str] = None,
        dom: Optional[Any] = None,
    ) -> ResolvedTarget:
        """Resolve target to selector."""
        target = target.strip()
        
        if not target:
            return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED)
        
        # 1. If it's already a selector, use it
        if self._is_selector(target):
            element = await self._try_selector(page, target)
            if element:
                return ResolvedTarget(
                    selector=target,
                    element=element,
                    layer=ResolutionLayer.EXACT,
                )
        
        # 2. Build smart selectors based on target text and intent
        selectors = self._build_smart_selectors(target, intent)
        
        for selector in selectors:
            element = await self._try_selector(page, selector)
            if element:
                is_visible = await self._is_visible(element)
                if is_visible:
                    logger.debug(f"Found '{target}' with: {selector}")
                    return ResolvedTarget(
                        selector=selector,
                        element=element,
                        layer=ResolutionLayer.SMART,
                        confidence=0.9,
                    )
        
        # 3. Fallback: search all visible interactive elements
        result = await self._search_interactive_elements(page, target, intent)
        if result.is_resolved:
            return result
        
        logger.warning(f"Could not resolve: {target}")
        return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED)
    
    def _is_selector(self, target: str) -> bool:
        """Check if target looks like a CSS selector."""
        return (
            target.startswith(("#", ".", "[", "//")) or
            "::" in target or
            "=" in target or
            ">" in target
        )
    
    async def _try_selector(self, page: "IPage", selector: str) -> Optional["IElement"]:
        """Try a selector safely."""
        try:
            return await page.query_selector(selector)
        except Exception:
            return None
    
    async def _is_visible(self, element: "IElement") -> bool:
        """Check if element is visible."""
        try:
            return await element.is_visible()
        except Exception:
            return True  # Assume visible if check fails
    
    def _build_smart_selectors(self, target: str, intent: Optional[str]) -> List[str]:
        """Build smart selectors for the target."""
        selectors = []
        clean_target = target.lower().strip()
        
        # Extract the core text (remove common words)
        core_text = self._extract_core_text(target)
        
        # Determine element type from intent and keywords
        is_button = intent in ("click", "submit") or any(
            w in clean_target for w in ["button", "btn", "submit", "click"]
        )
        is_input = intent in ("fill", "type") or any(
            w in clean_target for w in ["input", "field", "textbox", "box"]
        )
        is_link = any(w in clean_target for w in ["link"])
        is_search = "search" in clean_target
        
        # IMPORTANT: For fill/type intents, prioritize input elements FIRST
        if intent in ("fill", "type"):
            # Common search/input patterns first
            selectors.extend([
                'input[type="search"]',
                'input[type="text"]',
                '#searchInput',
                '#search-input',
                '#search',
                'input[name="q"]',
                'input[name="query"]',
                'input[name="search"]',
                '[role="searchbox"]',
                'textarea',
            ])
            
            # Then try attribute-based input selectors
            selectors.extend([
                f'input[placeholder*="{core_text}" i]',
                f'input[name*="{core_text}" i]',
                f'input[aria-label*="{core_text}" i]',
                f'textarea[placeholder*="{core_text}" i]',
                f'input[id*="{core_text}" i]',
            ])
            
            # Try ID patterns
            selectors.extend([
                f'#{core_text.replace(" ", "-")}',
                f'#{core_text.replace(" ", "_")}',
                f'input#{core_text.replace(" ", "-")}',
                f'input#{core_text.replace(" ", "_")}',
            ])
        
        # Standard text selectors (for clicks/links)
        if intent not in ("fill", "type"):
            # Playwright text selectors (most reliable for clicks)
            selectors.extend([
                f'text="{core_text}"',
                f"text={core_text}",
                f'text="{target}"',
            ])
            
            # Role-based with text (very reliable for buttons/links)
            if is_button:
                selectors.extend([
                    f'button:has-text("{core_text}")',
                    f'[role="button"]:has-text("{core_text}")',
                    f'input[type="submit"]:has-text("{core_text}")',
                    f'a:has-text("{core_text}")',
                ])
            
            if is_link:
                selectors.extend([
                    f'a:has-text("{core_text}")',
                    f'[role="link"]:has-text("{core_text}")',
                ])
        
        # Search-specific patterns (always useful for search)
        if is_search:
            selectors.extend([
                'input[type="search"]',
                'input[name="q"]',
                'input[name="query"]',
                'input[name="search"]',
                '#search',
                '#searchInput',
                '#search-input',
                '[role="searchbox"]',
                'input[placeholder*="search" i]',
                'input[aria-label*="search" i]',
            ])
        
        # Attribute selectors
        selectors.extend([
            f'[name="{core_text}"]',
            f'[data-testid="{core_text}"]',
            f'[aria-label*="{core_text}" i]',
            f'[title*="{core_text}" i]',
        ])
        
        # More permissive text matching (only for non-fill)
        if intent not in ("fill", "type"):
            selectors.extend([
                f'*:has-text("{core_text}")',
                f'button >> text="{core_text}"',
                f'a >> text="{core_text}"',
            ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_selectors = []
        for s in selectors:
            if s not in seen:
                seen.add(s)
                unique_selectors.append(s)
        
        return unique_selectors
    
    def _extract_core_text(self, target: str) -> str:
        """Extract core text from target description."""
        # Remove common descriptor words
        noise_words = [
            "the", "a", "an", "button", "link", "input", "field",
            "textbox", "box", "element", "click", "on", "in", "at",
            "top", "bottom", "left", "right", "first", "last"
        ]
        
        words = target.lower().split()
        filtered = [w for w in words if w not in noise_words]
        
        if filtered:
            return " ".join(filtered)
        return target
    
    async def _search_interactive_elements(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str],
    ) -> ResolvedTarget:
        """Search through interactive elements for a match."""
        
        # Get all interactive elements
        selector = "button, a, input, select, textarea, [role='button'], [role='link'], [onclick]"
        
        try:
            elements = await page.query_selector_all(selector)
            
            target_lower = target.lower()
            core_text = self._extract_core_text(target).lower()
            
            best_match = None
            best_score = 0
            
            for element in elements:
                # Skip hidden elements
                try:
                    if not await element.is_visible():
                        continue
                except:
                    continue
                
                # Get element info
                text = (await element.text_content() or "").lower().strip()
                aria_label = (await element.get_attribute("aria-label") or "").lower()
                placeholder = (await element.get_attribute("placeholder") or "").lower()
                name = (await element.get_attribute("name") or "").lower()
                id_attr = (await element.get_attribute("id") or "").lower()
                
                # Calculate match score
                score = 0
                
                # Exact text match
                if core_text == text:
                    score = 1.0
                elif core_text in text:
                    score = 0.8
                elif text in core_text and len(text) > 2:
                    score = 0.7
                
                # Check attributes
                if core_text in aria_label:
                    score = max(score, 0.85)
                if core_text in placeholder:
                    score = max(score, 0.8)
                if core_text in name:
                    score = max(score, 0.75)
                if core_text in id_attr:
                    score = max(score, 0.75)
                
                if score > best_score:
                    best_score = score
                    best_match = element
            
            if best_match and best_score >= 0.6:
                # Build selector for this element
                selector = await self._build_element_selector(best_match)
                logger.debug(f"Found '{target}' via search with score {best_score}: {selector}")
                return ResolvedTarget(
                    selector=selector,
                    element=best_match,
                    layer=ResolutionLayer.SMART,
                    confidence=best_score,
                )
        
        except Exception as e:
            logger.debug(f"Search error: {e}")
        
        return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED)
    
    async def _build_element_selector(self, element: "IElement") -> str:
        """Build a unique selector for an element."""
        try:
            # Try ID first
            id_attr = await element.get_attribute("id")
            if id_attr:
                return f"#{id_attr}"
            
            # Try data-testid
            testid = await element.get_attribute("data-testid")
            if testid:
                return f'[data-testid="{testid}"]'
            
            # Try name
            name = await element.get_attribute("name")
            if name:
                return f'[name="{name}"]'
            
            # Try text content
            text = await element.text_content()
            if text and len(text.strip()) < 50:
                return f'text="{text.strip()}"'
            
            # Fallback: use aria-label
            aria = await element.get_attribute("aria-label")
            if aria:
                return f'[aria-label="{aria}"]'
            
        except Exception:
            pass
        
        # Can't build a reliable selector
        return ""
    
    async def resolve_multiple(
        self,
        page: "IPage",
        targets: List[str],
        intent: Optional[str] = None,
    ) -> List[ResolvedTarget]:
        """Resolve multiple targets."""
        results = []
        for target in targets:
            result = await self.resolve(page, target, intent)
            results.append(result)
        return results
