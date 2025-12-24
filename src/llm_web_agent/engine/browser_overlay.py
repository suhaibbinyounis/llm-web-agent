"""
Browser Overlay - Visual feedback for agent actions.

Provides:
1. Sidebar overlay showing current action and history (pushes page content)
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
# CSS STYLES - Modern glassmorphism design that PUSHES content
# ============================================================================

OVERLAY_CSS = """
/* LLM Web Agent Overlay - Modern Design */
:root {
    --llm-sidebar-width: 300px;
    --llm-collapsed-width: 40px;
    --llm-accent: #6366f1;
    --llm-accent-glow: rgba(99, 102, 241, 0.3);
    --llm-bg: rgba(15, 23, 42, 0.95);
    --llm-bg-glass: rgba(30, 41, 59, 0.8);
    --llm-text: #f1f5f9;
    --llm-text-dim: #94a3b8;
    --llm-success: #22c55e;
    --llm-error: #ef4444;
    --llm-warning: #f59e0b;
    --llm-border: rgba(148, 163, 184, 0.1);
}

/* Push body content when sidebar is open */
body.llm-sidebar-open {
    margin-right: var(--llm-sidebar-width) !important;
    transition: margin-right 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

body.llm-sidebar-collapsed {
    margin-right: var(--llm-collapsed-width) !important;
    transition: margin-right 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

/* Main sidebar container */
#llm-sidebar {
    position: fixed;
    top: 0;
    right: 0;
    width: var(--llm-sidebar-width);
    height: 100vh;
    background: var(--llm-bg);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    color: var(--llm-text);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
    z-index: 2147483647;
    display: flex;
    flex-direction: column;
    transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border-left: 1px solid var(--llm-border);
    box-shadow: -10px 0 40px rgba(0, 0, 0, 0.3);
}

#llm-sidebar.collapsed {
    width: var(--llm-collapsed-width);
}

#llm-sidebar.collapsed .sidebar-content {
    opacity: 0;
    pointer-events: none;
}

#llm-sidebar.collapsed .toggle-btn {
    transform: rotate(180deg);
}

/* Header */
#llm-sidebar .header {
    padding: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 1px solid var(--llm-border);
    background: var(--llm-bg-glass);
}

#llm-sidebar .logo {
    width: 32px;
    height: 32px;
    background: linear-gradient(135deg, var(--llm-accent) 0%, #8b5cf6 100%);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
    box-shadow: 0 4px 12px var(--llm-accent-glow);
}

#llm-sidebar .title {
    flex: 1;
    font-weight: 600;
    font-size: 14px;
    letter-spacing: -0.3px;
    white-space: nowrap;
    overflow: hidden;
}

#llm-sidebar .toggle-btn {
    width: 28px;
    height: 28px;
    background: var(--llm-bg-glass);
    border: 1px solid var(--llm-border);
    border-radius: 8px;
    color: var(--llm-text-dim);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s ease;
    flex-shrink: 0;
}

#llm-sidebar .toggle-btn:hover {
    background: var(--llm-accent);
    color: white;
    border-color: var(--llm-accent);
}

/* Sidebar content wrapper */
#llm-sidebar .sidebar-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    transition: opacity 0.2s ease;
}

/* Current action card */
#llm-sidebar .current-action {
    margin: 12px;
    padding: 16px;
    background: linear-gradient(135deg, var(--llm-accent-glow) 0%, transparent 100%);
    border: 1px solid var(--llm-border);
    border-radius: 12px;
}

#llm-sidebar .current-action .label {
    font-size: 10px;
    text-transform: uppercase;
    color: var(--llm-accent);
    letter-spacing: 1px;
    margin-bottom: 8px;
    font-weight: 600;
}

#llm-sidebar .current-action .action-text {
    font-size: 14px;
    font-weight: 500;
    line-height: 1.4;
    color: var(--llm-text);
    word-break: break-word;
}

/* Stats row */
#llm-sidebar .stats {
    display: flex;
    gap: 8px;
    padding: 0 12px;
    margin-bottom: 12px;
}

