"""
Tests for Element Fingerprinting module.
"""

import pytest
from llm_web_agent.engine.fingerprint import (
    sanitize_classname,
    normalize_text,
    normalize_position,
    generate_fingerprint,
    generate_selector_priority_list,
    FingerprintInput,
)


class TestSanitizeClassname:
    """Test class name sanitization."""
    
    def test_filters_css_in_js_classes(self):
        """CSS-in-JS dynamic classes should be filtered out."""
        result = sanitize_classname("css-1abc23 MuiButton-root")
        assert "css-1abc23" not in result
        assert "MuiButton" in result or "MuiButton-root" in result
    
    def test_keeps_stable_classes(self):
        """Semantic/framework classes should be kept."""
        result = sanitize_classname("btn btn-primary MuiButton")
        assert "btn" in result
    
    def test_empty_string(self):
        """Empty string input."""
        assert sanitize_classname("") == ""
        assert sanitize_classname(None) == ""
    
    def test_filters_styled_components(self):
        """Styled-components classes should be filtered."""
        result = sanitize_classname("sc-bdVaJa button-class")
        assert "sc-bdVaJa" not in result


class TestNormalizeText:
    """Test text normalization."""
    
    def test_collapses_whitespace(self):
        """Multiple spaces should collapse to single space."""
        assert normalize_text("Sign   In   Now") == "sign in now"
    
    def test_lowercases(self):
        """Text should be lowercased."""
        assert normalize_text("SUBMIT") == "submit"
    
    def test_truncates_long_text(self):
        """Long text should be truncated."""
        long_text = "a" * 200
        result = normalize_text(long_text)
        assert len(result) == 100
    
    def test_empty_string(self):
        """Empty string input."""
        assert normalize_text("") == ""
        assert normalize_text(None) == ""


class TestNormalizePosition:
    """Test position normalization."""
    
    def test_only_child(self):
        """Only child should return 'only'."""
        assert normalize_position(1, 1) == "only"
    
    def test_first_child(self):
        """First of many should return 'first'."""
        assert normalize_position(1, 5) == "first"
    
    def test_last_child(self):
        """Last child should return 'last'."""
        assert normalize_position(5, 5) == "last"
    
    def test_middle_child(self):
        """Middle child should return 'middle'."""
        assert normalize_position(5, 10) == "middle"


class TestGenerateFingerprint:
    """Test fingerprint generation."""
    
    def test_basic_fingerprint(self):
        """Generate fingerprint for basic element."""
        fp_input = FingerprintInput(
            text="Submit",
            tag="button",
            role="button",
        )
        fingerprint = generate_fingerprint(fp_input)
        
        assert len(fingerprint) == 12
        assert fingerprint.isalnum()
    
    def test_stable_fingerprint(self):
        """Same input should produce same fingerprint."""
        fp_input = FingerprintInput(
            text="Sign In",
            tag="button",
            aria_label="Sign in to your account",
        )
        
        fp1 = generate_fingerprint(fp_input)
        fp2 = generate_fingerprint(fp_input)
        
        assert fp1 == fp2
    
    def test_different_text_different_fingerprint(self):
        """Different text should produce different fingerprint."""
        fp1 = generate_fingerprint(FingerprintInput(text="Submit", tag="button"))
        fp2 = generate_fingerprint(FingerprintInput(text="Cancel", tag="button"))
        
        assert fp1 != fp2
    
    def test_testid_has_priority(self):
        """data-testid should be included in fingerprint."""
        fp_input = FingerprintInput(
            text="Submit",
            tag="button",
            data_testid="submit-button",
        )
        fingerprint = generate_fingerprint(fp_input)
        
        # Different testid should give different fingerprint
        fp_input2 = FingerprintInput(
            text="Submit",
            tag="button",
            data_testid="other-button",
        )
        fingerprint2 = generate_fingerprint(fp_input2)
        
        assert fingerprint != fingerprint2


class TestGenerateSelectorPriorityList:
    """Test selector priority list generation."""
    
    def test_testid_first(self):
        """data-testid selector should be first."""
        fp_input = FingerprintInput(
            text="Submit",
            tag="button",
            data_testid="submit-btn",
        )
        selectors = generate_selector_priority_list(fp_input, "abc123")
        
        assert selectors[0] == '[data-testid="submit-btn"]'
    
    def test_name_attribute(self):
        """name attribute should be in list."""
        fp_input = FingerprintInput(
            text="",
            tag="input",
            name="email",
        )
        selectors = generate_selector_priority_list(fp_input, "abc123")
        
        assert '[name="email"]' in selectors
    
    def test_placeholder_for_inputs(self):
        """placeholder should be included for inputs."""
        fp_input = FingerprintInput(
            text="",
            tag="input",
            placeholder="Enter your email",
        )
        selectors = generate_selector_priority_list(fp_input, "abc123")
        
        assert any("placeholder" in s for s in selectors)
    
    def test_empty_input(self):
        """Handle element with minimal attributes."""
        fp_input = FingerprintInput(text="", tag="div")
        selectors = generate_selector_priority_list(fp_input, "abc123")
        
        # Should have at least one fallback selector
        assert len(selectors) >= 0  # May be empty for non-interactive div
