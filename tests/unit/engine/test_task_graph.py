"""
Tests for TaskGraph - step dependencies and batching.
"""

import pytest

from llm_web_agent.engine.task_graph import (
    TaskGraph,
    TaskStep,
    StepStatus,
    StepIntent,
)


class TestTaskStep:
    """Test TaskStep functionality."""
    
    def test_step_creation(self):
        """Test creating a step."""
        step = TaskStep(
            intent=StepIntent.CLICK,
            target="button",
        )
        
        assert step.intent == StepIntent.CLICK
        assert step.target == "button"
        assert step.status == StepStatus.PENDING
        assert step.id is not None
    
    def test_step_with_value(self):
        """Test step with value."""
        step = TaskStep(
            intent=StepIntent.FILL,
            target="email field",
            value="test@example.com",
        )
        
        assert step.value == "test@example.com"
    
    def test_step_with_store_as(self):
        """Test step with store_as for extraction."""
        step = TaskStep(
            intent=StepIntent.EXTRACT,
            target="price",
            store_as="product_price",
        )
        
        assert step.store_as == "product_price"
    
    def test_is_complete(self):
        """Test completion check."""
        step = TaskStep(intent=StepIntent.CLICK)
        
        assert step.is_complete() is False
        
        step.status = StepStatus.SUCCESS
        assert step.is_complete() is True
        
        step.status = StepStatus.FAILED
        assert step.is_complete() is True
        
        step.status = StepStatus.SKIPPED
        assert step.is_complete() is True
    
    def test_is_ready_no_dependencies(self):
        """Test ready check with no dependencies."""
        step = TaskStep(intent=StepIntent.CLICK)
        
        assert step.is_ready(set()) is True
    
    def test_is_ready_with_dependencies(self):
        """Test ready check with dependencies."""
        step = TaskStep(
            intent=StepIntent.CLICK,
            depends_on=["step1", "step2"],
        )
        
        # Not ready - missing dependencies
        assert step.is_ready(set()) is False
        assert step.is_ready({"step1"}) is False
        
        # Ready - all dependencies met
        assert step.is_ready({"step1", "step2"}) is True
        assert step.is_ready({"step1", "step2", "step3"}) is True
    
    def test_mark_success(self):
        """Test marking step as successful."""
        step = TaskStep(intent=StepIntent.CLICK)
        
        step.mark_success(result="clicked", duration_ms=100)
        
        assert step.status == StepStatus.SUCCESS
        assert step.result == "clicked"
        assert step.duration_ms == 100
    
    def test_mark_failed(self):
        """Test marking step as failed."""
        step = TaskStep(intent=StepIntent.CLICK)
        
        step.mark_failed("element not found", duration_ms=50)
        
        assert step.status == StepStatus.FAILED
        assert step.error == "element not found"
        assert step.duration_ms == 50
    
    def test_to_dict(self):
        """Test converting step to dict."""
        step = TaskStep(
            intent=StepIntent.FILL,
            target="email",
            value="test@test.com",
        )
        step.mark_success()
        
        d = step.to_dict()
        
        assert d["intent"] == "fill"
        assert d["target"] == "email"
        assert d["value"] == "test@test.com"
        assert d["status"] == "success"


class TestTaskGraph:
    """Test TaskGraph functionality."""
    
    def test_empty_graph(self):
        """Test empty graph."""
        graph = TaskGraph()
        
        assert len(graph.steps) == 0
        assert graph.is_complete() is True
        assert graph.has_failures() is False
    
    def test_add_step(self):
        """Test adding steps."""
        graph = TaskGraph()
        
        step1 = graph.add_step(StepIntent.NAVIGATE, target="google.com")
        step2 = graph.add_step(StepIntent.FILL, target="search", value="cats")
        
        assert len(graph.steps) == 2
        assert graph.steps[0].intent == StepIntent.NAVIGATE
        assert graph.steps[1].intent == StepIntent.FILL
    
    def test_add_step_auto_navigation(self):
        """Test auto-detection of navigation causing steps."""
        graph = TaskGraph()
        
        nav_step = graph.add_step(StepIntent.NAVIGATE, target="google.com")
        submit_step = graph.add_step(StepIntent.SUBMIT)
        
        assert nav_step.wait_for_navigation is True
        assert submit_step.wait_for_navigation is True
    
    def test_get_step(self):
        """Test getting step by ID."""
        graph = TaskGraph()
        step = graph.add_step(StepIntent.CLICK, target="button")
        
        found = graph.get_step(step.id)
        
        assert found == step
    
    def test_get_step_missing(self):
        """Test getting non-existent step."""
        graph = TaskGraph()
        
        found = graph.get_step("missing")
        
        assert found is None
    
    def test_get_ready_steps(self):
        """Test getting ready steps."""
        graph = TaskGraph()
        
        step1 = graph.add_step(StepIntent.NAVIGATE, target="google.com")
        step2 = graph.add_step(StepIntent.FILL, target="search", depends_on=[step1.id])
        step3 = graph.add_step(StepIntent.CLICK, target="button", depends_on=[step2.id])
        
        # Initially only step1 is ready
        ready = graph.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == step1.id
        
        # Mark step1 complete
        step1.mark_success()
        ready = graph.get_ready_steps()
        assert len(ready) == 1
        assert ready[0].id == step2.id
    
    def test_is_complete(self):
        """Test completion check."""
        graph = TaskGraph()
        step1 = graph.add_step(StepIntent.CLICK, target="button")
        step2 = graph.add_step(StepIntent.FILL, target="input")
        
        assert graph.is_complete() is False
        
        step1.mark_success()
        assert graph.is_complete() is False
        
        step2.mark_success()
        assert graph.is_complete() is True
    
    def test_has_failures_required(self):
        """Test failure detection for required steps."""
        graph = TaskGraph()
        step = graph.add_step(StepIntent.CLICK, target="button")
        
        step.mark_failed("error")
        
        assert graph.has_failures() is True
    
    def test_has_failures_optional(self):
        """Test failure detection for optional steps."""
        graph = TaskGraph()
        
        step = TaskStep(intent=StepIntent.CLICK, target="button", optional=True)
        graph.steps.append(step)
        
        step.mark_failed("error")
        
        assert graph.has_failures() is False


