"""
Browser Overlay - Visual feedback for agent actions.

Provides:
1. Sidebar overlay showing current action and history
2. Element highlighting before interactions

These features help with debugging and understanding what the agent is doing.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from llm_web_agent.interfaces.browser import IPage

logger = logging.getLogger(__name__)


# ============================================================================
# CSS STYLES
# ============================================================================

OVERLAY_CSS = """
/* LLM Web Agent Overlay Styles */
#llm-agent-overlay {
    position: fixed;
    top: 0;
    right: 0;
    width: 320px;
    height: 100vh;
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    color: #e8e8e8;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 13px;
    z-index: 2147483647;
    box-shadow: -4px 0 20px rgba(0, 0, 0, 0.4);
    display: flex;
    flex-direction: column;
    transition: transform 0.3s ease;
    border-left: 1px solid rgba(255,255,255,0.1);
}

#llm-agent-overlay.collapsed {
    transform: translateX(280px);
}

#llm-agent-overlay .header {
    padding: 16px;
    background: rgba(0,0,0,0.2);
    border-bottom: 1px solid rgba(255,255,255,0.1);
    display: flex;
    align-items: center;
    gap: 10px;
}

#llm-agent-overlay .header .logo {
    width: 28px;
    height: 28px;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: bold;
    font-size: 14px;
}

#llm-agent-overlay .header .title {
    flex: 1;
    font-weight: 600;
    font-size: 14px;
}

#llm-agent-overlay .toggle-btn {
    background: none;
    border: none;
    color: #888;
    cursor: pointer;
    font-size: 18px;
    padding: 4px 8px;
}

#llm-agent-overlay .toggle-btn:hover {
    color: #fff;
}

#llm-agent-overlay .current-action {
    padding: 16px;
    background: rgba(102, 126, 234, 0.15);
    border-bottom: 1px solid rgba(255,255,255,0.1);
}

#llm-agent-overlay .current-action .label {
    font-size: 11px;
    text-transform: uppercase;
    color: #888;
    margin-bottom: 8px;
    letter-spacing: 0.5px;
}

#llm-agent-overlay .current-action .action-text {
    font-size: 15px;
    font-weight: 500;
    color: #fff;
    word-break: break-word;
}

#llm-agent-overlay .progress {
    padding: 12px 16px;
    background: rgba(0,0,0,0.1);
    border-bottom: 1px solid rgba(255,255,255,0.1);
    display: flex;
    gap: 16px;
}

#llm-agent-overlay .progress .stat {
    display: flex;
    flex-direction: column;
    gap: 2px;
}

#llm-agent-overlay .progress .stat .value {
    font-size: 18px;
    font-weight: 600;
    color: #667eea;
}

#llm-agent-overlay .progress .stat .label {
    font-size: 10px;
    text-transform: uppercase;
    color: #666;
}

#llm-agent-overlay .history {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
}

#llm-agent-overlay .history-item {
    padding: 10px 12px;
    margin-bottom: 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 8px;
    border-left: 3px solid transparent;
}

#llm-agent-overlay .history-item.success {
    border-left-color: #4ade80;
}

#llm-agent-overlay .history-item.error {
    border-left-color: #f87171;
}

#llm-agent-overlay .history-item.pending {
    border-left-color: #fbbf24;
}

#llm-agent-overlay .history-item .action-name {
    font-weight: 500;
    margin-bottom: 4px;
}

#llm-agent-overlay .history-item .action-target {
    font-size: 11px;
    color: #888;
    word-break: break-all;
}

#llm-agent-overlay .history-item .action-time {
    font-size: 10px;
    color: #555;
    margin-top: 4px;
}

