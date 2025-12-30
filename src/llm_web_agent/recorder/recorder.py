"""
Browser Recorder - Captures user actions in the browser.

Uses Chrome DevTools Protocol (CDP) to monitor user interactions
and record them as replayable actions.
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING
from enum import Enum

if TYPE_CHECKING:
    from playwright.async_api import Page, CDPSession

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of recordable actions."""
    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    TYPE = "type"
    SELECT = "select"
    CHECK = "check"
    UNCHECK = "uncheck"
    PRESS = "press"
    SCROLL = "scroll"
    HOVER = "hover"
    WAIT = "wait"
    # Tab actions
    NEW_TAB = "new_tab"
    SWITCH_TAB = "switch_tab"
    CLOSE_TAB = "close_tab"
    # Advanced mouse
    RIGHT_CLICK = "right_click"
    DRAG = "drag"
    # Assertions
    ASSERT_TEXT = "assert_text"
    ASSERT_VALUE = "assert_value"
    ASSERT_VISIBLE = "assert_visible"
    ASSERT_HIDDEN = "assert_hidden"
    SCREENSHOT = "screenshot"



@dataclass
class RecordedAction:
    """A single recorded user action."""
    action_type: ActionType
    timestamp_ms: int
    selector: Optional[str] = None
    selectors: Optional[List[str]] = None
    value: Optional[str] = None
    url: Optional[str] = None
    key: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    element_info: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "action_type": self.action_type.value,
            "timestamp_ms": self.timestamp_ms,
        }
        if self.selector:
            result["selector"] = self.selector
        if self.selectors:
            result["selectors"] = self.selectors
        if self.value:
            result["value"] = self.value
        if self.url:
            result["url"] = self.url
        if self.key:
            result["key"] = self.key
        if self.x is not None:
            result["x"] = self.x
        if self.y is not None:
            result["y"] = self.y
        if self.element_info:
            result["element_info"] = self.element_info
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordedAction":
        """Create from dictionary."""
        return cls(
            action_type=ActionType(data["action_type"]),
            timestamp_ms=data.get("timestamp_ms", 0),
            selector=data.get("selector"),
            selectors=data.get("selectors"),
            value=data.get("value"),
            url=data.get("url"),
            key=data.get("key"),
            x=data.get("x"),
            y=data.get("y"),
            element_info=data.get("element_info", {}),
        )






@dataclass
class RecordingSession:
    """A complete recording session."""
    name: str
    actions: List[RecordedAction] = field(default_factory=list)
    start_url: Optional[str] = None
    recorded_at: Optional[str] = None
    duration_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "start_url": self.start_url,
            "recorded_at": self.recorded_at,
            "duration_ms": self.duration_ms,
            "actions": [a.to_dict() for a in self.actions],
            "metadata": self.metadata,
        }
    
    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecordingSession":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            start_url=data.get("start_url"),
            recorded_at=data.get("recorded_at"),
            duration_ms=data.get("duration_ms", 0),
            actions=[RecordedAction.from_dict(a) for a in data.get("actions", [])],
            metadata=data.get("metadata", {}),
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "RecordingSession":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))


