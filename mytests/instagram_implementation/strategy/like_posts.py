"""
Functions for liking posts on Instagram.
Handles liking posts in batches with appropriate delays.
"""

import logging
from typing import List, Optional, Dict, Any
from browser_use.browser.browser import Browser
from browser_use.agent.service import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from ..config import MAX_LIKES_PER_DAY, ACTIONS_PER_BATCH, HASHTAGS, DEFAULT_LLM
from .timing import wait_between_actions, wait_between_batches

logger = logging.getLogger(__name__)

async def like_user_posts(
    browser: Browser,
    username: str,
    max_likes: int = 3,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> int:
    """
    Like a specified number of posts from a user's profile.
    
    Args:
        browser: Browser instance
        username: Username whose posts to like
        max_likes: Maximum number of posts to like
        llm: Language model for agent instructions
    
    Returns:
        int: Number of posts successfully liked
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    try:
        # Create agent for liking user's posts
        task = (
            f"Navigate to instagram.com/{username} and:"
            f" 1. Scroll through their recent posts"
            f" 2. Like up to {max_likes} posts that aren't already liked"
            " 3. Return the number of posts you successfully liked"
        )
        
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser
        )
        
        # Run the agent
        history = await agent.run()
        
        # Count successful likes
        for action in history.action_results():
            if action.extracted_content:
                try:
                    return int(action.extracted_content)
                except ValueError:
                    # If we can't parse the number, assume no likes
                    pass
        
        return 0
        
    except Exception as e:
        logger.error(f"Error liking posts for user {username}: {str(e)}")
        return 0

async def like_hashtag_posts(
    browser: Browser,
    hashtag: str,
    max_likes: int = 10,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> int:
    """
    Like posts from a specific hashtag.
    
    Args:
        browser: Browser instance
        hashtag: Hashtag to find posts from (without #)
        max_likes: Maximum number of posts to like
        llm: Language model for agent instructions
    
    Returns:
        int: Number of posts successfully liked
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    try:
        # Create agent for liking hashtag posts
        task = (
            f"Navigate to instagram.com/explore/tags/{hashtag} and:"
            f" 1. Scroll through recent posts"
            f" 2. Like up to {max_likes} posts that aren't already liked"
            " 3. Return the number of posts you successfully liked"
        )
        
        agent = Agent(
            task=task,
            llm=llm,
            browser=browser
        )
        
        # Run the agent
        history = await agent.run()
        
        # Count successful likes
        for action in history.action_results():
            if action.extracted_content:
                try:
                    return int(action.extracted_content)
                except ValueError:
                    # If we can't parse the number, assume no likes
                    pass
        
        return 0
        
    except Exception as e:
        logger.error(f"Error liking posts for hashtag {hashtag}: {str(e)}")
        return 0

async def like_posts_batch(
    browser: Browser,
    usernames: List[str],
    hashtags: List[str],
    batch_size: int,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> Dict[str, int]:
    """
    Like posts from a batch of users and hashtags.
    
    Args:
        browser: Browser instance
        usernames: List of usernames to like posts from
        hashtags: List of hashtags to like posts from
        batch_size: Total number of likes to attempt in this batch
        llm: Language model for agent instructions
    
    Returns:
        Dict mapping sources (usernames/hashtags) to number of likes
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    results = {}
    likes_remaining = batch_size
    
    # Distribute likes between users and hashtags
    likes_per_user = min(3, batch_size // (len(usernames) + len(hashtags)) if usernames else 0)
    likes_per_hashtag = min(5, batch_size // (len(usernames) + len(hashtags)) if hashtags else 0)
    
    # Like posts from users
    for username in usernames:
        if likes_remaining <= 0:
            break
            
        likes = await like_user_posts(
            browser,
            username,
            min(likes_per_user, likes_remaining),
            llm
        )
        results[username] = likes
        likes_remaining -= likes
        
        await wait_between_actions()
    
    # Like posts from hashtags
    for hashtag in hashtags:
        if likes_remaining <= 0:
            break
            
        likes = await like_hashtag_posts(
            browser,
            hashtag,
            min(likes_per_hashtag, likes_remaining),
            llm
        )
        results[f"#{hashtag}"] = likes
        likes_remaining -= likes
        
        await wait_between_actions()
    
    return results

async def like_posts_daily(
    browser: Browser,
    usernames: List[str],
    llm: Optional[ChatGoogleGenerativeAI] = None,
    custom_hashtags: Optional[List[str]] = None
) -> Dict[str, int]:
    """
    Like posts throughout the day in batches, respecting daily limits.
    
    Args:
        browser: Browser instance
        usernames: List of usernames to like posts from
        llm: Language model for agent instructions
        custom_hashtags: Optional list of hashtags to use instead of config hashtags
    
    Returns:
        Dict mapping sources to number of likes
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    all_results = {}
    total_likes = 0
    likes_per_batch = ACTIONS_PER_BATCH["likes"]
    hashtags_to_use = custom_hashtags if custom_hashtags is not None else HASHTAGS
    
    while total_likes < MAX_LIKES_PER_DAY:
        # Calculate batch size
        batch_size = min(likes_per_batch, MAX_LIKES_PER_DAY - total_likes)
        
        # Like batch of posts
        batch_results = await like_posts_batch(
            browser,
            usernames,
            hashtags_to_use,
            batch_size,
            llm
        )
        
        # Update tracking
        for source, likes in batch_results.items():
            all_results[source] = all_results.get(source, 0) + likes
            total_likes += likes
        
        # If we haven't reached the daily limit, wait between batches
        if total_likes < MAX_LIKES_PER_DAY:
            await wait_between_batches()
    
    return all_results 