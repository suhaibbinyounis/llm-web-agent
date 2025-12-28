"""
Tests for the intelligence modules (NLP, DOM, planning).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestIntentType:
    """Test the IntentType enum."""
    
    def test_intent_types_exist(self):
        """Test that all expected intent types exist."""
        from llm_web_agent.intelligence.nlp.intent_parser import IntentType
        assert IntentType.CLICK
        assert IntentType.FILL_FORM  # Not just FILL
        assert IntentType.NAVIGATE
        assert IntentType.SCROLL
        assert IntentType.WAIT
        assert IntentType.EXTRACT
        assert IntentType.SEARCH
        assert IntentType.UNKNOWN


class TestIntent:
    """Test the Intent dataclass."""
    
    def test_create_click_intent(self):
        """Test creating a click intent."""
        from llm_web_agent.intelligence.nlp.intent_parser import Intent, IntentType
        intent = Intent(
            intent_type=IntentType.CLICK,
            target="submit button",
            confidence=0.95
        )
        assert intent.intent_type == IntentType.CLICK
        assert intent.target == "submit button"
        assert intent.confidence == 0.95
    
    def test_create_fill_intent_with_value(self):
        """Test creating a fill intent with value."""
        from llm_web_agent.intelligence.nlp.intent_parser import Intent, IntentType
        intent = Intent(
            intent_type=IntentType.FILL_FORM,
            target="email field",
            value="test@test.com",
            confidence=0.9
        )
        assert intent.value == "test@test.com"


class TestIntentParser:
    """Test the IntentParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create an IntentParser instance."""
        from llm_web_agent.intelligence.nlp.intent_parser import IntentParser
        return IntentParser()
    
    @pytest.mark.asyncio
    async def test_parse_click_instruction(self, parser):
        """Test parsing a click instruction."""
        result = await parser.parse("click the submit button")
        assert result is not None
        from llm_web_agent.intelligence.nlp.intent_parser import IntentType
        assert result.intent_type == IntentType.CLICK
    
    @pytest.mark.asyncio
    async def test_parse_navigate_instruction(self, parser):
        """Test parsing a navigate instruction."""
        result = await parser.parse("go to https://google.com")
        from llm_web_agent.intelligence.nlp.intent_parser import IntentType
        assert result.intent_type == IntentType.NAVIGATE
    
    @pytest.mark.asyncio
    async def test_parse_fill_instruction(self, parser):
        """Test parsing a fill instruction."""
        result = await parser.parse("fill in the email with test@test.com")
        from llm_web_agent.intelligence.nlp.intent_parser import IntentType
        assert result.intent_type == IntentType.FILL_FORM
    
    @pytest.mark.asyncio
    async def test_parse_scroll_instruction(self, parser):
        """Test parsing a scroll instruction."""
        result = await parser.parse("scroll down")
        from llm_web_agent.intelligence.nlp.intent_parser import IntentType
        assert result.intent_type == IntentType.SCROLL


class TestStepDependency:
    """Test StepDependency enum."""
    
    def test_dependency_types_exist(self):
        """Test dependency types exist."""
        from llm_web_agent.intelligence.planning.task_decomposer import StepDependency
        assert StepDependency.NONE
        assert StepDependency.SEQUENTIAL
        assert StepDependency.PARALLEL
        assert StepDependency.CONDITIONAL


class TestPlannedStep:
    """Test the PlannedStep dataclass."""
    
    def test_create_step(self):
        """Test creating a planned step."""
        from llm_web_agent.intelligence.planning.task_decomposer import PlannedStep
        step = PlannedStep(
            step_id="step1",
            action="click",
            target="button#submit"
        )
        assert step.step_id == "step1"
        assert step.action == "click"
    
    def test_step_with_value(self):
        """Test step with value."""
        from llm_web_agent.intelligence.planning.task_decomposer import PlannedStep
        step = PlannedStep(
            step_id="step1",
            action="fill",
            target="#email",
            value="test@test.com"
        )
        assert step.value == "test@test.com"


class TestTaskPlan:
    """Test the TaskPlan dataclass."""
    
    def test_create_empty_plan(self):
        """Test creating an empty plan."""
        from llm_web_agent.intelligence.planning.task_decomposer import TaskPlan
        plan = TaskPlan(task="test task", steps=[])
        assert plan.task == "test task"
        assert len(plan.steps) == 0
    
    def test_plan_with_steps(self):
        """Test plan with steps."""
        from llm_web_agent.intelligence.planning.task_decomposer import (
            TaskPlan, PlannedStep
        )
        steps = [
            PlannedStep(step_id="1", action="click", target="button"),
            PlannedStep(step_id="2", action="fill", target="input")
        ]
        plan = TaskPlan(task="test", steps=steps)
        assert len(plan.steps) == 2


class TestTaskDecomposer:
    """Test the TaskDecomposer class."""
    
    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM provider."""
        llm = MagicMock()
        llm.complete = AsyncMock()
        return llm
    
    @pytest.fixture
    def decomposer(self, mock_llm):
        """Create a TaskDecomposer instance."""
        from llm_web_agent.intelligence.planning.task_decomposer import TaskDecomposer
        return TaskDecomposer(mock_llm)
    
    @pytest.mark.asyncio
    async def test_decompose_not_implemented(self, decomposer):
        """Test decompose raises NotImplementedError (stub)."""
        with pytest.raises(NotImplementedError):
            await decomposer.decompose("Login to the app")
    
    @pytest.mark.asyncio
    async def test_decompose_from_intent_not_implemented(self, decomposer):
        """Test decompose_from_intent raises NotImplementedError (stub)."""
        from llm_web_agent.intelligence.nlp.intent_parser import Intent, IntentType
        intent = Intent(intent_type=IntentType.CLICK, target="button", confidence=0.9)
        with pytest.raises(NotImplementedError):
            await decomposer.decompose_from_intent(intent)
    
    def test_validate_empty_plan(self, decomposer):
        """Test validating empty plan returns error."""
        from llm_web_agent.intelligence.planning.task_decomposer import TaskPlan
        plan = TaskPlan(task="test", steps=[])
        is_valid, errors = decomposer.validate_plan(plan)
        assert is_valid is False
        assert len(errors) > 0


class TestDOMParser:
    """Test the DOMParser class."""
    
    def test_dom_parser_exists(self):
        """Test DOMParser class exists."""
        from llm_web_agent.intelligence.dom.parser import DOMParser
        assert DOMParser is not None
    
    @pytest.fixture
    def parser(self):
        """Create a DOMParser instance."""
        from llm_web_agent.intelligence.dom.parser import DOMParser
        return DOMParser()


class TestDOMSimplifier:
    """Test the DOMSimplifier class."""
    
    def test_simplifier_exists(self):
        """Test DOMSimplifier class exists."""
        from llm_web_agent.intelligence.dom.simplifier import DOMSimplifier
        assert DOMSimplifier is not None


class TestSelectorGenerator:
    """Test the SelectorGenerator class."""
    
    def test_selector_generator_exists(self):
        """Test SelectorGenerator class exists."""
        from llm_web_agent.intelligence.dom.selector_generator import SelectorGenerator
        assert SelectorGenerator is not None


class TestActionMapper:
    """Test the ActionMapper class."""
    
    def test_action_mapper_exists(self):
        """Test ActionMapper class exists."""
        from llm_web_agent.intelligence.planning.action_mapper import ActionMapper
        assert ActionMapper is not None
