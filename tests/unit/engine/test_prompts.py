"""
Tests for PromptBuilder - prompt template generation.
"""

import pytest

from llm_web_agent.engine.llm.prompts import (
    PromptBuilder,
    INSTRUCTION_PARSE_SYSTEM,
    ELEMENT_FIND_SYSTEM,
    ACTION_PLAN_SYSTEM,
    ERROR_RECOVERY_SYSTEM,
)


class TestPromptBuilder:
    """Test PromptBuilder functionality."""
    
    @pytest.fixture
    def builder(self):
        """Create a PromptBuilder instance."""
        return PromptBuilder()
    
    def test_build_instruction_parse_basic(self, builder):
        """Test building basic instruction parse prompt."""
        system, user = builder.build_instruction_parse("go to google.com")
        
        assert system == INSTRUCTION_PARSE_SYSTEM
        assert "go to google.com" in user
        assert "JSON" in user
    
    def test_build_instruction_parse_with_context(self, builder):
        """Test building instruction parse with context."""
        context = {
            "url": "https://example.com",
            "elements": [1, 2, 3],
        }
        
        system, user = builder.build_instruction_parse("click the button", context)
        
        assert "example.com" in user
        assert "3 interactive elements" in user
    
    def test_build_element_find(self, builder):
        """Test building element find prompt."""
        elements = [
            {"tag": "button", "text": "Login", "id": "login-btn"},
            {"tag": "input", "name": "email", "placeholder": "Enter email"},
        ]
        
        system, user = builder.build_element_find(
            description="login button",
            url="https://example.com",
            elements=elements,
        )
        
        assert system == ELEMENT_FIND_SYSTEM
        assert "login button" in user
        assert "example.com" in user
        assert "Login" in user
    
    def test_build_element_find_empty_elements(self, builder):
        """Test element find with no elements."""
        system, user = builder.build_element_find(
            description="button",
            url="https://example.com",
            elements=[],
        )
        
        assert "No interactive elements" in user
    
    def test_build_action_plan(self, builder):
        """Test building action plan prompt."""
        elements = [
            {"tag": "button", "text": "Submit", "id": "submit"},
        ]
        variables = {"email": "test@test.com"}
        
        system, user = builder.build_action_plan(
            goal="login to the site",
            url="https://example.com/login",
            title="Login Page",
            elements=elements,
            variables=variables,
        )
        
        assert system == ACTION_PLAN_SYSTEM
        assert "login to the site" in user
        assert "Login Page" in user
        assert "email" in user
    
    def test_build_action_plan_no_variables(self, builder):
        """Test action plan with no variables."""
        system, user = builder.build_action_plan(
            goal="click button",
            url="https://example.com",
            title="Page",
            elements=[],
            variables={},
        )
        
        assert "none" in user
    
    def test_build_error_recovery(self, builder):
        """Test building error recovery prompt."""
        elements = [
            {"tag": "button", "text": "Sign In"},
        ]
        history = [
            "navigate(google.com) → ✓",
            "click(Login button) → ✗",
        ]
        
        system, user = builder.build_error_recovery(
            action="click on Login button",
            error="Element not found",
            url="https://example.com",
            title="Page",
            elements=elements,
            history=history,
        )
        
        assert system == ERROR_RECOVERY_SYSTEM
        assert "Login button" in user
        assert "Element not found" in user
        assert "navigate(google.com)" in user
    
    def test_build_error_recovery_truncates_history(self, builder):
        """Test error recovery truncates long history."""
        history = [f"action{i}" for i in range(20)]
        
        system, user = builder.build_error_recovery(
            action="click",
            error="error",
            url="url",
            title="title",
            elements=[],
            history=history,
        )
        
        # Should only include last 5
        assert "action19" in user
        assert "action15" in user
        assert "action0" not in user


class TestFormatElements:
    """Test element formatting for prompts."""
    
    @pytest.fixture
    def builder(self):
        return PromptBuilder()
    
    def test_format_elements_basic(self, builder):
        """Test formatting basic elements."""
        elements = [
            {"tag": "button", "text": "Click Me", "id": "btn1"},
        ]
        
        result = builder._format_elements(elements)
        
        assert "[0]" in result
        assert "<button>" in result
        assert "id=btn1" in result
        assert "Click Me" in result
    
    def test_format_elements_multiple_attrs(self, builder):
        """Test formatting elements with multiple attributes."""
        elements = [
            {
                "tag": "input",
                "id": "email",
                "name": "user_email",
                "type": "email",
                "placeholder": "Enter your email",
                "aria_label": "Email address",
            },
        ]
        
        result = builder._format_elements(elements)
        
        assert "id=email" in result
        assert "name=user_email" in result
        assert "type=email" in result
        assert "placeholder=" in result
        assert "aria-label=" in result
    
    def test_format_elements_truncates(self, builder):
        """Test formatting truncates long lists."""
        elements = [{"tag": "button", "text": f"Button {i}"} for i in range(150)]
        
        result = builder._format_elements(elements, max_elements=50)
        
        # Should only have 50 elements
        assert "[49]" in result
        assert "[100]" not in result
    
    def test_format_elements_truncates_text(self, builder):
        """Test formatting truncates long text."""
        long_text = "A" * 200
        elements = [{"tag": "p", "text": long_text}]
        
        result = builder._format_elements(elements)
        
        # Text should be truncated to 50 chars
        assert len(result) < 250
    
    def test_format_elements_empty(self, builder):
        """Test formatting empty list."""
        result = builder._format_elements([])
        
        assert "No interactive elements" in result


class TestPromptContent:
    """Test that prompts contain expected content."""
    
    def test_instruction_parse_system_has_intents(self):
        """Test instruction parse system prompt lists intents."""
        assert "navigate" in INSTRUCTION_PARSE_SYSTEM
        assert "click" in INSTRUCTION_PARSE_SYSTEM
        assert "fill" in INSTRUCTION_PARSE_SYSTEM
        assert "extract" in INSTRUCTION_PARSE_SYSTEM
    
    def test_instruction_parse_system_has_example(self):
        """Test instruction parse system prompt has example."""
        assert "```json" in INSTRUCTION_PARSE_SYSTEM
        assert '"intent"' in INSTRUCTION_PARSE_SYSTEM
    
    def test_element_find_system_has_output_format(self):
        """Test element find system prompt has output format."""
        assert "OUTPUT FORMAT" in ELEMENT_FIND_SYSTEM
        assert '"found"' in ELEMENT_FIND_SYSTEM
        assert '"index"' in ELEMENT_FIND_SYSTEM
    
    def test_action_plan_system_has_structure(self):
        """Test action plan system prompt has structure."""
        assert "plan" in ACTION_PLAN_SYSTEM
        assert "variables_needed" in ACTION_PLAN_SYSTEM
    
    def test_error_recovery_system_has_diagnosis(self):
        """Test error recovery system prompt mentions diagnosis."""
        assert "diagnosis" in ERROR_RECOVERY_SYSTEM
        assert "recovery" in ERROR_RECOVERY_SYSTEM
