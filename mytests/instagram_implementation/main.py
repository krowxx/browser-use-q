"""
Main entry point for Instagram automation.
Handles browser setup, login, and daily task orchestration.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple
from browser_use import Agent, Browser
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from .config import INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, DEFAULT_LLM
from .daily_tasks import run_daily_tasks, resume_daily_tasks, DailyStats

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def instagram_login(
    browser_context: BrowserContext,
    llm: ChatGoogleGenerativeAI
) -> bool:
    """
    Log in to Instagram using the configured credentials.
    
    Args:
        browser_context: Browser context to use for login
        llm: Language model for instructions
    
    Returns:
        bool: True if login was successful, False otherwise
    """
    try:
        # Create agent for login with the provided context
        agent = Agent(
            task=(
                "Log in to Instagram with these credentials:\n"
                f"Username: {INSTAGRAM_USERNAME}\n"
                f"Password: {INSTAGRAM_PASSWORD}\n"
                "After logging in, verify we're on the Instagram home feed."
            ),
            llm=llm,
            browser_context=browser_context,
            use_vision=True
        )
        
        # Run the login agent
        history = await agent.run()
        
        # Check if login was successful by verifying we're on the home feed
        for action in history.action_results():
            if action.extracted_content and "successfully logged in" in action.extracted_content.lower():
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error during Instagram login: {str(e)}")
        return False

async def setup_browser_and_context() -> Tuple[Browser, BrowserContext]:
    """
    Set up the browser and context with appropriate configurations.
    
    Returns:
        Tuple[Browser, BrowserContext]: The configured browser and context instances
    """
    # Initialize browser with configuration to keep it alive
    browser_config = BrowserConfig(
        _force_keep_browser_alive=True,
        headless=False,  # Set to True for production
        disable_security=True
    )
    browser = Browser(config=browser_config)
    
    # Create context configuration that keeps the context alive
    context_config = BrowserContextConfig(
        _force_keep_context_alive=True,
        cookies_file="instagram_cookies.json"  # Save cookies for potential reuse
    )
    
    # Create and return the context
    browser_context = await browser.new_context(config=context_config)
    return browser, browser_context

async def main():
    """
    Main function to run the Instagram automation.
    """
    browser = None
    browser_context = None
    
    try:
        # Initialize browser, context and LLM
        browser, browser_context = await setup_browser_and_context()
        llm = DEFAULT_LLM
        
        # Perform login using the created context
        login_success = await instagram_login(browser_context, llm)
        if not login_success:
            logger.error("Failed to log in to Instagram")
            return
            
        logger.info("Successfully logged in to Instagram")
        
        # Continue with daily tasks using the same context
        await run_daily_tasks(browser_context, llm)
        
    except Exception as e:
        logger.error(f"Error in main function: {str(e)}")
    finally:
        # Clean up resources
        if browser_context:
            await browser_context.close()
        if browser:
            await browser.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Instagram Automation")
    parser.add_argument(
        "--resume",
        type=str,
        help="Path to stats file to resume from",
        default=None
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in headless mode"
    )
    
    args = parser.parse_args()
    
    # Run the main function
    asyncio.run(main()) 