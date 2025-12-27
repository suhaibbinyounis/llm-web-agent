"""
Test script: Run saucedemo checkout flow using AdaptiveEngine.

This tests the new adaptive architecture with a real browser.
"""

import asyncio
import logging
from playwright.async_api import async_playwright

from llm_web_agent.engine.adaptive_engine import AdaptiveEngine
from llm_web_agent.llm.copilot_provider import CopilotProvider

# Enable logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')



async def main():
    """Run the saucedemo checkout flow."""
    
    # Read instructions
    with open("instructions/google_search.txt", "r") as f:
        instructions = f.read()
    
    print("=" * 60)
    print("Running SauceDemo Checkout Flow with AdaptiveEngine")
    print("=" * 60)
    print(f"\nInstructions:\n{instructions}\n")
    
    # Initialize LLM provider
    print("Initializing LLM provider...")
    try:
        llm = CopilotProvider()
        # Check health
        healthy = await llm.health_check()
        if not healthy:
            raise Exception("Copilot Gateway not running")
        print("✓ Copilot provider initialized")
    except Exception as e:
        print(f"Could not initialize Copilot: {e}")
        print("Trying OpenAI...")
        from llm_web_agent.llm.openai_provider import OpenAIProvider
        llm = OpenAIProvider()
    
    # Create adaptive engine
    engine = AdaptiveEngine(llm_provider=llm, lookahead_steps=2)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # Visible browser
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        
        # Navigate to initial page
        print("\n🌐 Navigating to saucedemo.com...")
        await page.goto("https://www.saucedemo.com")
        await asyncio.sleep(1)
        
        # Run the full flow
        goal = """
        1. Enter username "standard_user" in the username field
        2. Enter password "secret_sauce" in the password field
        3. Click the Login button
        4. Wait for products page to load
        5. Click on "Sauce Labs Backpack"
        6. Click "Add to cart" button
        7. Click the shopping cart icon
        8. Click "Checkout" button
        9. Fill first name "John", last name "Doe", postal code "12345"
        10. Click Continue
        11. Click Finish
        """
        
        print(f"\n🎯 Executing goal with AdaptiveEngine...")
        result = await engine.run(page, goal)
        
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Success: {result.success}")
        print(f"Steps completed: {result.steps_completed}/{result.steps_total}")
        print(f"Steps failed: {result.steps_failed}")
        print(f"Duration: {result.duration_seconds:.2f}s")
        print(f"Framework detected: {result.framework_detected}")
        
        if result.error:
            print(f"Error: {result.error}")
        
        print("\n📋 Step Details:")
        for i, sr in enumerate(result.step_results):
            status = "✅" if sr.success else "❌"
            loc_info = f" [{sr.locator_type.value if sr.locator_type else 'N/A'}]" if sr.success else ""
            print(f"  {i+1}. {status} {sr.step.action.value}: {sr.step.target}{loc_info} ({sr.duration_ms:.0f}ms)")
            if sr.error:
                print(f"       Error: {sr.error}")
        
        # Keep browser open for viewing
        print("\n👀 Keeping browser open for 10 seconds...")
        await asyncio.sleep(10)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
