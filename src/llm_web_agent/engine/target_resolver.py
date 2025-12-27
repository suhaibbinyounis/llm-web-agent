"""
Target Resolver - Multi-Strategy Element Resolution.

Strategies (tried in order):
1. DIRECT - If target looks like a selector, use it
2. TEXT_FIRST - Find text on page, climb to clickable parent (human-like)
3. PLAYWRIGHT_TEXT - Use Playwright's built-in text= selector
4. SMART_SELECTORS - Try various selector patterns
5. INTERACTIVE_SEARCH - Score all visible interactive elements
6. DYNAMIC - Wait for elements that appear after interaction
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import asyncio
import re
import time
import logging

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage, IElement
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


class ResolutionStrategy(Enum):
    """Which strategy resolved the target."""
    DIRECT = "direct"           # Direct CSS selector
    TEXT_FIRST = "text_first"   # Human-like text search
    PLAYWRIGHT = "playwright"   # Playwright text= selector
    SMART = "smart"             # Pattern-based selectors
    FUZZY = "fuzzy"             # Interactive element search
    DYNAMIC = "dynamic"         # Wait for dynamic elements (dropdowns, modals)
    FAILED = "failed"
    # Backwards compatibility aliases
    EXACT = "direct"
    TEXT = "text_first"


# Backwards compatibility alias - tests use ResolutionLayer
ResolutionLayer = ResolutionStrategy


@dataclass
class ResolvedTarget:
    """A resolved target element."""
    selector: str
    element: Optional["IElement"] = None
    strategy: ResolutionStrategy = ResolutionStrategy.DIRECT
    confidence: float = 1.0
    alternatives: List[str] = field(default_factory=list)
    
    # Backwards compatibility
    @property
    def layer(self):
        return self.strategy
    
    @property
    def is_resolved(self) -> bool:
        return self.strategy != ResolutionStrategy.FAILED and bool(self.selector)


# JavaScript for text-first element finding
TEXT_FIRST_JS = r'''
(searchText) => {
    const results = [];
    searchText = searchText.toLowerCase().trim();
    
    // Helper: Check if element is visible
    function isVisible(el) {
        if (!el) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none') return false;
        if (style.visibility === 'hidden') return false;
        if (style.opacity === '0') return false;
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return false;
        if (rect.top > window.innerHeight || rect.bottom < 0) return false;
        if (rect.left > window.innerWidth || rect.right < 0) return false;
        return true;
    }
    
    // Helper: Check if element is truly clickable (semantic elements only)
    function isClickable(el) {
        if (!el) return false;
        const tag = el.tagName.toLowerCase();
        // Priority: actual clickable elements
        if (['a', 'button'].includes(tag)) return true;
        if (tag === 'input' && ['submit', 'button', 'reset'].includes(el.type)) return true;
        if (el.getAttribute('role') === 'button') return true;
        if (el.getAttribute('role') === 'link') return true;
        if (el.onclick) return true;
        return false;
    }
    
    // Check if probably clickable (includes cursor:pointer)
    function isProbablyClickable(el) {
        if (isClickable(el)) return true;
        if (el.getAttribute('tabindex') !== null) return true;
        const style = window.getComputedStyle(el);
        if (style.cursor === 'pointer') return true;
        return false;
    }
    
    // Check if element is a code/text editing container (should be skipped for clicks)
    // Uses both structural (tag/class) and semantic (content pattern) detection
    function isCodeContainer(el) {
        if (!el) return false;
        const tag = el.tagName.toLowerCase();
        
        // Structural: Known code container tags
        if (['textarea', 'pre', 'code'].includes(tag)) return true;
        
        // Structural: Known code editor class names
        if (el.className && typeof el.className === 'string') {
            const cls = el.className.toLowerCase();
            const codeClasses = ['code', 'editor', 'syntax', 'highlight', 'prism', 'monaco', 
                                 'codemirror', 'ace_', 'hljs', 'shiki', 'codeblock'];
            if (codeClasses.some(c => cls.includes(c))) return true;
        }
        
        // Structural: Contenteditable code blocks
        if (el.getAttribute('contenteditable') === 'true') return true;
        if (el.getAttribute('data-language')) return true;
        if (el.getAttribute('data-code')) return true;
        
        // Semantic: Check if content looks like code
        const text = el.innerText || '';
        if (text.length > 30 && text.length < 5000) {
            const codePatterns = [
                /^\s*(import|from|const|let|var|function|class|def|return|export)\s/m,
                /[{}\[\]();=]\s*$/m,  // Ends with code punctuation
                /<[A-Z][a-zA-Z]+\s/,  // JSX/React components
                /\.(map|filter|reduce|forEach|then|catch)\(/,  // JS methods
                /=>\s*{/,  // Arrow functions
                /^\s*@\w+/m,  // Decorators
                /^\s*(public|private|protected)\s/m,  // Class members
            ];
            const matchCount = codePatterns.filter(p => p.test(text)).length;
            if (matchCount >= 2) return true;  // Multiple code patterns = likely code
        }
        
        return false;
    }
    
    // Helper: Find clickable ancestor - prioritize <a> and <button>
    function findClickableAncestor(el) {
        let current = el;
        let fallback = null;
        
        while (current && current !== document.body) {
            // Skip code containers - they should not be clicked
            if (isCodeContainer(current)) {
                return null;  // Don't click into code editors/blocks
            }
            if (isClickable(current) && isVisible(current)) {
                return current;  // Found a true clickable
            }
            // Save first "probably clickable" as fallback
            if (!fallback && isProbablyClickable(current) && isVisible(current)) {
                fallback = current;
            }
            current = current.parentElement;
        }
        return fallback;  // Return fallback if no true clickable found
    }
    
    // Helper: Build unique selector
    function buildSelector(el) {
        if (el.id) return '#' + CSS.escape(el.id);
        
        // Try data-testid
        const testId = el.getAttribute('data-testid');
        if (testId) return `[data-testid="${testId}"]`;
        
        // Try unique class combo
        if (el.className && typeof el.className === 'string') {
            const classes = el.className.split(' ').filter(c => c.length > 0);
            if (classes.length > 0) {
                const selector = el.tagName.toLowerCase() + '.' + classes.slice(0, 2).join('.');
                if (document.querySelectorAll(selector).length === 1) {
                    return selector;
                }
            }
        }
        
        // Use nth-child path
        function getPath(el) {
            if (el.id) return '#' + CSS.escape(el.id);
            if (!el.parentElement) return el.tagName.toLowerCase();
            const siblings = Array.from(el.parentElement.children);
            const index = siblings.indexOf(el) + 1;
            return getPath(el.parentElement) + ' > ' + el.tagName.toLowerCase() + ':nth-child(' + index + ')';
        }
        return getPath(el);
    }
    
    // Calculate match score
    function scoreMatch(text, search) {
        text = text.toLowerCase().trim();
        if (text === search) return 1.0;
        if (text.includes(search)) return 0.9;
        if (search.includes(text) && text.length > 2) return 0.8;
        
        // Word matching
        const searchWords = search.split(/\s+/);
        const textWords = text.split(/\s+/);
        const matchedWords = searchWords.filter(w => textWords.some(tw => tw.includes(w)));
        if (matchedWords.length === searchWords.length) return 0.85;
        if (matchedWords.length > 0) return 0.5 + (matchedWords.length / searchWords.length) * 0.3;
        
        return 0;
    }
    
    // Walk all text nodes
    const walker = document.createTreeWalker(
        document.body,
        NodeFilter.SHOW_TEXT,
        null,
        false
    );
    
    const seen = new Set();
    
    while (walker.nextNode()) {
        const textNode = walker.currentNode;
        const text = textNode.textContent.trim();
        if (!text) continue;
        
        const score = scoreMatch(text, searchText);
        if (score >= 0.5) {
            // Find clickable parent
            const clickable = findClickableAncestor(textNode.parentElement);
            if (clickable && !seen.has(clickable)) {
                seen.add(clickable);
                const selector = buildSelector(clickable);
                results.push({
                    selector: selector,
                    text: text,
                    score: score,
                    tag: clickable.tagName.toLowerCase()
                });
            }
        }
    }
    
    // Also check aria-labels and titles
    document.querySelectorAll('[aria-label], [title], [placeholder]').forEach(el => {
        if (seen.has(el)) return;
        const ariaLabel = (el.getAttribute('aria-label') || '').toLowerCase();
        const title = (el.getAttribute('title') || '').toLowerCase();
        const placeholder = (el.getAttribute('placeholder') || '').toLowerCase();
        
        const score = Math.max(
            scoreMatch(ariaLabel, searchText),
            scoreMatch(title, searchText),
            scoreMatch(placeholder, searchText)
        );
        
        if (score >= 0.5 && isVisible(el)) {
            const clickable = isClickable(el) ? el : findClickableAncestor(el);
            if (clickable && !seen.has(clickable)) {
                seen.add(clickable);
                results.push({
                    selector: buildSelector(clickable),
                    text: ariaLabel || title || placeholder,
                    score: score,
                    tag: clickable.tagName.toLowerCase()
                });
            }
        }
    });
    
    // Sort by score descending
    results.sort((a, b) => b.score - a.score);
    
    return results.slice(0, 5);  // Return top 5 matches
}
'''


class TargetResolver:
    """
    Multi-strategy element resolution.
    
    Tries multiple approaches to find elements:
    0. DOMMap lookup (O(1) real-time registry) - NEW
    1. Direct selector (if target looks like CSS/XPath)
    2. Text-first search (human-like: find text, climb to clickable)
    3. Playwright text selector
    4. Smart pattern selectors
    5. Fuzzy interactive element search
    6. Dynamic element waiting (for dropdowns, modals)
    
    Includes:
    - DOMMap for O(1) multi-index lookups (text, aria, role, testid, etc.)
    - Parallel strategy execution for speed
    - Strategy success tracking for adaptive ordering
    - Exponential backoff for dynamic elements
    - Fingerprint-based stable element identification
    """
    
    def __init__(
        self,
        llm_provider: Optional["ILLMProvider"] = None,
        fuzzy_threshold: float = 0.5,
        enable_tracking: bool = True,
        enable_indexing: bool = True,
        enable_dom_map: bool = True,
    ):
        self._llm = llm_provider
        self._fuzzy_threshold = fuzzy_threshold
        self._enable_tracking = enable_tracking
        self._enable_indexing = enable_indexing
        self._enable_dom_map = enable_dom_map
        self._tracker = None
        self._text_index = None
        self._dom_map = None
        
        # Pre-analysis hints (set by Engine before resolution)
        self._synonyms: Dict[str, List[str]] = {}
        self._selector_hints: List[str] = []
        
        if enable_tracking:
            try:
                from llm_web_agent.engine.strategy_tracker import get_tracker
                self._tracker = get_tracker()
            except ImportError:
                logger.debug("Strategy tracker not available")
        
        if enable_indexing:
            try:
                from llm_web_agent.engine.text_index import TextIndex
                self._text_index = TextIndex()
            except ImportError:
                logger.debug("Text index not available")
        
        if enable_dom_map:
            try:
                from llm_web_agent.engine.dom_map import DOMMap
                self._dom_map = DOMMap()
            except ImportError:
                logger.debug("DOMMap not available")
    
    def set_hints(self, synonyms: Dict[str, List[str]] = None, selector_hints: List[str] = None):
        """
        Set pre-analysis hints for target resolution.
        
        These hints augment resolution without overriding user intent.
        
        Args:
            synonyms: Map of target -> [synonym1, synonym2, ...]
            selector_hints: List of CSS selectors to try
        """
        if synonyms:
            self._synonyms = synonyms
            logger.debug(f"Set {sum(len(s) for s in synonyms.values())} synonyms for {len(synonyms)} targets")
        if selector_hints:
            self._selector_hints = selector_hints
            logger.debug(f"Set {len(selector_hints)} selector hints")
    
    def clear_hints(self):
        """Clear pre-analysis hints."""
        self._synonyms = {}
        self._selector_hints = []
    
    async def resolve(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str] = None,
        dom: Optional[Any] = None,
        wait_timeout: int = 3000,  # Add timeout parameter for dynamic elements
        parallel: bool = True,  # Use parallel resolution for speed
    ) -> ResolvedTarget:
        """
        Resolve target to selector using multiple strategies.
        
        Args:
            page: Browser page
            target: Element to find (text or selector)
            intent: Action intent (click, fill, etc.)
            dom: Optional pre-parsed DOM
            wait_timeout: Timeout in ms to wait for dynamic elements (for dropdown menus, modals)
            parallel: If True, race fast strategies in parallel for speed
        """
        target = target.strip()
        
        if not target:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        start_time = time.time()
        
        # Extract hints if present: "click cart [hints: #shopping_cart, .cart]"
        # The instruction normalizer embeds these for smarter resolution
        hints: List[str] = []
        hint_match = re.search(r'\s*\[hints?:\s*(.+?)\]$', target, re.I)
        if hint_match:
            hints_str = hint_match.group(1)
            hints = [h.strip() for h in hints_str.split(',') if h.strip()]
            target = target[:hint_match.start()].strip()
            logger.debug(f"Extracted hints for '{target}': {hints}")
        
        # Strategy -1: TRY HINTS FIRST (provided by LLM normalizer)
        if hints:
            for hint in hints:
                try:
                    # If hint looks like a selector, try it directly
                    if hint.startswith('#') or hint.startswith('.') or hint.startswith('[') or '=' in hint:
                        element = await page.query_selector(hint)
                        if element and await element.is_visible():
                            elapsed = (time.time() - start_time) * 1000
                            logger.info(f"HINT found '{target}' with: {hint} ({elapsed:.0f}ms)")
                            return ResolvedTarget(
                                selector=hint,
                                element=element,
                                strategy=ResolutionStrategy.EXACT,
                                confidence=0.95,
                            )
                    else:
                        # Treat as text to match (aria-label, text content, id, name)
                        for selector in [
                            f'[id*="{hint}" i]',
                            f'[name*="{hint}" i]',
                            f'[aria-label*="{hint}" i]',
                            f'[data-test*="{hint}" i]',
                            f':text("{hint}")',
                        ]:
                            try:
                                element = await page.query_selector(selector)
                                if element and await element.is_visible():
                                    elapsed = (time.time() - start_time) * 1000
                                    logger.info(f"HINT found '{target}' with: {selector} ({elapsed:.0f}ms)")
                                    return ResolvedTarget(
                                        selector=selector,
                                        element=element,
                                        strategy=ResolutionStrategy.SMART,
                                        confidence=0.9,
                                    )
                            except Exception:
                                continue
                except Exception as e:
                    logger.debug(f"Hint '{hint}' failed: {e}")
                    continue
        
        # Check for spatial reference (e.g., "Submit near Email")
        # Use DOMMap for spatial queries if available
        spatial_match = re.search(r'(.+?)\s+(?:near|next to|close to|beside)\s+(.+)', target, re.I)
        if spatial_match:
            target_text = spatial_match.group(1).strip()
            ref_text = spatial_match.group(2).strip()
            
            # Try DOMMap spatial first (more accurate)
            if self._dom_map:
                result = await self._try_dom_map_spatial(page, target_text, ref_text)
                if result.is_resolved:
                    self._record_outcome(domain, "dom_map_spatial", True, start_time)
                    elapsed = (time.time() - start_time) * 1000
                    logger.info(f"DOMMAP_SPATIAL found '{target_text}' near '{ref_text}' with: {result.selector} ({elapsed:.0f}ms)")
                    return result
            
            # Fallback to text_index spatial
            if self._text_index:
                result = await self._try_spatial_match(page, target_text, ref_text)
                if result.is_resolved:
                    self._record_outcome(domain, "spatial", True, start_time)
                    logger.info(f"SPATIAL found '{target_text}' near '{ref_text}' with: {result.selector}")
                    return result
        
        # Extract domain for tracking
        domain = None
        if self._tracker:
            try:
                from urllib.parse import urlparse
                domain = urlparse(page.url).netloc
            except Exception:
                pass
        
        # Strategy 0: DOMMap lookup (O(1) real-time registry) - FASTEST
        if self._dom_map:
            result = await self._try_dom_map(page, target, intent)
            if result.is_resolved:
                self._record_outcome(domain, "dom_map", True, start_time)
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"DOMMAP found '{target}' with: {result.selector} ({elapsed:.0f}ms)")
                return result
        
        # Strategy 1: Direct selector (always first, very fast)
        if self._is_selector(target):
            result = await self._try_direct_selector(page, target)
            if result.is_resolved:
                self._record_outcome(domain, "direct", True, start_time)
                return result
        
        # Strategy 1.5: Text index fast-path (O(1) lookup) - legacy fallback
        if self._text_index:
            result = await self._try_text_index(page, target, intent)
            if result.is_resolved:
                self._record_outcome(domain, "index", True, start_time)
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"INDEX found '{target}' with: {result.selector} ({elapsed:.0f}ms)")
                return result
        
        if parallel:
            # Run fast strategies in parallel - return first success
            result = await self._resolve_parallel(page, target, intent, domain)
            if result.is_resolved:
                elapsed = (time.time() - start_time) * 1000
                logger.info(f"{result.strategy.value.upper()} found '{target}' with: {result.selector} ({elapsed:.0f}ms)")
                return result
        else:
            # Sequential fallback
            result = await self._resolve_sequential(page, target, intent, domain)
            if result.is_resolved:
                return result
        
        # Slower strategies (always sequential)
        
        # Strategy 4.5: Try synonyms from pre-analysis (before fuzzy)
        if self._synonyms:
            synonym_start = time.time()
            result = await self._try_synonyms(page, target, intent)
            if result.is_resolved:
                self._record_outcome(domain, "synonym", True, synonym_start)
                logger.info(f"SYNONYM found '{target}' with: {result.selector}")
                return result
            self._record_outcome(domain, "synonym", False, synonym_start)
        
        # Strategy 4.6: Accessibility attributes (name, id, placeholder, aria-label)
        access_start = time.time()
        result = await self._try_accessibility(page, target, intent)
        if result.is_resolved:
            self._record_outcome(domain, "accessibility", True, access_start)
            logger.info(f"ACCESSIBILITY found '{target}' with: {result.selector}")
            return result
        self._record_outcome(domain, "accessibility", False, access_start)
        
        # Strategy 4.7: Form field by label association
        form_start = time.time()
        result = await self._try_form_field(page, target, intent)
        if result.is_resolved:
            self._record_outcome(domain, "form_field", True, form_start)
            logger.info(f"FORM_FIELD found '{target}' with: {result.selector}")
            return result
        self._record_outcome(domain, "form_field", False, form_start)
        
        # Strategy 5: Fuzzy search all interactive elements
        fuzzy_start = time.time()
        result = await self._try_fuzzy_search(page, target, intent)
        if result.is_resolved:
            self._record_outcome(domain, "fuzzy", True, fuzzy_start)
            logger.info(f"FUZZY found '{target}' with: {result.selector}") 
            return result
        self._record_outcome(domain, "fuzzy", False, fuzzy_start)
        
        # Strategy 6: WAIT for dynamic elements (dropdowns, modals, popovers)
        # This waits for elements that might appear after an interaction
        dynamic_start = time.time()
        result = await self._try_wait_for_dynamic(page, target, intent, wait_timeout)
        if result.is_resolved:
            self._record_outcome(domain, "dynamic", True, dynamic_start)
            logger.info(f"DYNAMIC found '{target}' with: {result.selector}")
            return result
        self._record_outcome(domain, "dynamic", False, dynamic_start)
        
        # Strategy 7: LLM DISAMBIGUATION (adaptive fallback)
        # Uses LLM only when severity is high enough
        if self._llm:
            llm_start = time.time()
            result = await self._try_llm_disambiguation(page, target, intent)
            if result.is_resolved:
                self._record_outcome(domain, "llm", True, llm_start)
                logger.info(f"LLM found '{target}' with: {result.selector}")
                return result
            self._record_outcome(domain, "llm", False, llm_start)
        
        logger.warning(f"Could not resolve: {target}")
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    def _record_outcome(
        self,
        domain: Optional[str],
        strategy: str,
        success: bool,
        start_time: float,
    ) -> None:
        """Record strategy outcome for adaptive learning."""
        if not self._tracker or not domain:
            return
        elapsed_ms = (time.time() - start_time) * 1000
        try:
            self._tracker.record(domain, strategy, success, elapsed_ms)
        except Exception as e:
            logger.debug(f"Failed to record strategy outcome: {e}")
    
    async def _resolve_parallel(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str],
        domain: Optional[str] = None,
    ) -> ResolvedTarget:
        """
        Run fast strategies in parallel and return first success.
        This is much faster when the first strategy would fail.
        """
        start_times = {}
        
        # Create tasks for parallel execution
        async def timed_strategy(name: str, coro):
            start_times[name] = time.time()
            return await coro
        
        tasks = [
            asyncio.create_task(
                timed_strategy("text_first", self._try_text_first(page, target, intent)),
                name="text_first"
            ),
            asyncio.create_task(
                timed_strategy("playwright", self._try_playwright_text(page, target, intent)),
                name="playwright"
            ),
            asyncio.create_task(
                timed_strategy("smart", self._try_smart_selectors(page, target, intent)),
                name="smart"
            ),
        ]
        
        # Track which strategies completed
        completed_strategies = set()
        winning_strategy = None
        
        # Wait for first success or all to complete
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            
            for task in done:
                strategy_name = task.get_name()
                completed_strategies.add(strategy_name)
                try:
                    result = task.result()
                    if result.is_resolved:
                        winning_strategy = strategy_name
                        # Record success
                        self._record_outcome(domain, strategy_name, True, start_times.get(strategy_name, time.time()))
                        # Cancel remaining tasks
                        for p in pending:
                            p.cancel()
                            # Record incomplete as failed (they didn't find it first)
                            self._record_outcome(domain, p.get_name(), False, start_times.get(p.get_name(), time.time()))
                        return result
                    else:
                        # Strategy completed but didn't find element
                        self._record_outcome(domain, strategy_name, False, start_times.get(strategy_name, time.time()))
                except Exception as e:
                    logger.debug(f"Strategy {strategy_name} failed: {e}")
                    self._record_outcome(domain, strategy_name, False, start_times.get(strategy_name, time.time()))
                    continue
        
        # All parallel strategies failed
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _resolve_sequential(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str],
        domain: Optional[str] = None,
    ) -> ResolvedTarget:
        """Sequential resolution (fallback mode)."""
        # Strategy 2: Text-first (human-like)
        start = time.time()
        result = await self._try_text_first(page, target, intent)
        if result.is_resolved:
            self._record_outcome(domain, "text_first", True, start)
            logger.info(f"TEXT_FIRST found '{target}' with: {result.selector}")
            return result
        self._record_outcome(domain, "text_first", False, start)
        
        # Strategy 3: Playwright text selector
        start = time.time()
        result = await self._try_playwright_text(page, target, intent)
        if result.is_resolved:
            self._record_outcome(domain, "playwright", True, start)
            logger.info(f"PLAYWRIGHT found '{target}' with: {result.selector}")
            return result
        self._record_outcome(domain, "playwright", False, start)
        
        # Strategy 4: Smart selectors based on intent
        start = time.time()
        result = await self._try_smart_selectors(page, target, intent)
        if result.is_resolved:
            self._record_outcome(domain, "smart", True, start)
            logger.info(f"SMART found '{target}' with: {result.selector}")
            return result
        self._record_outcome(domain, "smart", False, start)
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    def _is_selector(self, target: str) -> bool:
        """Check if target looks like a CSS selector."""
        return (
            target.startswith(("#", ".", "[", "//")) or
            "::" in target or
            ">" in target or
            ("]" in target and "[" in target)
        )
    
    async def _try_direct_selector(self, page: "IPage", selector: str) -> ResolvedTarget:
        """Try using target directly as a selector."""
        try:
            element = await page.query_selector(selector)
            if element and await self._is_visible(element):
                return ResolvedTarget(
                    selector=selector,
                    element=element,
                    strategy=ResolutionStrategy.DIRECT,
                    confidence=1.0,
                )
        except Exception:
            pass
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_dom_map(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str] = None,
    ) -> ResolvedTarget:
        """
        Try to resolve using DOMMap (O(1) multi-index lookup).
        
        This is the fastest resolution strategy, using pre-built indexes
        for text, aria-label, data-testid, role, and placeholder.
        """
        if not self._dom_map:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Build or refresh DOMMap if needed
        if not self._dom_map.is_for_url(page.url) or self._dom_map.is_stale():
            await self._dom_map.build(page)
        
        # Use DOMMap's universal find method
        elements = self._dom_map.find(target, intent=intent)
        
        if not elements:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Verify candidates and return first visible match
        for dom_elem in elements:
            try:
                # Try each selector in priority order
                for selector in dom_elem.selectors:
                    element = await page.query_selector(selector)
                    if element and await self._is_visible(element):
                        return ResolvedTarget(
                            selector=selector,
                            element=element,
                            strategy=ResolutionStrategy.DIRECT,  # Effectively a direct hit
                            confidence=0.98,
                            alternatives=[s for s in dom_elem.selectors if s != selector][:3],
                        )
            except Exception:
                continue
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_dom_map_spatial(
        self,
        page: "IPage",
        target_text: str,
        reference_text: str,
    ) -> ResolvedTarget:
        """
        Resolve target using DOMMap spatial index.
        
        Finds element with target_text that is closest to reference_text element.
        """
        if not self._dom_map:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Build or refresh DOMMap if needed
        if not self._dom_map.is_for_url(page.url) or self._dom_map.is_stale():
            await self._dom_map.build(page)
        
        # Use spatial query
        match = self._dom_map.find_near(target_text, reference_text)
        
        if not match:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Verify the match
        for selector in match.selectors:
            try:
                element = await page.query_selector(selector)
                if element and await self._is_visible(element):
                    return ResolvedTarget(
                        selector=selector,
                        element=element,
                        strategy=ResolutionStrategy.SMART,  # Spatial is smart
                        confidence=0.90,
                    )
            except Exception:
                continue
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_text_index(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str] = None
    ) -> ResolvedTarget:
        """Try to resolve using pre-built text index (O(1))."""
        if not self._text_index:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Build index if needed
        if self._text_index.built_at_url != page.url or self._text_index.is_stale():
            await self._text_index.build(page)
        
        # Look for match
        elements = self._text_index.find_phrase(target)
        if not elements:
            # Fallback: simple case-insensitive word match if target is single word
            if " " not in target.strip():
                elements = self._text_index.find_word(target)
        
        if not elements:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Iterate candidates and verify visibility
        for indexed_elem in elements:
            try:
                # If intent is click, skip non-clickable unless it's the only match
                if intent in ('click', 'press', 'tap') and not indexed_elem.is_clickable and len(elements) > 1:
                    continue
                
                element = await page.query_selector(indexed_elem.selector)
                if element and await self._is_visible(element):
                    return ResolvedTarget(
                        selector=indexed_elem.selector,
                        element=element,
                        strategy=ResolutionStrategy.DIRECT, # It's effectively a direct hit
                        confidence=0.95,
                    )
            except Exception:
                continue
                
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_spatial_match(
        self,
        page: "IPage",
        target_text: str,
        reference_text: str,
    ) -> ResolvedTarget:
        """Resolve target based on spatial proximity to reference."""
        if not self._text_index:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Ensure index is up to date
        if self._text_index.built_at_url != page.url or self._text_index.is_stale():
            await self._text_index.build(page)
        
        # 1. Find reference element
        ref_elements = self._text_index.find_phrase(reference_text)
        if not ref_elements:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Use first visible reference for now
        # TODO: Handle multiple references better
        reference_selector = ref_elements[0].selector
        
        # 2. Find target near reference
        match = self._text_index.find_near(target_text, reference_selector)
        
        if match:
            try:
                element = await page.query_selector(match.selector)
                if element and await self._is_visible(element):
                    return ResolvedTarget(
                        selector=match.selector,
                        element=element,
                        strategy=ResolutionStrategy.SMART, # Spatial is a smart capability
                        confidence=0.85,
                    )
            except Exception:
                pass
                
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_text_first(self, page: "IPage", target: str, intent: Optional[str]) -> ResolvedTarget:
        """
        Human-like text search.
        
        1. Execute JS to find all text matching target
        2. Climb to clickable parent
        3. Return best match
        """
        try:
            # Execute the text-first JavaScript
            results = await page.evaluate(TEXT_FIRST_JS, target)
            
            if results and len(results) > 0:
                best = results[0]
                
                # For input intents, prefer input elements
                if intent in ("fill", "type"):
                    for r in results:
                        if r.get("tag") in ("input", "textarea", "select"):
                            best = r
                            break
                
                # Verify the element exists
                element = await page.query_selector(best["selector"])
                if element:
                    return ResolvedTarget(
                        selector=best["selector"],
                        element=element,
                        strategy=ResolutionStrategy.TEXT_FIRST,
                        confidence=best["score"],
                        alternatives=[r["selector"] for r in results[1:]],
                    )
        except Exception as e:
            logger.debug(f"Text-first search error: {e}")
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_playwright_text(self, page: "IPage", target: str, intent: Optional[str]) -> ResolvedTarget:
        """Use Playwright's built-in text matching."""
        
        # For fill/type, skip text selectors (need input elements)
        if intent in ("fill", "type"):
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        # Try various text patterns (most specific first)
        selectors = [
            f'text="{target}"',       # Exact match
            f'text={target}',          # Case-insensitive substring
        ]
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await self._is_visible(element):
                    return ResolvedTarget(
                        selector=selector,
                        element=element,
                        strategy=ResolutionStrategy.PLAYWRIGHT,
                        confidence=0.85,
                    )
            except Exception:
                continue
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_smart_selectors(self, page: "IPage", target: str, intent: Optional[str]) -> ResolvedTarget:
        """Try smart selectors based on intent."""
        
        selectors = self._build_smart_selectors(target, intent)
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await self._is_visible(element):
                    return ResolvedTarget(
                        selector=selector,
                        element=element,
                        strategy=ResolutionStrategy.SMART,
                        confidence=0.8,
                    )
            except Exception:
                continue
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    def _build_smart_selectors(self, target: str, intent: Optional[str]) -> List[str]:
        """Build smart selectors based on target and intent."""
        selectors = []
        clean = target.lower().strip()
        core = self._extract_core_text(target)
        
        # For input actions, prioritize input elements
        if intent in ("fill", "type"):
            selectors.extend([
                f'input[placeholder*="{core}" i]',
                f'input[aria-label*="{core}" i]',
                f'input[name*="{core}" i]',
                f'textarea[placeholder*="{core}" i]',
                'input[type="search"]',
                'input[type="text"]',
                '#searchInput',
                'input[name="q"]',
                '[role="searchbox"]',
            ])
        
        # For click actions
        if intent in ("click", None):
            selectors.extend([
                f'button:has-text("{core}")',
                f'a:has-text("{core}")',
                f'[role="button"]:has-text("{core}")',
                f'[role="link"]:has-text("{core}")',
            ])
        
        # Attribute-based
        selectors.extend([
            f'[aria-label*="{core}" i]',
            f'[title*="{core}" i]',
            f'#{core.replace(" ", "-")}',
            f'#{core.replace(" ", "_")}',
        ])
        
        return selectors
    
    def _extract_core_text(self, target: str) -> str:
        """Extract core text, removing noise words."""
        noise = {"the", "a", "an", "button", "link", "input", "field", "click", "on", "in"}
        words = [w for w in target.lower().split() if w not in noise]
        return " ".join(words) if words else target.lower()
    
    async def _try_synonyms(self, page: "IPage", target: str, intent: Optional[str]) -> ResolvedTarget:
        """
        Try pre-analyzed synonyms to find the target element.
        
        This runs BEFORE fuzzy matching and uses LLM-generated synonyms
        that respect the user's original intent.
        """
        target_lower = target.lower()
        
        # Find synonyms for this target
        synonyms = []
        for key, syns in self._synonyms.items():
            if key.lower() == target_lower or target_lower in key.lower():
                synonyms.extend(syns)
        
        if not synonyms:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        logger.debug(f"Trying {len(synonyms)} synonyms for '{target}': {synonyms[:3]}...")
        
        for synonym in synonyms:
            # Try TEXT_FIRST strategy with synonym
            result = await self._try_text_first(page, synonym)
            if result.is_resolved:
                logger.debug(f"Synonym '{synonym}' matched")
                return ResolvedTarget(
                    selector=result.selector,
                    element=result.element,
                    strategy=ResolutionStrategy.TEXT_FIRST,  # Keep original strategy
                    confidence=0.9,  # High confidence for synonym match
                )
            
            # Try Playwright text selector with synonym
            result = await self._try_playwright_text(page, synonym)
            if result.is_resolved:
                logger.debug(f"Synonym '{synonym}' matched via Playwright")
                return ResolvedTarget(
                    selector=result.selector,
                    element=result.element,
                    strategy=ResolutionStrategy.PLAYWRIGHT,
                    confidence=0.85,
                )
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_accessibility(self, page: "IPage", target: str, intent: Optional[str]) -> ResolvedTarget:
        """
        Find elements using accessibility attributes.
        
        This is excellent for forms because most inputs have:
        - name, id, placeholder, aria-label attributes
        
        Matches target against these attributes.
        """
        target_lower = target.lower().strip()
        
        # Extract key words from target
        keywords = [w for w in target_lower.split() if len(w) > 2]
        
        # Selectors to try based on accessibility
        selectors = [
            # Exact matches
            f'[name="{target}"]',
            f'[id="{target}"]',
            f'[placeholder="{target}"]',
            f'[aria-label="{target}"]',
            f'[data-testid="{target}"]',
            f'[data-test="{target}"]',  # saucedemo uses this
            # Case-insensitive partial matches
            f'[name*="{target_lower}" i]',
            f'[id*="{target_lower}" i]',
            f'[placeholder*="{target_lower}" i]',
            f'[aria-label*="{target_lower}" i]',
            f'[data-test*="{target_lower}" i]',
        ]
        
        # Add keyword-based selectors
        for kw in keywords[:3]:  # Limit to 3 keywords
            selectors.extend([
                f'[name*="{kw}" i]',
                f'[id*="{kw}" i]',
                f'[placeholder*="{kw}" i]',
            ])
        
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    final_selector = await self._build_element_selector(element)
                    return ResolvedTarget(
                        selector=final_selector or selector,
                        element=element,
                        strategy=ResolutionStrategy.SMART,
                        confidence=0.85,
                    )
            except Exception:
                continue
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_form_field(self, page: "IPage", target: str, intent: Optional[str]) -> ResolvedTarget:
        """
        Find form fields by associated labels or nearby text.
        
        Uses FormHandler for smart field matching:
        - Label text association
        - Placeholder matching  
        - Name/ID attribute matching
        - Fuzzy text matching
        
        For targets like:
        - "username field" -> find input near "username" text
        - "email" -> find label[for] or input with matching id
        - "first name" -> match against label "First Name"
        """
        target_lower = target.lower().strip()
        
        # Remove common suffixes
        for suffix in [" field", " input", " box", " text", " area"]:
            if target_lower.endswith(suffix):
                target_lower = target_lower[:-len(suffix)].strip()
                break
        
        # NEW: Try FormHandler for smart field matching
        try:
            from llm_web_agent.engine.form_handler import FormFieldAnalyzer
            
            analyzer = FormFieldAnalyzer()
            context = await analyzer.analyze(page)
            
            if context.fields:
                # Find best matching field
                best_match = None
                best_score = 0.6  # Minimum threshold
                
                for field in context.fields:
                    if not field.is_visible or field.is_disabled:
                        continue
                    
                    score = field.matches(target_lower)
                    if score > best_score:
                        best_score = score
                        best_match = field
                
                if best_match:
                    # Build unique selector for this specific field
                    if best_match.id:
                        selector = f"#{best_match.id}"
                    elif best_match.name:
                        selector = f"[name='{best_match.name}']"
                    else:
                        selector = best_match.selector
                    
                    # Verify the selector works
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.debug(f"FormHandler matched '{target}' to field: {best_match.get_best_identifier()} (score: {best_score:.2f})")
                        return ResolvedTarget(
                            selector=selector,
                            element=element,
                            strategy=ResolutionStrategy.SMART,
                            confidence=best_score,
                        )
        except Exception as e:
            logger.debug(f"FormHandler matching failed: {e}")
        
        # Fallback: Strategy 1: Label with for attribute
        try:
            label = await page.query_selector(f'label:has-text("{target_lower}")')
            if label:
                for_attr = await label.get_attribute("for")
                if for_attr:
                    input_elem = await page.query_selector(f'#{for_attr}')
                    if input_elem and await input_elem.is_visible():
                        return ResolvedTarget(
                            selector=f"#{for_attr}",
                            element=input_elem,
                            strategy=ResolutionStrategy.SMART,
                            confidence=0.9,
                        )
        except Exception:
            pass
        
        # Strategy 2: Input inside label
        try:
            input_in_label = await page.query_selector(
                f'label:has-text("{target_lower}") input, label:has-text("{target_lower}") textarea'
            )
            if input_in_label and await input_in_label.is_visible():
                selector = await self._build_element_selector(input_in_label)
                return ResolvedTarget(
                    selector=selector,
                    element=input_in_label,
                    strategy=ResolutionStrategy.SMART,
                    confidence=0.85,
                )
        except Exception:
            pass
        
        # Strategy 3: getByLabel (Playwright accessibility locator)
        try:
            locator = page.get_by_label(target_lower, exact=False)
            count = await locator.count()
            if count == 1:
                element = locator.first
                if await element.is_visible():
                    # Build a selector for the element
                    element_id = await element.get_attribute("id")
                    if element_id:
                        selector = f"#{element_id}"
                    else:
                        name = await element.get_attribute("name")
                        if name:
                            selector = f"[name='{name}']"
                        else:
                            selector = f"input >> nth=0"
                    
                    return ResolvedTarget(
                        selector=selector,
                        element=element,
                        strategy=ResolutionStrategy.SMART,
                        confidence=0.9,
                    )
        except Exception:
            pass
        
        # Strategy 4: Input by placeholder
        try:
            locator = page.get_by_placeholder(target_lower, exact=False)
            count = await locator.count()
            if count == 1:
                element = locator.first
                if await element.is_visible():
                    element_id = await element.get_attribute("id")
                    if element_id:
                        selector = f"#{element_id}"
                    else:
                        name = await element.get_attribute("name")
                        if name:
                            selector = f"[name='{name}']"
                        else:
                            placeholder = await element.get_attribute("placeholder")
                            selector = f"[placeholder='{placeholder}']"
                    
                    return ResolvedTarget(
                        selector=selector,
                        element=element,
                        strategy=ResolutionStrategy.SMART,
                        confidence=0.85,
                    )
        except Exception:
            pass
        
        # Strategy 5: Input/textarea with matching attributes
        try:
            inputs = await page.query_selector_all('input:not([type="hidden"]), textarea, select')
            
            for inp in inputs:
                try:
                    if not await inp.is_visible():
                        continue
                    
                    # Check attributes
                    attrs_to_check = ["id", "name", "placeholder", "aria-label"]
                    for attr_name in attrs_to_check:
                        attr_val = await inp.get_attribute(attr_name)
                        if attr_val and target_lower in attr_val.lower():
                            selector = await self._build_element_selector(inp)
                            return ResolvedTarget(
                                selector=selector,
                                element=inp,
                                strategy=ResolutionStrategy.SMART,
                                confidence=0.8,
                            )
                except Exception:
                    continue
        except Exception:
            pass
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    async def _try_llm_disambiguation(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str],
    ) -> ResolvedTarget:
        """
        Use LLM to disambiguate and find the right element.
        
        This is the final fallback when all other strategies fail.
        Uses LLMFallback to assess severity and ask LLM for help.
        """
        if not self._llm:
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
        
        try:
            from llm_web_agent.engine.llm_fallback import (
                LLMFallback, ResolutionContext
            )
            
            fallback = LLMFallback(self._llm)
            
            # Build context - safely get title (may fail during navigation)
            try:
                page_title = await page.title() if hasattr(page, 'title') else ""
            except Exception:
                page_title = ""
            
            context = ResolutionContext(
                target=target,
                page_title=page_title,
            )
            
            # Get visible elements
            context.visible_buttons = await fallback._get_visible_elements(page)
            
            if not context.visible_buttons:
                logger.debug("No visible elements for LLM disambiguation")
                return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
            
            # Ask LLM
            result = await fallback.disambiguate(page, context)
            
            if not result.success or not result.matched_text:
                logger.debug(f"LLM disambiguation failed: {result.reasoning}")
                return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
            
            # Try to find the element LLM suggested
            matched = result.matched_text
            logger.info(f"LLM suggests: '{matched}' for target '{target}'")
            
            # Try text-first with LLM's suggestion
            resolved = await self._try_text_first(page, matched)
            if resolved.is_resolved:
                return ResolvedTarget(
                    selector=resolved.selector,
                    element=resolved.element,
                    strategy=ResolutionStrategy.FUZZY,  # Mark as fuzzy since LLM-assisted
                    confidence=0.8,
                )
            
            # Try Playwright text selector
            resolved = await self._try_playwright_text(page, matched)
            if resolved.is_resolved:
                return ResolvedTarget(
                    selector=resolved.selector,
                    element=resolved.element,
                    strategy=ResolutionStrategy.PLAYWRIGHT,
                    confidence=0.75,
                )
            
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
            
        except Exception as e:
            logger.debug(f"LLM disambiguation error: {e}")
            return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    async def _try_fuzzy_search(self, page: "IPage", target: str, intent: Optional[str]) -> ResolvedTarget:
        """
        Search all interactive elements with enhanced fuzzy matching.
        
        Matching strategies (in order of score):
        1. Exact match (1.0)
        2. Contains target (0.9)
        3. Target contains text (0.8)
        4. Word overlap (0.5-0.85 based on overlap %)
        5. Levenshtein similarity (0.5-0.75)
        """
        try:
            selector = "button, a, input, select, textarea, [role='button'], [role='link'], [onclick], .MuiButton-root, .MuiButtonBase-root"
            elements = await page.query_selector_all(selector)
            
            target_lower = target.lower().strip()
            target_words = set(target_lower.split())
            core = self._extract_core_text(target).lower()
            
            best_match = None
            best_score = 0
            best_text = ""
            
            for element in elements:
                try:
                    if not await self._is_visible(element):
                        continue
                    
                    # Get element info
                    text = (await element.text_content() or "").lower().strip()
                    aria = (await element.get_attribute("aria-label") or "").lower()
                    placeholder = (await element.get_attribute("placeholder") or "").lower()
                    title = (await element.get_attribute("title") or "").lower()
                    
                    # Calculate best score across all attributes
                    score = 0
                    matched_text = ""
                    for check in [text, aria, placeholder, title]:
                        if not check:
                            continue
                        s = self._fuzzy_score(core, check, target_words)
                        if s > score:
                            score = s
                            matched_text = check
                    
                    if score > best_score:
                        best_score = score
                        best_match = element
                        best_text = matched_text
                        
                except Exception:
                    continue
            
            if best_match and best_score >= self._fuzzy_threshold:
                selector = await self._build_element_selector(best_match)
                if selector:
                    logger.debug(f"Fuzzy matched '{target}' → '{best_text}' (score={best_score:.2f})")
                    return ResolvedTarget(
                        selector=selector,
                        element=best_match,
                        strategy=ResolutionStrategy.FUZZY,
                        confidence=best_score,
                    )
                    
        except Exception as e:
            logger.debug(f"Fuzzy search error: {e}")
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
    def _fuzzy_score(self, target: str, text: str, target_words: set) -> float:
        """
        Calculate fuzzy similarity score between target and text.
        
        Returns score 0.0 to 1.0.
        """
        if not text or not target:
            return 0.0
        
        # Exact match
        if target == text:
            return 1.0
        
        # Target contained in text (e.g., "start" in "Get started")
        if target in text:
            return 0.9
        
        # Text contained in target (e.g., "Get" in "Get started button")
        if text in target and len(text) > 2:
            return 0.8
        
        # SEMANTIC REJECTION: Check key words are compatible
        # E.g., "add-to-cart" should NOT match "back-to-products"
        text_words = set(text.replace('-', ' ').replace('_', ' ').split())
        target_clean = target.replace('-', ' ').replace('_', ' ')
        target_words_clean = set(target_clean.split())
        
        # Extract key action words
        action_words = {'add', 'remove', 'back', 'next', 'continue', 'finish', 'cancel', 'submit', 'login', 'logout', 'checkout', 'cart'}
        target_actions = target_words_clean & action_words
        text_actions = text_words & action_words
        
        # If both have action words but different ones, reject completely
        if target_actions and text_actions and not (target_actions & text_actions):
            return 0.0  # Semantic mismatch!
        
        # Word overlap (e.g., "Get started" vs "Getting started" share "started")
        if target_words_clean and text_words:
            # Check for common root words (start → started, starting)
            overlap = 0
            for tw in target_words_clean:
                for ew in text_words:
                    if tw in ew or ew in tw:
                        overlap += 1
                        break
                    # Common prefix (3+ chars)
                    if len(tw) >= 3 and len(ew) >= 3 and tw[:3] == ew[:3]:
                        overlap += 0.7
                        break
            
            if overlap > 0:
                ratio = overlap / max(len(target_words_clean), len(text_words))
                return 0.5 + (ratio * 0.35)  # 0.5 to 0.85
        
        # Levenshtein-like ratio for short strings
        if len(target) <= 20 and len(text) <= 30:
            ratio = self._simple_ratio(target, text)
            if ratio > 0.6:
                return 0.5 + (ratio * 0.25)  # 0.5 to 0.75
        
        return 0.0
    
    def _simple_ratio(self, s1: str, s2: str) -> float:
        """Simple string similarity ratio without external deps."""
        if s1 == s2:
            return 1.0
        
        # Use longest common subsequence ratio
        len1, len2 = len(s1), len(s2)
        if len1 == 0 or len2 == 0:
            return 0.0
        
        # Quick check: if one is much longer, low similarity
        if max(len1, len2) / min(len1, len2) > 3:
            return 0.0
        
        # Count matching chars in order
        matches = 0
        j = 0
        for c in s1:
            for k in range(j, len2):
                if s2[k] == c:
                    matches += 1
                    j = k + 1
                    break
        
        return (2.0 * matches) / (len1 + len2)
    
    async def _is_visible(self, element: "IElement") -> bool:
        """Check if element is visible."""
        try:
            return await element.is_visible()
        except Exception:
            return True  # Assume visible if check fails
    
    async def _build_element_selector(self, element: "IElement") -> str:
        """Build unique selector for an element."""
        try:
            # Try ID
            id_attr = await element.get_attribute("id")
            if id_attr:
                return f"#{id_attr}"
            
            # Try data-testid
            testid = await element.get_attribute("data-testid")
            if testid:
                return f'[data-testid="{testid}"]'
            
            # Try text content
            text = await element.text_content()
            if text and len(text.strip()) < 50:
                return f'text="{text.strip()}"'
            
            # Try aria-label
            aria = await element.get_attribute("aria-label")
            if aria:
                return f'[aria-label="{aria}"]'
                
        except Exception:
            pass
        
        return ""
    
    async def _try_wait_for_dynamic(
        self,
        page: "IPage",
        target: str,
        intent: Optional[str],
        timeout: int = 3000,
    ) -> ResolvedTarget:
        """
        Wait for dynamic elements like dropdown menus, modals, popovers.
        
        These elements only appear in the DOM after a user interaction.
        Uses wait_for_selector with exponential backoff for adaptive timeouts.
        """
        # Build selectors to wait for
        core = self._extract_core_text(target)
        selectors_to_try = [
            f'text={target}',
            f'text={core}',
            f'[role="option"]:has-text("{core}")',   # Dropdown options
            f'[role="menuitem"]:has-text("{core}")', # Menu items
            f'[role="listbox"] >> text={core}',      # Listbox items
            f'li:has-text("{core}")',                # List items
            f'.MuiMenuItem-root:has-text("{core}")', # MUI menu items
            f'.MuiListItem-root:has-text("{core}")', # MUI list items
        ]
        
        # Exponential backoff: start fast, increase timeout progressively
        # This allows quick failure for non-existent elements while waiting for slow ones
        backoff_timeouts = [100, 300, 1000, timeout]
        
        for wait_timeout in backoff_timeouts:
            for selector in selectors_to_try:
                try:
                    # Wait for the element to appear
                    element = await page.wait_for_selector(
                        selector,
                        state="visible",
                        timeout=wait_timeout
                    )
                    if element:
                        logger.info(f"DYNAMIC wait found '{target}' with: {selector} (timeout={wait_timeout}ms)")
                        return ResolvedTarget(
                            selector=selector,
                            element=element,
                            strategy=ResolutionStrategy.DYNAMIC,
                            confidence=0.75,
                        )
                except Exception as e:
                    # Timeout or not found - try next selector/timeout
                    logger.debug(f"wait_for_selector failed for {selector} (timeout={wait_timeout}ms)")
                    continue
        
        return ResolvedTarget(selector="", strategy=ResolutionStrategy.FAILED)
    
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


# Standalone function for backwards compatibility
async def resolve_multiple(
    resolver: TargetResolver,
    page: "IPage",
    targets: Dict[str, str],
    intent: Optional[str] = None,
) -> Dict[str, ResolvedTarget]:
    """Resolve multiple targets by name."""
    results = {}
    for name, target in targets.items():
        results[name] = await resolver.resolve(page, target, intent)
    return results
