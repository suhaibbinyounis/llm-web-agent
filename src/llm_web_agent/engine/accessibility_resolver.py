"""
Accessibility Resolver - Uses Playwright's built-in accessibility-first locators.

Inspired by Playwright MCP's approach of using the accessibility tree,
this resolver prioritizes stable, semantic locators over brittle CSS selectors.

Priority order:
1. data-testid (most stable, explicitly for testing)
2. ARIA role + name (semantic, framework-agnostic)
3. Label association (for form inputs)
4. Visible text content (user-facing, stable)
5. Placeholder text (for inputs)
6. CSS selectors (fallback only)

Key insight: Playwright's getByRole, getByLabel, getByText methods
internally use the accessibility tree, making them framework-agnostic.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from llm_web_agent.engine.task_planner import Locator, LocatorType, PlannedStep

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.engine.site_profiler import SiteProfile

logger = logging.getLogger(__name__)


@dataclass
class ResolutionResult:
    """Result of resolving an element."""
    success: bool
    locator: Any = None              # Playwright Locator object
    selector_used: Optional[str] = None
    locator_type: Optional[LocatorType] = None
    confidence: float = 0.0
    alternatives: List[str] = None   # Other selectors that worked
    
    def __post_init__(self):
        if self.alternatives is None:
            self.alternatives = []


class AccessibilityResolver:
    """
    Resolve elements using Playwright's accessibility-first locators.
    
    This is the primary resolution strategy. Uses:
    - getByTestId() for data-testid
    - getByRole() for ARIA roles
    - getByLabel() for form labels
    - getByText() for visible text
    - getByPlaceholder() for input placeholders
    
    Falls back to CSS/XPath only when accessibility methods fail.
    
    Usage:
        resolver = AccessibilityResolver()
        result = await resolver.resolve(page, step.locators, profile)
        if result.success:
            await result.locator.click()
    """
    
    # Timeout for each locator attempt (ms)
    LOCATOR_TIMEOUT_MS = 2000
    
    def __init__(self, enable_learning: bool = True):
        self._enable_learning = enable_learning
        # Cache of working selectors: (domain, target_hash) -> locator_type
        self._success_cache: Dict[str, LocatorType] = {}
    
    async def resolve(
        self,
        page: "IPage",
        locators: List[Locator],
        profile: Optional["SiteProfile"] = None,
        target_description: str = "",
    ) -> ResolutionResult:
        """
        Resolve element using multiple locator strategies.
        
        Args:
            page: Playwright page
            locators: List of Locator objects to try
            profile: Optional SiteProfile for priority ordering
            target_description: Human description (for caching)
            
        Returns:
            ResolutionResult with locator if found
        """
        if not locators:
            return ResolutionResult(success=False)
        
        # Reorder locators based on site profile and learning
        ordered = self._prioritize_locators(locators, profile, page.url, target_description)
        
        logger.debug(f"Resolving '{target_description}' with {len(ordered)} locators")
        
        alternatives = []
        
        for locator_spec in ordered:
            try:
                result = await self._try_locator(page, locator_spec)
                if result.success:
                    # Learn from success
                    self._record_success(page.url, target_description, locator_spec.type)
                    result.alternatives = alternatives
                    return result
                else:
                    alternatives.append(locator_spec.to_playwright())
            except Exception as e:
                logger.debug(f"Locator {locator_spec.type.value} failed: {e}")
                alternatives.append(locator_spec.to_playwright())
                continue
        
        logger.warning(f"All locators failed for '{target_description}'")
        return ResolutionResult(success=False, alternatives=alternatives)
    
    async def _try_locator(self, page: "IPage", locator_spec: Locator) -> ResolutionResult:
        """Try a single locator strategy."""
        
        loc_type = locator_spec.type
        value = locator_spec.value
        name = locator_spec.name
        
        try:
            locator = None
            selector_str = ""
            
            if loc_type == LocatorType.TESTID:
                locator = page.get_by_test_id(value)
                selector_str = f'getByTestId("{value}")'
                
            elif loc_type == LocatorType.ROLE:
                if name:
                    locator = page.get_by_role(value, name=name)
                    selector_str = f'getByRole("{value}", name="{name}")'
                else:
                    locator = page.get_by_role(value)
                    selector_str = f'getByRole("{value}")'
                    
            elif loc_type == LocatorType.LABEL:
                locator = page.get_by_label(value)
                selector_str = f'getByLabel("{value}")'
                
            elif loc_type == LocatorType.PLACEHOLDER:
                locator = page.get_by_placeholder(value)
                selector_str = f'getByPlaceholder("{value}")'
                
            elif loc_type == LocatorType.TEXT:
                if locator_spec.exact:
                    locator = page.get_by_text(value, exact=True)
                    selector_str = f'getByText("{value}", exact=True)'
                else:
                    locator = page.get_by_text(value)
                    selector_str = f'getByText("{value}")'
                    
            elif loc_type == LocatorType.ARIA:
                # Use attribute selector for aria-label
                locator = page.locator(f'[aria-label*="{value}" i]')
                selector_str = f'[aria-label*="{value}"]'
                
            elif loc_type == LocatorType.CSS:
                locator = page.locator(value)
                selector_str = value
                
            elif loc_type == LocatorType.XPATH:
                locator = page.locator(f'xpath={value}')
                selector_str = f'xpath={value}'
            
            if locator is None:
                return ResolutionResult(success=False)
            
            # Check if element exists and is visible
            count = await asyncio.wait_for(
                locator.count(),
                timeout=self.LOCATOR_TIMEOUT_MS / 1000
            )
            
            if count == 0:
                return ResolutionResult(success=False)
            
            # Get first visible element
            first = locator.first
            try:
                is_visible = await asyncio.wait_for(
                    first.is_visible(),
                    timeout=self.LOCATOR_TIMEOUT_MS / 1000
                )
                if not is_visible:
                    # Try to find any visible one
                    for i in range(min(count, 5)):
                        nth = locator.nth(i)
                        if await nth.is_visible():
                            first = nth
                            is_visible = True
                            break
            except:
                is_visible = True  # Assume visible if check fails
            
            if is_visible:
                logger.debug(f"Found element with {selector_str}")
                return ResolutionResult(
                    success=True,
                    locator=first,
                    selector_used=selector_str,
                    locator_type=loc_type,
                    confidence=self._get_confidence(loc_type),
                )
            
            return ResolutionResult(success=False)
            
        except asyncio.TimeoutError:
            return ResolutionResult(success=False)
        except Exception as e:
            logger.debug(f"Error trying {loc_type.value}: {e}")
            return ResolutionResult(success=False)
    
    def _prioritize_locators(
        self,
        locators: List[Locator],
        profile: Optional["SiteProfile"],
        url: str,
        target: str,
    ) -> List[Locator]:
        """Reorder locators based on profile and learning."""
        
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        cache_key = f"{domain}:{target.lower()}"
        
        # Check if we've learned what works for this target
        if cache_key in self._success_cache:
            learned_type = self._success_cache[cache_key]
            # Move learned type to front
            locators = sorted(
                locators,
                key=lambda l: 0 if l.type == learned_type else 1
            )
            return locators
        
        # Use site profile priorities if available
        if profile and profile.selector_priorities:
            type_to_priority = {
                'testid': LocatorType.TESTID,
                'role': LocatorType.ROLE,
                'label': LocatorType.LABEL,
                'placeholder': LocatorType.PLACEHOLDER,
                'text': LocatorType.TEXT,
                'aria': LocatorType.ARIA,
                'css': LocatorType.CSS,
            }
            
            priority_order = []
            for p in profile.selector_priorities:
                if p in type_to_priority:
                    priority_order.append(type_to_priority[p])
            
            def get_priority(loc: Locator) -> int:
                try:
                    return priority_order.index(loc.type)
                except ValueError:
                    return 999
            
            locators = sorted(locators, key=get_priority)
        
        return locators
    
    def _record_success(self, url: str, target: str, loc_type: LocatorType) -> None:
        """Record successful resolution for learning."""
        if not self._enable_learning:
            return
        
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        cache_key = f"{domain}:{target.lower()}"
        
        self._success_cache[cache_key] = loc_type
        logger.debug(f"Learned: '{target}' on {domain} uses {loc_type.value}")
    
    def _get_confidence(self, loc_type: LocatorType) -> float:
        """Get confidence score based on locator type."""
        confidence_map = {
            LocatorType.TESTID: 0.98,       # Most reliable
            LocatorType.ROLE: 0.95,         # Semantic, stable
            LocatorType.LABEL: 0.92,        # Form association
            LocatorType.ARIA: 0.90,         # Accessibility attribute
            LocatorType.PLACEHOLDER: 0.85,  # User-facing but changeable
            LocatorType.TEXT: 0.80,         # Could change with i18n
            LocatorType.CSS: 0.60,          # Brittle
            LocatorType.XPATH: 0.50,        # Most brittle
        }
        return confidence_map.get(loc_type, 0.5)
    
    async def resolve_with_fallback(
        self,
        page: "IPage",
        step: PlannedStep,
        profile: Optional["SiteProfile"] = None,
    ) -> ResolutionResult:
        """
        Resolve with additional fallback strategies.
        
        If initial resolution fails, tries:
        1. Fuzzy text matching
        2. Waiting for element to appear
        3. Scrolling to find element
        """
        # First try normal resolution
        result = await self.resolve(page, step.locators, profile, step.target)
        
        if result.success:
            return result
        
        # Fallback 1: Wait for element to appear (dynamic content)
        logger.debug(f"Trying wait fallback for '{step.target}'")
        for locator_spec in step.locators[:3]:  # Try first 3 only
            try:
                locator = self._build_locator(page, locator_spec)
                if locator:
                    await locator.wait_for(state="visible", timeout=3000)
                    if await locator.count() > 0:
                        return ResolutionResult(
                            success=True,
                            locator=locator.first,
                            selector_used=locator_spec.to_playwright(),
                            locator_type=locator_spec.type,
                            confidence=0.75,
                        )
            except:
                continue
        
        # Fallback 2: Try fuzzy text match
        logger.debug(f"Trying fuzzy match for '{step.target}'")
        fuzzy_result = await self._try_fuzzy_match(page, step.target)
        if fuzzy_result.success:
            return fuzzy_result
        
        return ResolutionResult(success=False, alternatives=result.alternatives)
    
    def _build_locator(self, page: "IPage", spec: Locator) -> Any:
        """Build Playwright locator from spec."""
        if spec.type == LocatorType.TESTID:
            return page.get_by_test_id(spec.value)
        elif spec.type == LocatorType.ROLE:
            return page.get_by_role(spec.value, name=spec.name) if spec.name else page.get_by_role(spec.value)
        elif spec.type == LocatorType.TEXT:
            return page.get_by_text(spec.value)
        elif spec.type == LocatorType.LABEL:
            return page.get_by_label(spec.value)
        elif spec.type == LocatorType.PLACEHOLDER:
            return page.get_by_placeholder(spec.value)
        elif spec.type in (LocatorType.CSS, LocatorType.ARIA):
            return page.locator(spec.value)
        return None
    
    async def _try_fuzzy_match(self, page: "IPage", target: str) -> ResolutionResult:
        """Try fuzzy matching as last resort."""
        # Use case-insensitive partial text match
        words = target.lower().split()
        
        for word in words:
            if len(word) < 3:
                continue
            try:
                # Try partial text match
                locator = page.locator(f'text=/{word}/i')
                count = await locator.count()
                
                if 0 < count <= 5:  # Reasonable number of matches
                    for i in range(count):
                        elem = locator.nth(i)
                        if await elem.is_visible():
                            # Verify it's interactive
                            tag = await elem.evaluate('el => el.tagName.toLowerCase()')
                            if tag in ('button', 'a', 'input', 'select', 'textarea'):
                                return ResolutionResult(
                                    success=True,
                                    locator=elem,
                                    selector_used=f'text=/{word}/i',
                                    locator_type=LocatorType.TEXT,
                                    confidence=0.5,
                                )
            except:
                continue
        
        return ResolutionResult(success=False)


# Module-level singleton
_resolver: Optional[AccessibilityResolver] = None


def get_accessibility_resolver() -> AccessibilityResolver:
    """Get or create the global accessibility resolver."""
    global _resolver
    if _resolver is None:
        _resolver = AccessibilityResolver()
    return _resolver
