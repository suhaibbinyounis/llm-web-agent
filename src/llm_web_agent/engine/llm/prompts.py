"""
Prompt Templates - All LLM prompts for the engine.

Design principles:
1. Be explicit and structured
2. Request JSON output
3. Provide examples
4. Keep token count manageable
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# =============================================================================
# INSTRUCTION PARSING PROMPT
# =============================================================================

INSTRUCTION_PARSE_SYSTEM = """You are an expert at converting natural language instructions into structured browser automation steps.

Your task is to parse user instructions and output a JSON array of steps. Each step should have:
- `intent`: The action type (navigate, click, fill, type, select, extract, hover, scroll, wait, submit, press_key)
- `target`: What element to interact with (URL, selector description, or element description)
- `value`: Value to input (for fill/type/select) or key to press
- `store_as`: If extracting data, the key to store it under

RULES:
1. Be precise - each step should be ONE atomic action
2. Infer targets from context (e.g., "search" usually means a search input)
3. For forms, each field is a separate fill step
4. For copy/extract operations, include store_as
5. Navigation changes pages - subsequent steps are on new page

OUTPUT FORMAT (JSON array):
```json
[
  {"intent": "navigate", "target": "amazon.com"},
  {"intent": "fill", "target": "search box", "value": "laptops"},
  {"intent": "click", "target": "search button"},
  {"intent": "extract", "target": "first result price", "store_as": "price"}
]
```"""

INSTRUCTION_PARSE_USER = """Parse this instruction into steps:

{instruction}

{context}

Output ONLY valid JSON array, no explanation."""

# =============================================================================
# ELEMENT FINDING PROMPT
# =============================================================================

ELEMENT_FIND_SYSTEM = """You are an expert at finding elements in web page DOM.

Given a simplified DOM and an element description, identify the best matching element.

OUTPUT FORMAT (JSON object):
```json
{
  "found": true,
  "index": 5,
  "selector": "#login-button",
  "confidence": 0.95,
  "reasoning": "Button with text 'Login' matches the description"
}
```

If no match found:
```json
{
  "found": false,
  "suggestions": ["Try looking for 'Sign in' instead"],
  "reasoning": "No element matching 'login button' found in DOM"
}
```

RULES:
1. Match by text content, aria-label, placeholder, id, name, or role
2. Consider synonyms (login = sign in, search = find)
3. Prefer visible, interactive elements
4. Return the element INDEX from the provided list"""

ELEMENT_FIND_USER = """Find this element: "{description}"

Current URL: {url}

Available elements:
{elements}

Output ONLY valid JSON, no explanation."""

# =============================================================================
# ACTION PLANNING PROMPT
# =============================================================================

ACTION_PLAN_SYSTEM = """You are an expert web automation planner.

Given the current page state and a goal, create a step-by-step plan to achieve it.

Consider:
1. What elements are available on the current page
2. What actions are possible (click, fill, navigate, etc.)
3. Dependencies between steps
4. Error handling (what if element not found?)

OUTPUT FORMAT (JSON object):
```json
{
  "plan": [
    {"step": 1, "intent": "click", "target": "login link", "reason": "Navigate to login page"},
    {"step": 2, "intent": "fill", "target": "email field", "value": "{{email}}", "reason": "Enter email"},
    {"step": 3, "intent": "fill", "target": "password field", "value": "{{password}}", "reason": "Enter password"},
    {"step": 4, "intent": "click", "target": "submit button", "reason": "Submit form"}
  ],
  "variables_needed": ["email", "password"],
  "estimated_pages": 2
}
```"""

ACTION_PLAN_USER = """Goal: {goal}

Current URL: {url}
Page title: {title}

Available elements on current page:
{elements}

Variables available: {variables}

Create a plan. Output ONLY valid JSON, no explanation."""

# =============================================================================
# ERROR RECOVERY PROMPT
# =============================================================================

ERROR_RECOVERY_SYSTEM = """You are an expert at debugging web automation failures.

Given a failed action and the current page state, suggest how to recover.

Consider:
1. The element might have a different name/selector
2. The page might not have loaded fully
3. A popup or modal might be blocking
4. The page structure might have changed

OUTPUT FORMAT (JSON object):
```json
{
  "diagnosis": "Button text is 'Sign In' not 'Login'",
  "recovery_steps": [
    {"intent": "click", "target": "Sign In button"}
  ],
  "should_retry": true,
  "alternative_approach": "Try pressing Enter after filling password"
}
```"""

ERROR_RECOVERY_USER = """Action failed: {action}
Error: {error}

Current URL: {url}
Page title: {title}

Available elements:
{elements}

History of actions taken:
{history}

Suggest recovery. Output ONLY valid JSON, no explanation."""

# =============================================================================
# DOM DESCRIPTION PROMPT (for element extraction)
# =============================================================================

DOM_DESCRIBE_SYSTEM = """You are analyzing a web page DOM to extract a specific piece of information.

Given the DOM and what to extract, find and return the value.

