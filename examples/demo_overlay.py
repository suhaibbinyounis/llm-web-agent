"""
Demo script to showcase the browser overlay with sidebar and element highlighting.
"""

import asyncio
from playwright.async_api import async_playwright

from llm_web_agent.engine.browser_overlay import BrowserOverlay, OverlayConfig


async def demo_overlay():
    """Demonstrate the overlay features on a real website."""
    
    # Configure overlay with both features enabled
    config = OverlayConfig(
        enabled=True,           # Show sidebar
        highlight_enabled=True, # Highlight elements
        position="right",
        highlight_color="#FF6B6B",
        highlight_duration_ms=1200,
    )
    
    overlay = BrowserOverlay(config)
    
    async with async_playwright() as p:
        # Launch visible browser
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})
        
        # Navigate to a test site
        print("🌐 Navigating to example website...")
        await page.goto("https://the-internet.herokuapp.com/login")
        await asyncio.sleep(1)
        
        # Inject overlay
        await overlay.inject(page)
        await overlay.update_action(page, "Navigate", "Login Page")
        await overlay.update_progress(page, 1, 5, 0)
        await asyncio.sleep(0.5)
        
        # Step 1: Highlight and fill username
        print("📝 Filling username...")
        await overlay.update_action(page, "Fill", "Username field")
        await overlay.highlight_element(page, "#username", "Fill: username")
        await asyncio.sleep(1.2)
        await overlay.clear_highlight(page)
        await page.fill("#username", "tomsmith")
        await overlay.add_history(page, "Fill", "username", "success")
        await overlay.update_progress(page, 2, 5, 1)
        await asyncio.sleep(0.5)
        
        # Step 2: Highlight and fill password
        print("🔒 Filling password...")
        await overlay.update_action(page, "Fill", "Password field")
        await overlay.highlight_element(page, "#password", "Fill: password")
        await asyncio.sleep(1.2)
        await overlay.clear_highlight(page)
        await page.fill("#password", "SuperSecretPassword!")
        await overlay.add_history(page, "Fill", "password", "success")
        await overlay.update_progress(page, 3, 5, 2)
        await asyncio.sleep(0.5)
        
        # Step 3: Highlight and click login button
        print("🔘 Clicking Login button...")
        await overlay.update_action(page, "Click", "Login button")
        await overlay.highlight_element(page, "button[type='submit']", "Click: Login")
        await asyncio.sleep(1.5)
        await overlay.clear_highlight(page)
        await page.click("button[type='submit']")
        await overlay.add_history(page, "Click", "Login button", "success")
        await overlay.update_progress(page, 4, 5, 3)
        
        # Wait for navigation
        await asyncio.sleep(1)
        
        # Re-inject overlay after navigation
        await overlay.inject(page)
        await asyncio.sleep(0.5)
        
        # Step 4: Check for success message
        print("✅ Verifying login success...")
        await overlay.update_action(page, "Verify", "Login success message")
        flash = page.locator(".flash.success")
        if await flash.is_visible():
            await overlay.highlight_element(page, ".flash.success", "✓ Success!")
            await overlay.add_history(page, "Verify", "Login successful", "success")
            await overlay.update_progress(page, 5, 5, 4)
        await asyncio.sleep(2)
        
        # Step 5: Click logout
        print("🚪 Logging out...")
        await overlay.update_action(page, "Click", "Logout button")
        await overlay.highlight_element(page, "a.button", "Click: Logout")
        await asyncio.sleep(1.5)
        await overlay.clear_highlight(page)
        await page.click("a.button")
        await overlay.add_history(page, "Click", "Logout", "success")
        await asyncio.sleep(1)
        
        # Re-inject and show completion
        await overlay.inject(page)
        await overlay.update_action(page, "Complete", "All steps done!")
        await overlay.update_progress(page, 5, 5, 5)
        
        print("\n🎉 Demo complete! Keeping browser open for 5 seconds...")
        await asyncio.sleep(5)
        
        await browser.close()


if __name__ == "__main__":
    print("=" * 60)
    print("LLM Web Agent - Browser Overlay Demo")
    print("=" * 60)
    print()
    asyncio.run(demo_overlay())
