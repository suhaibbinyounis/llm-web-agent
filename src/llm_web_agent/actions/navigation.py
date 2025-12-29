"""
Navigation Actions - Page navigation actions.
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


class NavigateAction(BaseAction):
    """Navigate to a URL."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.NAVIGATE
    
    @property
    def description(self) -> str:
        return "Navigate to a URL"
    
    @property
    def requires_selector(self) -> bool:
        return False
    
    def validate_params(self, params: ActionParams) -> tuple[bool, Optional[str]]:
        if not params.value:
            return False, "Navigate action requires a URL in 'value'"
        return True, None
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        url = params.value or ""
        # Get timeout from options (navigation_timeout_ms from settings)
        timeout = params.get("timeout")
        if timeout:
            await page.goto(url, timeout=timeout)
        else:
            await page.goto(url)
        return ActionResult.success_result(
            action_type=self.action_type,
            data={"url": url},
        )


class ReloadAction(BaseAction):
    """Reload the current page."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.RELOAD
    
    @property
    def description(self) -> str:
        return "Reload the current page"
    
    @property
    def requires_selector(self) -> bool:
        return False
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        await page.reload()
        return ActionResult.success_result(action_type=self.action_type)


class GoBackAction(BaseAction):
    """Navigate back in history."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.GO_BACK
    
    @property
    def description(self) -> str:
        return "Navigate back in browser history"
    
    @property
    def requires_selector(self) -> bool:
        return False
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        await page.go_back()
        return ActionResult.success_result(action_type=self.action_type)


class GoForwardAction(BaseAction):
    """Navigate forward in history."""
    
    @property
    def action_type(self) -> ActionType:
        return ActionType.GO_FORWARD
    
    @property
    def description(self) -> str:
        return "Navigate forward in browser history"
    
    @property
    def requires_selector(self) -> bool:
        return False
    
    async def _execute(self, page: "IPage", params: ActionParams) -> ActionResult:
        await page.go_forward()
        return ActionResult.success_result(action_type=self.action_type)
