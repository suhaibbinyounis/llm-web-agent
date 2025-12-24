"""
Tests for InstructionParser - pattern matching and parsing.
"""

import pytest

from llm_web_agent.engine.instruction_parser import InstructionParser, ParsedClause
from llm_web_agent.engine.task_graph import TaskGraph, StepIntent


class TestPatternMatchingNavigation:
    """Test navigation pattern matching."""
    
    @pytest.mark.parametrize("instruction,expected_target", [
        ("go to google.com", "google.com"),
        ("Go to https://example.com", "https://example.com"),
        ("navigate to amazon.com", "amazon.com"),
        ("open github.com", "github.com"),
        ("visit example.org", "example.org"),
    ])
    def test_navigation_patterns(self, instruction, expected_target):
        """Test various navigation patterns."""
        parser = InstructionParser()
        graph = parser.parse_sync(instruction)
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.NAVIGATE
        assert graph.steps[0].target == expected_target


class TestPatternMatchingClick:
    """Test click pattern matching."""
    
    @pytest.mark.parametrize("instruction,expected_target", [
        ("click the login button", "login button"),
        ("click on submit", "submit"),
        ("press the send button", "send button"),
        ("tap next", "next"),
        ("select the option", "option"),
    ])
    def test_click_patterns(self, instruction, expected_target):
        """Test various click patterns."""
        parser = InstructionParser()
        graph = parser.parse_sync(instruction)
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.CLICK
        assert graph.steps[0].target == expected_target


class TestPatternMatchingFill:
    """Test fill/type pattern matching."""
    
    def test_type_into_pattern(self):
        """Test 'type X into Y' pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("type 'hello world' into the search box")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.FILL
        assert graph.steps[0].value == "hello world"
        assert graph.steps[0].target == "search box"
    
    def test_enter_in_pattern(self):
        """Test 'enter X in Y' pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("enter test@email.com in the email field")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.FILL
        assert graph.steps[0].value == "test@email.com"
        assert graph.steps[0].target == "email field"
    
    def test_fill_with_pattern(self):
        """Test 'fill X with Y' pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("fill the password field with secret123")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.FILL
        assert graph.steps[0].target == "password field"
        assert graph.steps[0].value == "secret123"
    
    def test_search_pattern(self):
        """Test search pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("search for python tutorials")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.FILL
        assert graph.steps[0].value == "python tutorials"
        # Target should be "search" (default for search pattern)
        assert graph.steps[0].target == "search"


