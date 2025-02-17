import os
import json
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.controller.service import Controller

load_dotenv()

# Configuration
COOKIES_FILE = "insta_cookie.json"
PROGRESS_FILE = "fitness_posts_progress.json"
FITNESS_HASHTAGS = [
    "fitness",
    "workout",
    "gym",
    "fitnessmotivation",
    "training"
]

class FitnessPost(BaseModel):
    """Structure for storing fitness post information"""
    url: str
    hashtags: List[str]
    collected_at: str
    hashtag_source: str  # The hashtag page where this post was found

class FitnessProgress(BaseModel):
    """Structure for tracking progress and storing collected posts"""
    visited_hashtags: List[str] = []
    collected_posts: List[Dict] = []
    last_hashtag: Optional[str] = None
    last_scroll_position: int = 0
    last_updated: str = ""

def load_progress() -> FitnessProgress:
    """Load progress from JSON file or create new if doesn't exist"""
    try:
        if os.path.exists(PROGRESS_FILE):
            with open(PROGRESS_FILE, 'r') as f:
                data = json.load(f)
                return FitnessProgress(**data)
    except Exception as e:
        print(f"Error loading progress file: {e}")
    return FitnessProgress()

def save_progress(progress: FitnessProgress):
    """Save progress to JSON file"""
    progress.last_updated = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress.dict(), f, indent=2)

async def explore_fitness_hashtag(browser_context: BrowserContext, hashtag: str, llm: ChatOpenAI) -> List[FitnessPost]:
    """
    Explore a fitness hashtag page and collect post URLs.
    Returns a list of FitnessPost objects.
    """
    task = (
        f"Visit Instagram explore page for #{hashtag} and collect post information:\n"
        "1. Go to https://www.instagram.com/explore/tags/{hashtag}/\n"
        "2. Wait for the page to load completely\n"
        "3. For each visible post:\n"
        "   a. Extract the post URL\n"
        "   b. Look for related hashtags in the post preview\n"
        "4. Scroll down to load more posts (3 times)\n"
        "5. For each batch of posts found:\n"
        "   Return the data in this exact format:\n"
        "   POST_URL:::[hashtag1,hashtag2,...]:::\n"
        "6. Continue until you've collected at least 10 unique posts\n"
        "7. If no more posts are visible or loaded, return 'DONE'"
    )
    
    posts: List[FitnessPost] = []
    agent = Agent(
        task=task,
        llm=llm,
        browser_context=browser_context,
        generate_gif=False
    )
    
    history = await agent.run(max_steps=20)
    
    for action in history.action_results():
        if action.extracted_content:
            content = action.extracted_content.strip()
            if content == "DONE":
                break
                
            # Process each line that matches our expected format
            for line in content.split('\n'):
                if ':::' in line:
                    url, hashtags_str = line.split(':::')[:2]
                    try:
                        hashtags = json.loads(hashtags_str)
                        post = FitnessPost(
                            url=url.strip(),
                            hashtags=hashtags,
                            collected_at=datetime.now().isoformat(),
                            hashtag_source=hashtag
                        )
                        posts.append(post)
                    except json.JSONDecodeError:
                        continue
    
    return posts

async def main():
    # Initialize the language model
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)
    
    # Load progress
    progress = load_progress()
    
    # Initialize browser with proper configuration
    browser_config = BrowserConfig(
        headless=False,
        disable_security=True
    )
    browser = Browser(config=browser_config)
    
    try:
        # Create a browser context with cookie handling
        context_config = BrowserContextConfig(
            cookies_file=COOKIES_FILE
        )
        context = await browser.new_context(config=context_config)
        
        # Process each hashtag that hasn't been visited
        for hashtag in FITNESS_HASHTAGS:
            if hashtag in progress.visited_hashtags:
                continue
                
            print(f"Exploring #{hashtag}...")
            posts = await explore_fitness_hashtag(context, hashtag, llm)
            
            # Update progress
            progress.visited_hashtags.append(hashtag)
            progress.last_hashtag = hashtag
            progress.collected_posts.extend([post.dict() for post in posts])
            save_progress(progress)
            
            print(f"Collected {len(posts)} posts from #{hashtag}")
            
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Ensure proper cleanup
        if 'context' in locals():
            await context.close()
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main()) 