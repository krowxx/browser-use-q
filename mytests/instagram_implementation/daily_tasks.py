"""
Main orchestration module for Instagram automation tasks.
Coordinates the daily routine of finding users, following, liking, and commenting.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from langchain_google_genai import ChatGoogleGenerativeAI
from .strategy.find_audience import find_target_audience
from .strategy.follow_users import follow_users_daily
from .strategy.like_posts import like_posts_daily
from .strategy.comment_posts import comment_posts_daily
from .strategy.timing import wait_between_batches

logger = logging.getLogger(__name__)

class DailyStats:
    """Class to track and store daily automation statistics."""
    
    def __init__(self, log_dir: str = "logs"):
        self.date = datetime.now().strftime("%Y-%m-%d")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        self.stats = {
            "date": self.date,
            "target_audience": [],
            "follows": {},
            "likes": {},
            "comments": {},
            "errors": []
        }
    
    def update_target_audience(self, users: List[str]) -> None:
        """Update the list of target users found."""
        self.stats["target_audience"] = users
    
    def update_follows(self, results: Dict[str, bool]) -> None:
        """Update follow action results."""
        self.stats["follows"] = {
            "total_attempts": len(results),
            "successful": sum(1 for success in results.values() if success),
            "results": results
        }
    
    def update_likes(self, results: Dict[str, int]) -> None:
        """Update like action results."""
        self.stats["likes"] = {
            "total_likes": sum(results.values()),
            "by_source": results
        }
    
    def update_comments(self, results: Dict[str, List[Tuple[str, bool]]]) -> None:
        """Update comment action results."""
        total_attempts = sum(len(posts) for posts in results.values())
        total_success = sum(
            sum(1 for _, success in posts if success)
            for posts in results.values()
        )
        
        self.stats["comments"] = {
            "total_attempts": total_attempts,
            "successful": total_success,
            "by_hashtag": {
                hashtag: {
                    "attempts": len(posts),
                    "successful": sum(1 for _, success in posts if success),
                    "posts": [url for url, _ in posts]
                }
                for hashtag, posts in results.items()
            }
        }
    
    def log_error(self, error: str) -> None:
        """Log an error that occurred during automation."""
        self.stats["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "error": str(error)
        })
    
    def save(self) -> None:
        """Save the daily stats to a JSON file."""
        filename = self.log_dir / f"instagram_stats_{self.date}.json"
        with open(filename, "w") as f:
            json.dump(self.stats, f, indent=2)
        logger.info(f"Saved daily stats to {filename}")

async def run_daily_tasks(
    browser_context: BrowserContext,
    llm: Optional[ChatGoogleGenerativeAI] = None,
    stats: Optional[DailyStats] = None
) -> DailyStats:
    """
    Run the complete daily Instagram automation routine.
    
    Args:
        browser_context: BrowserContext instance
        llm: Language model for instructions and content generation
        stats: Optional DailyStats instance for tracking
    
    Returns:
        DailyStats object with the day's results
    """
    if llm is None:
        llm = ChatGoogleGenerativeAI(model="gpt-4")
    
    if stats is None:
        stats = DailyStats()
    
    try:
        # 1. Find target audience
        logger.info("Finding target audience...")
        target_users = await find_target_audience(browser_context, llm=llm)
        stats.update_target_audience(target_users)
        
        # Wait between major tasks
        await wait_between_batches()
        
        # 2. Follow users
        logger.info("Following users...")
        follow_results = await follow_users_daily(
            browser_context,
            target_users,
            llm=llm,
            engage_first=True  # Like a post before following
        )
        stats.update_follows(follow_results)
        
        await wait_between_batches()
        
        # 3. Like posts
        logger.info("Liking posts...")
        like_results = await like_posts_daily(
            browser_context,
            target_users,  # Like posts from target users
            llm=llm
        )
        stats.update_likes(like_results)
        
        await wait_between_batches()
        
        # 4. Comment on posts
        logger.info("Commenting on posts...")
        comment_results = await comment_posts_daily(
            browser_context,
            llm=llm
        )
        stats.update_comments(comment_results)
        
    except Exception as e:
        error_msg = f"Error during daily tasks: {str(e)}"
        logger.error(error_msg)
        stats.log_error(error_msg)
        raise
    
    finally:
        # Save stats but don't close browser_context - it's managed by main.py
        stats.save()
    
    return stats

async def resume_daily_tasks(
    browser_context: BrowserContext,
    stats_file: str,
    llm: Optional[ChatGoogleGenerativeAI] = None
) -> DailyStats:
    """
    Resume daily tasks from a previous run using saved stats.
    
    Args:
        browser_context: BrowserContext instance
        stats_file: Path to the stats JSON file from previous run
        llm: Language model for instructions and content generation
    
    Returns:
        Updated DailyStats object
    """
    # Load previous stats
    with open(stats_file) as f:
        previous_stats = json.load(f)
    
    stats = DailyStats()
    stats.stats = previous_stats
    
    # Calculate remaining actions
    remaining_follows = max(0, 200 - stats.stats["follows"].get("successful", 0))
    remaining_likes = max(0, 200 - stats.stats["likes"].get("total_likes", 0))
    remaining_comments = max(0, 200 - stats.stats["comments"].get("successful", 0))
    
    if remaining_follows + remaining_likes + remaining_comments == 0:
        logger.info("All daily limits reached, nothing to resume")
        return stats
    
    try:
        # Resume following if needed
        if remaining_follows > 0:
            logger.info(f"Resuming follows ({remaining_follows} remaining)...")
            # Get users we haven't tried yet
            previous_attempts = set(stats.stats["follows"].get("results", {}).keys())
            remaining_users = [
                user for user in stats.stats["target_audience"]
                if user not in previous_attempts
            ]
            
            if remaining_users:
                follow_results = await follow_users_daily(
                    browser_context,
                    remaining_users,
                    llm=llm,
                    engage_first=True
                )
                # Merge new results with previous
                all_follows = {**stats.stats["follows"].get("results", {}), **follow_results}
                stats.update_follows(all_follows)
        
        # Resume liking if needed
        if remaining_likes > 0:
            logger.info(f"Resuming likes ({remaining_likes} remaining)...")
            like_results = await like_posts_daily(
                browser_context,
                stats.stats["target_audience"],
                llm=llm
            )
            # Merge new results with previous
            all_likes = {
                source: count + stats.stats["likes"].get("by_source", {}).get(source, 0)
                for source, count in like_results.items()
            }
            stats.update_likes(all_likes)
        
        # Resume commenting if needed
        if remaining_comments > 0:
            logger.info(f"Resuming comments ({remaining_comments} remaining)...")
            comment_results = await comment_posts_daily(
                browser_context,
                llm=llm
            )
            # Merge new results with previous
            all_comments = stats.stats["comments"].get("by_hashtag", {}).copy()
            for hashtag, new_posts in comment_results.items():
                if hashtag not in all_comments:
                    all_comments[hashtag] = []
                all_comments[hashtag].extend(new_posts)
            stats.update_comments(all_comments)
        
    except Exception as e:
        error_msg = f"Error resuming daily tasks: {str(e)}"
        logger.error(error_msg)
        stats.log_error(error_msg)
        raise
    
    finally:
        # Save stats but don't close browser_context - it's managed by main.py
        stats.save()
    
    return stats 