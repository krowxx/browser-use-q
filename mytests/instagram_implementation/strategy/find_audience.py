"""
Functions for discovering and analyzing potential Instagram users to engage with.
Handles hashtag exploration and competitor follower analysis.
"""

import logging
from typing import List, Set, Dict, Any, Optional
from browser_use.browser.browser import Browser
from browser_use.agent.service import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from ..config import HASHTAGS, COMPETITOR_ACCOUNTS, DEFAULT_LLM
from .timing import wait_between_actions

logger = logging.getLogger(__name__)

async def find_users_from_hashtag(
    browser: Browser,
    hashtag: str,
    max_users: int = 50,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> Set[str]:
    """
    Find users by exploring posts under a specific hashtag.
    
    Args:
        browser: Browser instance
        hashtag: Hashtag to explore (without #)
        max_users: Maximum number of users to collect
        llm: Language model for agent instructions
    
    Returns:
        Set of usernames found
    """
    users = set()
    hashtag_url = f"https://www.instagram.com/explore/tags/{hashtag}/"
    
    if llm is None:
        llm = DEFAULT_LLM
    
    try:
        # Create an agent for hashtag exploration
        agent = Agent(
            task=f"Navigate to {hashtag_url} and collect usernames from post authors",
            llm=llm,
            browser=browser
        )
        
        # Run the agent and collect results
        history = await agent.run()
        
        # Process results
        for action in history.action_results():
            if action.extracted_content:
                # Clean usernames and add to set
                usernames = [
                    username.strip('@/').split('/')[0]
                    for username in action.extracted_content.split()
                    if username.strip('@/')
                ]
                users.update(usernames)
                if len(users) >= max_users:
                    return set(list(users)[:max_users])
            
            await wait_between_actions()
            
    except Exception as e:
        logger.error(f"Error finding users from hashtag {hashtag}: {str(e)}")
    
    return users

async def find_users_from_competitor(
    browser: Browser,
    competitor_username: str,
    max_users: int = 50,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> Set[str]:
    """
    Find users by analyzing a competitor's followers.
    
    Args:
        browser: Browser instance
        competitor_username: Competitor's username (without @)
        max_users: Maximum number of users to collect
        llm: Language model for agent instructions
    
    Returns:
        Set of usernames found
    """
    users = set()
    profile_url = f"https://www.instagram.com/{competitor_username}/"
    
    if llm is None:
        llm = DEFAULT_LLM
    
    try:
        # Create an agent for competitor analysis
        agent = Agent(
            task=f"Navigate to {profile_url}, open the followers list, and collect usernames",
            llm=llm,
            browser=browser
        )
        
        # Run the agent and collect results
        history = await agent.run()
        
        # Process results
        for action in history.action_results():
            if action.extracted_content:
                # Clean usernames and add to set
                usernames = [
                    username.strip('@/').split('/')[0]
                    for username in action.extracted_content.split()
                    if username.strip('@/')
                ]
                users.update(usernames)
                if len(users) >= max_users:
                    return set(list(users)[:max_users])
            
            await wait_between_actions()
            
    except Exception as e:
        logger.error(f"Error finding users from competitor {competitor_username}: {str(e)}")
    
    return users

async def find_target_audience(
    browser: Browser,
    max_users: int = 200,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> List[str]:
    """
    Find target audience by combining users from hashtags and competitor analysis.
    
    Args:
        browser: Browser instance
        max_users: Maximum total users to collect
        llm: Language model for agent instructions
    
    Returns:
        List of target usernames
    """
    all_users = set()
    users_per_source = max_users // (len(HASHTAGS) + len(COMPETITOR_ACCOUNTS))
    
    if llm is None:
        llm = DEFAULT_LLM
    
    # Find users from hashtags
    for hashtag in HASHTAGS:
        if len(all_users) >= max_users:
            break
        users = await find_users_from_hashtag(browser, hashtag, users_per_source, llm)
        all_users.update(users)
        await wait_between_actions()
    
    # Find users from competitor accounts
    for competitor in COMPETITOR_ACCOUNTS:
        if len(all_users) >= max_users:
            break
        users = await find_users_from_competitor(
            browser,
            competitor.strip('@'),
            users_per_source,
            llm
        )
        all_users.update(users)
        await wait_between_actions()
    
    return list(all_users)[:max_users] 