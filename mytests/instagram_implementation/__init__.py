"""
Instagram automation package using Browser-Use and LangChain.
Provides tools for automated Instagram engagement with safety features.
"""

from .config import (
    INSTAGRAM_USERNAME,
    INSTAGRAM_PASSWORD,
    MAX_FOLLOWS_PER_DAY,
    MAX_LIKES_PER_DAY,
    MAX_COMMENTS_PER_DAY,
    ACTIONS_PER_BATCH,
    HASHTAGS,
    COMPETITOR_ACCOUNTS,
    COMMENT_TEMPLATES
)

from .daily_tasks import (
    DailyStats,
    run_daily_tasks,
    resume_daily_tasks
)

from .strategy.find_audience import (
    find_target_audience,
    find_users_from_hashtag,
    find_users_from_competitor
)

from .strategy.follow_users import (
    follow_user,
    follow_users_batch,
    follow_users_daily
)

from .strategy.like_posts import (
    like_user_posts,
    like_hashtag_posts,
    like_posts_batch,
    like_posts_daily
)

from .strategy.comment_posts import (
    generate_comment,
    comment_on_post,
    find_posts_to_comment,
    comment_posts_batch,
    comment_posts_daily
)

from .strategy.timing import (
    wait_random_interval,
    wait_between_actions,
    wait_between_batches,
    calculate_batch_schedule
)

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

__all__ = [
    # Configuration
    "INSTAGRAM_USERNAME",
    "INSTAGRAM_PASSWORD",
    "MAX_FOLLOWS_PER_DAY",
    "MAX_LIKES_PER_DAY",
    "MAX_COMMENTS_PER_DAY",
    "ACTIONS_PER_BATCH",
    "HASHTAGS",
    "COMPETITOR_ACCOUNTS",
    "COMMENT_TEMPLATES",
    
    # Daily Tasks
    "DailyStats",
    "run_daily_tasks",
    "resume_daily_tasks",
    
    # Find Audience
    "find_target_audience",
    "find_users_from_hashtag",
    "find_users_from_competitor",
    
    # Follow Users
    "follow_user",
    "follow_users_batch",
    "follow_users_daily",
    
    # Like Posts
    "like_user_posts",
    "like_hashtag_posts",
    "like_posts_batch",
    "like_posts_daily",
    
    # Comment Posts
    "generate_comment",
    "comment_on_post",
    "find_posts_to_comment",
    "comment_posts_batch",
    "comment_posts_daily",
    
    # Timing
    "wait_random_interval",
    "wait_between_actions",
    "wait_between_batches",
    "calculate_batch_schedule"
] 