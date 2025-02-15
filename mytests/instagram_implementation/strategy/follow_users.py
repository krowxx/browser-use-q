"""
Functions for following users on Instagram.
Handles following users in batches with appropriate delays and engagement.
"""

import logging
from typing import List, Optional, Dict, Any
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from browser_use.agent.service import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from ..config import MAX_FOLLOWS_PER_DAY, ACTIONS_PER_BATCH, DEFAULT_LLM
from .timing import wait_between_actions, wait_between_batches

logger = logging.getLogger(__name__)

async def follow_user(
    browser_context: BrowserContext,
    username: str,
    llm: Optional[ChatGoogleGenerativeAI] = None,
    engage_first: bool = True
) -> bool:
    """
    Follow a single user on Instagram, optionally engaging with their content first.
    
    Args:
        browser_context: BrowserContext instance
        username: Username to follow
        llm: Language model for agent instructions
        engage_first: Whether to engage with user's content before following
    
    Returns:
        bool: True if follow was successful, False otherwise
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    try:
        # Create agent for following the user
        task = (
            f"Navigate to instagram.com/{username} and:"
            f"{' 1. Like their most recent post.' if engage_first else ''}"
            f"{' 2.' if engage_first else ' 1.'} Click the follow button if not already following"
            " 3. Verify the follow action was successful"
            " 4. Return 'followed' if successful"
        )
        
        agent = Agent(
            task=task,
            llm=llm,
            browser_context=browser_context
        )
        
        # Run the agent
        history = await agent.run()
        
        # Check if follow was successful
        for action in history.action_results():
            if action.extracted_content and "followed" in action.extracted_content.lower():
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error following user {username}: {str(e)}")
        return False

async def follow_users_batch(
    browser_context: BrowserContext,
    usernames: List[str],
    batch_size: int,
    llm: Optional[ChatGoogleGenerativeAI] = None,
    engage_first: bool = True
) -> Dict[str, bool]:
    """
    Follow a batch of users with appropriate delays between actions.
    
    Args:
        browser_context: BrowserContext instance
        usernames: List of usernames to follow
        batch_size: Number of users to follow in this batch
        llm: Language model for agent instructions
        engage_first: Whether to engage with users' content before following
    
    Returns:
        Dict mapping usernames to success status
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    results = {}
    users_to_follow = usernames[:batch_size]
    
    for username in users_to_follow:
        # Skip if we've already tried this user
        if username in results:
            continue
            
        # Follow the user
        success = await follow_user(browser_context, username, llm, engage_first)
        results[username] = success
        
        # Wait between actions
        await wait_between_actions()
    
    return results

async def follow_users_daily(
    browser_context: BrowserContext,
    usernames: List[str],
    llm: Optional[ChatGoogleGenerativeAI] = None,
    engage_first: bool = True
) -> Dict[str, bool]:
    """
    Follow users throughout the day in batches, respecting daily limits.
    
    Args:
        browser_context: BrowserContext instance
        usernames: List of usernames to follow
        llm: Language model for agent instructions
        engage_first: Whether to engage with users' content before following
    
    Returns:
        Dict mapping usernames to success status
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    all_results = {}
    remaining_users = usernames.copy()
    users_per_batch = ACTIONS_PER_BATCH["follows"]
    total_followed = 0
    
    while remaining_users and total_followed < MAX_FOLLOWS_PER_DAY:
        # Calculate batch size
        batch_size = min(users_per_batch, MAX_FOLLOWS_PER_DAY - total_followed)
        
        # Follow batch of users
        batch_results = await follow_users_batch(
            browser_context,
            remaining_users,
            batch_size,
            llm,
            engage_first
        )
        
        # Update tracking
        all_results.update(batch_results)
        successful_follows = sum(1 for success in batch_results.values() if success)
        total_followed += successful_follows
        
        # Remove processed users
        processed_users = list(batch_results.keys())
        remaining_users = [u for u in remaining_users if u not in processed_users]
        
        # If we have more users to process, wait between batches
        if remaining_users and total_followed < MAX_FOLLOWS_PER_DAY:
            await wait_between_batches()
    
    return all_results 