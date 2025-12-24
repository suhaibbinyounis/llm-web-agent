"""
Tests for LLM schemas - structured output validation.
"""

import pytest
import json

from llm_web_agent.engine.llm.schemas import (
    ParsedInstruction,
    ParsedStep,
    FoundElement,
    ActionPlan,
    PlannedAction,
    ErrorRecovery,
    ExtractedValue,
    LLMResponse,
    LLMResponseStatus,
    StepIntent,
    get_instruction_parse_schema,
    get_element_find_schema,
    get_action_plan_schema,
)


class TestParsedStep:
    """Test ParsedStep schema."""
    
    def test_create_step(self):
        """Test creating a parsed step."""
        step = ParsedStep(
            intent=StepIntent.CLICK,
            target="login button",
        )
        
        assert step.intent == StepIntent.CLICK
        assert step.target == "login button"
    
    def test_step_with_value(self):
        """Test step with value."""
        step = ParsedStep(
            intent=StepIntent.FILL,
            target="email",
            value="test@example.com",
        )
        
        assert step.value == "test@example.com"
    
    def test_step_with_store_as(self):
        """Test step with store_as."""
        step = ParsedStep(
            intent=StepIntent.EXTRACT,
            target="price",
            store_as="product_price",
        )
        
        assert step.store_as == "product_price"
    
    def test_from_dict(self):
        """Test creating from dictionary."""
        step = ParsedStep(**{
            "intent": "navigate",
            "target": "google.com",
        })
        
        assert step.intent == "navigate"


class TestParsedInstruction:
    """Test ParsedInstruction schema."""
    
    def test_from_list(self):
        """Test parsing from list format."""
        data = [
            {"intent": "navigate", "target": "google.com"},
            {"intent": "fill", "target": "search", "value": "cats"},
            {"intent": "click", "target": "submit"},
        ]
        
        parsed = ParsedInstruction.from_json(data)
        
        assert len(parsed.steps) == 3
        assert parsed.steps[0].intent == "navigate"
        assert parsed.steps[1].value == "cats"
    
    def test_from_dict_with_steps(self):
        """Test parsing from dict with steps key."""
        data = {
            "steps": [
                {"intent": "click", "target": "button"},
            ]
        }
        
        parsed = ParsedInstruction.from_json(data)
        
        assert len(parsed.steps) == 1
    
    def test_from_invalid_format(self):
        """Test parsing invalid format raises error."""
        with pytest.raises(ValueError):
            ParsedInstruction.from_json("invalid")


class TestFoundElement:
    """Test FoundElement schema."""
    
    def test_found_element(self):
        """Test found element."""
        elem = FoundElement(
            found=True,
            index=5,
            selector="#login-btn",
            confidence=0.95,
            reasoning="Matched button text",
        )
        
        assert elem.is_found is True
        assert elem.index == 5
        assert elem.confidence == 0.95
    
    def test_not_found_element(self):
        """Test not found element."""
        elem = FoundElement(
            found=False,
            suggestions=["Try 'Sign in' instead"],
            reasoning="No matching element",
        )
        
        assert elem.is_found is False
        assert len(elem.suggestions) == 1
    
    def test_is_found_requires_index(self):
        """Test is_found requires index."""
        elem = FoundElement(found=True)  # No index
        
        assert elem.is_found is False


class TestActionPlan:
    """Test ActionPlan schema."""
    
    def test_create_plan(self):
        """Test creating action plan."""
        plan = ActionPlan(
            plan=[
                PlannedAction(step=1, intent=StepIntent.CLICK, target="login"),
                PlannedAction(step=2, intent=StepIntent.FILL, target="email", value="{{email}}"),
            ],
            variables_needed=["email", "password"],
            estimated_pages=2,
        )
        
        assert plan.step_count == 2
        assert "email" in plan.variables_needed
        assert plan.estimated_pages == 2
    
    def test_empty_plan(self):
        """Test empty plan."""
        plan = ActionPlan(plan=[])
        
        assert plan.step_count == 0


class TestErrorRecovery:
    """Test ErrorRecovery schema."""
    
    def test_recovery_with_steps(self):
        """Test recovery with steps."""
        recovery = ErrorRecovery(
            diagnosis="Button text is 'Sign In' not 'Login'",
            recovery_steps=[],
            should_retry=True,
            alternative_approach="Press Enter instead",
        )
        
        assert recovery.diagnosis is not None
        assert recovery.should_retry is True


class TestExtractedValue:
    """Test ExtractedValue schema."""
    
    def test_found_value(self):
        """Test found value."""
        value = ExtractedValue(
            found=True,
            value="$299.99",
            element_index=42,
            confidence=0.9,
        )
        
        assert value.found is True
        assert value.value == "$299.99"
    
    def test_not_found_value(self):
        """Test not found value."""
        value = ExtractedValue(found=False)
        
        assert value.found is False
        assert value.value is None


class TestLLMResponse:
    """Test LLMResponse parsing."""
    
    def test_parse_valid_json(self):
        """Test parsing valid JSON response."""
        text = '[{"intent": "click", "target": "button"}]'
        
        response = LLMResponse.from_text(text, ParsedInstruction)
        
        assert response.success is True
        assert response.status == LLMResponseStatus.SUCCESS
        assert len(response.parsed.steps) == 1
    
    def test_parse_json_in_markdown(self):
        """Test parsing JSON wrapped in markdown code block."""
        text = """Here's the response:
```json
[{"intent": "navigate", "target": "google.com"}]
```
"""
        
        response = LLMResponse.from_text(text, ParsedInstruction)
        
        assert response.success is True
        assert response.parsed.steps[0].intent == "navigate"
    
    def test_parse_invalid_json(self):
        """Test parsing invalid JSON."""
        text = "this is not json"
        
        response = LLMResponse.from_text(text, ParsedInstruction)
        
        assert response.success is False
        assert response.status == LLMResponseStatus.PARSE_ERROR
        assert "JSON parse error" in response.error
    
    def test_parse_empty_response(self):
        """Test parsing empty response."""
        response = LLMResponse.from_text("", ParsedInstruction)
        
        assert response.success is False
        assert response.status == LLMResponseStatus.EMPTY
    
    def test_parse_with_tokens(self):
        """Test parsing tracks tokens."""
        text = '[{"intent": "click", "target": "x"}]'
        
        response = LLMResponse.from_text(text, ParsedInstruction, tokens=150, latency=250.5)
        
        assert response.tokens_used == 150
        assert response.latency_ms == 250.5
    
    def test_parse_found_element(self):
        """Test parsing FoundElement response."""
        text = '{"found": true, "index": 5, "selector": "#btn", "confidence": 0.9}'
        
        response = LLMResponse.from_text(text, FoundElement)
        
        assert response.success is True
        assert response.parsed.found is True
        assert response.parsed.index == 5


class TestJSONSchemas:
    """Test JSON schema generation for function calling."""
    
    def test_instruction_parse_schema(self):
        """Test instruction parsing schema."""
        schema = get_instruction_parse_schema()
        
        assert schema["name"] == "parse_instruction"
        assert "parameters" in schema
        assert "steps" in schema["parameters"]["properties"]
    
    def test_element_find_schema(self):
        """Test element finding schema."""
        schema = get_element_find_schema()
        
        assert schema["name"] == "find_element"
        assert "found" in schema["parameters"]["properties"]
        assert "index" in schema["parameters"]["properties"]
    
    def test_action_plan_schema(self):
        """Test action planning schema."""
        schema = get_action_plan_schema()
        
        assert schema["name"] == "create_plan"
        assert "plan" in schema["parameters"]["properties"]