class TestTaskGraphBatching:
    """Test TaskGraph batching functionality."""
    
    def test_single_batch_no_navigation(self):
        """Test batching when no navigation."""
        graph = TaskGraph()
        graph.add_step(StepIntent.FILL, target="email", value="a@b.com")
        graph.add_step(StepIntent.FILL, target="password", value="secret")
        graph.add_step(StepIntent.CLICK, target="submit")
        
        batches = graph.get_execution_batches()
        
        assert len(batches) == 1
        assert len(batches[0]) == 3
    
    def test_split_on_navigation(self):
        """Test batching splits on navigation."""
        graph = TaskGraph()
        step1 = graph.add_step(StepIntent.NAVIGATE, target="google.com")
        step2 = graph.add_step(StepIntent.FILL, target="search", depends_on=[step1.id])
        step3 = graph.add_step(StepIntent.SUBMIT, depends_on=[step2.id])
        step4 = graph.add_step(StepIntent.CLICK, target="result", depends_on=[step3.id])
        
        batches = graph.get_execution_batches()
        
        # Should be: [navigate], [fill, submit], [click]
        # Note: Navigation ends batch, submit causes navigation
        assert len(batches) >= 2
    
    def test_respects_dependencies(self):
        """Test batching respects step dependencies."""
        graph = TaskGraph()
        step1 = graph.add_step(StepIntent.CLICK, target="button1")
        step2 = graph.add_step(StepIntent.CLICK, target="button2", depends_on=[step1.id])
        step3 = graph.add_step(StepIntent.CLICK, target="button3", depends_on=[step2.id])
        
        batches = graph.get_execution_batches()
        
        # Each step depends on previous, so 3 separate batches
        assert len(batches) == 3
    
    def test_parallel_steps_same_batch(self):
        """Test parallel steps go in same batch."""
        graph = TaskGraph()
        step0 = graph.add_step(StepIntent.NAVIGATE, target="page.com")
        
        # These three don't depend on each other
        step1 = graph.add_step(StepIntent.FILL, target="field1", depends_on=[step0.id])
        step2 = graph.add_step(StepIntent.FILL, target="field2", depends_on=[step0.id])
        step3 = graph.add_step(StepIntent.FILL, target="field3", depends_on=[step0.id])
        
        batches = graph.get_execution_batches()
        
        # First batch: navigate
        # Second batch: all three fills
        assert len(batches) == 2
        assert len(batches[1]) == 3


class TestTaskGraphSamePageGroups:
    """Test same-page grouping."""
    
    def test_group_by_navigation(self):
        """Test grouping by navigation."""
        graph = TaskGraph()
        graph.add_step(StepIntent.NAVIGATE, target="page1.com")
        graph.add_step(StepIntent.FILL, target="field")
        graph.add_step(StepIntent.NAVIGATE, target="page2.com")
        graph.add_step(StepIntent.CLICK, target="button")
        
        groups = graph.get_same_page_groups()
        
        # Should have at least 2 groups (one per navigation)
        assert len(groups) >= 2


class TestTaskGraphSummary:
    """Test TaskGraph summary generation."""
    
    def test_to_summary(self):
        """Test summary generation."""
        graph = TaskGraph()
        step1 = graph.add_step(StepIntent.NAVIGATE, target="google.com")
        step2 = graph.add_step(StepIntent.FILL, target="search", value="cats")
        step1.mark_success()
        step2.status = StepStatus.RUNNING
        
        summary = graph.to_summary()
        
        assert "2 steps" in summary
        assert "navigate" in summary
        assert "fill" in summary
    
    def test_to_dict(self):
        """Test dictionary conversion."""
        graph = TaskGraph(original_instruction="test instruction")
        graph.add_step(StepIntent.CLICK, target="button")
        
        d = graph.to_dict()
        
        assert d["original_instruction"] == "test instruction"
        assert len(d["steps"]) == 1
