"""
Selector Pattern Tracker - Learn which selector patterns work for target types.

This is an enhanced version of StrategyTracker that learns:
- Not just "which strategy works" but "which selector patterns work for which targets"
- Pattern-based learning: "login" targets on site X use [data-testid='*-btn']
- Per-domain knowledge that persists across sessions

Example learning:
    Step 1: "click Login" → [data-testid='login-btn'] works
    Learns: On example.com, targets containing "login" use testid pattern
    
    Step 2: "click Signup"
    Uses learning: Try [data-testid='signup-btn'] first
    Works immediately!
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from llm_web_agent.engine.task_planner import LocatorType

logger = logging.getLogger(__name__)


@dataclass
class SelectorPattern:
    """A learned selector pattern for a target type."""
    
    # Keywords that trigger this pattern
    target_keywords: List[str]
    
    # The locator type that works
    locator_type: str  # 'testid', 'role', 'text', etc.
    
    # Pattern template (if applicable)
    # e.g., "[data-testid='{keyword}-btn']" or just "testid"
    template: Optional[str] = None
    
    # Statistics
    success_count: int = 1
    failure_count: int = 0
    last_success: Optional[str] = None
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5
    
    @property
    def confidence(self) -> float:
        """Higher with more successes and higher success rate."""
        rate = self.success_rate
        count_factor = min(self.success_count / 10, 1.0)  # Max at 10 successes
        return rate * 0.7 + count_factor * 0.3


@dataclass
class DomainKnowledge:
    """Accumulated knowledge about a domain."""
    
    domain: str
    
    # Patterns learned for this domain
    patterns: List[SelectorPattern] = field(default_factory=list)
    
    # Exact target -> working selector cache
    exact_matches: Dict[str, str] = field(default_factory=dict)
    
    # Which locator types work best overall
    type_success_counts: Dict[str, int] = field(default_factory=dict)
    type_failure_counts: Dict[str, int] = field(default_factory=dict)
    
    # Metadata
    first_seen: Optional[str] = None
    last_updated: Optional[str] = None
    total_resolutions: int = 0
    
    def get_best_types(self) -> List[str]:
        """Get locator types ordered by success rate."""
        type_scores = {}
        for loc_type in set(self.type_success_counts.keys()) | set(self.type_failure_counts.keys()):
            successes = self.type_success_counts.get(loc_type, 0)
            failures = self.type_failure_counts.get(loc_type, 0)
            total = successes + failures
            if total > 0:
                type_scores[loc_type] = successes / total
        
        return sorted(type_scores.keys(), key=lambda t: type_scores[t], reverse=True)


class SelectorPatternTracker:
    """
    Learn which selector patterns work for which target types.
    
    Usage:
        tracker = SelectorPatternTracker()
        
        # Record successful resolution
        tracker.record_success("github.com", "Login button", "testid", "[data-testid='login-btn']")
        
        # Get suggestions for new target
        suggestions = tracker.suggest("github.com", "Signup button")
        # Returns: ["testid with pattern *-btn", ...]
    """
    
    def __init__(self, cache_path: str = "~/.llm-web-agent/selector_patterns.json"):
        self.cache_path = Path(cache_path).expanduser()
        self._knowledge: Dict[str, DomainKnowledge] = {}
        self._dirty = False
        self._load()
    
    def _load(self) -> None:
        """Load cached patterns from disk."""
        if not self.cache_path.exists():
            return
        
        try:
            data = json.loads(self.cache_path.read_text())
            for domain, knowledge_dict in data.items():
                patterns = [
                    SelectorPattern(**p) for p in knowledge_dict.get('patterns', [])
                ]
                self._knowledge[domain] = DomainKnowledge(
                    domain=domain,
                    patterns=patterns,
                    exact_matches=knowledge_dict.get('exact_matches', {}),
                    type_success_counts=knowledge_dict.get('type_success_counts', {}),
                    type_failure_counts=knowledge_dict.get('type_failure_counts', {}),
                    first_seen=knowledge_dict.get('first_seen'),
                    last_updated=knowledge_dict.get('last_updated'),
                    total_resolutions=knowledge_dict.get('total_resolutions', 0),
                )
            logger.debug(f"Loaded selector patterns for {len(self._knowledge)} domains")
        except Exception as e:
            logger.warning(f"Failed to load selector patterns: {e}")
    
    def _save(self) -> None:
        """Persist patterns to disk."""
        if not self._dirty:
            return
        
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for domain, knowledge in self._knowledge.items():
                data[domain] = {
                    'patterns': [asdict(p) for p in knowledge.patterns],
                    'exact_matches': knowledge.exact_matches,
                    'type_success_counts': knowledge.type_success_counts,
                    'type_failure_counts': knowledge.type_failure_counts,
                    'first_seen': knowledge.first_seen,
                    'last_updated': knowledge.last_updated,
                    'total_resolutions': knowledge.total_resolutions,
                }
            self.cache_path.write_text(json.dumps(data, indent=2))
            self._dirty = False
            logger.debug(f"Saved selector patterns for {len(data)} domains")
        except Exception as e:
            logger.warning(f"Failed to save selector patterns: {e}")
    
    def record_success(
        self,
        domain: str,
        target: str,
        locator_type: str,
        selector: str,
    ) -> None:
        """
        Record a successful resolution.
        
        Args:
            domain: Website domain
            target: Target description (e.g., "Login button")
            locator_type: Type that worked (e.g., "testid", "role")
            selector: Actual selector that worked
        """
        knowledge = self._get_or_create_knowledge(domain)
        now = datetime.now().isoformat()
        
        # Update exact match cache
        target_lower = target.lower().strip()
        knowledge.exact_matches[target_lower] = selector
        
        # Update type success count
        knowledge.type_success_counts[locator_type] = \
            knowledge.type_success_counts.get(locator_type, 0) + 1
        
        # Extract keywords and update patterns
        keywords = self._extract_keywords(target)
        self._update_pattern(knowledge, keywords, locator_type, selector)
        
        knowledge.last_updated = now
        knowledge.total_resolutions += 1
        
        self._dirty = True
        
        # Batch save every 5 resolutions
        if knowledge.total_resolutions % 5 == 0:
            self._save()
    
    def record_failure(
        self,
        domain: str,
        target: str,
        locator_type: str,
    ) -> None:
        """Record a failed resolution attempt."""
        knowledge = self._get_or_create_knowledge(domain)
        
        knowledge.type_failure_counts[locator_type] = \
            knowledge.type_failure_counts.get(locator_type, 0) + 1
        
        # Update pattern failure count if matching pattern exists
        keywords = self._extract_keywords(target)
        for pattern in knowledge.patterns:
            if self._keywords_match(keywords, pattern.target_keywords):
                if pattern.locator_type == locator_type:
                    pattern.failure_count += 1
        
        self._dirty = True
    
    def suggest(
        self,
        domain: str,
        target: str,
    ) -> List[Tuple[str, float]]:
        """
        Suggest locator types based on learned patterns.
        
        Args:
            domain: Website domain
            target: Target description
            
        Returns:
            List of (locator_type, confidence) tuples, ordered by confidence
        """
        if domain not in self._knowledge:
            return []
        
        knowledge = self._knowledge[domain]
        suggestions = []
        
        # Check exact match first
        target_lower = target.lower().strip()
        if target_lower in knowledge.exact_matches:
            # Infer type from cached selector
            cached = knowledge.exact_matches[target_lower]
            loc_type = self._infer_type_from_selector(cached)
            suggestions.append((loc_type, 1.0))
        
        # Check pattern matches
        keywords = self._extract_keywords(target)
        for pattern in knowledge.patterns:
            if self._keywords_match(keywords, pattern.target_keywords):
                suggestions.append((pattern.locator_type, pattern.confidence))
        
        # Add overall best types for this domain
        for loc_type in knowledge.get_best_types():
            if not any(s[0] == loc_type for s in suggestions):
                # Calculate confidence from success rate
                successes = knowledge.type_success_counts.get(loc_type, 0)
                failures = knowledge.type_failure_counts.get(loc_type, 0)
                total = successes + failures
                if total > 0:
                    confidence = successes / total * 0.5  # Lower weight for general stats
                    suggestions.append((loc_type, confidence))
        
        # Deduplicate and sort by confidence
        seen = set()
        unique = []
        for loc_type, conf in sorted(suggestions, key=lambda x: -x[1]):
            if loc_type not in seen:
                seen.add(loc_type)
                unique.append((loc_type, conf))
        
        return unique
    
    def get_exact_match(self, domain: str, target: str) -> Optional[str]:
        """Get cached exact match selector if available."""
        if domain not in self._knowledge:
            return None
        
        target_lower = target.lower().strip()
        return self._knowledge[domain].exact_matches.get(target_lower)
    
    def get_domain_stats(self, domain: str) -> Optional[Dict]:
        """Get learning statistics for a domain."""
        if domain not in self._knowledge:
            return None
        
        knowledge = self._knowledge[domain]
        return {
            'total_resolutions': knowledge.total_resolutions,
            'patterns_learned': len(knowledge.patterns),
            'exact_matches': len(knowledge.exact_matches),
            'best_types': knowledge.get_best_types()[:3],
            'first_seen': knowledge.first_seen,
            'last_updated': knowledge.last_updated,
        }
    
    def _get_or_create_knowledge(self, domain: str) -> DomainKnowledge:
        """Get or create knowledge entry for domain."""
        if domain not in self._knowledge:
            self._knowledge[domain] = DomainKnowledge(
                domain=domain,
                first_seen=datetime.now().isoformat(),
            )
        return self._knowledge[domain]
    
    def _extract_keywords(self, target: str) -> List[str]:
        """Extract meaningful keywords from target description."""
        # Lowercase and split
        words = target.lower().split()
        
        # Filter out common stopwords
        stopwords = {'the', 'a', 'an', 'on', 'in', 'to', 'for', 'of', 'and', 'or', 'is', 'are'}
        keywords = [w for w in words if w not in stopwords and len(w) > 1]
        
        # Remove trailing punctuation
        keywords = [re.sub(r'[^\w]', '', k) for k in keywords]
        keywords = [k for k in keywords if k]
        
        return keywords
    
    def _update_pattern(
        self,
        knowledge: DomainKnowledge,
        keywords: List[str],
        locator_type: str,
        selector: str,
    ) -> None:
        """Update or create pattern for keywords."""
        if not keywords:
            return
        
        # Look for existing pattern with overlapping keywords
        for pattern in knowledge.patterns:
            overlap = set(keywords) & set(pattern.target_keywords)
            if overlap and pattern.locator_type == locator_type:
                # Update existing pattern
                pattern.success_count += 1
                pattern.last_success = datetime.now().isoformat()
                # Merge keywords
                pattern.target_keywords = list(set(pattern.target_keywords) | set(keywords))
                return
        
        # Create new pattern
        knowledge.patterns.append(SelectorPattern(
            target_keywords=keywords,
            locator_type=locator_type,
            success_count=1,
            last_success=datetime.now().isoformat(),
        ))
    
    def _keywords_match(
        self,
        query_keywords: List[str],
        pattern_keywords: List[str],
    ) -> bool:
        """Check if query keywords match pattern keywords."""
        if not query_keywords or not pattern_keywords:
            return False
        
        query_set = set(query_keywords)
        pattern_set = set(pattern_keywords)
        
        # At least one keyword must match
        return bool(query_set & pattern_set)
    
    def _infer_type_from_selector(self, selector: str) -> str:
        """Infer locator type from selector string."""
        selector_lower = selector.lower()
        
        if 'testid' in selector_lower or 'data-testid' in selector_lower:
            return 'testid'
        elif 'role' in selector_lower:
            return 'role'
        elif 'label' in selector_lower:
            return 'label'
        elif 'placeholder' in selector_lower:
            return 'placeholder'
        elif 'text' in selector_lower:
            return 'text'
        elif 'aria' in selector_lower:
            return 'aria'
        else:
            return 'css'
    
    def flush(self) -> None:
        """Force save to disk."""
        self._dirty = True
        self._save()
    
    def clear(self, domain: Optional[str] = None) -> None:
        """Clear learned patterns."""
        if domain:
            self._knowledge.pop(domain, None)
        else:
            self._knowledge.clear()
        self._dirty = True
        self._save()


# Module-level singleton
_tracker: Optional[SelectorPatternTracker] = None


def get_pattern_tracker() -> SelectorPatternTracker:
    """Get or create the global pattern tracker."""
    global _tracker
    if _tracker is None:
        _tracker = SelectorPatternTracker()
    return _tracker
