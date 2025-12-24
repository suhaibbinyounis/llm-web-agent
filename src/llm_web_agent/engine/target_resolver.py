"""
Target Resolver - Multi-layer element resolution.

Resolves element descriptions to actual DOM elements using:
1. Exact match (ID, data-testid, name)
2. Text match (button text, label)
3. Fuzzy match (similarity scoring)
4. LLM resolution (complex cases)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import re
import logging

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage, IElement
    from llm_web_agent.interfaces.llm import ILLMProvider
    from llm_web_agent.intelligence.dom.parser import ParsedDOM

logger = logging.getLogger(__name__)


class ResolutionLayer(Enum):
    """Which layer resolved the target."""
    EXACT = "exact"        # ID, data-testid, name
    TEXT = "text"          # Text content match
    FUZZY = "fuzzy"        # Similarity scoring
    LLM = "llm"            # LLM resolution
    FAILED = "failed"      # Could not resolve


@dataclass
class ResolvedTarget:
    """
    A resolved target element.
    
    Attributes:
        selector: CSS selector to use
        element: Direct element reference if available
        layer: Which resolution layer succeeded
        confidence: Confidence score (0-1)
        alternatives: Other possible matches
    """
    selector: str
    element: Optional["IElement"] = None
    layer: ResolutionLayer = ResolutionLayer.EXACT
    confidence: float = 1.0
    alternatives: List[str] = field(default_factory=list)
    
    @property
    def is_resolved(self) -> bool:
        """Check if target was successfully resolved."""
        return self.layer != ResolutionLayer.FAILED


class TargetResolver:
    """
    Multi-layer element resolution.
    
    Tries multiple strategies to find elements:
    1. EXACT: Direct selectors (ID, data-testid, name attributes)
    2. TEXT: Text content matching
    3. FUZZY: Fuzzy text matching with scoring
    4. LLM: Ask LLM to identify element from DOM
    
    Example:
        >>> resolver = TargetResolver()
        >>> target = await resolver.resolve(page, "login button")
        >>> if target.is_resolved:
        ...     await page.click(target.selector)
    """
    
    # Common element patterns for different intents
    ROLE_SELECTORS = {
        "button": ["button", "input[type='button']", "input[type='submit']", "[role='button']"],
        "link": ["a", "[role='link']"],
        "input": ["input:not([type='button']):not([type='submit'])", "textarea"],
        "search": ["input[type='search']", "input[name*='search']", "input[placeholder*='search' i]", 
                   "#search", ".search", "[role='searchbox']"],
        "checkbox": ["input[type='checkbox']", "[role='checkbox']"],
        "dropdown": ["select", "[role='combobox']", "[role='listbox']"],
    }
    
    # Words that indicate element types
    TYPE_KEYWORDS = {
        "button": ["button", "btn", "submit", "click", "press"],
        "link": ["link", "href", "url", "navigate"],
        "input": ["field", "input", "textbox", "textarea", "form"],
        "search": ["search", "find", "query"],
    }
    
    def __init__(
        self,
        llm_provider: Optional["ILLMProvider"] = None,
        fuzzy_threshold: float = 0.6,
    ):
        """
        Initialize the resolver.
        
        Args:
            llm_provider: Optional LLM for complex resolution
            fuzzy_threshold: Minimum similarity score for fuzzy matching
        """
        self._llm = llm_provider
        self._fuzzy_threshold = fuzzy_threshold
    
    async def resolve(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str] = None,
        dom: Optional["ParsedDOM"] = None,
    ) -> ResolvedTarget:
        """
        Resolve a target description to a selector.
        
        Args:
            page: Browser page
            target: Target description (selector, text, or natural language)
            intent: Optional intent hint (click, fill, etc.)
            dom: Optional pre-parsed DOM
            
        Returns:
            ResolvedTarget with selector and metadata
        """
        target = target.strip()
        
        if not target:
            return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED, confidence=0)
        
        # Layer 1: Exact match
        result = await self._try_exact_match(page, target)
        if result.is_resolved:
            return result
        
        # Layer 2: Text match
        result = await self._try_text_match(page, target, intent)
        if result.is_resolved:
            return result
        
        # Layer 3: Fuzzy match
        result = await self._try_fuzzy_match(page, target, intent)
        if result.is_resolved:
            return result
        
        # Layer 4: LLM resolution
        if self._llm:
            result = await self._try_llm_resolution(page, target, intent, dom)
            if result.is_resolved:
                return result
        
        # Failed to resolve
        logger.warning(f"Could not resolve target: {target}")
        return ResolvedTarget(
            selector="",
            layer=ResolutionLayer.FAILED,
            confidence=0,
        )
    
    async def _try_exact_match(
        self,
        page: "IPage",
        target: str,
    ) -> ResolvedTarget:
        """Try exact CSS selector or ID match."""
        
        # If it looks like a selector, try it directly
        if target.startswith(("#", ".", "[")) or "=" in target:
            try:
                element = await page.query_selector(target)
                if element:
                    return ResolvedTarget(
                        selector=target,
                        element=element,
                        layer=ResolutionLayer.EXACT,
                        confidence=1.0,
                    )
            except Exception:
                pass
        
        # Try common exact patterns
        exact_patterns = [
            f"#{target}",                          # ID
            f"#{target.lower().replace(' ', '-')}", # ID with dashes
            f"#{target.lower().replace(' ', '_')}", # ID with underscores
            f"[data-testid='{target}']",           # data-testid
            f"[data-test='{target}']",             # data-test
            f"[name='{target}']",                  # name attribute
            f"[aria-label='{target}']",            # aria-label
        ]
        
        for pattern in exact_patterns:
            try:
                element = await page.query_selector(pattern)
                if element:
                    return ResolvedTarget(
                        selector=pattern,
                        element=element,
                        layer=ResolutionLayer.EXACT,
                        confidence=0.95,
                    )
            except Exception:
                continue
        
        return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED, confidence=0)
    
    async def _try_text_match(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str] = None,
    ) -> ResolvedTarget:
        """Try matching by text content."""
        
        # Determine element type from intent and keywords
        element_types = self._infer_element_types(target, intent)
        
        # Build text-based selectors
        text_selectors = []
        
        for elem_type, base_selectors in self.ROLE_SELECTORS.items():
            if not element_types or elem_type in element_types:
                for base in base_selectors:
                    # Exact text match
                    text_selectors.append(f"{base}:has-text('{target}')")
                    # Case-insensitive text
                    text_selectors.append(f"{base}:text-is('{target}')")
        
        # Also try generic text selectors
        text_selectors.extend([
            f"text='{target}'",
            f"text={target}",
            f"*:has-text('{target}')",
        ])
        
        for selector in text_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    # Verify element is visible and interactable
                    if await element.is_visible():
                        return ResolvedTarget(
                            selector=selector,
                            element=element,
                            layer=ResolutionLayer.TEXT,
                            confidence=0.85,
                        )
            except Exception:
                continue
        
        return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED, confidence=0)
    
    async def _try_fuzzy_match(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str] = None,
    ) -> ResolvedTarget:
        """Try fuzzy matching with similarity scoring."""
        
        # Get all interactive elements
        element_types = self._infer_element_types(target, intent)
        
        candidates: List[Tuple[str, float, Any]] = []
        
        # Build selector for candidate elements
        if element_types:
            selectors = []
            for elem_type in element_types:
                selectors.extend(self.ROLE_SELECTORS.get(elem_type, []))
            candidate_selector = ", ".join(selectors) if selectors else "button, a, input, select"
        else:
            candidate_selector = "button, a, input, select, [role='button'], [onclick]"
        
        try:
            elements = await page.query_selector_all(candidate_selector)
            
            for element in elements:
                if not await element.is_visible():
                    continue
                
                # Get element text/attributes
                text = await element.text_content() or ""
                aria_label = await element.get_attribute("aria-label") or ""
                placeholder = await element.get_attribute("placeholder") or ""
                title = await element.get_attribute("title") or ""
                
                # Score similarity
                combined = f"{text} {aria_label} {placeholder} {title}".lower()
                score = self._similarity_score(target.lower(), combined)
                
                if score >= self._fuzzy_threshold:
                    # Build a selector for this element
                    selector = await self._build_selector(element)
                    candidates.append((selector, score, element))
        
        except Exception as e:
            logger.debug(f"Fuzzy match error: {e}")
        
        if candidates:
            # Sort by score descending
            candidates.sort(key=lambda x: x[1], reverse=True)
            best_selector, best_score, best_element = candidates[0]
            
            return ResolvedTarget(
                selector=best_selector,
                element=best_element,
                layer=ResolutionLayer.FUZZY,
                confidence=best_score,
                alternatives=[c[0] for c in candidates[1:5]],
            )
        
        return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED, confidence=0)
    
    async def _try_llm_resolution(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str],
        dom: Optional["ParsedDOM"],
    ) -> ResolvedTarget:
        """Use LLM to resolve complex targets."""
        
        if not self._llm:
            return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED, confidence=0)
        
        from llm_web_agent.engine.llm.strategy import LLMStrategy
        from llm_web_agent.engine.llm.dom_simplifier import DOMSimplifier
        
        logger.info(f"Using LLM to find element: {target}")
        
        # Create strategy
        strategy = LLMStrategy(self._llm)
        
        # Get simplified DOM
        simplifier = DOMSimplifier()
        simplified_dom = await simplifier.simplify(page)
        
        # Ask LLM to find element
        found = await strategy.find_element(page, target, simplified_dom)
        
        if found.is_found and found.selector:
            # Verify the selector works
            try:
                element = await page.query_selector(found.selector)
                if element:
                    logger.info(f"LLM found element with selector: {found.selector}")
                    return ResolvedTarget(
                        selector=found.selector,
                        element=element,
                        layer=ResolutionLayer.LLM,
                        confidence=found.confidence,
                    )
            except Exception as e:
                logger.debug(f"LLM selector failed to match: {e}")
        
        # Try using index if provided
        if found.is_found and found.index is not None:
            elem_info = simplified_dom.get_element(found.index)
            if elem_info and elem_info.selector:
                try:
                    element = await page.query_selector(elem_info.selector)
                    if element:
                        logger.info(f"LLM found element by index {found.index}: {elem_info.selector}")
                        return ResolvedTarget(
                            selector=elem_info.selector,
                            element=element,
                            layer=ResolutionLayer.LLM,
                            confidence=found.confidence,
                        )
                except Exception as e:
                    logger.debug(f"LLM index selector failed: {e}")
        
        logger.warning(f"LLM could not find element: {target}")
        return ResolvedTarget(selector="", layer=ResolutionLayer.FAILED, confidence=0)
    
    def _infer_element_types(
        self,
        target: str,
        intent: Optional[str] = None,
    ) -> List[str]:
        """Infer likely element types from target and intent."""
        types = []
        target_lower = target.lower()
        
        # Check intent
        if intent:
            if intent in ("click", "press", "submit"):
                types.extend(["button", "link"])
            elif intent in ("fill", "type", "input"):
                types.extend(["input"])
            elif intent == "select":
                types.append("dropdown")
        
        # Check keywords in target
        for elem_type, keywords in self.TYPE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in target_lower:
                    if elem_type not in types:
                        types.append(elem_type)
                    break
        
        return types
    
    def _similarity_score(self, target: str, text: str) -> float:
        """Calculate similarity score between target and element text."""
        if not target or not text:
            return 0.0
        
        # Simple word overlap scoring
        target_words = set(target.split())
        text_words = set(text.split())
        
        if not target_words:
            return 0.0
        
        # Check for exact substring match
        if target in text:
            return 0.9
        
        # Word overlap
        overlap = len(target_words & text_words)
        score = overlap / len(target_words)
        
        # Boost if all target words found
        if overlap == len(target_words):
            score = min(score + 0.2, 1.0)
        
        return score
    
    async def _build_selector(self, element: "IElement") -> str:
        """Build a CSS selector for an element."""
        # Try to get unique identifier
        elem_id = await element.get_attribute("id")
        if elem_id:
            return f"#{elem_id}"
        
        data_testid = await element.get_attribute("data-testid")
        if data_testid:
            return f"[data-testid='{data_testid}']"
        
        name = await element.get_attribute("name")
        if name:
            tag = await element.evaluate("el => el.tagName.toLowerCase()")
            return f"{tag}[name='{name}']"
        
        # Fallback: use text content
        text = await element.text_content()
        if text and len(text) < 50:
            return f"text='{text.strip()}'"
        
        # Last resort: nth-child selector
        # This is fragile but better than nothing
        return await element.evaluate("""el => {
            function getSelector(element) {
                if (element.id) return '#' + element.id;
                let path = [];
                while (element && element.nodeType === Node.ELEMENT_NODE) {
                    let selector = element.tagName.toLowerCase();
                    if (element.id) {
                        selector = '#' + element.id;
                        path.unshift(selector);
                        break;
                    }
                    let sibling = element;
                    let nth = 1;
                    while (sibling = sibling.previousElementSibling) {
                        if (sibling.tagName === element.tagName) nth++;
                    }
                    if (nth > 1) selector += ':nth-of-type(' + nth + ')';
                    path.unshift(selector);
                    element = element.parentNode;
                }
                return path.join(' > ');
            }
            return getSelector(el);
        }""")


async def resolve_multiple(
    resolver: TargetResolver,
    page: "IPage",
    targets: Dict[str, str],
    intent: Optional[str] = None,
) -> Dict[str, ResolvedTarget]:
    """
    Resolve multiple targets efficiently.
    
    Args:
        resolver: TargetResolver instance
        page: Browser page
        targets: Dict of name → target description
        intent: Optional intent hint
        
    Returns:
        Dict of name → ResolvedTarget
    """
    results = {}
    for name, target in targets.items():
        results[name] = await resolver.resolve(page, target, intent)
    return results