class BrowserRecorder:
    """
    Records user browser actions using CDP events.
    
    Example:
        >>> recorder = BrowserRecorder()
        >>> await recorder.start(page, "my_recording")
        >>> # User performs actions...
        >>> session = await recorder.stop()
        >>> print(session.to_json())
    """
    
    def __init__(self, show_panel: bool = True):
        """Initialize the recorder."""
        self._page: Optional["Page"] = None
        self._cdp: Optional["CDPSession"] = None
        self._session: Optional[RecordingSession] = None
        self._is_recording = False
        self._is_paused = False
        self._show_panel = show_panel
        self._start_time: float = 0
        self._last_url: str = ""
        self._pending_input: str = ""
        self._pending_selector: Optional[str] = None
        self._on_action_callbacks: List[Callable[[RecordedAction], None]] = []
        self._on_stop_callback: Optional[Callable[[], None]] = None
        # Multi-tab tracking
        self._context = None  # Browser context
        self._pages: List["Page"] = []  # All tracked pages
        self._active_page_index: int = 0  # Currently active tab
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._is_recording
    
    @property
    def current_session(self) -> Optional[RecordingSession]:
        """Get the current recording session."""
        return self._session
    
    def on_action(self, callback: Callable[[RecordedAction], None]) -> None:
        """Register a callback for when an action is recorded."""
        self._on_action_callbacks.append(callback)
    
    def on_stop(self, callback: Callable[[], None]) -> None:
        """Register a callback for when stop is requested from panel."""
        self._on_stop_callback = callback
    
    async def undo_last_action(self) -> Optional[RecordedAction]:
        """Remove and return the last recorded action."""
        if self._session and self._session.actions:
            action = self._session.actions.pop()
            await self._update_panel_count()
            return action
        return None
    
    async def _update_panel_count(self) -> None:
        """Update the action count display in the panel."""
        if not self._page or not self._show_panel:
            return
        count = len(self._session.actions) if self._session else 0
        try:
            await self._page.evaluate(f"window._updateRecorderCount && window._updateRecorderCount({count})")
        except Exception:
            pass
    
    async def start(
        self,
        page: "Page",
        name: str = "recording",
        start_url: Optional[str] = None,
    ) -> None:
        """
        Start recording actions on the page.
        
        Args:
            page: Playwright page to record
            name: Name for this recording session
            start_url: Optional URL to navigate to first
        """
        if self._is_recording:
            raise RuntimeError("Already recording. Call stop() first.")
        
        self._page = page
        self._start_time = time.time()
        self._last_url = page.url
        
        # Track browser context for multi-tab support
        self._context = page.context
        self._pages = [page]
        self._active_page_index = 0
        
        # Listen for new tabs/popups
        self._context.on("page", self._on_new_page)
        
        # Create recording session
        from datetime import datetime
        self._session = RecordingSession(
            name=name,
            start_url=start_url or page.url,
            recorded_at=datetime.now().isoformat(),
        )
        
        # Navigate to start URL if provided
        if start_url and page.url != start_url:
            await page.goto(start_url)
            self._record_action(RecordedAction(
                action_type=ActionType.NAVIGATE,
                timestamp_ms=self._elapsed_ms(),
                url=start_url,
            ))
        
        # Set up CDP session for event monitoring
        await self._setup_cdp_listeners()
        
        # Set up page event listeners
        self._setup_page_listeners()
        
        # Inject floating control panel
        if self._show_panel:
            await self._inject_control_panel()
        
        self._is_recording = True
        logger.info(f"Started recording session: {name}")
    
    async def stop(self) -> RecordingSession:
        """
        Stop recording and return the session.
        
        Returns:
            The completed recording session
        """
        if not self._is_recording:
            raise RuntimeError("Not recording. Call start() first.")
        
        # Flush any pending input
        self._flush_pending_input()
        
        # Calculate duration
        if self._session:
            self._session.duration_ms = self._elapsed_ms()
        
        # Clean up CDP session
        if self._cdp:
            try:
                await self._cdp.detach()
            except Exception:
                pass
            self._cdp = None
        
        self._is_recording = False
        session = self._session
        self._session = None
        self._page = None
        
        logger.info(f"Stopped recording. Captured {len(session.actions) if session else 0} actions.")
        return session
    
    async def _setup_cdp_listeners(self) -> None:
        """Set up Chrome DevTools Protocol listeners."""
        if not self._page:
            return
        
        # Get the underlying Playwright page
        # Access the internal page object to get CDP session
        try:
            context = self._page.context
            self._cdp = await context.new_cdp_session(self._page)
            
            # Enable required domains
            await self._cdp.send("DOM.enable")
            await self._cdp.send("Runtime.enable")
            
            # We'll primarily use page events, but CDP helps with element info
            logger.debug("CDP session established for recording")
            
        except Exception as e:
            logger.warning(f"Could not establish CDP session: {e}")
            # Continue without CDP - we'll rely on page events
    
    def _setup_page_listeners(self) -> None:
        """Set up Playwright page event listeners."""
        if not self._page:
            return
        
        # Track navigation
        self._page.on("framenavigated", self._on_navigation)
        
        # We'll inject JavaScript to capture user interactions
        asyncio.create_task(self._inject_event_listeners())
    
    def _on_new_page(self, new_page: "Page") -> None:
        """Handle a new tab/popup being opened."""
        if not self._is_recording:
            return
        
        # Add to tracked pages
        self._pages.append(new_page)
        new_tab_index = len(self._pages) - 1
        
        # Record new tab action
        self._record_action(RecordedAction(
            action_type=ActionType.NEW_TAB,
            timestamp_ms=self._elapsed_ms(),
            url=new_page.url or "about:blank",
            element_info={"tab_index": new_tab_index},
        ))
        
        logger.info(f"New tab opened: {new_page.url}")
        
        # Attach recording to new page
        asyncio.create_task(self._attach_to_page(new_page))
        
        # Listen for when this page closes
        new_page.on("close", lambda: self._on_page_close(new_page))
    
    async def _attach_to_page(self, page: "Page") -> None:
        """Attach recording listeners to a page."""
        try:
            # Wait for page to be ready
            await page.wait_for_load_state("domcontentloaded")
            
            # Switch active page to this one
            if page in self._pages:
                old_index = self._active_page_index
                new_index = self._pages.index(page)
                if new_index != old_index:
                    self._active_page_index = new_index
                    self._record_action(RecordedAction(
                        action_type=ActionType.SWITCH_TAB,
                        timestamp_ms=self._elapsed_ms(),
                        element_info={"from_tab": old_index, "to_tab": new_index},
                    ))
            
            # Update current page reference
            self._page = page
            self._last_url = page.url
            
            # Expose functions if not already
            try:
                await page.expose_function("_recordAction", self._handle_js_event)
            except Exception:
                pass  # Already exposed
            
            try:
                await page.expose_function("_recorderControl", self._handle_control_event)
            except Exception:
                pass
            
            # Inject event listeners
            await self._inject_event_listeners_to_page(page)
            
            # Inject control panel
            if self._show_panel:
                await self._inject_control_panel_to_page(page)
            
            # Track navigation on new page
            page.on("framenavigated", self._on_navigation)
            
        except Exception as e:
            logger.warning(f"Failed to attach to page: {e}")
    
    def _on_page_close(self, page: "Page") -> None:
        """Handle a page/tab being closed."""
        if not self._is_recording or page not in self._pages:
            return
        
        tab_index = self._pages.index(page)
        self._record_action(RecordedAction(
            action_type=ActionType.CLOSE_TAB,
            timestamp_ms=self._elapsed_ms(),
            element_info={"tab_index": tab_index},
        ))
        
        # Remove from tracked pages  
        self._pages.remove(page)
        
        # If closed page was active, switch to another
        if self._active_page_index >= len(self._pages):
            self._active_page_index = max(0, len(self._pages) - 1)
        
        if self._pages:
            self._page = self._pages[self._active_page_index]
        
        logger.info(f"Tab closed, remaining tabs: {len(self._pages)}")
    
    async def _inject_control_panel(self) -> None:
        """Inject the floating control panel into the page."""
        if not self._page:
            return
        
        # Expose control functions to JavaScript
        try:
            await self._page.expose_function("_recorderControl", self._handle_control_event)
        except Exception:
            pass  # May already be exposed
        
        panel_js = """
        (function() {
            // Remove existing panel if any
            const existing = document.getElementById('recorder-panel');
            if (existing) existing.remove();
            
            // Create panel container
            const panel = document.createElement('div');
            panel.id = 'recorder-panel';
            panel.innerHTML = `
                <style>
                    #recorder-panel {
                        position: fixed;
                        bottom: 20px;
                        right: 20px;
                        z-index: 999999;
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        font-size: 14px;
                        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
                        border: 1px solid #0f3460;
                        border-radius: 12px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.5);
                        color: #fff;
                        min-width: 280px;
                        user-select: none;
                        cursor: move;
                    }
                    #recorder-panel-header {
                        padding: 12px 16px;
                        display: flex;
                        align-items: center;
                        justify-content: space-between;
                        border-bottom: 1px solid #0f3460;
                        background: rgba(255,255,255,0.05);
                        border-radius: 12px 12px 0 0;
                    }
                    #recorder-panel-status {
                        display: flex;
                        align-items: center;
                        gap: 8px;
                    }
                    #recorder-panel-status .dot {
                        width: 10px;
                        height: 10px;
                        background: #e94560;
                        border-radius: 50%;
                        animation: pulse 1.5s infinite;
                    }
                    #recorder-panel-status .dot.paused {
                        background: #ffc107;
                        animation: none;
                    }
                    @keyframes pulse {
                        0%, 100% { opacity: 1; }
                        50% { opacity: 0.5; }
                    }
                    #recorder-panel-buttons {
                        padding: 12px;
                        display: grid;
                        grid-template-columns: repeat(4, 1fr);
                        gap: 8px;
                    }
                    #recorder-panel button {
                        background: rgba(255,255,255,0.1);
                        border: 1px solid rgba(255,255,255,0.2);
                        border-radius: 8px;
                        color: #fff;
                        padding: 10px 8px;
                        cursor: pointer;
                        font-size: 12px;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        gap: 4px;
                        transition: all 0.2s;
                    }
                    #recorder-panel button:hover {
                        background: rgba(255,255,255,0.2);
                        transform: translateY(-2px);
                    }
                    #recorder-panel button:active {
                        transform: translateY(0);
                    }
                    #recorder-panel button .icon {
                        font-size: 18px;
                    }
                    #recorder-panel button.stop-btn {
                        background: #e94560;
                        border-color: #e94560;
                    }
                    #recorder-panel button.pause-btn.active {
                        background: #ffc107;
                        border-color: #ffc107;
                        color: #000;
                    }
                    #recorder-panel-actions {
                        max-height: 0;
                        overflow: hidden;
                        transition: max-height 0.3s;
                        border-top: 1px solid #0f3460;
                    }
                    #recorder-panel-actions.open {
                        max-height: 200px;
                    }
                    #recorder-panel-actions-list {
                        padding: 8px;
                        max-height: 150px;
                        overflow-y: auto;
                        font-size: 12px;
                    }
                    #recorder-panel-actions-list .action-item {
                        padding: 6px 8px;
                        background: rgba(255,255,255,0.05);
                        border-radius: 4px;
                        margin-bottom: 4px;
                        display: flex;
                        justify-content: space-between;
                    }
                    #recorder-panel-assert-menu {
                        display: none;
                        padding: 8px;
                        border-top: 1px solid #0f3460;
                    }
                    #recorder-panel-assert-menu.open {
                        display: block;
                    }
                    #recorder-panel-assert-menu button {
                        width: 100%;
                        margin-bottom: 4px;
                    }
                </style>
                <div id="recorder-panel-header">
                    <div id="recorder-panel-status">
                        <span class="dot"></span>
                        <span>Recording... (<span id="recorder-count">0</span> actions)</span>
                    </div>
                </div>
                <div id="recorder-panel-buttons">
                    <button class="pause-btn" onclick="window._recorderTogglePause()">
                        <span class="icon">⏸️</span>
                        <span>Pause</span>
                    </button>
                    <button onclick="window._recorderUndo()">
                        <span class="icon">↩️</span>
                        <span>Undo</span>
                    </button>
                    <button onclick="window._recorderToggleView()">
                        <span class="icon">📋</span>
                        <span>View</span>
                    </button>
                    <button onclick="window._recorderToggleAssert()">
                        <span class="icon">✅</span>
                        <span>Assert</span>
                    </button>
                    <button onclick="window._recorderScreenshot()">
                        <span class="icon">📸</span>
                        <span>Screenshot</span>
                    </button>
                    <button onclick="window._recorderAddWait()">
                        <span class="icon">⏱️</span>
                        <span>Wait</span>
                    </button>
                    <button onclick="window._recorderControl(JSON.stringify({action:'stop'}))">
                        <span class="icon">⏹️</span>
                        <span>Stop</span>
                    </button>
                </div>
                <div id="recorder-panel-actions">
                    <div id="recorder-panel-actions-list"></div>
                </div>
                <div id="recorder-panel-assert-menu">
                    <button onclick="window._recorderAssert('text')">📝 Assert text visible</button>
                    <button onclick="window._recorderAssert('element')">🔍 Assert element visible</button>
                    <button onclick="window._recorderAssert('url')">🔗 Assert URL contains</button>
                </div>
            `;
            document.body.appendChild(panel);
            
            // Make panel draggable - FIXED: use getBoundingClientRect
            let isDragging = false;
            let offsetX, offsetY;
            const header = panel.querySelector('#recorder-panel-header');
            
            header.addEventListener('mousedown', (e) => {
                e.preventDefault();  // Prevent text selection
                isDragging = true;
                const rect = panel.getBoundingClientRect();
                offsetX = e.clientX - rect.left;
                offsetY = e.clientY - rect.top;
                panel.style.cursor = 'grabbing';
            });
            
            document.addEventListener('mousemove', (e) => {
                if (isDragging) {
                    e.preventDefault();
                    panel.style.left = (e.clientX - offsetX) + 'px';
                    panel.style.right = 'auto';
                    panel.style.top = (e.clientY - offsetY) + 'px';
                    panel.style.bottom = 'auto';
                }
            });
            
            document.addEventListener('mouseup', () => {
                isDragging = false;
                panel.style.cursor = 'move';
            });
            
            // Global functions for UI
            window._updateRecorderCount = function(count) {
                const el = document.getElementById('recorder-count');
                if (el) el.textContent = count;
            };
            
            let paused = false;
            window._recorderTogglePause = function() {
                paused = !paused;
                const btn = panel.querySelector('.pause-btn');
                const dot = panel.querySelector('.dot');
                if (paused) {
                    btn.classList.add('active');
                    btn.querySelector('span:last-child').textContent = 'Resume';
                    dot.classList.add('paused');
                } else {
                    btn.classList.remove('active');
                    btn.querySelector('span:last-child').textContent = 'Pause';
                    dot.classList.remove('paused');
                }
                window._recorderControl(JSON.stringify({action: paused ? 'pause' : 'resume'}));
            };
            
            window._recorderUndo = function() {
                window._recorderControl(JSON.stringify({action: 'undo'}));
            };
            
            window._recorderToggleView = function() {
                const actions = panel.querySelector('#recorder-panel-actions');
                actions.classList.toggle('open');
                window._recorderControl(JSON.stringify({action: 'get_actions'}));
            };
            
            window._recorderToggleAssert = function() {
                const menu = panel.querySelector('#recorder-panel-assert-menu');
                menu.classList.toggle('open');
            };
            
            window._recorderAssert = function(type) {
                const text = type === 'text' ? prompt('Enter text to assert:') : 
                             type === 'url' ? prompt('Enter URL to match:') : null;
                window._recorderControl(JSON.stringify({action: 'assert', assertType: type, value: text}));
                panel.querySelector('#recorder-panel-assert-menu').classList.remove('open');
            };
            
            window._recorderScreenshot = function() {
                window._recorderControl(JSON.stringify({action: 'screenshot'}));
            };
            
            window._recorderAddWait = function() {
                const seconds = prompt('Wait seconds:', '2');
                if (seconds) {
                    window._recorderControl(JSON.stringify({action: 'wait', value: parseFloat(seconds) * 1000}));
                }
            };
            
            window._recorderUpdateActions = function(actions) {
                const list = document.getElementById('recorder-panel-actions-list');
                if (!list) return;
                list.innerHTML = actions.map((a, i) => `
                    <div class="action-item">
                        <span>${a.type}: ${a.target || ''}</span>
                        <span style="opacity:0.5">#${i+1}</span>
                    </div>
                `).join('');
            };
            
            console.log('[Recorder] Control panel injected');
        })();
        """
        
        try:
            await self._page.evaluate(panel_js)
            
            # Re-inject panel on navigation
            async def reinject_panel():
                await asyncio.sleep(0.5)
                if self._page and self._is_recording and self._show_panel:
                    try:
                        await self._page.evaluate(panel_js)
                    except Exception:
                        pass
            
            self._page.on("load", lambda: asyncio.create_task(reinject_panel()))
        except Exception as e:
            logger.warning(f"Could not inject control panel: {e}")
    
    async def _handle_control_event(self, event_json: str) -> str:
        """Handle control events from the panel."""
        try:
            # Flush any pending input before handling control event
            # This ensures that typing followed immediately by a panel action is recorded first
            self._flush_pending_input()
            
            event = json.loads(event_json)
            action = event.get("action")
            
            if action == "pause":
                self._is_paused = True
                return json.dumps({"status": "paused"})
                
            elif action == "resume":
                self._is_paused = False
                return json.dumps({"status": "recording"})
                
            elif action == "undo":
                undone = await self.undo_last_action()
                if undone:
                    return json.dumps({"status": "undone", "action": undone.action_type.value})
                return json.dumps({"status": "nothing_to_undo"})
                
            elif action == "stop":
                if self._on_stop_callback:
                    self._on_stop_callback()
                return json.dumps({"status": "stopping"})
                
            elif action == "get_actions":
                if self._session:
                    actions = [{"type": a.action_type.value, "target": a.selector or a.url or a.value} 
                               for a in self._session.actions[-10:]]  # Last 10
                    if self._page:
                        await self._page.evaluate(f"window._recorderUpdateActions && window._recorderUpdateActions({json.dumps(actions)})")
                return json.dumps({"status": "ok"})
                
            elif action == "assert":
                assert_type = event.get("assertType")
                value = event.get("value")
                # Record as a special assertion action
                self._record_action(RecordedAction(
                    action_type=ActionType.WAIT,  # Using WAIT as placeholder
                    timestamp_ms=self._elapsed_ms(),
                    value=f"assert:{assert_type}:{value or 'element'}",
                    element_info={"assertion": True, "type": assert_type, "value": value},
                ))
                return json.dumps({"status": "assertion_added"})
                
            elif action == "screenshot":
                if self._page:
                    # Take screenshot
                    import base64
                    screenshot = await self._page.screenshot()
                    # Store in metadata or as a special action
                    if self._session:
                        if "screenshots" not in self._session.metadata:
                            self._session.metadata["screenshots"] = []
                        self._session.metadata["screenshots"].append({
                            "timestamp_ms": self._elapsed_ms(),
                            "data": base64.b64encode(screenshot).decode(),
                        })
                return json.dumps({"status": "screenshot_taken"})
                
            elif action == "wait":
                wait_ms = event.get("value", 1000)
                self._record_action(RecordedAction(
                    action_type=ActionType.WAIT,
                    timestamp_ms=self._elapsed_ms(),
                    value=str(int(wait_ms)),
                ))
                await self._update_panel_count()
                return json.dumps({"status": "wait_added"})
                
        except Exception as e:
            logger.warning(f"Control event error: {e}")
            return json.dumps({"error": str(e)})
        
        return json.dumps({"status": "unknown"})

    
    async def _inject_event_listeners(self) -> None:
        """Inject JavaScript to capture user interactions."""
        if not self._page:
            return
        
        # Expose Python function to receive events from JavaScript
        try:
            await self._page.expose_function(
                "_recordAction",
                self._handle_js_event
            )
        except Exception as e:
            # Function may already be exposed - that's OK
            logger.debug(f"expose_function: {e}")
        
        # JavaScript code - no guard, always installs fresh
        js_code = r"""
        (function() {
            // Remove old listeners if they exist
            if (window._recorderCleanup) {
                window._recorderCleanup();
            }
            
            function getSelectors(el) {
                if (!el || el === document.body) return ['body'];
                
                const strategies = [];
                
                // 1. Precise attributes (Best)
                if (el.id) strategies.push('#' + CSS.escape(el.id));
                if (el.dataset.testid) strategies.push(`[data-testid="${el.dataset.testid}"]`);
                if (el.getAttribute('data-qa')) strategies.push(`[data-qa="${el.getAttribute('data-qa')}"]`);
                if (el.name) strategies.push(`[name="${el.name}"]`);
                if (el.getAttribute('aria-label')) strategies.push(`[aria-label="${el.getAttribute('aria-label')}"]`);
                if (el.placeholder) strategies.push(`[placeholder="${el.placeholder}"]`);
                if (el.alt) strategies.push(`[alt="${el.alt}"]`);
                
                // 2. Text content (Good for buttons/links)
                const text = (el.textContent || '').trim();
                if (text && text.length < 20 && ['A', 'BUTTON', 'LABEL', 'SPAN', 'DIV'].includes(el.tagName)) {
                   // Avoid generic text
                   strategies.push(`text=${text}`);
                }
                
                // 3. CSS Path (Fallback)
                let path = [];
                let current = el;
                while (current && current !== document.body && current.tagName) {
                    let selector = current.tagName.toLowerCase();
                    if (current.id) {
                        path.unshift('#' + CSS.escape(current.id));
                        break; 
                    }
                    if (current.className && typeof current.className === 'string') {
                        const classes = current.className.trim().split(/\s+/).filter(c => c && !c.includes(':'));
                        if (classes.length > 0) {
                            selector += '.' + classes[0]; // Use first class only
                        }
                    }
                    // Nth-child if duplicates exist
                    if (current.parentElement) {
                        const siblings = Array.from(current.parentElement.children).filter(c => c.tagName === current.tagName);
                        if (siblings.length > 1) {
                            const index = siblings.indexOf(current) + 1;
                            selector += `:nth-child(${index})`;
                        }
                    }
                    
                    path.unshift(selector);
                    current = current.parentElement;
                }
                strategies.push(path.slice(-3).join(' > '));
                
                // 4. XPath (Last resort)
                // Simplified XPath generation could be added here if needed
                
                // Deduplicate and filter empty
                return [...new Set(strategies)].filter(s => s && s.length > 0);
            }
            
            function getElementInfo(el) {
                return {
                    tag: el.tagName ? el.tagName.toLowerCase() : 'unknown',
                    id: el.id || null,
                    text: (el.textContent || '').trim().substring(0, 100),
                    type: el.type || null,
                    name: el.name || null,
                    placeholder: el.placeholder || null,
                    value: el.value || null,
                };
            }
            
            function sendAction(data) {
                try {
                    if (window._recordAction) {
                        window._recordAction(JSON.stringify(data));
                    }
                } catch (e) {
                    console.warn('[Recorder] Failed to send action:', e);
                }
            }
            
            // Click handler
            function handleClick(e) {
                // Ignore clicks on the recorder panel
                if (e.target.closest('#recorder-panel')) {
                    return;
                }
                
                const selectors = getSelectors(e.target);
                const info = getElementInfo(e.target);
                sendAction({
                    type: 'click',
                    selector: selectors[0], // Keep backward compat
                    selectors: selectors,
                    x: e.clientX,
                    y: e.clientY,
                    element_info: info
                });
            }
            
            // Input handler (for typing)
            function handleInput(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    const selectors = getSelectors(e.target);
                    sendAction({
                        type: 'input',
                        selector: selectors[0],
                        selectors: selectors,
                        value: e.target.value,
                        element_info: getElementInfo(e.target)
                    });
                }
            }
            
            // Change handler (for selects)
            function handleChange(e) {
                if (e.target.tagName === 'SELECT') {
                    const selectors = getSelectors(e.target);
                    sendAction({
                        type: 'select',
                        selector: selectors[0],
                        selectors: selectors,
                        value: e.target.value,
                        element_info: getElementInfo(e.target)
                    });
                } else if (e.target.type === 'checkbox') {
                    const selectors = getSelectors(e.target);
                    sendAction({
                        type: e.target.checked ? 'check' : 'uncheck',
                        selector: selectors[0],
                        selectors: selectors,
                        element_info: getElementInfo(e.target)
                    });
                }
            }
            
            // Keyboard shortcuts
            function handleKeydown(e) {
                // Only record special keys (Enter, Tab, Escape, etc.)
                if (['Enter', 'Tab', 'Escape', 'Backspace', 'Delete'].includes(e.key) ||
                    e.ctrlKey || e.metaKey || e.altKey) {
                    const selectors = getSelectors(e.target);
                    let key = e.key;
                    if (e.ctrlKey) key = 'Control+' + key;
                    if (e.metaKey) key = 'Meta+' + key;
                    if (e.altKey) key = 'Alt+' + key;
                    if (e.shiftKey) key = 'Shift+' + key;
                    
                    sendAction({
                        type: 'press',
                        selector: selectors[0],
                        selectors: selectors,
                        key: key
                    });
                }
            }
            
            // Scroll handler (debounced)
            let scrollTimeout = null;
            let scrollStartY = window.scrollY;
            function handleScroll(e) {
                // Debounce scroll events
                if (scrollTimeout) clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    const scrollDelta = window.scrollY - scrollStartY;
                    if (Math.abs(scrollDelta) > 100) {  // Only record significant scrolls
                        sendAction({
                            type: 'scroll',
                            y: scrollDelta
                        });
                        scrollStartY = window.scrollY;
                    }
                }, 300);
            }
            
            // Add listeners
            document.addEventListener('click', handleClick, true);
            document.addEventListener('input', handleInput, true);
            document.addEventListener('change', handleChange, true);
            document.addEventListener('keydown', handleKeydown, true);
            window.addEventListener('scroll', handleScroll, true);
            
            // Store cleanup function
            window._recorderCleanup = function() {
                document.removeEventListener('click', handleClick, true);
                document.removeEventListener('input', handleInput, true);
                document.removeEventListener('change', handleChange, true);
                document.removeEventListener('keydown', handleKeydown, true);
                window.removeEventListener('scroll', handleScroll, true);
                if (scrollTimeout) clearTimeout(scrollTimeout);
            };
            
            console.log('[Recorder] Event listeners installed');
        })();
        """
        
        async def inject_js():
            if self._page and self._is_recording:
                try:
                    await self._page.evaluate(js_code)
                except Exception as e:
                    logger.debug(f"JS injection error: {e}")
        
        # Initial injection
        await inject_js()
        
        # Re-inject after each navigation
        async def on_load_inject():
            # Small delay to ensure page is ready
            await asyncio.sleep(0.1)
            await inject_js()
        
        self._page.on("load", lambda: asyncio.create_task(on_load_inject()))
    
    async def _inject_event_listeners_to_page(self, page: "Page") -> None:
        """Inject event listeners to a specific page (for multi-tab support)."""
        # Reuse the same JS code from _inject_event_listeners
        js_code = self._get_event_listener_js()
        
        async def inject_js():
            if self._is_recording:
                try:
                    await page.evaluate(js_code)
                except Exception as e:
                    logger.debug(f"JS injection to page error: {e}")
        
        await inject_js()
        
        async def on_load_inject():
            await asyncio.sleep(0.1)
            await inject_js()
        
        page.on("load", lambda: asyncio.create_task(on_load_inject()))
    
    async def _inject_control_panel_to_page(self, page: "Page") -> None:
        """Inject control panel to a specific page (for multi-tab support)."""
        panel_js = self._get_control_panel_js()
        try:
            await page.evaluate(panel_js)
        except Exception as e:
            logger.debug(f"Control panel injection error: {e}")
    
    def _get_event_listener_js(self) -> str:
        """Return the JavaScript code for event listeners."""
        return r"""
        (function() {
            if (window._recorderCleanup) {
                window._recorderCleanup();
            }
            
            function getSelectors(el) {
                if (!el || el === document.body) return ['body'];
                const strategies = [];
                if (el.id) strategies.push('#' + CSS.escape(el.id));
                if (el.dataset.testid) strategies.push(`[data-testid="${el.dataset.testid}"]`);
                if (el.getAttribute('data-qa')) strategies.push(`[data-qa="${el.getAttribute('data-qa')}"]`);
                if (el.name) strategies.push(`[name="${el.name}"]`);
                if (el.getAttribute('aria-label')) strategies.push(`[aria-label="${el.getAttribute('aria-label')}"]`);
                if (el.placeholder) strategies.push(`[placeholder="${el.placeholder}"]`);
                
                const text = (el.textContent || '').trim();
                if (text && text.length < 20 && ['A', 'BUTTON', 'LABEL', 'SPAN', 'DIV'].includes(el.tagName)) {
                   strategies.push(`text=${text}`);
                }
                
                let path = [];
                let current = el;
                while (current && current !== document.body && current.tagName) {
                    let selector = current.tagName.toLowerCase();
                    if (current.id) {
                        path.unshift('#' + CSS.escape(current.id));
                        break; 
                    }
                    if (current.className && typeof current.className === 'string') {
                        const classes = current.className.trim().split(/\s+/).filter(c => c && !c.includes(':'));
                        if (classes.length > 0) selector += '.' + classes[0];
                    }
                    if (current.parentElement) {
                        const siblings = Array.from(current.parentElement.children).filter(c => c.tagName === current.tagName);
                        if (siblings.length > 1) {
                            const index = siblings.indexOf(current) + 1;
                            selector += `:nth-child(${index})`;
                        }
                    }
                    path.unshift(selector);
                    current = current.parentElement;
                }
                strategies.push(path.slice(-3).join(' > '));
                return [...new Set(strategies)].filter(s => s && s.length > 0);
            }
            
            function getElementInfo(el) {
                return {
                    tag: el.tagName ? el.tagName.toLowerCase() : 'unknown',
                    id: el.id || null,
                    text: (el.textContent || '').trim().substring(0, 100),
                    type: el.type || null,
                    name: el.name || null,
                    placeholder: el.placeholder || null,
                };
            }
            
            function sendAction(data) {
                try {
                    if (window._recordAction) window._recordAction(JSON.stringify(data));
                } catch (e) {}
            }
            
            function handleClick(e) {
                if (e.target.closest('#recorder-panel')) return;
                const selectors = getSelectors(e.target);
                sendAction({
                    type: 'click',
                    selector: selectors[0],
                    selectors: selectors,
                    x: e.clientX,
                    y: e.clientY,
                    element_info: getElementInfo(e.target)
                });
            }
            
            function handleInput(e) {
                if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                    const selectors = getSelectors(e.target);
                    sendAction({
                        type: 'input',
                        selector: selectors[0],
                        selectors: selectors,
                        value: e.target.value,
                        element_info: getElementInfo(e.target)
                    });
                }
            }
            
            function handleChange(e) {
                if (e.target.tagName === 'SELECT') {
                    const selectors = getSelectors(e.target);
                    sendAction({ type: 'select', selector: selectors[0], selectors: selectors, value: e.target.value });
                } else if (e.target.type === 'checkbox') {
                    const selectors = getSelectors(e.target);
                    sendAction({ type: e.target.checked ? 'check' : 'uncheck', selector: selectors[0], selectors: selectors });
                }
            }
            
            function handleKeydown(e) {
                if (['Enter', 'Tab', 'Escape', 'Backspace', 'Delete'].includes(e.key) || e.ctrlKey || e.metaKey || e.altKey) {
                    const selectors = getSelectors(e.target);
                    let key = e.key;
                    if (e.ctrlKey) key = 'Control+' + key;
                    if (e.metaKey) key = 'Meta+' + key;
                    if (e.altKey) key = 'Alt+' + key;
                    if (e.shiftKey) key = 'Shift+' + key;
                    sendAction({ type: 'press', selector: selectors[0], selectors: selectors, key: key });
                }
            }
            
            let scrollTimeout = null;
            let scrollStartY = window.scrollY;
            function handleScroll(e) {
                if (scrollTimeout) clearTimeout(scrollTimeout);
                scrollTimeout = setTimeout(() => {
                    const scrollDelta = window.scrollY - scrollStartY;
                    if (Math.abs(scrollDelta) > 100) {
                        sendAction({ type: 'scroll', y: scrollDelta });
                        scrollStartY = window.scrollY;
                    }
                }, 300);
            }
            
            document.addEventListener('click', handleClick, true);
            document.addEventListener('input', handleInput, true);
            document.addEventListener('change', handleChange, true);
            document.addEventListener('keydown', handleKeydown, true);
            window.addEventListener('scroll', handleScroll, true);
            
            window._recorderCleanup = function() {
                document.removeEventListener('click', handleClick, true);
                document.removeEventListener('input', handleInput, true);
                document.removeEventListener('change', handleChange, true);
                document.removeEventListener('keydown', handleKeydown, true);
                window.removeEventListener('scroll', handleScroll, true);
                if (scrollTimeout) clearTimeout(scrollTimeout);
            };
            
            console.log('[Recorder] Event listeners installed');
        })();
        """
    
    def _get_control_panel_js(self) -> str:
        """Return the JavaScript code for control panel (simplified for new tabs)."""
        # This returns a minimal version - full panel is only on main page
        return """
        (function() {
            if (document.getElementById('recorder-panel')) return;
            // Just log for now - full panel on main page only
            console.log('[Recorder] Recording active on this tab');
        })();
        """
    
    def _handle_js_event(self, event_json: str) -> None:
        """Handle an event from JavaScript."""
        if not self._is_recording:
            return
        
        try:
            event = json.loads(event_json)
            event_type = event.get("type")
            
            if event_type == "click":
                # Flush pending input before recording click
                self._flush_pending_input()
                self._record_action(RecordedAction(
                    action_type=ActionType.CLICK,
                    timestamp_ms=self._elapsed_ms(),
                    selector=event.get("selector"),
                    selectors=event.get("selectors"),
                    x=event.get("x"),
                    y=event.get("y"),
                    element_info=event.get("element_info", {}),
                ))

                
            elif event_type == "input":
                # Debounce input - we'll record the final value
                self._pending_input = event.get("value", "")
                self._pending_selector = event.get("selector")
                self._pending_selectors = event.get("selectors")
                
            elif event_type == "select":
                self._record_action(RecordedAction(
                    action_type=ActionType.SELECT,
                    timestamp_ms=self._elapsed_ms(),
                    selector=event.get("selector"),
                    selectors=event.get("selectors"),
                    value=event.get("value"),
                    element_info=event.get("element_info", {}),
                ))
                
            elif event_type in ("check", "uncheck"):
                self._record_action(RecordedAction(
                    action_type=ActionType.CHECK if event_type == "check" else ActionType.UNCHECK,
                    timestamp_ms=self._elapsed_ms(),
                    selector=event.get("selector"),
                    selectors=event.get("selectors"),
                    element_info=event.get("element_info", {}),
                ))
                
            elif event_type == "press":
                # Flush pending input before recording key press
                self._flush_pending_input()
                self._record_action(RecordedAction(
                    action_type=ActionType.PRESS,
                    timestamp_ms=self._elapsed_ms(),
                    selector=event.get("selector"),
                    selectors=event.get("selectors"),
                    key=event.get("key"),
                ))
                
            elif event_type == "scroll":
                self._record_action(RecordedAction(
                    action_type=ActionType.SCROLL,
                    timestamp_ms=self._elapsed_ms(),
                    y=event.get("y"),
                ))
                
        except Exception as e:
            logger.warning(f"Error handling JS event: {e}")
    
    def _on_navigation(self, frame) -> None:
        """Handle navigation events."""
        if not self._is_recording or not self._page:
            return
        
        # Only track main frame navigation
        if frame != self._page.main_frame:
            return
        
        new_url = frame.url
        if new_url != self._last_url and new_url != "about:blank":
            # Flush pending input before navigation
            self._flush_pending_input()
            
            self._record_action(RecordedAction(
                action_type=ActionType.NAVIGATE,
                timestamp_ms=self._elapsed_ms(),
                url=new_url,
            ))
            self._last_url = new_url
    
    def _flush_pending_input(self) -> None:
        """Flush any pending input as a fill action."""
        if self._pending_input and self._pending_selector:
            self._record_action(RecordedAction(
                action_type=ActionType.FILL,
                timestamp_ms=self._elapsed_ms(),
                selector=self._pending_selector,
                selectors=getattr(self, "_pending_selectors", None),
                value=self._pending_input,
            ))
            self._pending_input = ""
            self._pending_selector = None
            self._pending_selectors = None
    
    def _record_action(self, action: RecordedAction) -> None:
        """Record an action to the session."""
        # Skip if paused (except for special control actions)
        if self._is_paused and not action.element_info.get("assertion"):
            return
            
        if self._session:
            self._session.actions.append(action)
            logger.debug(f"Recorded: {action.action_type.value} -> {action.selector or action.url}")
            
            # Update panel count
            if self._show_panel and self._page:
                asyncio.create_task(self._update_panel_count())
            
            # Notify callbacks
            for callback in self._on_action_callbacks:
                try:
                    callback(action)
                except Exception as e:
                    logger.warning(f"Action callback error: {e}")
    
    def _elapsed_ms(self) -> int:
        """Get elapsed time since recording started."""
        return int((time.time() - self._start_time) * 1000)
