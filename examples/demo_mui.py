"""
Demo: Complex form interactions on MUI website.
"""

import asyncio
from playwright.async_api import async_playwright

from llm_web_agent.engine.browser_overlay import BrowserOverlay, OverlayConfig


async def demo_mui():
    """Demo overlay on MUI components page."""
    
    config = OverlayConfig(
        enabled=True,
        highlight_enabled=True,
        highlight_color="#6366f1",
        highlight_duration_ms=1000,
    )
    
    overlay = BrowserOverlay(config)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        # Step 1: Navigate to MUI TextField demo
        print("🌐 Navigating to MUI TextField demo...")
        await page.goto("https://mui.com/material-ui/react-text-field/")
        await asyncio.sleep(2)
        
        # Inject overlay
        await overlay.inject(page)
        await overlay.update_action(page, "Navigate", "MUI TextField Demo")
        await overlay.update_progress(page, 1, 6, 0)
        await asyncio.sleep(1)
        
        # Step 2: Find and interact with first text field
        print("📝 Finding text fields...")
        await overlay.update_action(page, "Locate", "Text field components")
        
        # Try to find the demo text field
        text_field_selectors = [
            'input[placeholder="Outlined"]',
            'input.MuiInputBase-input',
            '#outlined-basic',
        ]
        
        for selector in text_field_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    print(f"✅ Found: {selector}")
                    await overlay.highlight_element(page, selector, "Fill: Text Input")
                    await overlay.add_history(page, "Locate", selector, "success")
                    await asyncio.sleep(1.5)
                    await overlay.clear_highlight(page)
                    
                    await overlay.update_action(page, "Fill", "Demo text field")
                    await element.fill("Hello from LLM Web Agent!")
                    await overlay.add_history(page, "Fill", "text field", "success")
                    await overlay.update_progress(page, 2, 6, 1)
                    break
            except Exception as e:
                print(f"Skip {selector}: {e}")
        
        await asyncio.sleep(1)
        
        # Step 3: Navigate to Button page
        print("🔘 Navigating to Button demo...")
        await overlay.update_action(page, "Navigate", "Button components")
        await page.goto("https://mui.com/material-ui/react-button/")
        await asyncio.sleep(2)
        
        await overlay.inject(page)  # Re-inject after navigation
        await overlay.update_progress(page, 3, 6, 2)
        
        # Step 4: Find and click a button
        print("🔘 Looking for buttons...")
        await overlay.update_action(page, "Locate", "Primary Button")
        
        button_selectors = [
            'button.MuiButton-containedPrimary',
            'button:has-text("Primary")',
        ]
        
        for selector in button_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    print(f"✅ Found: {selector}")
                    await overlay.highlight_element(page, selector, "Click: Button")
                    await overlay.add_history(page, "Locate", "Primary button", "success")
                    await asyncio.sleep(1.5)
                    await overlay.clear_highlight(page)
                    
                    await overlay.update_action(page, "Click", "Primary button")
                    await element.click()
                    await overlay.add_history(page, "Click", "button", "success")
                    await overlay.update_progress(page, 4, 6, 3)
                    break
            except Exception as e:
                print(f"Skip {selector}: {e}")
        
        await asyncio.sleep(1)
        
        # Step 5: Navigate to Checkbox page
        print("☑️ Navigating to Checkbox demo...")
        await overlay.update_action(page, "Navigate", "Checkbox components")
        await page.goto("https://mui.com/material-ui/react-checkbox/")
        await asyncio.sleep(2)
        
        await overlay.inject(page)
        await overlay.update_progress(page, 5, 6, 4)
        
        # Step 6: Find and toggle checkbox
        print("☑️ Finding checkboxes...")
        await overlay.update_action(page, "Locate", "Checkbox")
        
        checkbox_selectors = [
            'input[type="checkbox"]',
            '.MuiCheckbox-root input',
        ]
        
        for selector in checkbox_selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    print(f"✅ Found: {selector}")
                    await overlay.highlight_element(page, selector, "Toggle: Checkbox")
                    await overlay.add_history(page, "Locate", "Checkbox", "success")
                    await asyncio.sleep(1.5)
                    await overlay.clear_highlight(page)
                    
                    await overlay.update_action(page, "Toggle", "Checkbox")
                    await element.click()
                    await overlay.add_history(page, "Toggle", "checkbox", "success")
                    await overlay.update_progress(page, 6, 6, 5)
                    break
            except Exception as e:
                print(f"Skip {selector}: {e}")
        
        await asyncio.sleep(1)
        
        # Complete
        await overlay.update_action(page, "Complete", "All 6 steps done!")
        await overlay.add_history(page, "Complete", "Task finished", "success")
        
        print("\n🎉 Demo complete! Keeping browser open for 8 seconds...")
        await asyncio.sleep(8)
        
        await browser.close()


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Web Agent - MUI Complex Demo")
    print("=" * 60)
    print()
    asyncio.run(demo_mui())