OUTPUT FORMAT (JSON object):
```json
{
  "found": true,
  "value": "$299.99",
  "element_index": 42,
  "confidence": 0.9
}
```"""

DOM_DESCRIBE_USER = """Extract: {what_to_extract}

Page content:
{elements}

Output ONLY valid JSON, no explanation."""

# =============================================================================
# PROMPT BUILDER
# =============================================================================

@dataclass
class PromptBuilder:
    """
    Build prompts for LLM calls.
    
    Handles:
    - Template variable substitution
    - Token counting and truncation
    - Context window management
    """
    
    max_tokens: int = 4000
    
    def build_instruction_parse(
        self,
        instruction: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[str, str]:
        """Build instruction parsing prompt."""
        context_str = ""
        if context:
            if "url" in context:
                context_str += f"Current page: {context['url']}\n"
            if "elements" in context:
                context_str += f"Available elements: {len(context['elements'])} interactive elements\n"
        
        user_prompt = INSTRUCTION_PARSE_USER.format(
            instruction=instruction,
            context=context_str,
        )
        
        return INSTRUCTION_PARSE_SYSTEM, user_prompt
    
    def build_element_find(
        self,
        description: str,
        url: str,
        elements: List[Dict[str, Any]],
    ) -> tuple[str, str]:
        """Build element finding prompt."""
        # Format elements list
        elements_str = self._format_elements(elements)
        
        user_prompt = ELEMENT_FIND_USER.format(
            description=description,
            url=url,
            elements=elements_str,
        )
        
        return ELEMENT_FIND_SYSTEM, user_prompt
    
    def build_action_plan(
        self,
        goal: str,
        url: str,
        title: str,
        elements: List[Dict[str, Any]],
        variables: Dict[str, Any],
    ) -> tuple[str, str]:
        """Build action planning prompt."""
        elements_str = self._format_elements(elements)
        variables_str = ", ".join(variables.keys()) if variables else "none"
        
        user_prompt = ACTION_PLAN_USER.format(
            goal=goal,
            url=url,
            title=title,
            elements=elements_str,
            variables=variables_str,
        )
        
        return ACTION_PLAN_SYSTEM, user_prompt
    
    def build_error_recovery(
        self,
        action: str,
        error: str,
        url: str,
        title: str,
        elements: List[Dict[str, Any]],
        history: List[str],
    ) -> tuple[str, str]:
        """Build error recovery prompt."""
        elements_str = self._format_elements(elements)
        history_str = "\n".join(f"- {h}" for h in history[-5:])  # Last 5 actions
        
        user_prompt = ERROR_RECOVERY_USER.format(
            action=action,
            error=error,
            url=url,
            title=title,
            elements=elements_str,
            history=history_str,
        )
        
        return ERROR_RECOVERY_SYSTEM, user_prompt
    
    def build_dom_describe(
        self,
        what_to_extract: str,
        elements: List[Dict[str, Any]],
    ) -> tuple[str, str]:
        """Build DOM description/extraction prompt."""
        elements_str = self._format_elements(elements)
        
        user_prompt = DOM_DESCRIBE_USER.format(
            what_to_extract=what_to_extract,
            elements=elements_str,
        )
        
        return DOM_DESCRIBE_SYSTEM, user_prompt
    
    def _format_elements(
        self,
        elements: List[Dict[str, Any]],
        max_elements: int = 100,
    ) -> str:
        """Format elements list for prompt."""
        if not elements:
            return "No interactive elements found."
        
        # Truncate if too many
        if len(elements) > max_elements:
            elements = elements[:max_elements]
        
        lines = []
        for i, elem in enumerate(elements):
            tag = elem.get("tag", "?")
            text = elem.get("text", "")[:50]  # Truncate text
            attrs = []
            
            if elem.get("id"):
                attrs.append(f"id={elem['id']}")
            if elem.get("name"):
                attrs.append(f"name={elem['name']}")
            if elem.get("type"):
                attrs.append(f"type={elem['type']}")
            if elem.get("placeholder"):
                attrs.append(f"placeholder={elem['placeholder'][:30]}")
            if elem.get("aria_label"):
                attrs.append(f"aria-label={elem['aria_label'][:30]}")
            
            attrs_str = " ".join(attrs)
            text_str = f'"{text}"' if text else ""
            
            lines.append(f"[{i}] <{tag}> {attrs_str} {text_str}".strip())
        
        return "\n".join(lines)


# Convenience instances
INSTRUCTION_PARSE_PROMPT = (INSTRUCTION_PARSE_SYSTEM, INSTRUCTION_PARSE_USER)
ELEMENT_FIND_PROMPT = (ELEMENT_FIND_SYSTEM, ELEMENT_FIND_USER)
ACTION_PLAN_PROMPT = (ACTION_PLAN_SYSTEM, ACTION_PLAN_USER)
ERROR_RECOVERY_PROMPT = (ERROR_RECOVERY_SYSTEM, ERROR_RECOVERY_USER)
