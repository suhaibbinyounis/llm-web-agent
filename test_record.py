"""
Recorded script: recording
Recorded at: 2025-12-30T14:38:25.195086
Start URL: https://notes.suhaib.in
Actions: 7
"""

import asyncio
import re
from playwright.async_api import async_playwright, expect, TimeoutError

async def perform_action(page, action_type, selectors, **kwargs):
    """Perform action with fallback selectors."""
    for selector in selectors:
        try:
            loc = page.locator(selector).first
            if action_type == 'click':
                await loc.click(timeout=1000)
            elif action_type == 'fill':
                await loc.fill(kwargs['value'], timeout=1000)
            elif action_type == 'select':
                await loc.select_option(kwargs['value'], timeout=1000)
            elif action_type == 'check':
                await loc.check(timeout=1000)
            elif action_type == 'uncheck':
                await loc.uncheck(timeout=1000)
            elif action_type == 'dblclick':
                await loc.dblclick(timeout=1000)
            return
        except:
            continue
    
    # Fallback: try best selector with full timeout
    if selectors:
        loc = page.locator(selectors[0]).first
        if action_type == 'click': await loc.click(timeout=5000)
        elif action_type == 'fill': await loc.fill(kwargs['value'], timeout=5000)
        elif action_type == 'select': await loc.select_option(kwargs['value'], timeout=5000)
        elif action_type == 'check': await loc.check(timeout=5000)
        elif action_type == 'uncheck': await loc.uncheck(timeout=5000)
        elif action_type == 'dblclick': await loc.dblclick(timeout=5000)
    else:
        raise Exception("No selectors provided for action")

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context()
        page = await context.new_page()
        pages = [page]  # Track all pages for multi-tab support

        # Set generous timeout for slow pages
        page.set_default_timeout(30000)

        # Step 1: Navigate to https://notes.suhaib.in
        try:
            await page.goto("https://notes.suhaib.in", wait_until="domcontentloaded")
        except TimeoutError:
            print("Navigation timeout for https://notes.suhaib.in..., continuing...")
        
        # Wait 1861ms (as recorded)
        await asyncio.sleep(1.9)
        # Step 2: Navigate to https://notes.suhaib.in/docs/tech/how-to/
        try:
            await page.goto("https://notes.suhaib.in/docs/tech/how-to/", wait_until="domcontentloaded")
        except TimeoutError:
            print("Navigation timeout for https://notes.suhaib.in/docs/tech/how-to/..., continuing...")
        
        # Wait 1366ms (as recorded)
        await asyncio.sleep(1.4)
        # Step 3: Click on Curl Your Way to Productivity: Pastebin CLI Secret...
        try:
            await page.locator("div.hx-mb-10:nth-child(2) > h3 > a.hx-block").first.click(timeout=10000)
        except TimeoutError:
            print("Click timeout for div.hx-mb-10:nth-child(2) > h3 > a.hx-block..., continuing...")
        
        # Wait 34227ms (as recorded)
        await asyncio.sleep(5.0)
        # Step 4: Navigate to https://notes.suhaib.in/docs/tech/how-to/curl-pastebin-cli-t...
        try:
            await page.goto("https://notes.suhaib.in/docs/tech/how-to/curl-pastebin-cli-tricks-productivity/", wait_until="domcontentloaded")
        except TimeoutError:
            print("Navigation timeout for https://notes.suhaib.in/docs/tech/how-to/curl-past..., continuing...")
        
        # Wait 2700ms (as recorded)
        await asyncio.sleep(2.7)
        # Step 5: Scroll by 249px
        await page.evaluate("window.scrollTo(0, 249)")
        
        # Wait 1034ms (as recorded)
        await asyncio.sleep(1.0)
        # Step 6: Scroll by 456px
        await page.evaluate("window.scrollTo(0, 456)")
        
        # Wait 784ms (as recorded)
        await asyncio.sleep(0.8)
        # Step 7: Scroll by 1118px
        await page.evaluate("window.scrollTo(0, 1118)")
        

        print('Replay completed successfully!')
        await asyncio.sleep(2)  # Keep browser open briefly to see result
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