#llm-sidebar .stat-card {
    flex: 1;
    padding: 12px;
    background: var(--llm-bg-glass);
    border: 1px solid var(--llm-border);
    border-radius: 10px;
    text-align: center;
}

#llm-sidebar .stat-card .value {
    font-size: 20px;
    font-weight: 700;
    color: var(--llm-accent);
    line-height: 1;
}

#llm-sidebar .stat-card .label {
    font-size: 9px;
    text-transform: uppercase;
    color: var(--llm-text-dim);
    margin-top: 4px;
    letter-spacing: 0.5px;
}

/* History section */
#llm-sidebar .history-header {
    padding: 8px 16px;
    font-size: 10px;
    text-transform: uppercase;
    color: var(--llm-text-dim);
    letter-spacing: 1px;
    font-weight: 600;
}

#llm-sidebar .history {
    flex: 1;
    overflow-y: auto;
    padding: 0 12px 12px;
}

#llm-sidebar .history::-webkit-scrollbar {
    width: 4px;
}

#llm-sidebar .history::-webkit-scrollbar-track {
    background: transparent;
}

#llm-sidebar .history::-webkit-scrollbar-thumb {
    background: var(--llm-border);
    border-radius: 4px;
}

#llm-sidebar .history-item {
    padding: 12px;
    margin-bottom: 8px;
    background: var(--llm-bg-glass);
    border: 1px solid var(--llm-border);
    border-radius: 10px;
    position: relative;
    overflow: hidden;
}

#llm-sidebar .history-item::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 3px;
    background: var(--llm-text-dim);
    border-radius: 0 3px 3px 0;
}

#llm-sidebar .history-item.success::before { background: var(--llm-success); }
#llm-sidebar .history-item.error::before { background: var(--llm-error); }
#llm-sidebar .history-item.pending::before { background: var(--llm-warning); }

#llm-sidebar .history-item .action-name {
    font-weight: 600;
    font-size: 12px;
    margin-bottom: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
}

#llm-sidebar .history-item .action-target {
    font-size: 11px;
    color: var(--llm-text-dim);
    word-break: break-all;
    line-height: 1.4;
}

#llm-sidebar .history-item .action-time {
    font-size: 10px;
    color: var(--llm-text-dim);
    margin-top: 6px;
    opacity: 0.6;
}

/* Element Highlight - Enhanced */
.llm-highlight {
    outline: 3px solid var(--llm-accent) !important;
    outline-offset: 3px !important;
    box-shadow: 
        0 0 0 3px rgba(99, 102, 241, 0.2),
        0 0 30px rgba(99, 102, 241, 0.4) !important;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
    border-radius: 4px !important;
}

.llm-highlight-label {
    position: fixed;
    background: linear-gradient(135deg, var(--llm-accent) 0%, #8b5cf6 100%);
    color: white;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    font-family: 'Inter', -apple-system, sans-serif;
    z-index: 2147483646;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    animation: llm-label-in 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    pointer-events: none;
}

@keyframes llm-label-in {
    0% { 
        opacity: 0; 
        transform: translateY(8px) scale(0.9); 
    }
    100% { 
        opacity: 1; 
        transform: translateY(0) scale(1); 
    }
}

/* Collapsed state toggle button always visible */
#llm-sidebar.collapsed .header {
    justify-content: center;
    padding: 12px 6px;
}

#llm-sidebar.collapsed .logo,
#llm-sidebar.collapsed .title {
    display: none;
}
"""


# ============================================================================
# SIDEBAR HTML - Clean modern structure
# ============================================================================

OVERLAY_HTML = """
<div id="llm-sidebar">
    <div class="header">
        <div class="logo">⚡</div>
        <div class="title">LLM Web Agent</div>
        <button class="toggle-btn" onclick="window.__llmToggle()">‹</button>
    </div>
    <div class="sidebar-content">
        <div class="current-action">
            <div class="label">Current Action</div>
            <div class="action-text" id="llm-action">Ready</div>
        </div>
        <div class="stats">
            <div class="stat-card">
                <div class="value" id="llm-step">0</div>
                <div class="label">Step</div>
            </div>
            <div class="stat-card">
                <div class="value" id="llm-total">0</div>
                <div class="label">Total</div>
            </div>
            <div class="stat-card">
                <div class="value" id="llm-success">0</div>
                <div class="label">Done</div>
            </div>
        </div>
        <div class="history-header">Activity Log</div>
        <div class="history" id="llm-history"></div>
    </div>
