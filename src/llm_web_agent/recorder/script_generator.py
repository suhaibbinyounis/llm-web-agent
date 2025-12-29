"""
Playwright Script Generator - Generates executable scripts from recordings.

Converts recorded actions into Playwright Python scripts or other formats.
"""

import json
from typing import List, Optional
from textwrap import dedent, indent

from llm_web_agent.recorder.recorder import RecordingSession, RecordedAction, ActionType


class PlaywrightScriptGenerator:
    """
    Generates Playwright Python scripts from recorded sessions.
    
    Example:
        >>> generator = PlaywrightScriptGenerator()
        >>> script = generator.generate(session)
        >>> print(script)
    """
    
    def __init__(
        self,
        async_mode: bool = True,
        include_comments: bool = True,
        include_timing: bool = True,  # Changed default to True
        browser_type: str = "chromium",
        headless: bool = False,
        min_delay_ms: int = 500,  # Minimum delay between actions
    ):
        """
        Initialize the generator.
        
        Args:
            async_mode: Generate async code (recommended)
            include_comments: Add comments explaining each step
            include_timing: Include wait times between actions
            browser_type: Browser to use (chromium, firefox, webkit)
            headless: Run in headless mode
            min_delay_ms: Minimum delay between actions
        """
        self._async = async_mode
        self._comments = include_comments
        self._timing = include_timing
        self._browser = browser_type
        self._headless = headless
        self._min_delay = min_delay_ms
    
    def generate(self, session: RecordingSession) -> str:
        """
        Generate a Playwright script from a recording session.
        
        Args:
            session: The recording session to convert
            
        Returns:
            Python script as a string
        """
        # Don't over-optimize - keep all meaningful actions
        optimized_actions = self._optimize_actions(session.actions)
        
        # Analyze inputs on optimized actions for parametrization
        # This creates self._input_data (vars) and self._input_map (action index -> var name)
        self._analyze_inputs(optimized_actions)
        
        optimized_session = RecordingSession(
            name=session.name,
            actions=optimized_actions,
            start_url=session.start_url,
            recorded_at=session.recorded_at,
            duration_ms=session.duration_ms,
            metadata=session.metadata,
        )
        
        if self._async:
            return self._generate_async(optimized_session)
        else:
            return self._generate_sync(optimized_session)

    def _analyze_inputs(self, actions: List[RecordedAction]) -> None:
        """Analyze actions to extract input values for parametrization."""
        self._input_map = {}  # Action index -> variable name
        self._input_data = {} # Variable name -> value
        
        for i, action in enumerate(actions):
            if action.action_type in (ActionType.FILL, ActionType.TYPE) and action.value:
                # Generate a variable name
                hint = "input"
                if action.element_info:
                    hint = action.element_info.get("name") or action.element_info.get("placeholder") or "input"
                
                # Sanitize hint
                hint = "".join(c if c.isalnum() else "_" for c in hint).strip("_").lower()
                if not hint:
                    hint = "input"
                
                # Ensure unique variable name if multiple steps use same hint
                base_var = f"step_{i+1}_{hint}"
                # But actually, if we want reusable variables, 
                # if steps 2 and 5 both fill "email" with same value, should they reuse variable?
                # For now, simplistic approach: unique variable per step.
                
                self._input_map[i] = base_var
                self._input_data[base_var] = action.value
    
    def _optimize_actions(self, actions: List[RecordedAction]) -> List[RecordedAction]:
        """
        Lightly optimize recorded actions.
        
        - Remove obvious duplicates
        - Filter out ad-related fragments
        """
        if not actions:
            return actions
        
        optimized = []
        
        for i, action in enumerate(actions):
            # Skip ad fragments
            if action.action_type == ActionType.NAVIGATE and action.url:
                if '#google_vignette' in action.url or '#ad' in action.url.lower():
                    continue
                    
            # Skip duplicate consecutive navigations to same URL
            if (action.action_type == ActionType.NAVIGATE and 
                optimized and 
                optimized[-1].action_type == ActionType.NAVIGATE and
                optimized[-1].url == action.url):
                continue
            
            optimized.append(action)
        
        return optimized
    
    def _generate_async(self, session: RecordingSession) -> str:
        """Generate async Playwright script."""
        lines = []
        
        # Header
        lines.append('"""')
        lines.append(f"Recorded script: {session.name}")
        if session.recorded_at:
            lines.append(f"Recorded at: {session.recorded_at}")
        if session.start_url:
            lines.append(f"Start URL: {session.start_url}")
        lines.append(f"Actions: {len(session.actions)}")
        lines.append('"""')
        lines.append("")
        
        # Imports
        lines.append("import asyncio")
        lines.append("import re")
        lines.append("from playwright.async_api import async_playwright, expect, TimeoutError")
        lines.append("")
        
        # Add Input Data
        if hasattr(self, "_input_data") and self._input_data:
            lines.append("# Test Data - Parametrized Inputs")
            lines.append("INPUT_DATA = {")
            for k, v in self._input_data.items():
                lines.append(f'    "{k}": "{self._escape_string(v)}",')
            lines.append("}")
            lines.append("")
        
        # Helper function
        lines.append("async def perform_action(page, action_type, selectors, **kwargs):")
        lines.append('    """Perform action with fallback selectors."""')
        lines.append("    for selector in selectors:")
        lines.append("        try:")
        lines.append("            loc = page.locator(selector).first")
        lines.append("            if action_type == 'click':")
        lines.append("                await loc.click(timeout=1000)")
        lines.append("            elif action_type == 'fill':")
        lines.append("                await loc.fill(kwargs['value'], timeout=1000)")
        lines.append("            elif action_type == 'select':")
        lines.append("                await loc.select_option(kwargs['value'], timeout=1000)")
        lines.append("            elif action_type == 'check':")
        lines.append("                await loc.check(timeout=1000)")
        lines.append("            elif action_type == 'uncheck':")
        lines.append("                await loc.uncheck(timeout=1000)")
        lines.append("            return")
        lines.append("        except:")
        lines.append("            continue")
        lines.append("    ")
        lines.append("    # Fallback: try best selector with full timeout")
        lines.append("    if selectors:")
        lines.append("        loc = page.locator(selectors[0]).first")
        lines.append("        if action_type == 'click': await loc.click(timeout=5000)")
        lines.append("        elif action_type == 'fill': await loc.fill(kwargs['value'], timeout=5000)")
        lines.append("        elif action_type == 'select': await loc.select_option(kwargs['value'], timeout=5000)")
        lines.append("        elif action_type == 'check': await loc.check(timeout=5000)")
        lines.append("        elif action_type == 'uncheck': await loc.uncheck(timeout=5000)")
        lines.append("    else:")
        lines.append('        raise Exception("No selectors provided for action")')
        lines.append("")
        
        # Main function
        lines.append("async def main():")
        lines.append("    async with async_playwright() as p:")
        lines.append(f"        browser = await p.{self._browser}.launch(headless={self._headless}, slow_mo=100)")
        lines.append("        context = await browser.new_context()")
        lines.append("        page = await context.new_page()")
        lines.append("")
        lines.append("        # Set generous timeout for slow pages")
        lines.append("        page.set_default_timeout(30000)")
        lines.append("")
        
        # Generate actions
        prev_timestamp = 0
        for i, action in enumerate(session.actions):
            action_lines = self._generate_action(action, i + 1, prev_timestamp)
            for line in action_lines:
                lines.append("        " + line)
            prev_timestamp = action.timestamp_ms
        
        lines.append("")
        lines.append("        print('Replay completed successfully!')")
        lines.append("        await asyncio.sleep(2)  # Keep browser open briefly to see result")
        lines.append("        await browser.close()")
        lines.append("")
        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    asyncio.run(main())")
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_sync(self, session: RecordingSession) -> str:
        """Generate sync Playwright script."""
        lines = []
        
        # Header
        lines.append('"""')
        lines.append(f"Recorded script: {session.name}")
        if session.recorded_at:
            lines.append(f"Recorded at: {session.recorded_at}")
        lines.append('"""')
        lines.append("")
        
        # Imports
        lines.append("import time")
        lines.append("import re")
        lines.append("from playwright.sync_api import sync_playwright, expect, TimeoutError")
        lines.append("")
        
        # Add Input Data
        if hasattr(self, "_input_data") and self._input_data:
            lines.append("# Test Data - Parametrized Inputs")
            lines.append("INPUT_DATA = {")
            for k, v in self._input_data.items():
                lines.append(f'    "{k}": "{self._escape_string(v)}",')
            lines.append("}")
            lines.append("")
        
        # Helper function
        lines.append("def perform_action(page, action_type, selectors, **kwargs):")
        lines.append('    """Perform action with fallback selectors."""')
        lines.append("    for selector in selectors:")
        lines.append("        try:")
        lines.append("            loc = page.locator(selector).first")
        lines.append("            if action_type == 'click':")
        lines.append("                loc.click(timeout=1000)")
        lines.append("            elif action_type == 'fill':")
        lines.append("                loc.fill(kwargs['value'], timeout=1000)")
        lines.append("            elif action_type == 'select':")
        lines.append("                loc.select_option(kwargs['value'], timeout=1000)")
        lines.append("            elif action_type == 'check':")
        lines.append("                loc.check(timeout=1000)")
        lines.append("            elif action_type == 'uncheck':")
        lines.append("                loc.uncheck(timeout=1000)")
        lines.append("            return")
        lines.append("        except:")
        lines.append("            continue")
        lines.append("    ")
        lines.append("    # Fallback: try best selector with full timeout")
        lines.append("    if selectors:")
        lines.append("        loc = page.locator(selectors[0]).first")
        lines.append("        if action_type == 'click': loc.click(timeout=5000)")
        lines.append("        elif action_type == 'fill': loc.fill(kwargs['value'], timeout=5000)")
        lines.append("        elif action_type == 'select': loc.select_option(kwargs['value'], timeout=5000)")
        lines.append("        elif action_type == 'check': loc.check(timeout=5000)")
        lines.append("        elif action_type == 'uncheck': loc.uncheck(timeout=5000)")
        lines.append("    else:")
        lines.append('        raise Exception("No selectors provided for action")')
        lines.append("")
        
        # Main function
        lines.append("def main():")
        lines.append("    with sync_playwright() as p:")
        lines.append(f"        browser = p.{self._browser}.launch(headless={self._headless}, slow_mo=100)")
        lines.append("        context = browser.new_context()")
        lines.append("        page = context.new_page()")
        lines.append("")
        lines.append("        # Set generous timeout")
        lines.append("        page.set_default_timeout(30000)")
        lines.append("")
        
        # Generate actions
        prev_timestamp = 0
        for i, action in enumerate(session.actions):
            action_lines = self._generate_action(action, i + 1, prev_timestamp, sync=True)
            for line in action_lines:
                lines.append("        " + line)
            prev_timestamp = action.timestamp_ms
        
        lines.append("")
        lines.append("        print('Replay completed successfully!')")
        lines.append("        time.sleep(2)")
        lines.append("        browser.close()")
        lines.append("")
        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    main()")
        lines.append("")
        
        return "\n".join(lines)
    
    def _generate_action(
        self,
        action: RecordedAction,
        step_num: int,
        prev_timestamp: int,
        sync: bool = False,
    ) -> List[str]:
        """Generate code for a single action."""
        lines = []
        await_prefix = "" if sync else "await "
        sleep_func = "time.sleep" if sync else "asyncio.sleep"
        
        # Add timing delay based on user's actual timing
        if self._timing and prev_timestamp > 0:
            delay_ms = action.timestamp_ms - prev_timestamp
            if delay_ms > self._min_delay:
                delay_sec = max(delay_ms / 1000, 0.5)  # At least 500ms
                delay_sec = min(delay_sec, 5.0)  # Cap at 5 seconds
                lines.append(f"# Wait {delay_ms}ms (as recorded)")
                lines.append(f"{await_prefix}{sleep_func}({delay_sec:.1f})")
        
        # Add comment
        if self._comments:
            comment = self._get_action_comment(action, step_num)
            if comment:
                lines.append(f"# Step {step_num}: {comment}")
        
        # Prepare selectors
        selectors = action.selectors if action.selectors else ([action.selector] if action.selector else [])
        # Format selectors list for Python code
        selectors_code = "[" + ", ".join(f'"{self._escape_string(s)}"' for s in selectors) + "]"
        
        # Check for parametrization
        input_var = getattr(self, "_input_map", {}).get(step_num - 1)
        
        if action.action_type == ActionType.NAVIGATE:
            url = self._escape_string(action.url)
            lines.append("try:")
            lines.append(f'    {await_prefix}page.goto("{url}", wait_until="domcontentloaded")')
            lines.append("except TimeoutError:")
            lines.append(f'    print("Navigation timeout for {url[:50]}..., continuing...")')
            
        elif action.action_type in (ActionType.CLICK, ActionType.CHECK, ActionType.UNCHECK, ActionType.HOVER):
            action_map = {
                ActionType.CLICK: "click",
                ActionType.CHECK: "check",
                ActionType.UNCHECK: "uncheck",
                ActionType.HOVER: "hover"
            }
            method = action_map.get(action.action_type, "click")
            
            if selectors:
                if len(selectors) > 1:
                    lines.append(f"{await_prefix}perform_action(page, '{method}', {selectors_code})")
                else:
                    # Single selector logic (keep backward compatibility style or use perform_action too?)
                    # Using standard try/except for single is cleaner/lighter
                    s = self._escape_string(selectors[0])
                    lines.append("try:")
                    if method == "click":
                        lines.append(f'    {await_prefix}page.locator("{s}").first.click(timeout=10000)')
                    elif method == "check":
                        lines.append(f'    {await_prefix}page.locator("{s}").first.check(timeout=10000)')
                    elif method == "uncheck":
                        lines.append(f'    {await_prefix}page.locator("{s}").first.uncheck(timeout=10000)')
                    elif method == "hover":
                        lines.append(f'    {await_prefix}page.locator("{s}").first.hover(timeout=10000)')
                    lines.append("except TimeoutError:")
                    lines.append(f'    print("{method.capitalize()} timeout for {s[:50]}..., continuing...")')
            elif action.action_type == ActionType.CLICK and action.x is not None and action.y is not None:
                lines.append(f'{await_prefix}page.mouse.click({action.x}, {action.y})')

        elif action.action_type in (ActionType.FILL, ActionType.TYPE, ActionType.SELECT):
            # Resolve value: use variable if mapped, else literal
            value_code = f'INPUT_DATA["{input_var}"]' if input_var else f'"{self._escape_string(action.value)}"'
            
            if action.action_type == ActionType.SELECT:
                 method = "select"
            else: # FILL or TYPE
                 # We prefer FILL usually, treat TYPE as FILL for robustness unless specific reason
                 method = "fill"
                 
            if selectors:
                if len(selectors) > 1:
                    lines.append(f"{await_prefix}perform_action(page, '{method}', {selectors_code}, value={value_code})")
                else:
                    s = self._escape_string(selectors[0])
                    lines.append("try:")
                    if action.action_type == ActionType.SELECT:
                        lines.append(f'    {await_prefix}page.locator("{s}").first.select_option({value_code})')
                    elif action.action_type == ActionType.TYPE:
                        # Fallback to type if strictly needed, but fill is usually safer.
                        # Using type for TYPE action
                        lines.append(f'    {await_prefix}page.locator("{s}").first.type({value_code})')
                    else:
                        lines.append(f'    {await_prefix}page.locator("{s}").first.fill({value_code})')
                    lines.append("except TimeoutError:")
                    lines.append(f'    print("{method.capitalize()} timeout for {s[:50]}..., continuing...")')

        elif action.action_type == ActionType.PRESS:
            key = self._escape_string(action.key)
            lines.append(f'{await_prefix}page.keyboard.press("{key}")')
                
        elif action.action_type == ActionType.SCROLL:
            if action.y:
                lines.append(f'{await_prefix}page.mouse.wheel(0, {action.y})')
                
        elif action.action_type == ActionType.WAIT:
            value = action.value or "1000"
            if value.startswith("assert:"):
                # Handle assertions: assert:type:value
                parts = value.split(":", 2)
                assert_type = parts[1]
                assert_value = parts[2] if len(parts) > 2 else ""
                
                if assert_type == "text":
                    lines.append(f'{await_prefix}expect(page.locator("text=\'{self._escape_string(assert_value)}\' >> visible=true").first).to_be_visible()')
                elif assert_type == "element":
                    lines.append(f"# Assertion: Element '{assert_value}' visible")
                    if assert_value and assert_value != "element": 
                        lines.append(f'{await_prefix}expect(page.locator("{self._escape_string(assert_value)}").first).to_be_visible()')
                elif assert_type == "url":
                    lines.append(f'{await_prefix}expect(page).to_have_url(re.compile(r".*{self._escape_string(assert_value)}.*"))')
            else:
                wait_sec = int(value) / 1000
                lines.append(f'{await_prefix}{sleep_func}({wait_sec})')
        
        lines.append("")  # Blank line after each action
        return lines
    
    def _get_action_comment(self, action: RecordedAction, step_num: int) -> str:
        """Generate a human-readable comment for an action."""
        info = action.element_info
        
        if action.action_type == ActionType.NAVIGATE:
            url = action.url or ""
            if len(url) > 60:
                url = url[:60] + "..."
            return f"Navigate to {url}"
            
        elif action.action_type == ActionType.CLICK:
            target = info.get("text") or info.get("id") or action.selector or "element"
            if len(target) > 50:
                target = target[:50] + "..."
            return f"Click on {target}"
            
        elif action.action_type == ActionType.FILL:
            target = info.get("placeholder") or info.get("name") or action.selector or "field"
            value = action.value or ""
            if len(value) > 20:
                value = value[:20] + "..."
            return f"Fill {target} with '{value}'"
            
        elif action.action_type == ActionType.SELECT:
            return f"Select '{action.value}'"
            
        elif action.action_type == ActionType.CHECK:
            return "Check checkbox"
            
        elif action.action_type == ActionType.UNCHECK:
            return "Uncheck checkbox"
            
        elif action.action_type == ActionType.PRESS:
            return f"Press {action.key}"
            
        elif action.action_type == ActionType.SCROLL:
            return f"Scroll by {action.y}px"
            
        return action.action_type.value.capitalize()
    
    def _escape_string(self, s: Optional[str]) -> str:
        """Escape a string for use in Python code."""
        if s is None:
            return ""
        return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def generate_instruction_file(session: RecordingSession) -> str:
    """
    Generate a simple instruction file format (for run-file command).
    
    Args:
        session: Recording session
        
    Returns:
        Instructions as plain text
    """
    lines = []
    lines.append(f"# Recording: {session.name}")
    if session.recorded_at:
        lines.append(f"# Recorded: {session.recorded_at}")
    lines.append("")
    
    for action in session.actions:
        if action.action_type == ActionType.NAVIGATE:
            lines.append(f"go to {action.url}")
            
        elif action.action_type == ActionType.CLICK:
            target = action.element_info.get("text") or action.selector
            lines.append(f"click {target}")
            
        elif action.action_type == ActionType.FILL:
            target = action.element_info.get("name") or action.element_info.get("placeholder") or action.selector
            lines.append(f"type {action.value} in {target}")
            
        elif action.action_type == ActionType.SELECT:
            lines.append(f"select {action.value}")
            
        elif action.action_type == ActionType.PRESS:
            lines.append(f"press {action.key}")
            
        elif action.action_type == ActionType.CHECK:
            lines.append(f"check {action.selector}")
            
        elif action.action_type == ActionType.UNCHECK:
            lines.append(f"uncheck {action.selector}")
    
    return "\n".join(lines)
