"""
Site Profiler - Dynamic framework detection and selector strategy learning.

Detects:
- Frontend framework (React, Angular, Vue, vanilla)
- Available selector types (data-testid, aria-label, etc.)
- Optimal selector priority order for this site
- Timing characteristics (hydration wait, typical load time)

Learns from each successful resolution to improve future attempts.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


@dataclass
class SiteProfile:
    """Knowledge about a specific website's characteristics."""
    
    domain: str
    framework: Optional[str] = None          # react, next.js, angular, vue, vanilla
    framework_version: Optional[str] = None
    
    # What selector types work here (ordered by priority)
    selector_priorities: List[str] = field(default_factory=lambda: ['text'])
    
    # Framework-specific root element
    root_selector: str = "body"
    
    # Characteristics
    uses_shadow_dom: bool = False
    needs_hydration_wait: bool = False
    typical_load_time_ms: int = 1000
    
    # Detection metadata
    detected_at: Optional[str] = None
    detection_confidence: float = 0.0
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "SiteProfile":
        return cls(**data)


# JavaScript to detect site characteristics
DETECT_SITE_JS = '''() => {
    const profile = {
        framework: null,
        frameworkVersion: null,
        rootSelector: 'body',
        usesShadowDom: false,
        needsHydrationWait: false,
        selectorPriorities: [],
        detectionConfidence: 0
    };
    
    // Detect React
    const hasReactDevtools = !!window.__REACT_DEVTOOLS_GLOBAL_HOOK__;
    const hasReactRoot = !!document.querySelector('[data-reactroot]');
    const hasReactFiber = !!document.querySelector('[data-reactid]');
    const hasNextData = !!window.__NEXT_DATA__ || !!document.getElementById('__next');
    
    if (hasNextData) {
        profile.framework = 'next.js';
        profile.rootSelector = '#__next';
        profile.needsHydrationWait = true;
        profile.detectionConfidence = 0.95;
    } else if (hasReactDevtools || hasReactRoot || hasReactFiber) {
        profile.framework = 'react';
        profile.rootSelector = '#root, #app, [data-reactroot]';
        profile.needsHydrationWait = true;
        profile.detectionConfidence = 0.85;
    }
    
    // Detect Angular
    const hasNg = !!window.ng || !!window.getAllAngularRootElements;
    const hasNgVersion = !!window.angular;
    const hasAppRoot = !!document.querySelector('app-root');
    const hasNgAttrs = !!document.querySelector('[ng-version], [_ngcontent], [_nghost]');
    
    if (!profile.framework && (hasNg || hasAppRoot || hasNgAttrs)) {
        profile.framework = hasNgVersion ? 'angularjs' : 'angular';
        profile.rootSelector = 'app-root';
        profile.needsHydrationWait = true;
        profile.detectionConfidence = 0.85;
    }
    
    // Detect Vue
    const hasVue = !!window.__VUE__ || !!window.Vue;
    const hasVueAttrs = !!document.querySelector('[data-v-]');
    const hasNuxt = !!window.__NUXT__ || !!document.getElementById('__nuxt');
    
    if (!profile.framework && (hasVue || hasVueAttrs || hasNuxt)) {
        profile.framework = hasNuxt ? 'nuxt' : 'vue';
        profile.rootSelector = hasNuxt ? '#__nuxt' : '#app';
        profile.needsHydrationWait = hasNuxt;
        profile.detectionConfidence = 0.85;
    }
    
    // Detect Svelte
    const hasSvelte = !!document.querySelector('[class*="svelte-"]');
    if (!profile.framework && hasSvelte) {
        profile.framework = 'svelte';
        profile.detectionConfidence = 0.7;
    }
    
    // Default to vanilla if nothing detected
    if (!profile.framework) {
        profile.framework = 'vanilla';
        profile.detectionConfidence = 0.5;
    }
    
    // Detect available selector types
    const hasTestIds = !!document.querySelector('[data-testid]');
    const hasCyTestIds = !!document.querySelector('[data-cy]');
    const hasAriaLabels = document.querySelectorAll('[aria-label]').length > 3;
    const hasRoles = document.querySelectorAll('[role]').length > 3;
    const hasIds = document.querySelectorAll('[id]').length > 5;
    const hasNames = document.querySelectorAll('[name]').length > 3;
    const hasPlaceholders = document.querySelectorAll('[placeholder]').length > 2;
    
    // Build priority list based on what exists
    const priorities = [];
    if (hasTestIds) priorities.push('testid');
    if (hasCyTestIds) priorities.push('cy');
    if (hasRoles) priorities.push('role');
    if (hasAriaLabels) priorities.push('aria');
    if (hasNames) priorities.push('label');
    if (hasPlaceholders) priorities.push('placeholder');
    priorities.push('text');  // Always available
    if (hasIds) priorities.push('css');
    
    profile.selectorPriorities = priorities;
    
    // Check for Shadow DOM
    const allElements = document.querySelectorAll('*');
    for (let i = 0; i < Math.min(allElements.length, 100); i++) {
        if (allElements[i].shadowRoot) {
            profile.usesShadowDom = true;
            break;
        }
    }
    
    return profile;
}'''


