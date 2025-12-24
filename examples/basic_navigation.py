"""
Example: Basic Navigation

This example shows how to use the agent for basic web navigation.
"""

import asyncio
from llm_web_agent import Agent
from llm_web_agent.config import load_config


async def main():
    """Run a basic navigation example."""
    
    # Load configuration (from env vars, config files, or defaults)
    settings = load_config()
    
    # Create and initialize the agent
    agent = Agent(settings=settings)
    
    async with agent:
        # Navigate to a website
        print("Navigating to example.com...")
        await agent.goto("https://example.com")
        
        # Take a screenshot
        screenshot = await agent.screenshot()
        with open("screenshot.png", "wb") as f:
            f.write(screenshot)
        print("Screenshot saved to screenshot.png")
        
        print(f"Current URL: {agent.page.url}")
        print(f"Page title: {agent.page.title}")


if __name__ == "__main__":
    asyncio.run(main())
