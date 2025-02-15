"""
Main entry point for Instagram automation.
Handles browser setup, login, and daily task orchestration.
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from browser_use.agent.service import Agent
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
    browser: Browser,
    llm: ChatGoogleGenerativeAI
) -> bool:
    """
    Log in to Instagram using the configured credentials.
    
    Args:
        browser: Browser instance
        llm: Language model for instructions
    
    Returns:
        bool: True if login was successful, False otherwise
    """
    try:
        # Create agent for login
        agent = Agent(
            task=(
                "Log in to Instagram with these credentials:\n"
                f"Username: {INSTAGRAM_USERNAME}\n"
                f"Password: {INSTAGRAM_PASSWORD}\n"
                "After logging in, verify we're on the Instagram home feed."
            ),
            llm=llm,
            browser=browser
        )
        
        # Run the login agent
        history = await agent.run()
        
        # Check if login was successful
        for action in history.action_results():
            if action.is_done:
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error during Instagram login: {str(e)}")
        return False

async def main(
    resume_file: Optional[str] = None,
    headless: bool = False
) -> None:
    """
    Main function to run the Instagram automation.
    
    Args:
        resume_file: Optional path to stats file to resume from
        headless: Whether to run the browser in headless mode
    """
    # Validate environment
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        raise ValueError(
            "Instagram credentials not found. "
            "Please set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in your .env file."
        )
    
    # Initialize browser with custom config
    context_config = BrowserContextConfig(
        browser_window_size={'width': 1280, 'height': 800},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        locale="en-US",
        disable_security=True,
        wait_for_network_idle_page_load_time=3.0,
        highlight_elements=True
    )
    
    browser_config = BrowserConfig(
        headless=headless,
        disable_security=True,
        new_context_config=context_config
    )
    
    browser = Browser(config=browser_config)
    llm = DEFAULT_LLM
    
    try:
        # Log in to Instagram
        logger.info("Logging in to Instagram...")
        login_success = await instagram_login(browser, llm)
        
        if not login_success:
            raise Exception("Failed to log in to Instagram")
        
        logger.info("Successfully logged in to Instagram")
        
        # Run or resume daily tasks
        if resume_file:
            if not os.path.exists(resume_file):
                raise FileNotFoundError(f"Resume file not found: {resume_file}")
            
            logger.info(f"Resuming tasks from {resume_file}")
            stats = await resume_daily_tasks(browser, resume_file, llm)
        else:
            logger.info("Starting new daily tasks")
            stats = await run_daily_tasks(browser, llm)
        
        # Log final stats
        logger.info("Daily tasks completed. Final stats:")
        logger.info(f"- Target audience size: {len(stats.stats['target_audience'])}")
        logger.info(f"- Successful follows: {stats.stats['follows'].get('successful', 0)}")
        logger.info(f"- Total likes: {stats.stats['likes'].get('total_likes', 0)}")
        logger.info(f"- Successful comments: {stats.stats['comments'].get('successful', 0)}")
        
        if stats.stats['errors']:
            logger.warning(f"Encountered {len(stats.stats['errors'])} errors during execution")
        
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise
    
    finally:
        # Always close the browser
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
    asyncio.run(main(args.resume, args.headless)) 