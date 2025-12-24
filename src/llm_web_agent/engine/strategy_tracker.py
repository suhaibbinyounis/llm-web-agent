"""
Strategy Tracker - Learn which resolution strategies work best per domain.

This module tracks success rates, timing, and adapts strategy order based on
observed performance patterns. Data is persisted across sessions.
"""

from dataclasses import dataclass, field, asdict
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional
import json
import logging
import time

logger = logging.getLogger(__name__)


@dataclass
class StrategyStats:
    """Statistics for a single strategy on a domain."""
    attempts: int = 0
    successes: int = 0
    total_time_ms: float = 0
    
    @property
    def success_rate(self) -> float:
        """Probability of success."""
        if self.attempts == 0:
            return 0.5  # Default prior
        return self.successes / self.attempts
    
    @property
    def avg_time_ms(self) -> float:
        """Average execution time."""
        if self.attempts == 0:
            return 1000  # Default estimate
        return self.total_time_ms / self.attempts
    
    @property
    def efficiency_score(self) -> float:
        """Combined score: prefer high success rate AND low time."""
        # Weighted: success rate is more important than speed
        return self.success_rate * 0.7 + (1 - min(self.avg_time_ms / 2000, 1)) * 0.3


class StrategyTracker:
    """
    Track and learn which strategies work best for different sites.
    
    Usage:
        tracker = StrategyTracker()
        
        # Record outcome
        tracker.record("github.com", "text_first", success=True, time_ms=50)
        
        # Get adaptive order
        order = tracker.get_best_order("github.com")
    """
    
    DEFAULT_ORDER = ["text_first", "playwright", "smart", "fuzzy", "dynamic"]
    MIN_SAMPLES = 5  # Minimum samples before adapting order
    
    def __init__(self, cache_path: str = "~/.llm-web-agent/strategy_cache.json"):
        self.cache_path = Path(cache_path).expanduser()
        self._stats: Dict[str, Dict[str, StrategyStats]] = defaultdict(lambda: defaultdict(StrategyStats))
        self._dirty = False  # Track if we need to save
        self._load()
    
    def _load(self) -> None:
        """Load cached statistics from disk."""
        if not self.cache_path.exists():
            return
        
        try:
            data = json.loads(self.cache_path.read_text())
            for domain, strategies in data.items():
                for strategy, stats_dict in strategies.items():
                    self._stats[domain][strategy] = StrategyStats(**stats_dict)
            logger.debug(f"Loaded strategy stats for {len(data)} domains")
        except Exception as e:
            logger.warning(f"Failed to load strategy cache: {e}")
    
    def _save(self) -> None:
        """Persist statistics to disk."""
        if not self._dirty:
            return
        
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                domain: {
                    strategy: asdict(stats)
                    for strategy, stats in strategies.items()
                }
                for domain, strategies in self._stats.items()
            }
            self.cache_path.write_text(json.dumps(data, indent=2))
            self._dirty = False
            logger.debug(f"Saved strategy stats for {len(data)} domains")
        except Exception as e:
            logger.warning(f"Failed to save strategy cache: {e}")
    
    def record(
        self,
        domain: str,
        strategy: str,
        success: bool,
        time_ms: float,
    ) -> None:
        """
        Record the outcome of a resolution attempt.
        
        Args:
            domain: Website domain (e.g., "github.com")
            strategy: Strategy name (e.g., "text_first")
            success: Whether the resolution succeeded
            time_ms: Time taken in milliseconds
        """
        stats = self._stats[domain][strategy]
        stats.attempts += 1
        if success:
            stats.successes += 1
        stats.total_time_ms += time_ms
        self._dirty = True
        
        # Batch saves: save every 10 records
        if sum(s.attempts for d in self._stats.values() for s in d.values()) % 10 == 0:
            self._save()
    
    def get_best_order(self, domain: str) -> Optional[List[str]]:
        """
        Get strategies ordered by effectiveness for this domain.
        
        Returns:
            Ordered list of strategy names, or None to use default order.
        """
        domain_stats = self._stats.get(domain, {})
        
        # Not enough data - use default
        total_samples = sum(s.attempts for s in domain_stats.values())
        if total_samples < self.MIN_SAMPLES:
            return None
        
        # Sort by efficiency score (success rate + speed)
        sorted_strategies = sorted(
            domain_stats.items(),
            key=lambda x: x[1].efficiency_score,
            reverse=True
        )
        
        custom_order = [name for name, _ in sorted_strategies]
        
        # Ensure all strategies are included
        for strategy in self.DEFAULT_ORDER:
            if strategy not in custom_order:
                custom_order.append(strategy)
        
        return custom_order
    
    def get_stats(self, domain: str) -> Dict[str, dict]:
        """Get human-readable stats for a domain."""
        return {
            strategy: {
                "success_rate": f"{stats.success_rate:.1%}",
                "avg_time_ms": f"{stats.avg_time_ms:.0f}",
                "attempts": stats.attempts,
            }
            for strategy, stats in self._stats.get(domain, {}).items()
        }
    
    def flush(self) -> None:
        """Force save to disk."""
        self._dirty = True
        self._save()
    
    def clear(self, domain: Optional[str] = None) -> None:
        """Clear statistics for a domain or all domains."""
        if domain:
            if domain in self._stats:
                del self._stats[domain]
        else:
            self._stats.clear()
        self._dirty = True
        self._save()


# Global singleton instance
_tracker: Optional[StrategyTracker] = None


def get_tracker() -> StrategyTracker:
    """Get or create the global strategy tracker."""
    global _tracker
    if _tracker is None:
        _tracker = StrategyTracker()
    return _tracker
