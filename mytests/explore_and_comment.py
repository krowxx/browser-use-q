import os
import json
import asyncio
from datetime import datetime
from typing import Set

from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.controller.service import Controller
from mytests.like_with_mouse import instagram_like_with_mouse, InstagramLikeAction

# Import exploration utilities from fitness_explore.py
from mytests.fitness_explore import FITNESS_HASHTAGS, load_progress, save_progress, FitnessPost, explore_fitness_hashtag

# Constants for file paths
COOKIES_FILE = "insta_cookie.json"
PROGRESS_FILE = "fitness_posts_progress.json"  # used by fitness_explore.py
INTERACTED_FILE = "interacted_posts.json"  # new file to track post URLs that have been interacted with

def load_interacted_posts() -> Set[str]:
    """Load the set of post URLs that have already been interacted with."""
    if os.path.exists(INTERACTED_FILE):
        try:
            with open(INTERACTED_FILE, "r") as f:
                data = json.load(f)
                return set(data)
        except Exception as e:
            print(f"Error loading interacted posts: {e}")
    return set()

def save_interacted_posts(interacted: Set[str]) -> None:
    """Save the set of post URLs that have been interacted with."""
    with open(INTERACTED_FILE, "w") as f:
        json.dump(list(interacted), f, indent=2)

# Initialize controller with custom Instagram actions
controller = Controller(exclude_actions=['click_element'])  # Prevent normal clicking

@controller.action(
    'Like Instagram post using mouse interaction',
    param_model=InstagramLikeAction
)
async def like_instagram_post(params: InstagramLikeAction, browser: BrowserContext):
    return await instagram_like_with_mouse(browser)

async def verify_login(context: BrowserContext, llm: ChatOpenAI) -> bool:
    """Verify if the current session is logged in to Instagram."""
    verify_task = (
        "1. Navigate to instagram.com\n"
        "2. Look for these specific elements to confirm login:\n"
        "   - The Instagram logo in the sidebar\n"
        "   - Your profile picture in the navigation\n"
        "   - The 'Create' button\n"
        "3. If ALL elements are found, return 'logged in'\n"
        "4. If ANY elements are missing, return 'not logged in'"
    )
    verify_agent = Agent(
        task=verify_task,
        llm=llm,
        browser_context=context,
        generate_gif=False
    )
    history = await verify_agent.run(max_steps=5)
    
    for action in history.action_results():
        if action.extracted_content and "logged in" in action.extracted_content.lower():
            return True
    return False

async def like_and_comment(post_url: str, llm: ChatOpenAI) -> bool:
    """
    Create an agent to interact with an Instagram post by liking it and posting a comment.
    The task is parameterized by the given post_url.
    """
    task = (
        "1. First, navigate to instagram.com to ensure we're properly logged in.\n"
        f"2. Then, go to the Instagram post URL {post_url}.\n"
        "IMPORTANT: To like the post, you MUST use the 'Like Instagram post using mouse interaction' action - "
        "do NOT try to click the like button directly as it won't work.\n"
        "3. After liking, post a relevant comment that reflects the content of the post."
    )
    # Create a new browser instance and context using the Instagram cookies.
    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
            _force_keep_browser_alive=True,
        )
    )
    context_config = BrowserContextConfig(
        cookies_file=COOKIES_FILE,
        _force_keep_context_alive=True
    )
    context: BrowserContext = await browser.new_context(config=context_config)
    try:
        # Verify login status first
        is_logged_in = await verify_login(context, llm)
        if not is_logged_in:
            print("Error: Not logged in to Instagram. Please ensure valid cookies in the cookie file.")
            return False

        agent = Agent(
            task=task,
            llm=llm,
            browser_context=context,
            controller=controller  # Use our custom controller with Instagram actions
        )
        await agent.run(max_steps=10)
        print(f"Interaction completed for {post_url}")
        return True
    except Exception as e:
        print(f"Error interacting with {post_url}: {str(e)}")
        return False
    finally:
        await context.close()
        await browser.close()

async def main():
    # Initialize the language model (using GPT-4o as in comment.py)
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

    # Load existing fitness progress (collected posts) from fitness_explore.py progress file
    progress = load_progress()
    # Create a shared browser context for exploring fitness hashtags.
    exploration_browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
        )
    )
    exploration_context_config = BrowserContextConfig(
        cookies_file=COOKIES_FILE
    )
    exploration_context: BrowserContext = await exploration_browser.new_context(config=exploration_context_config)

    # For each hashtag that has not yet been visited, explore and update progress.
    for hashtag in FITNESS_HASHTAGS:
        if hashtag not in progress.visited_hashtags:
            print(f"Exploring #{hashtag}...")
            posts = await explore_fitness_hashtag(exploration_context, hashtag, llm)
            progress.visited_hashtags.append(hashtag)
            for post in posts:
                progress.collected_posts.append(post.dict())
            save_progress(progress)
            print(f"Collected {len(posts)} posts from #{hashtag}")

    await exploration_context.close()
    await exploration_browser.close()

    # Load the set of post URLs already interacted with.
    interacted = load_interacted_posts()

    # Iterate over all collected posts and interact with new ones.
    for post in progress.collected_posts:
        url = post.get("url")
        if url and url not in interacted:
            print(f"Interacting with post: {url}")
            success = await like_and_comment(url, llm)
            if success:
                interacted.add(url)
                save_interacted_posts(interacted)
            else:
                print(f"Failed interaction with {url}")

if __name__ == "__main__":
    asyncio.run(main())