</div>
"""


# ============================================================================
# JAVASCRIPT - Controls sidebar and page content shifting
# ============================================================================

OVERLAY_JS = """
(function() {
    window.__llmState = {
        collapsed: false,
        history: []
    };
    
    // Initialize body class
    document.body.classList.add('llm-sidebar-open');
    
    window.__llmToggle = function() {
        const sidebar = document.getElementById('llm-sidebar');
        const state = window.__llmState;
        state.collapsed = !state.collapsed;
        
        if (state.collapsed) {
            sidebar.classList.add('collapsed');
            document.body.classList.remove('llm-sidebar-open');
            document.body.classList.add('llm-sidebar-collapsed');
        } else {
            sidebar.classList.remove('collapsed');
            document.body.classList.add('llm-sidebar-open');
            document.body.classList.remove('llm-sidebar-collapsed');
        }
    };
    
    window.__llmUpdateAction = function(action, target) {
        const el = document.getElementById('llm-action');
        if (el) el.textContent = target ? action + ': ' + target : action;
    };
    
    window.__llmUpdateStats = function(step, total, success) {
        const els = {
            step: document.getElementById('llm-step'),
            total: document.getElementById('llm-total'),
            success: document.getElementById('llm-success')
        };
        if (els.step) els.step.textContent = step;
        if (els.total) els.total.textContent = total;
        if (els.success) els.success.textContent = success;
    };
    
    window.__llmAddHistory = function(action, target, status) {
        const history = document.getElementById('llm-history');
        if (!history) return;
        
        const icons = { success: '✓', error: '✗', pending: '○' };
        const item = document.createElement('div');
        item.className = 'history-item ' + status;
        item.innerHTML = 
            '<div class="action-name">' + (icons[status] || '•') + ' ' + action + '</div>' +
            (target ? '<div class="action-target">' + target + '</div>' : '') +
            '<div class="action-time">' + new Date().toLocaleTimeString() + '</div>';
        
        history.insertBefore(item, history.firstChild);
        while (history.children.length > 15) history.removeChild(history.lastChild);
    };
})();
"""


# ============================================================================
# HIGHLIGHT JS
# ============================================================================

HIGHLIGHT_JS = """
(selector, label) => {
    // Clear existing
    document.querySelectorAll('.llm-highlight').forEach(el => el.classList.remove('llm-highlight'));
    document.querySelectorAll('.llm-highlight-label').forEach(el => el.remove());
    
    // Find element
    let element;
    try { element = document.querySelector(selector); } catch(e) { return false; }
    if (!element) return false;
    
    // Highlight
    element.classList.add('llm-highlight');
    element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    
    // Label
    if (label) {
        const rect = element.getBoundingClientRect();
        const lbl = document.createElement('div');
        lbl.className = 'llm-highlight-label';
        lbl.textContent = label;
        lbl.style.left = Math.max(8, rect.left) + 'px';
        lbl.style.top = Math.max(8, rect.top - 32) + 'px';
        document.body.appendChild(lbl);
    }
    return true;
}
"""

CLEAR_HIGHLIGHT_JS = """
() => {
    document.querySelectorAll('.llm-highlight').forEach(el => el.classList.remove('llm-highlight'));
    document.querySelectorAll('.llm-highlight-label').forEach(el => el.remove());
}
"""


# ============================================================================
# OVERLAY MANAGER CLASS
# ============================================================================

@dataclass
class OverlayConfig:
    """Configuration for browser overlay."""
    enabled: bool = False
    highlight_enabled: bool = False
    position: str = "right"
    highlight_color: str = "#6366f1"  # Modern indigo
    highlight_duration_ms: int = 1200


class BrowserOverlay:
    """
    Modern browser overlay with page-shifting sidebar and element highlighting.
    
    Features:
    - Pushes page content aside (doesn't cover it)
    - Collapsible with smooth animation
    - Modern glassmorphism design
    - Activity log with status indicators
    """
    
    def __init__(self, config: Optional[OverlayConfig] = None):
        self.config = config or OverlayConfig()
        self._injected: set = set()
    
    async def inject(self, page: "IPage") -> bool:
        """Inject overlay into page."""
        if not self.config.enabled and not self.config.highlight_enabled:
            return False
        
        page_id = id(page)
        if page_id in self._injected:
            return True
        
        try:
            # Inject CSS
            css = OVERLAY_CSS.replace('var(--llm-accent)', self.config.highlight_color)
            await page.evaluate(f"""
                () => {{
                    if (document.getElementById('llm-styles')) return;
                    const style = document.createElement('style');
                    style.id = 'llm-styles';
                    style.textContent = `{css}`;
                    document.head.appendChild(style);
                }}
            """)
            
            # Inject sidebar if enabled
            if self.config.enabled:
                await page.evaluate(f"""
                    () => {{
                        if (document.getElementById('llm-sidebar')) return;
                        const wrap = document.createElement('div');
                        wrap.innerHTML = `{OVERLAY_HTML}`;
                        document.body.appendChild(wrap.firstElementChild);
                    }}
                """)
                await page.evaluate(OVERLAY_JS)
            
            self._injected.add(page_id)
            logger.debug("Modern overlay injected")
            return True
            
        except Exception as e:
            logger.warning(f"Overlay injection failed: {e}")
            return False
    
    async def update_action(self, page: "IPage", action: str, target: str = "") -> None:
        """Update current action display."""
        if not self.config.enabled:
            return
        try:
            await self.inject(page)
            a = action.replace("'", "\\'")
            t = target.replace("'", "\\'")
            await page.evaluate(f"() => window.__llmUpdateAction && window.__llmUpdateAction('{a}', '{t}')")
        except Exception:
            pass
    
    async def update_progress(self, page: "IPage", step: int, total: int, success: int) -> None:
        """Update progress stats."""
        if not self.config.enabled:
            return
        try:
            await self.inject(page)
            await page.evaluate(f"() => window.__llmUpdateStats && window.__llmUpdateStats({step}, {total}, {success})")
        except Exception:
            pass
    
    async def add_history(self, page: "IPage", action: str, target: str = "", status: str = "success") -> None:
        """Add history entry."""
        if not self.config.enabled:
            return
        try:
            await self.inject(page)
            a = action.replace("'", "\\'")
            t = target.replace("'", "\\'")
            await page.evaluate(f"() => window.__llmAddHistory && window.__llmAddHistory('{a}', '{t}', '{status}')")
        except Exception:
            pass
    
    async def highlight_element(self, page: "IPage", selector: str, label: str = "") -> bool:
        """Highlight element before interaction."""
        if not self.config.highlight_enabled:
            return False
        try:
            await self.inject(page)
            s = selector.replace("'", "\\'").replace('"', '\\"')
            l = label.replace("'", "\\'")
            return await page.evaluate(f"({HIGHLIGHT_JS})('{s}', '{l}')") is True
        except Exception:
            return False
    
    async def clear_highlight(self, page: "IPage") -> None:
        """Clear all highlights."""
        try:
            await page.evaluate(f"({CLEAR_HIGHLIGHT_JS})()")
        except Exception:
            pass
    
    async def highlight_and_wait(self, page: "IPage", selector: str, label: str = "") -> None:
        """Highlight, wait, then clear."""
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
                    document.getElementById('llm-sidebar')?.remove();
                    document.getElementById('llm-styles')?.remove();
                    document.body.classList.remove('llm-sidebar-open', 'llm-sidebar-collapsed');
                    document.querySelectorAll('.llm-highlight').forEach(e => e.classList.remove('llm-highlight'));
                    document.querySelectorAll('.llm-highlight-label').forEach(e => e.remove());
                }
            """)
            self._injected.discard(id(page))
        except Exception:
            pass


# Global instance
_overlay: Optional[BrowserOverlay] = None

def get_overlay(config: Optional[OverlayConfig] = None) -> BrowserOverlay:
    """Get or create global overlay."""
    global _overlay
    if _overlay is None or config is not None:
        _overlay = BrowserOverlay(config)
    return _overlay
