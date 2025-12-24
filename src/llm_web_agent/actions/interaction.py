"""
Interaction Actions - Element interaction actions.
"""

from typing import Optional, TYPE_CHECKING

from llm_web_agent.interfaces.action import (
    BaseAction,
    ActionType,
    ActionResult,
    ActionParams,
)

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage


class ClickAction(BaseAction):
    """Click on an element."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.CLICK
    
    @property
    def description(self) -> str:
        return "Click on an element"
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        selector = params.selector or ""
        await page.click(selector, **params.options)
        return ActionResult.success_result(
            action_type=self.action_type,
            selector=selector,
        )


class FillAction(BaseAction):
    """Fill an input element with text."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.FILL
    
    @property
    def description(self) -> str:
        return "Fill an input element with text"
    
    def validate_params(self, params: ActionParams) -> tuple[bool, Optional[str]]:
        if not params.selector:
            return False, "Fill action requires a selector"
        if params.value is None:
            return False, "Fill action requires a value"
        return True, None
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        selector = params.selector or ""
        value = params.value or ""
        await page.fill(selector, value, **params.options)
        return ActionResult.success_result(
            action_type=self.action_type,
            selector=selector,
        )


class TypeAction(BaseAction):
    """Type text into an element character by character."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.TYPE
    
    @property
    def description(self) -> str:
        return "Type text character by character"
    
    def validate_params(self, params: ActionParams) -> tuple[bool, Optional[str]]:
        if not params.selector:
            return False, "Type action requires a selector"
        if params.value is None:
            return False, "Type action requires a value"
        return True, None
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        selector = params.selector or ""
        value = params.value or ""
        delay = params.get("delay", 50)
        await page.type(selector, value, delay=delay, **params.options)
        return ActionResult.success_result(
            action_type=self.action_type,
            selector=selector,
        )


class SelectAction(BaseAction):
    """Select an option in a dropdown."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.SELECT
    
    @property
    def description(self) -> str:
        return "Select an option in a dropdown"
    
    def validate_params(self, params: ActionParams) -> tuple[bool, Optional[str]]:
        if not params.selector:
            return False, "Select action requires a selector"
        if params.value is None:
            return False, "Select action requires a value"
        return True, None
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        selector = params.selector or ""
        value = params.value or ""
        selected = await page.select_option(selector, value, **params.options)
        return ActionResult.success_result(
            action_type=self.action_type,
            data={"selected": selected},
            selector=selector,
        )


class HoverAction(BaseAction):
    """Hover over an element."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.HOVER
    
    @property
    def description(self) -> str:
        return "Hover over an element"
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        selector = params.selector or ""
        await page.hover(selector, **params.options)
        return ActionResult.success_result(
            action_type=self.action_type,
            selector=selector,
        )
