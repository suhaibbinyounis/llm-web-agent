"""
Task Planner - LLM-first task planning with multiple locator options.

Replaces the regex-based InstructionParser with a single LLM call that:
1. Understands the user's goal in context
2. Plans all steps upfront
3. Generates multiple locator strategies per step
4. Detects framework and recommends selector approach
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage
    from llm_web_agent.interfaces.llm import ILLMProvider

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Supported action types."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SELECT = "select"
    SCROLL = "scroll"
    WAIT = "wait"
    PRESS_KEY = "press_key"
    HOVER = "hover"
    EXTRACT = "extract"


class LocatorType(str, Enum):
    """Locator strategy types - ordered by reliability."""
    TESTID = "testid"       # data-testid - most stable
    ROLE = "role"           # ARIA role + name
    LABEL = "label"         # Form label association
    PLACEHOLDER = "placeholder"
    TEXT = "text"           # Visible text content
    ARIA = "aria"           # aria-label
    CSS = "css"             # CSS selector (fallback)
    XPATH = "xpath"         # XPath (last resort)


@dataclass
class Locator:
    """A single locator strategy for finding an element."""
    type: LocatorType
    value: str
    name: Optional[str] = None  # For role locators: getByRole(role, {name: ...})
    exact: bool = False         # Exact text match vs contains
    
    def to_playwright(self) -> str:
        """Convert to Playwright locator method call."""
        if self.type == LocatorType.TESTID:
            return f'getByTestId("{self.value}")'
        elif self.type == LocatorType.ROLE:
            if self.name:
                return f'getByRole("{self.value}", name="{self.name}")'
            return f'getByRole("{self.value}")'
        elif self.type == LocatorType.LABEL:
            return f'getByLabel("{self.value}")'
        elif self.type == LocatorType.PLACEHOLDER:
            return f'getByPlaceholder("{self.value}")'
        elif self.type == LocatorType.TEXT:
            if self.exact:
                return f'getByText("{self.value}", exact=True)'
            return f'getByText("{self.value}")'
        elif self.type == LocatorType.ARIA:
            return f'locator("[aria-label*=\\"{self.value}\\"]")'
        elif self.type == LocatorType.CSS:
            return f'locator("{self.value}")'
        elif self.type == LocatorType.XPATH:
            return f'locator("xpath={self.value}")'
        return f'locator("{self.value}")'


@dataclass
class PlannedStep:
    """A planned step with multiple resolution options."""
    id: str
    action: ActionType
    target: str                    # Human description of target
    locators: List[Locator]        # Multiple ways to find it
    value: Optional[str] = None    # For fill/type actions
    wait_after: Optional[str] = None  # What to wait for after
    optional: bool = False         # Can fail without stopping


@dataclass
class ExecutionPlan:
    """Complete execution plan from LLM."""
    goal: str
    steps: List[PlannedStep]
    framework_hints: List[str] = field(default_factory=list)
    recommended_strategy: Optional[str] = None
    
    def __len__(self):
        return len(self.steps)


PLANNING_PROMPT = '''You are a browser automation planner. Create a precise execution plan.

## Current Page Context
URL: {url}
Title: {title}
Interactive Elements: {elements_summary}

## User Goal
{goal}

## Instructions
Create steps to achieve the goal. For EACH step, provide:
1. action: navigate|click|fill|type|select|scroll|wait|press_key|hover|extract
2. target: For "navigate" action, this MUST be a full URL starting with https:// (e.g., "https://www.example.com"). For other actions, use a human-readable description.
3. locators: MULTIPLE ways to find the element (in priority order):
   - testid: data-testid attribute value (if likely exists)
   - role: ARIA role (button, link, textbox, etc.) with name
   - label: Associated label text (for form inputs)
   - placeholder: Placeholder text (for inputs)
   - text: Exact visible text
   - css: CSS selector
4. value: For fill/type actions, and also for navigate actions (the URL)
5. wait_after: navigation|network_idle|selector:XXX|time:XXX (optional)

IMPORTANT: For navigate actions, "target" and "value" MUST be actual URLs like "https://www.saucedemo.com", NOT descriptions.

## Response Format (JSON only)
{{
  "steps": [
    {{
      "action": "navigate",
      "target": "https://www.saucedemo.com",
      "locators": [],
      "value": "https://www.saucedemo.com",
      "wait_after": "navigation"
    }},
    {{
      "action": "fill",
      "target": "Username field",
      "locators": [
        {{"type": "testid", "value": "username"}},
        {{"type": "label", "value": "Username"}},
        {{"type": "placeholder", "value": "Enter username"}}
      ],
      "value": "john_doe"
    }},
    {{
      "action": "click",
      "target": "Login button",
      "locators": [
        {{"type": "testid", "value": "login-btn"}},
        {{"type": "role", "value": "button", "name": "Login"}},
        {{"type": "text", "value": "Login"}}
      ],
      "wait_after": "navigation"
    }}
  ],
  "framework_hints": ["react"],
  "recommended_strategy": "testid"
}}

Only output valid JSON. No markdown, no explanation.'''


class TaskPlanner:
    """
    LLM-first task planning - ONE call, complete execution plan.
    
    Replaces the regex-based InstructionParser with intelligent planning
    that understands context and generates multiple locator strategies.
    """
    
    def __init__(self, llm_provider: "ILLMProvider", timeout_seconds: int = 60):
        self._llm = llm_provider
        self._timeout = timeout_seconds
    
    async def plan(
        self,
        page: "IPage",
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionPlan:
        """
        Create complete execution plan with ONE LLM call.
        
        Args:
            page: Current browser page (for context)
            goal: User's natural language goal
            context: Optional additional context
            
        Returns:
            ExecutionPlan with all steps and locators
        """
        import asyncio
        from llm_web_agent.interfaces.llm import Message
        
        # Get lightweight page context
        page_context = await self._get_page_context(page)
        
        # Format prompt
        prompt = PLANNING_PROMPT.format(
            url=page.url,
            title=await page.title(),
            elements_summary=json.dumps(page_context.get('elements', [])[:25], indent=2),
            goal=goal,
        )
        
        logger.debug(f"Planning task: {goal}")
        
        try:
            response = await asyncio.wait_for(
                self._llm.complete([Message.user(prompt)], temperature=0.2),
                timeout=self._timeout
            )
            
            plan_data = self._parse_response(response.content)
            
            # Build ExecutionPlan
            steps = []
            for i, step_data in enumerate(plan_data.get('steps', [])):
                step = self._build_step(i, step_data)
                if step:
                    steps.append(step)
            
            if not steps:
                logger.warning("LLM returned no valid steps")
                # Fallback: parse goal into multiple steps
                steps = self._parse_fallback_steps(goal)
            
            plan = ExecutionPlan(
                goal=goal,
                steps=steps,
                framework_hints=plan_data.get('framework_hints', []),
                recommended_strategy=plan_data.get('recommended_strategy'),
            )
            
            logger.info(f"Planned {len(plan)} steps, framework hints: {plan.framework_hints}")
            return plan
            
        except asyncio.TimeoutError:
            logger.error(f"Planning timed out after {self._timeout}s")
            return ExecutionPlan(goal=goal, steps=self._parse_fallback_steps(goal))
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            return ExecutionPlan(goal=goal, steps=self._parse_fallback_steps(goal))
    
    async def plan_streaming(
        self,
        page: "IPage",
        goal: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> "AsyncIterator[PlannedStep]":
        """
        Stream planned steps as they are parsed from LLM response.
        
        This enables execution to start before the full plan is received,
        reducing overall latency for multi-step tasks.
        
        Args:
            page: Current browser page
            goal: User's natural language goal
            context: Optional additional context
            
        Yields:
            PlannedStep objects as they are parsed
        """
        import asyncio
        import re
        from llm_web_agent.interfaces.llm import Message
        from typing import AsyncIterator
        
        # Get lightweight page context
        page_context = await self._get_page_context(page)
        
        # Format prompt
        prompt = PLANNING_PROMPT.format(
            url=page.url,
            title=await page.title(),
            elements_summary=json.dumps(page_context.get('elements', [])[:25], indent=2),
            goal=goal,
        )
        
        logger.debug(f"Streaming plan for: {goal}")
        
        # Track which steps we've yielded
        yielded_step_ids = set()
        step_index = 0
        
        try:
            # Try streaming if provider supports it
            buffer = ""
            async for chunk in self._llm.stream([Message.user(prompt)], temperature=0.2):
                buffer += chunk
                
                # Try to extract complete step objects from buffer
                # Look for complete JSON objects within the steps array
                step_pattern = r'\{\s*"action"\s*:\s*"[^"]+"\s*,\s*"target"\s*:\s*"[^"]*"[^}]*\}'
                
                for match in re.finditer(step_pattern, buffer):
                    step_json = match.group()
                    
                    # Check if this step object looks complete
                    try:
                        step_data = json.loads(step_json)
                        step = self._build_step(step_index, step_data)
                        
                        if step and step.id not in yielded_step_ids:
                            yielded_step_ids.add(step.id)
                            step_index += 1
                            logger.info(f"Streaming step {step_index}: {step.action.value} {step.target}")
                            yield step
                            
                            # Remove parsed step from buffer to avoid re-matching
                            # Only remove the first occurrence
                            buffer = buffer.replace(step_json, "", 1)
                            
                    except json.JSONDecodeError:
                        # Incomplete JSON, keep buffering
                        continue
            
            # After streaming completes, try to parse any remaining steps
            # that might have been missed due to formatting
            if buffer:
                full_data = self._parse_response(buffer)
                for i, step_data in enumerate(full_data.get('steps', [])):
                    step = self._build_step(i + step_index, step_data)
                    if step and step.id not in yielded_step_ids:
                        yielded_step_ids.add(step.id)
                        yield step
                        
        except Exception as e:
            logger.warning(f"Streaming plan failed, falling back to batch: {e}")
            # Fallback to regular planning
            plan = await self.plan(page, goal, context)
            for step in plan.steps:
                if step.id not in yielded_step_ids:
                    yield step
    
    async def _get_page_context(self, page: "IPage") -> Dict[str, Any]:
        """Extract lightweight page context for planning."""
        try:
            return await page.evaluate('''() => {
                const elements = [];
                const seen = new Set();
                
                // Interactive elements
                document.querySelectorAll(
                    'button, a, input, select, textarea, [role="button"], [role="link"], [role="textbox"]'
                ).forEach(el => {
                    if (el.offsetParent === null) return;  // Not visible
                    
                    const text = (el.textContent || '').trim().slice(0, 50);
                    const key = el.tagName + ':' + text;
                    if (seen.has(key)) return;
                    seen.add(key);
                    
                    elements.push({
                        tag: el.tagName.toLowerCase(),
                        text: text,
                        id: el.id || null,
                        testid: el.dataset?.testid || null,
                        role: el.getAttribute('role'),
                        ariaLabel: el.getAttribute('aria-label'),
                        placeholder: el.placeholder || null,
                        type: el.type || null,
                        name: el.name || null,
                    });
                });
                
                return {
                    elements: elements.slice(0, 50),
                    hasTestIds: elements.some(e => e.testid),
                    hasAriaLabels: elements.some(e => e.ariaLabel),
                    formCount: document.forms.length,
                };
            }''')
        except Exception as e:
            logger.debug(f"Failed to get page context: {e}")
            return {'elements': [], 'hasTestIds': False, 'hasAriaLabels': False}
    
    def _parse_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response, handling markdown code blocks."""
        content = content.strip()
        
        # Handle markdown code blocks
        if '```json' in content:
            start = content.index('```json') + 7
            end = content.index('```', start)
            content = content[start:end]
        elif '```' in content:
            start = content.index('```') + 3
            end = content.index('```', start)
            content = content[start:end]
        
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            logger.debug(f"Response content: {content[:500]}")
            return {'steps': []}
    
    def _build_step(self, index: int, data: Dict[str, Any]) -> Optional[PlannedStep]:
        """Build a PlannedStep from parsed data."""
        try:
            action_str = data.get('action', '').lower()
            try:
                action = ActionType(action_str)
            except ValueError:
                logger.warning(f"Unknown action type: {action_str}")
                action = ActionType.CLICK  # Default

            target = data.get('target', '')
            value = data.get('value')

            # For navigate actions, ensure target is a valid URL
            if action == ActionType.NAVIGATE:
                # Use value if it looks like a URL, otherwise try to fix target
                if value and (value.startswith('http://') or value.startswith('https://')):
                    target = value
                elif not (target.startswith('http://') or target.startswith('https://')):
                    # Try to extract domain from target description
                    import re
                    # Look for domain-like patterns in the target
                    domain_match = re.search(r'(\w+(?:\.\w+)+)', target.lower())
                    if domain_match:
                        target = f"https://{domain_match.group(1)}"
                    else:
                        # Common site mappings for fallback
                        target_lower = target.lower()
                        if 'saucedemo' in target_lower:
                            target = 'https://www.saucedemo.com'
                        elif 'google' in target_lower:
                            target = 'https://www.google.com'
                        else:
                            logger.warning(f"Navigate target '{target}' is not a valid URL")
                value = target  # Ensure value matches target for navigate

            # Parse locators
            locators = []
            for loc_data in data.get('locators', []):
                try:
                    loc_type = LocatorType(loc_data.get('type', 'text'))
                    locators.append(Locator(
                        type=loc_type,
                        value=loc_data.get('value', ''),
                        name=loc_data.get('name'),
                        exact=loc_data.get('exact', False),
                    ))
                except ValueError:
                    continue

            # Ensure at least one locator (not needed for navigate)
            if not locators and action != ActionType.NAVIGATE:
                locators = [Locator(type=LocatorType.TEXT, value=target)]

            return PlannedStep(
                id=f"step_{index}",
                action=action,
                target=target,
                locators=locators,
                value=value,
                wait_after=data.get('wait_after'),
                optional=data.get('optional', False),
            )
        except Exception as e:
            logger.error(f"Failed to build step: {e}")
            return None
    
    def _parse_fallback_steps(self, goal: str) -> List[PlannedStep]:
        """
        Parse goal into multiple fallback steps.
        
        Handles:
        - Numbered lists (1. do this 2. do that)
        - Comma-separated steps
        - Newline-separated steps
        """
        import re
        
        steps = []
        
        # Try to split by numbered list pattern
        numbered_pattern = r'(?:^|\n)\s*\d+[\.\)]\s*(.+?)(?=(?:\n\s*\d+[\.\)])|$)'
        numbered_matches = re.findall(numbered_pattern, goal, re.IGNORECASE | re.DOTALL)
        
        if numbered_matches:
            for i, match in enumerate(numbered_matches):
                step = self._parse_single_step(i, match.strip())
                if step:
                    steps.append(step)
        else:
            # Try newline separation
            lines = [l.strip() for l in goal.split('\n') if l.strip()]
            if len(lines) > 1:
                for i, line in enumerate(lines):
                    step = self._parse_single_step(i, line)
                    if step:
                        steps.append(step)
            else:
                # Try comma separation
                parts = [p.strip() for p in goal.split(',') if p.strip()]
                if len(parts) > 1:
                    for i, part in enumerate(parts):
                        step = self._parse_single_step(i, part)
                        if step:
                            steps.append(step)
                else:
                    # Single step
                    step = self._parse_single_step(0, goal)
                    if step:
                        steps.append(step)
        
        return steps if steps else [self._create_default_step(goal)]
    
    def _parse_single_step(self, index: int, text: str) -> Optional[PlannedStep]:
        """Parse a single instruction text into a step."""
        import re
        
        text = text.strip()
        if not text:
            return None
        
        text_lower = text.lower()
        
        # Navigation
        nav_match = re.match(r'^(?:go\s+to|navigate\s+to|open)\s+(.+)$', text_lower)
        if nav_match:
            url = nav_match.group(1).strip()
            if not url.startswith('http'):
                url = 'https://' + url
            return PlannedStep(
                id=f"step_{index}",
                action=ActionType.NAVIGATE,
                target=url,
                locators=[],
                value=url,
            )
        
        # Fill action with value
        fill_match = re.match(r'^(?:enter|fill|type|input)\s+(?:(?:the\s+)?(?:value\s+)?)?["\']?(.+?)["\']?\s+(?:in|into|to)\s+(?:the\s+)?(.+)$', text_lower)
        if fill_match:
            value, target = fill_match.groups()
            return PlannedStep(
                id=f"step_{index}",
                action=ActionType.FILL,
                target=target.strip(),
                locators=[
                    Locator(type=LocatorType.LABEL, value=target.strip()),
                    Locator(type=LocatorType.PLACEHOLDER, value=target.strip()),
                    Locator(type=LocatorType.TEXT, value=target.strip()),
                ],
                value=value.strip().strip('"\''),
            )
        
        # Fill with username/password pattern
        fill_match2 = re.match(r'^(?:enter|fill|type)\s+(?:username|password)\s+["\']?(.+?)["\']?$', text_lower)
        if fill_match2:
            value = fill_match2.group(1)
            field_type = 'username' if 'username' in text_lower else 'password'
            return PlannedStep(
                id=f"step_{index}",
                action=ActionType.FILL,
                target=f"{field_type} field",
                locators=[
                    Locator(type=LocatorType.LABEL, value=field_type.capitalize()),
                    Locator(type=LocatorType.PLACEHOLDER, value=field_type),
                    Locator(type=LocatorType.CSS, value=f'input[type="{field_type}"]' if field_type == 'password' else f'input[name="{field_type}"], input#user-name'),
                ],
                value=value.strip().strip('"\''),
            )
        
        # Click action
        click_match = re.match(r'^click\s+(?:on\s+)?(?:the\s+)?(.+)$', text_lower)
        if click_match:
            target = click_match.group(1).strip()
            return PlannedStep(
                id=f"step_{index}",
                action=ActionType.CLICK,
                target=target,
                locators=[
                    Locator(type=LocatorType.ROLE, value="button", name=target),
                    Locator(type=LocatorType.TEXT, value=target),
                ],
            )
        
        # Wait action
        if text_lower.startswith('wait'):
            return PlannedStep(
                id=f"step_{index}",
                action=ActionType.WAIT,
                target=text,
                locators=[],
                value="2",  # Default 2 second wait
            )
        
        # Scroll action
        if 'scroll' in text_lower:
            direction = 'down' if 'down' in text_lower else 'up'
            return PlannedStep(
                id=f"step_{index}",
                action=ActionType.SCROLL,
                target=direction,
                locators=[],
            )
        
        # Default: try as click
        return PlannedStep(
            id=f"step_{index}",
            action=ActionType.CLICK,
            target=text,
            locators=[Locator(type=LocatorType.TEXT, value=text)],
        )
    
    def _create_default_step(self, goal: str) -> PlannedStep:
        """Create a default step when all parsing fails."""
        return PlannedStep(
            id="step_0",
            action=ActionType.CLICK,
            target=goal[:50],  # Truncate long goals
            locators=[Locator(type=LocatorType.TEXT, value=goal[:50])],
        )
