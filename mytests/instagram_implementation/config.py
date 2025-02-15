"""
Configuration settings for Instagram automation.
Contains environment variables, daily limits, and other constants.
"""

import os
from dotenv import load_dotenv
from typing import List
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import SecretStr

# Load environment variables
load_dotenv()

# LLM Configuration
api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError('GEMINI_API_KEY is not set')

DEFAULT_LLM = ChatGoogleGenerativeAI(model='gemini-2.0-flash', api_key=SecretStr(api_key))

# Instagram credentials
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME", "")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD", "")

# Daily action limits
MAX_FOLLOWS_PER_DAY = 200
MAX_LIKES_PER_DAY = 200
MAX_COMMENTS_PER_DAY = 200

# Batch configuration
BATCHES_PER_DAY = 5
ACTIONS_PER_BATCH = {
    "follows": MAX_FOLLOWS_PER_DAY // BATCHES_PER_DAY,
    "likes": MAX_LIKES_PER_DAY // BATCHES_PER_DAY,
    "comments": MAX_COMMENTS_PER_DAY // BATCHES_PER_DAY
}

# Time intervals (in seconds)
MIN_ACTION_DELAY = 3
MAX_ACTION_DELAY = 7
MIN_BATCH_DELAY = 30 * 60  # 30 minutes
MAX_BATCH_DELAY = 90 * 60  # 90 minutes

# Target hashtags for content discovery
HASHTAGS: List[str] = [
    "veganfitness",
    "biohacking",
    "plantbaseddiet",
    "wellnessjourney",
    "holistichealth"
]

# Competitor/influencer accounts to analyze
COMPETITOR_ACCOUNTS: List[str] = [
    # Add your target competitor accounts here
    # Example: "@veganinfluencer", "@biohackingexpert"
]

# Comment templates for variety (can be expanded with LLM)
COMMENT_TEMPLATES: List[str] = [
    "Great content! 🙌",
    "This is inspiring! 💪",
    "Amazing perspective! 🌟",
    "Love this! 🔥",
    "Thanks for sharing! 👏"
]

# Browser configuration
BROWSER_CONFIG = {
    "headless": False,  # Set to True for production
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Logging configuration
LOG_DIR = "logs"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s" 