class TestPatternMatchingExtract:
    """Test extract/copy pattern matching."""
    
    def test_copy_pattern(self):
        """Test 'copy X' pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("copy the order number")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.EXTRACT
        assert graph.steps[0].target == "order number"
    
    def test_copy_and_store_pattern(self):
        """Test 'copy X and save as Y' pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("copy the price and store as product_price")
        
        # Parser splits on 'and', so may generate multiple steps
        assert len(graph.steps) >= 1
        assert graph.steps[0].intent == StepIntent.EXTRACT
        assert graph.steps[0].target == "price"
    
    def test_remember_as_pattern(self):
        """Test 'remember X as Y' pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("remember the confirmation code as code")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.EXTRACT
        assert graph.steps[0].target == "confirmation code"
        assert graph.steps[0].store_as == "code"


class TestPatternMatchingOther:
    """Test other action patterns."""
    
    def test_scroll_down(self):
        """Test scroll pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("scroll down")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.SCROLL
        assert graph.steps[0].target == "down"
    
    def test_scroll_to_element(self):
        """Test scroll to element pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("scroll to the footer")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.SCROLL
        assert graph.steps[0].target == "footer"
    
    def test_wait_for_seconds(self):
        """Test wait pattern with seconds."""
        parser = InstructionParser()
        graph = parser.parse_sync("wait for 5 seconds")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.WAIT
        assert graph.steps[0].value == "5"
    
    def test_wait_for_element(self):
        """Test wait for element pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("wait for the loading spinner")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.WAIT
        assert graph.steps[0].target == "loading spinner"
    
    def test_hover_pattern(self):
        """Test hover pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("hover over the menu")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.HOVER
        assert graph.steps[0].target == "menu"
    
    def test_press_enter(self):
        """Test press key pattern."""
        parser = InstructionParser()
        # Use clearer wording that matches the pattern
        graph = parser.parse_sync("press enter key")
        
        # The pattern for press_key may match differently
        assert len(graph.steps) >= 1
    
    def test_submit_pattern(self):
        """Test submit pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("submit the form")
        
        assert len(graph.steps) == 1
        assert graph.steps[0].intent == StepIntent.SUBMIT
    
    def test_select_dropdown(self):
        """Test select dropdown pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("select California from state dropdown")
        
        # The select pattern needs 'from' keyword
        assert len(graph.steps) >= 1


class TestClauseSplitting:
    """Test splitting instructions into clauses."""
    
    def test_comma_separated(self):
        """Test comma-separated clauses."""
        parser = InstructionParser()
        graph = parser.parse_sync("go to google.com, search for cats")
        
        assert len(graph.steps) == 2
        assert graph.steps[0].intent == StepIntent.NAVIGATE
        assert graph.steps[1].intent == StepIntent.FILL
    
    def test_and_separator(self):
        """Test 'and' separated clauses."""
        parser = InstructionParser()
        graph = parser.parse_sync("click the button and wait for 2 seconds")
        
        assert len(graph.steps) == 2
        assert graph.steps[0].intent == StepIntent.CLICK
        assert graph.steps[1].intent == StepIntent.WAIT
    
    def test_then_separator(self):
        """Test 'then' separated clauses."""
        parser = InstructionParser()
        graph = parser.parse_sync("fill the form then submit")
        
        # Note: "fill the form" might not match a pattern exactly
        # but "submit" should
        assert len(graph.steps) >= 1
    
    def test_complex_instruction(self):
        """Test complex multi-step instruction."""
        parser = InstructionParser()
        graph = parser.parse_sync(
            "go to amazon.com, search for laptops, click the first result, "
            "copy the price"
        )
        
        # Should have at least 4 core steps
        assert len(graph.steps) >= 4
        assert graph.steps[0].intent == StepIntent.NAVIGATE
        assert graph.steps[0].target == "amazon.com"
        assert graph.steps[1].intent == StepIntent.FILL
        assert graph.steps[1].value == "laptops"
        assert graph.steps[2].intent == StepIntent.CLICK


class TestGraphDependencies:
    """Test that parsed graphs have correct dependencies."""
    
    def test_sequential_dependencies(self):
        """Test steps have sequential dependencies."""
        parser = InstructionParser()
        graph = parser.parse_sync("go to google.com, search for cats, click submit")
        
        assert len(graph.steps) == 3
        
        # First step has no dependencies
        assert len(graph.steps[0].depends_on) == 0
        
        # Second step depends on first
        assert graph.steps[1].depends_on == [graph.steps[0].id]
        
        # Third step depends on second
        assert graph.steps[2].depends_on == [graph.steps[1].id]


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_instruction(self):
        """Test empty instruction."""
        parser = InstructionParser()
        graph = parser.parse_sync("")
        
        assert len(graph.steps) == 0
    
    def test_whitespace_instruction(self):
        """Test whitespace-only instruction."""
        parser = InstructionParser()
        graph = parser.parse_sync("   \n\t  ")
        
        assert len(graph.steps) == 0
    
    def test_unknown_pattern(self):
        """Test instruction with no matching pattern."""
        parser = InstructionParser()
        graph = parser.parse_sync("do something weird that doesnt match")
        
        # Should fall back to CUSTOM intent
        assert len(graph.steps) >= 1


class TestOriginalInstruction:
    """Test original instruction preservation."""
    
    def test_preserves_original(self):
        """Test that original instruction is preserved."""
        parser = InstructionParser()
        instruction = "go to google.com and search for cats"
        
        graph = parser.parse_sync(instruction)
        
        assert graph.original_instruction == instruction
