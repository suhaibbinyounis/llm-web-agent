"""
Policy Engine - Evaluate and enforce policies.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
import re
import logging

logger = logging.getLogger(__name__)


class PolicyType(Enum):
    """Types of policies."""
    DOMAIN = "domain"
    ACTION = "action"
    DATA = "data"
    TIME = "time"
    CUSTOM = "custom"


class PolicyAction(Enum):
    """Actions to take when policy matches."""
    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"
    CONFIRM = "confirm"  # Require user confirmation


@dataclass
class PolicyResult:
    """
    Result of policy evaluation.
    
    Attributes:
        allowed: Whether the action is allowed
        action: Action to take
        policy: The policy that matched
        message: Human-readable message
    """
    allowed: bool
    action: PolicyAction
    policy: Optional["Policy"] = None
    message: str = ""


@dataclass
class Policy:
    """
    A policy rule.
    
    Attributes:
        name: Policy name
        policy_type: Type of policy
        pattern: Pattern to match (regex for domains, etc.)
        action: Action to take when matched
        priority: Higher priority policies are evaluated first
        enabled: Whether policy is active
        metadata: Additional policy data
    """
    name: str
    policy_type: PolicyType
    pattern: str
    action: PolicyAction
    priority: int = 0
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def matches(self, value: str) -> bool:
        """Check if value matches policy pattern."""
        try:
            return bool(re.match(self.pattern, value))
        except re.error:
            return self.pattern in value


class PolicyEngine:
    """
    Evaluate and enforce policies.
    
    Example:
        >>> engine = PolicyEngine()
        >>> engine.add_policy(Policy(
        ...     name="block-social",
        ...     policy_type=PolicyType.DOMAIN,
        ...     pattern=r".*\.(facebook|twitter|instagram)\.com",
        ...     action=PolicyAction.DENY,
        ... ))
        >>> result = engine.evaluate_domain("https://facebook.com")
        >>> print(result.allowed)  # False
    """
    
    def __init__(self):
        """Initialize the policy engine."""
        self._policies: List[Policy] = []
        self._default_action = PolicyAction.ALLOW
    
    def add_policy(self, policy: Policy) -> None:
        """
        Add a policy.
        
        Args:
            policy: Policy to add
        """
        self._policies.append(policy)
        # Sort by priority (higher first)
        self._policies.sort(key=lambda p: p.priority, reverse=True)
    
    def remove_policy(self, name: str) -> bool:
        """
        Remove a policy by name.
        
        Args:
            name: Policy name to remove
            
        Returns:
            True if policy was removed
        """
        initial_count = len(self._policies)
        self._policies = [p for p in self._policies if p.name != name]
        return len(self._policies) < initial_count
    
    def evaluate_domain(self, url: str) -> PolicyResult:
        """
        Evaluate domain policies for a URL.
        
        Args:
            url: URL to evaluate
            
        Returns:
            Policy result
        """
        for policy in self._policies:
            if policy.policy_type != PolicyType.DOMAIN or not policy.enabled:
                continue
            
            if policy.matches(url):
                return PolicyResult(
                    allowed=policy.action == PolicyAction.ALLOW,
                    action=policy.action,
                    policy=policy,
                    message=f"Policy '{policy.name}' matched: {policy.action.value}",
                )
        
        # No policy matched, use default
        return PolicyResult(
            allowed=True,
            action=self._default_action,
            message="No matching policy, using default",
        )
    
    def evaluate_action(self, action: str, target: str = "") -> PolicyResult:
        """
        Evaluate action policies.
        
        Args:
            action: Action type
            target: Action target
            
        Returns:
            Policy result
        """
        for policy in self._policies:
            if policy.policy_type != PolicyType.ACTION or not policy.enabled:
                continue
            
            if policy.matches(action):
                return PolicyResult(
                    allowed=policy.action == PolicyAction.ALLOW,
                    action=policy.action,
                    policy=policy,
                    message=f"Action policy '{policy.name}': {policy.action.value}",
                )
        
        return PolicyResult(allowed=True, action=self._default_action)
    
    def get_policies(
        self,
        policy_type: Optional[PolicyType] = None,
    ) -> List[Policy]:
        """
        Get policies, optionally filtered by type.
        
        Args:
            policy_type: Filter by type
            
        Returns:
            List of policies
        """
        if policy_type is None:
            return self._policies.copy()
        return [p for p in self._policies if p.policy_type == policy_type]
    
    def set_default_action(self, action: PolicyAction) -> None:
        """Set the default action when no policy matches."""
        self._default_action = action
