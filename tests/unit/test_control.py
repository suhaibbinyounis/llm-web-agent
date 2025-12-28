"""
Tests for the control module (policies, security).
"""

import pytest


class TestPolicyType:
    """Test the PolicyType enum."""
    
    def test_policy_types_exist(self):
        """Test that all expected policy types exist."""
        from llm_web_agent.control.policies.policy_engine import PolicyType
        assert PolicyType.DOMAIN
        assert PolicyType.ACTION
        assert PolicyType.DATA
        assert PolicyType.TIME
        assert PolicyType.CUSTOM


class TestPolicyAction:
    """Test the PolicyAction enum."""
    
    def test_policy_actions_exist(self):
        """Test that all expected policy actions exist."""
        from llm_web_agent.control.policies.policy_engine import PolicyAction
        assert PolicyAction.ALLOW
        assert PolicyAction.DENY
        assert PolicyAction.WARN
        assert PolicyAction.CONFIRM


class TestPolicy:
    """Test the Policy dataclass."""
    
    def test_create_policy(self):
        """Test creating a policy."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        policy = Policy(
            name="block-social",
            policy_type=PolicyType.DOMAIN,
            pattern=r".*facebook\.com",
            action=PolicyAction.DENY
        )
        assert policy.name == "block-social"
        assert policy.enabled is True
    
    def test_policy_matches_regex(self):
        """Test policy matching with regex."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        policy = Policy(
            name="test",
            policy_type=PolicyType.DOMAIN,
            pattern=r".*example\.com",
            action=PolicyAction.DENY
        )
        assert policy.matches("https://example.com") is True
        assert policy.matches("https://other.com") is False
    
    def test_policy_matches_substring(self):
        """Test policy matching with regex pattern."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        policy = Policy(
            name="test",
            policy_type=PolicyType.DOMAIN,
            pattern=r".*facebook.*",  # Regex that matches facebook anywhere
            action=PolicyAction.DENY
        )
        assert policy.matches("https://facebook.com") is True


class TestPolicyEngine:
    """Test the PolicyEngine class."""
    
    @pytest.fixture
    def engine(self):
        """Create a PolicyEngine instance."""
        from llm_web_agent.control.policies.policy_engine import PolicyEngine
        return PolicyEngine()
    
    def test_add_policy(self, engine):
        """Test adding a policy."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        policy = Policy(
            name="test",
            policy_type=PolicyType.DOMAIN,
            pattern="example.com",
            action=PolicyAction.DENY
        )
        engine.add_policy(policy)
        policies = engine.get_policies()
        assert len(policies) == 1
    
    def test_remove_policy(self, engine):
        """Test removing a policy."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        policy = Policy(
            name="test",
            policy_type=PolicyType.DOMAIN,
            pattern="example.com",
            action=PolicyAction.DENY
        )
        engine.add_policy(policy)
        assert engine.remove_policy("test") is True
        assert engine.remove_policy("nonexistent") is False
    
    def test_evaluate_domain_allow(self, engine):
        """Test domain evaluation with no matching policy (default allow)."""
        result = engine.evaluate_domain("https://example.com")
        assert result.allowed is True
    
    def test_evaluate_domain_deny(self, engine):
        """Test domain evaluation with deny policy."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        policy = Policy(
            name="block-facebook",
            policy_type=PolicyType.DOMAIN,
            pattern=r".*facebook\.com",
            action=PolicyAction.DENY
        )
        engine.add_policy(policy)
        
        result = engine.evaluate_domain("https://facebook.com/page")
        assert result.allowed is False
        assert result.policy.name == "block-facebook"
    
    def test_evaluate_action(self, engine):
        """Test action evaluation."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        policy = Policy(
            name="block-delete",
            policy_type=PolicyType.ACTION,
            pattern="delete",
            action=PolicyAction.DENY
        )
        engine.add_policy(policy)
        
        result = engine.evaluate_action("delete")
        assert result.allowed is False
    
    def test_get_policies_by_type(self, engine):
        """Test filtering policies by type."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        domain_policy = Policy(
            name="domain1", policy_type=PolicyType.DOMAIN,
            pattern="test", action=PolicyAction.ALLOW
        )
        action_policy = Policy(
            name="action1", policy_type=PolicyType.ACTION,
            pattern="click", action=PolicyAction.ALLOW
        )
        engine.add_policy(domain_policy)
        engine.add_policy(action_policy)
        
        domain_policies = engine.get_policies(PolicyType.DOMAIN)
        assert len(domain_policies) == 1
        assert domain_policies[0].name == "domain1"
    
    def test_set_default_action(self, engine):
        """Test setting default action."""
        from llm_web_agent.control.policies.policy_engine import PolicyAction
        engine.set_default_action(PolicyAction.DENY)
        result = engine.evaluate_domain("https://example.com")
        # With no matching policy, should use default
        assert result.action == PolicyAction.DENY
    
    def test_policy_priority(self, engine):
        """Test that higher priority policies are evaluated first."""
        from llm_web_agent.control.policies.policy_engine import (
            Policy, PolicyType, PolicyAction
        )
        low_priority = Policy(
            name="allow-all", policy_type=PolicyType.DOMAIN,
            pattern=".*", action=PolicyAction.ALLOW, priority=0
        )
        high_priority = Policy(
            name="block-facebook", policy_type=PolicyType.DOMAIN,
            pattern=r".*facebook\.com", action=PolicyAction.DENY, priority=10
        )
        engine.add_policy(low_priority)
        engine.add_policy(high_priority)
        
        result = engine.evaluate_domain("https://facebook.com")
        assert result.allowed is False
        assert result.policy.name == "block-facebook"


class TestPolicyResult:
    """Test the PolicyResult dataclass."""
    
    def test_create_allowed_result(self):
        """Test creating an allowed result."""
        from llm_web_agent.control.policies.policy_engine import (
            PolicyResult, PolicyAction
        )
        result = PolicyResult(allowed=True, action=PolicyAction.ALLOW)
        assert result.allowed is True
    
    def test_create_denied_result(self):
        """Test creating a denied result."""
        from llm_web_agent.control.policies.policy_engine import (
            PolicyResult, PolicyAction
        )
        result = PolicyResult(allowed=False, action=PolicyAction.DENY, message="Blocked")
        assert result.allowed is False
        assert result.message == "Blocked"
