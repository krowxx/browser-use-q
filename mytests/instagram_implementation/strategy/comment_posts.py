"""
Functions for commenting on Instagram posts.
Handles commenting in batches with appropriate delays and content generation.
"""

import logging
import random
from typing import List, Optional, Dict, Any, Tuple
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from browser_use.agent.service import Agent
from langchain_google_genai import ChatGoogleGenerativeAI
from ..config import (
    MAX_COMMENTS_PER_DAY,
    ACTIONS_PER_BATCH,
    HASHTAGS,
    COMMENT_TEMPLATES,
    DEFAULT_LLM
)
from .timing import wait_between_actions, wait_between_batches

logger = logging.getLogger(__name__)

async def generate_comment(
    post_content: str,
    llm: ChatGoogleGenerativeAI
) -> str:
    """
    Generate a relevant comment for a post using LLM.
    
    Args:
        post_content: Content/description of the post to comment on
        llm: Language model for generating comments
    
    Returns:
        str: Generated comment
    """
    task = (
        "Generate a short, engaging Instagram comment based on this post content. "
        "The comment should be natural, positive, and include 1-2 relevant emojis. "
        "Keep it under 150 characters. Post content: " + post_content
    )
    
    agent = Agent(
        task=task,
        llm=llm,
        browser=None  # No browser needed for comment generation
    )
    
    try:
        history = await agent.run()
        for action in history.action_results():
            if action.extracted_content:
                return action.extracted_content.strip()
    except Exception as e:
        logger.error(f"Error generating comment: {str(e)}")
    
    # Fallback to template if generation fails
    return random.choice(COMMENT_TEMPLATES)

async def comment_on_post(
    browser_context: BrowserContext,
    post_url: str,
    llm: Optional[ChatGoogleGenerativeAI] = None,
    comment: Optional[str] = None
) -> bool:
    """
    Comment on a specific Instagram post.
    
    Args:
        browser_context: BrowserContext instance
        post_url: URL of the post to comment on
        llm: Language model for instructions and comment generation
        comment: Optional pre-generated comment to use
    
    Returns:
        bool: True if comment was successful, False otherwise
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    try:
        # First, analyze the post content
        analysis_agent = Agent(
            task=f"Navigate to {post_url} and extract the post's content/caption for analysis",
            llm=llm,
            browser_context=browser_context
        )
        
        analysis_history = await analysis_agent.run()
        post_content = ""
        for action in analysis_history.action_results():
            if action.extracted_content:
                post_content = action.extracted_content
                break
        
        # Generate or use provided comment
        comment_text = comment if comment else await generate_comment(post_content, llm)
        
        # Create agent for commenting
        comment_agent = Agent(
            task=(
                f"On the current Instagram post:"
                f" 1. Click the comment input area"
                f" 2. Type this comment: {comment_text}"
                f" 3. Submit the comment"
                f" 4. Verify the comment was posted successfully"
                f" 5. Return 'commented' if successful"
            ),
            llm=llm,
            browser_context=browser_context
        )
        
        # Run the comment agent
        comment_history = await comment_agent.run()
        
        # Check if comment was successful
        for action in comment_history.action_results():
            if action.extracted_content and "commented" in action.extracted_content.lower():
                return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error commenting on post {post_url}: {str(e)}")
        return False

async def find_posts_to_comment(
    browser_context: BrowserContext,
    hashtag: str,
    max_posts: int = 5,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> List[str]:
    """
    Find suitable posts to comment on from a hashtag.
    
    Args:
        browser_context: BrowserContext instance
        hashtag: Hashtag to find posts from (without #)
        max_posts: Maximum number of posts to find
        llm: Language model for instructions
    
    Returns:
        List of post URLs
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    try:
        # Create agent to find posts
        agent = Agent(
            task=(
                f"Navigate to instagram.com/explore/tags/{hashtag} and:"
                f" 1. Scroll through recent posts"
                f" 2. Collect URLs of {max_posts} posts that:"
                "    - Have comments enabled"
                "    - Are from real users (not businesses)"
                "    - Have good engagement"
                f" 3. Return the list of post URLs"
            ),
            llm=llm,
            browser_context=browser_context
        )
        
        # Run the agent
        history = await agent.run()
        
        # Extract post URLs
        for action in history.action_results():
            if action.extracted_content:
                # Split content into lines and filter for Instagram post URLs
                urls = [
                    line.strip()
                    for line in action.extracted_content.split()
                    if "instagram.com/p/" in line
                ]
                return urls[:max_posts]
        
        return []
        
    except Exception as e:
        logger.error(f"Error finding posts for hashtag {hashtag}: {str(e)}")
        return []

async def comment_posts_batch(
    browser_context: BrowserContext,
    hashtags: List[str],
    batch_size: int,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> Dict[str, List[Tuple[str, bool]]]:
    """
    Comment on a batch of posts from different hashtags.
    
    Args:
        browser_context: BrowserContext instance
        hashtags: List of hashtags to find posts from
        batch_size: Number of comments to attempt in this batch
        llm: Language model for instructions and comment generation
    
    Returns:
        Dict mapping hashtags to list of (post_url, success) tuples
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    results = {}
    comments_remaining = batch_size
    posts_per_hashtag = max(1, batch_size // len(hashtags))
    
    for hashtag in hashtags:
        if comments_remaining <= 0:
            break
            
        # Find posts for this hashtag
        posts = await find_posts_to_comment(
            browser_context,
            hashtag,
            min(posts_per_hashtag, comments_remaining),
            llm
        )
        
        results[hashtag] = []
        
        # Comment on each post
        for post_url in posts:
            if comments_remaining <= 0:
                break
                
            success = await comment_on_post(browser_context, post_url, llm)
            results[hashtag].append((post_url, success))
            if success:
                comments_remaining -= 1
            
            await wait_between_actions()
    
    return results

async def comment_posts_daily(
    browser_context: BrowserContext,
    llm: Optional[ChatGoogleGenerativeAI] = None,
    custom_hashtags: Optional[List[str]] = None
) -> Dict[str, List[Tuple[str, bool]]]:
    """
    Comment on posts throughout the day in batches, respecting daily limits.
    
    Args:
        browser_context: BrowserContext instance
        llm: Language model for instructions and comment generation
        custom_hashtags: Optional list of hashtags to use instead of config hashtags
    
    Returns:
        Dict mapping hashtags to list of (post_url, success) tuples
    """
    if llm is None:
        llm = DEFAULT_LLM
    
    all_results = {}
    total_comments = 0
    comments_per_batch = ACTIONS_PER_BATCH["comments"]
    hashtags_to_use = custom_hashtags if custom_hashtags is not None else HASHTAGS
    
    while total_comments < MAX_COMMENTS_PER_DAY:
        # Calculate batch size
        batch_size = min(comments_per_batch, MAX_COMMENTS_PER_DAY - total_comments)
        
        # Comment on batch of posts
        batch_results = await comment_posts_batch(
            browser_context,
            hashtags_to_use,
            batch_size,
            llm
        )
        
        # Update tracking
        for hashtag, posts in batch_results.items():
            if hashtag not in all_results:
                all_results[hashtag] = []
            all_results[hashtag].extend(posts)
            total_comments += sum(1 for _, success in posts if success)
        
        # If we haven't reached the daily limit, wait between batches
        if total_comments < MAX_COMMENTS_PER_DAY:
            await wait_between_batches()
    
    return all_results 