/* Element Highlight */
.llm-agent-highlight {
    outline: 3px solid var(--highlight-color, #FF6B6B) !important;
    outline-offset: 2px !important;
    box-shadow: 0 0 20px var(--highlight-color, #FF6B6B) !important;
    transition: outline 0.2s ease, box-shadow 0.2s ease !important;
}

.llm-agent-highlight-label {
    position: fixed;
    background: var(--highlight-color, #FF6B6B);
    color: white;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    z-index: 2147483646;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    animation: llm-highlight-pulse 0.5s ease-out;
}

@keyframes llm-highlight-pulse {
    0% { transform: scale(0.8); opacity: 0; }
    50% { transform: scale(1.05); }
    100% { transform: scale(1); opacity: 1; }
}
"""


# ============================================================================
# SIDEBAR HTML
# ============================================================================

OVERLAY_HTML = """
<div id="llm-agent-overlay">
    <div class="header">
        <div class="logo">⚡</div>
        <div class="title">LLM Web Agent</div>
        <button class="toggle-btn" onclick="window.__llmAgentToggle()">◀</button>
    </div>
    <div class="current-action">
        <div class="label">Current Action</div>
        <div class="action-text" id="llm-current-action">Initializing...</div>
    </div>
    <div class="progress">
        <div class="stat">
            <div class="value" id="llm-step-current">0</div>
            <div class="label">Step</div>
        </div>
        <div class="stat">
            <div class="value" id="llm-step-total">0</div>
            <div class="label">Total</div>
        </div>
        <div class="stat">
            <div class="value" id="llm-success-count">0</div>
            <div class="label">Success</div>
        </div>
    </div>
    <div class="history" id="llm-history"></div>
</div>
"""


# ============================================================================
# JAVASCRIPT
# ============================================================================

OVERLAY_JS = """
(function() {
    // State
    window.__llmAgentState = {
        collapsed: false,
        history: [],
        currentStep: 0,
        totalSteps: 0,
        successCount: 0,
        highlightColor: '#FF6B6B',
    };
    
    // Toggle sidebar
    window.__llmAgentToggle = function() {
        const overlay = document.getElementById('llm-agent-overlay');
        const btn = overlay.querySelector('.toggle-btn');
        window.__llmAgentState.collapsed = !window.__llmAgentState.collapsed;
        overlay.classList.toggle('collapsed');
        btn.textContent = window.__llmAgentState.collapsed ? '▶' : '◀';
    };
    
    // Update current action
    window.__llmAgentUpdateAction = function(action, target) {
        const el = document.getElementById('llm-current-action');
        if (el) {
            el.textContent = action + (target ? ': ' + target : '');
        }
    };
    
    // Update progress
    window.__llmAgentUpdateProgress = function(current, total, success) {
        const state = window.__llmAgentState;
        state.currentStep = current;
        state.totalSteps = total;
        state.successCount = success;
        
        const elCurrent = document.getElementById('llm-step-current');
        const elTotal = document.getElementById('llm-step-total');
        const elSuccess = document.getElementById('llm-success-count');
        
        if (elCurrent) elCurrent.textContent = current;
        if (elTotal) elTotal.textContent = total;
        if (elSuccess) elSuccess.textContent = success;
    };
    
    // Add history item
    window.__llmAgentAddHistory = function(action, target, status) {
        const history = document.getElementById('llm-history');
        if (!history) return;
        
        const item = document.createElement('div');
        item.className = 'history-item ' + status;
        item.innerHTML = 
            '<div class="action-name">' + action + '</div>' +
            '<div class="action-target">' + (target || '') + '</div>' +
            '<div class="action-time">' + new Date().toLocaleTimeString() + '</div>';
        
        history.insertBefore(item, history.firstChild);
        
        // Limit history
        while (history.children.length > 20) {
            history.removeChild(history.lastChild);
        }
    };
    
    // Set highlight color
    window.__llmAgentSetHighlightColor = function(color) {
        window.__llmAgentState.highlightColor = color;
        document.documentElement.style.setProperty('--highlight-color', color);
    };
})();
"""


# ============================================================================
# HIGHLIGHT JS
# ============================================================================

HIGHLIGHT_ELEMENT_JS = """
(selector, label, color) => {
    // Remove existing highlights
    document.querySelectorAll('.llm-agent-highlight').forEach(el => {
        el.classList.remove('llm-agent-highlight');
    });
    document.querySelectorAll('.llm-agent-highlight-label').forEach(el => el.remove());
    
    // Set color
    if (color) {
        document.documentElement.style.setProperty('--highlight-color', color);
    }
    
    // Find element
    let element = null;
    try {
        element = document.querySelector(selector);
    } catch (e) {
        return false;
    }
    
    if (!element) return false;
    
    // Add highlight class
    element.classList.add('llm-agent-highlight');
    
    // Scroll into view
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Add label
    if (label) {
        const rect = element.getBoundingClientRect();
        const labelEl = document.createElement('div');
        labelEl.className = 'llm-agent-highlight-label';
        labelEl.textContent = label;
        labelEl.style.left = rect.left + 'px';
        labelEl.style.top = (rect.top - 30) + 'px';
        document.body.appendChild(labelEl);
    }
    
    return true;
}
"""

CLEAR_HIGHLIGHT_JS = """
() => {
    document.querySelectorAll('.llm-agent-highlight').forEach(el => {
        el.classList.remove('llm-agent-highlight');
    });
    document.querySelectorAll('.llm-agent-highlight-label').forEach(el => el.remove());
}
"""


# ============================================================================
# OVERLAY MANAGER
# ============================================================================

@dataclass
class OverlayConfig:
    """Configuration for browser overlay."""
    enabled: bool = False
    highlight_enabled: bool = False
    position: str = "right"  # "left" or "right"
    highlight_color: str = "#FF6B6B"
    highlight_duration_ms: int = 1500


class BrowserOverlay:
    """
    Manages browser overlay UI and element highlighting.
    
    Usage:
        overlay = BrowserOverlay(config)
        await overlay.inject(page)
        await overlay.update_action("Click", "Sign In button")
        await overlay.highlight_element(page, "#sign-in-btn", "Click")
    """
    
    def __init__(self, config: Optional[OverlayConfig] = None):
        self.config = config or OverlayConfig()
        self._injected_pages: set = set()
    
    async def inject(self, page: "IPage") -> bool:
        """
        Inject overlay CSS, HTML, and JS into the page.
        
        Args:
            page: Browser page
            
        Returns:
            True if injection succeeded
        """
        if not self.config.enabled and not self.config.highlight_enabled:
            return False
        
        page_id = id(page)
        if page_id in self._injected_pages:
            return True
        
        try:
            # Inject CSS
            await page.evaluate(f"""
                () => {{
                    if (document.getElementById('llm-agent-styles')) return;
                    const style = document.createElement('style');
                    style.id = 'llm-agent-styles';
                    style.textContent = `{OVERLAY_CSS}`;
                    document.head.appendChild(style);
                }}
            """)
            
            # Inject sidebar HTML (only if enabled)
            if self.config.enabled:
                position_css = "left: 0; right: auto;" if self.config.position == "left" else ""
                await page.evaluate(f"""
                    () => {{
                        if (document.getElementById('llm-agent-overlay')) return;
                        const container = document.createElement('div');
                        container.innerHTML = `{OVERLAY_HTML}`;
                        const overlay = container.firstElementChild;
                        if ('{position_css}') {{
                            overlay.style.cssText += '{position_css}';
                        }}
                        document.body.appendChild(overlay);
                    }}
                """)
                
                # Inject JS
                await page.evaluate(OVERLAY_JS)
            
            # Set highlight color
            await page.evaluate(f"""
                () => {{
                    document.documentElement.style.setProperty('--highlight-color', '{self.config.highlight_color}');
                }}
            """)
            
            self._injected_pages.add(page_id)
            logger.debug("Overlay injected successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to inject overlay: {e}")
            return False
    
    async def update_action(
        self,
        page: "IPage",
        action: str,
        target: Optional[str] = None,
    ) -> None:
        """Update the current action display."""
        if not self.config.enabled:
            return
        
        try:
            await self.inject(page)
            escaped_action = action.replace("'", "\\'")
            escaped_target = (target or "").replace("'", "\\'")
            await page.evaluate(
                f"() => window.__llmAgentUpdateAction && window.__llmAgentUpdateAction('{escaped_action}', '{escaped_target}')"
            )
        except Exception as e:
            logger.debug(f"Failed to update action: {e}")
    
    async def update_progress(
        self,
        page: "IPage",
        current: int,
        total: int,
        success: int,
    ) -> None:
        """Update progress counters."""
        if not self.config.enabled:
            return
        
        try:
            await self.inject(page)
            await page.evaluate(
                f"() => window.__llmAgentUpdateProgress && window.__llmAgentUpdateProgress({current}, {total}, {success})"
            )
        except Exception as e:
            logger.debug(f"Failed to update progress: {e}")
    
    async def add_history(
        self,
        page: "IPage",
        action: str,
        target: Optional[str] = None,
        status: str = "success",
    ) -> None:
        """Add an item to the history."""
        if not self.config.enabled:
            return
        
        try:
            await self.inject(page)
            escaped_action = action.replace("'", "\\'")
            escaped_target = (target or "").replace("'", "\\'")
            await page.evaluate(
                f"() => window.__llmAgentAddHistory && window.__llmAgentAddHistory('{escaped_action}', '{escaped_target}', '{status}')"
            )
        except Exception as e:
            logger.debug(f"Failed to add history: {e}")
    
    async def highlight_element(
        self,
        page: "IPage",
        selector: str,
        label: Optional[str] = None,
    ) -> bool:
        """
        Highlight an element before interaction.
        
        Args:
            page: Browser page
            selector: CSS selector of element to highlight
            label: Optional label to show above element
            
        Returns:
            True if element was highlighted
        """
        if not self.config.highlight_enabled:
            return False
        
        try:
            await self.inject(page)
            
            escaped_selector = selector.replace("'", "\\'").replace('"', '\\"')
            escaped_label = (label or "").replace("'", "\\'")
            
            result = await page.evaluate(
                f"({HIGHLIGHT_ELEMENT_JS})('{escaped_selector}', '{escaped_label}', '{self.config.highlight_color}')"
            )
            
            return result is True
            
        except Exception as e:
            logger.debug(f"Failed to highlight element: {e}")
            return False
    
    async def clear_highlight(self, page: "IPage") -> None:
        """Remove all highlights from the page."""
        try:
            await page.evaluate(f"({CLEAR_HIGHLIGHT_JS})()")
        except Exception as e:
            logger.debug(f"Failed to clear highlight: {e}")
    
    async def highlight_and_wait(
        self,
        page: "IPage",
        selector: str,
        label: Optional[str] = None,
    ) -> None:
        """
        Highlight element and wait for configured duration.
        
        Convenience method for action classes.
        """
        if not self.config.highlight_enabled:
            return
        
        await self.highlight_element(page, selector, label)
        await asyncio.sleep(self.config.highlight_duration_ms / 1000)
        await self.clear_highlight(page)
    
    async def remove(self, page: "IPage") -> None:
        """Remove overlay from page."""
        try:
            await page.evaluate("""
                () => {
                    const overlay = document.getElementById('llm-agent-overlay');
                    if (overlay) overlay.remove();
                    const styles = document.getElementById('llm-agent-styles');
                    if (styles) styles.remove();
                    document.querySelectorAll('.llm-agent-highlight').forEach(el => {
                        el.classList.remove('llm-agent-highlight');
                    });
                    document.querySelectorAll('.llm-agent-highlight-label').forEach(el => el.remove());
                }
            """)
            self._injected_pages.discard(id(page))
        except Exception as e:
            logger.debug(f"Failed to remove overlay: {e}")


# Global overlay instance
_overlay: Optional[BrowserOverlay] = None


def get_overlay(config: Optional[OverlayConfig] = None) -> BrowserOverlay:
    """Get or create the global overlay instance."""
    global _overlay
    if _overlay is None or config is not None:
        _overlay = BrowserOverlay(config)
    return _overlay