class SiteProfiler:
    """
    Detect and learn site characteristics for optimal element resolution.
    
    Usage:
        profiler = SiteProfiler()
        profile = await profiler.get_profile(page)
        
        # Profile tells you:
        # - What framework the site uses
        # - What selector types to try first
        # - Whether to wait for hydration
    """
    
    def __init__(self, cache_path: str = "~/.llm-web-agent/site_profiles.json"):
        self.cache_path = Path(cache_path).expanduser()
        self._profiles: Dict[str, SiteProfile] = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cached profiles from disk."""
        if not self.cache_path.exists():
            return
        
        try:
            data = json.loads(self.cache_path.read_text())
            for domain, profile_dict in data.items():
                self._profiles[domain] = SiteProfile.from_dict(profile_dict)
            logger.debug(f"Loaded {len(self._profiles)} site profiles from cache")
        except Exception as e:
            logger.warning(f"Failed to load site profiles cache: {e}")
    
    def _save_cache(self) -> None:
        """Persist profiles to disk."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                domain: profile.to_dict()
                for domain, profile in self._profiles.items()
            }
            self.cache_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning(f"Failed to save site profiles cache: {e}")
    
    async def get_profile(self, page: "IPage", force_refresh: bool = False) -> SiteProfile:
        """
        Get or detect site profile.
        
        Args:
            page: Browser page
            force_refresh: Force re-detection even if cached
            
        Returns:
            SiteProfile with detected characteristics
        """
        domain = self._get_domain(page.url)
        
        # Return cached if available and not forcing refresh
        if not force_refresh and domain in self._profiles:
            logger.debug(f"Using cached profile for {domain}")
            return self._profiles[domain]
        
        # Detect fresh
        profile = await self._detect(page, domain)
        self._profiles[domain] = profile
        self._save_cache()
        
        return profile
    
    async def _detect(self, page: "IPage", domain: str) -> SiteProfile:
        """Run detection JavaScript on page."""
        logger.info(f"Detecting site profile for {domain}")
        
        try:
            result = await page.evaluate(DETECT_SITE_JS)
            
            profile = SiteProfile(
                domain=domain,
                framework=result.get('framework'),
                root_selector=result.get('rootSelector', 'body'),
                selector_priorities=result.get('selectorPriorities', ['text']),
                uses_shadow_dom=result.get('usesShadowDom', False),
                needs_hydration_wait=result.get('needsHydrationWait', False),
                detected_at=datetime.now().isoformat(),
                detection_confidence=result.get('detectionConfidence', 0.5),
            )
            
            logger.info(
                f"Detected: framework={profile.framework}, "
                f"priorities={profile.selector_priorities[:3]}, "
                f"confidence={profile.detection_confidence:.0%}"
            )
            
            return profile
            
        except Exception as e:
            logger.error(f"Site detection failed: {e}")
            return SiteProfile(
                domain=domain,
                framework='unknown',
                detected_at=datetime.now().isoformat(),
            )
    
    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc or 'unknown'
        except:
            return 'unknown'
    
    def update_priority(self, domain: str, selector_type: str, success: bool) -> None:
        """
        Update selector priority based on success/failure.
        
        Called after each resolution attempt to learn what works.
        """
        if domain not in self._profiles:
            return
        
        profile = self._profiles[domain]
        priorities = profile.selector_priorities.copy()
        
        if success and selector_type in priorities:
            # Move successful type toward front
            idx = priorities.index(selector_type)
            if idx > 0:
                priorities.remove(selector_type)
                priorities.insert(max(0, idx - 1), selector_type)
                profile.selector_priorities = priorities
                self._save_cache()
        
        elif not success and selector_type in priorities:
            # Move failed type toward back
            idx = priorities.index(selector_type)
            if idx < len(priorities) - 1:
                priorities.remove(selector_type)
                priorities.insert(min(len(priorities), idx + 1), selector_type)
                profile.selector_priorities = priorities
                self._save_cache()
    
    def get_wait_strategy(self, profile: SiteProfile) -> Optional[str]:
        """Get recommended wait strategy for this site's framework."""
        if profile.framework in ('next.js', 'react'):
            return 'networkidle'
        elif profile.framework in ('angular', 'angularjs'):
            return 'domcontentloaded'
        elif profile.framework in ('vue', 'nuxt'):
            return 'networkidle'
        else:
            return 'load'
    
    def clear_cache(self, domain: Optional[str] = None) -> None:
        """Clear cached profiles."""
        if domain:
            self._profiles.pop(domain, None)
        else:
            self._profiles.clear()
        self._save_cache()


# Module-level singleton
_profiler: Optional[SiteProfiler] = None


def get_site_profiler() -> SiteProfiler:
    """Get or create the global site profiler."""
    global _profiler
    if _profiler is None:
        _profiler = SiteProfiler()
    return _profiler
