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

class FitnessPostOutput(BaseModel):
    """Structure for the agent's output format"""
    url: str
    hashtags: List[str]

class FitnessOutput(BaseModel):
    """Structure for the complete output from the agent"""
    posts: List[FitnessPostOutput]

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
    Explore a fitness hashtag page and collect post URLs using structured output.
    Returns a list of FitnessPost objects with additional metadata.
    """
    # Create a controller with the structured output model
    controller = Controller(output_model=FitnessOutput)
    
    task = (
        f"Visit Instagram explore page for #{hashtag} and collect at least 10 unique posts. "
        "For each post, extract the post URL and a list of hashtags mentioned in the post preview. "
        "Return a JSON object with a key 'posts' containing a list of objects. "
        "Each object must have keys 'url' (a string) and 'hashtags' (a list of strings). "
        "Do not include any additional text."
    )
    
    agent = Agent(
        task=task,
        llm=llm,
        controller=controller,
        browser_context=browser_context,
        generate_gif=False
    )
    
    history = await agent.run(max_steps=20)
    final_output = history.final_result()
    if not final_output:
        return []
    
    try:
        fitness_output = FitnessOutput.model_validate_json(final_output)
    except Exception as e:
        print(f"Error parsing structured output: {e}")
        return []
    
    posts = []
    for post_output in fitness_output.posts:
        post = FitnessPost(
            url=post_output.url,
            hashtags=post_output.hashtags,
            collected_at=datetime.now().isoformat(),
            hashtag_source=hashtag
        )
        posts.append(post)
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