import os
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI

from browser_use import Agent, Controller
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.agent.views import ActionResult

load_dotenv()

# =============== Configuration Section ===============
COOKIES_FILE = "insta_cookie.json"
INTERACTIONS_FILE = "instagram_interactions.json"

# If you want to explore multiple hashtags, put them here
HASHTAGS_TO_EXPLORE = ["fitness"]

# Instagram credentials from environment variables
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


# =============== Data Models ===============

class InstagramLikeAction(BaseModel):
    """Parameters for Instagram like action"""
    index: Optional[int] = None


# This is the custom function to actually move the mouse over the Like button
# and click it (originally from like_with_mouse.py).
async def instagram_like_with_mouse(page) -> bool:
    """Find the like button's approximate coordinates using an SVG check, then move/click mouse."""
    async def find_like_button_coordinates():
        """Locate like button bounding box via possible aria-label match."""
        try:
            # Find all like buttons
            like_buttons = await page.query_selector_all("svg[aria-label*='Like']")
            if not like_buttons:
                like_buttons = await page.query_selector_all("svg[aria-label*='Like'][width='24']")
            
            # Get the last button that matches
            if like_buttons and len(like_buttons) > 0:
                like_button = like_buttons[-1]  # Get the last button
                box = await like_button.bounding_box()
                if box:
                    return {
                        'x': box['x'] + box['width'] / 2,
                        'y': box['y'] + box['height'] / 2
                    }
        except:
            pass
        return None

    coords = await find_like_button_coordinates()
    if not coords:
        return False

    try:
        # Simulate human-like mouse move
        await page.mouse.move(coords['x'], coords['y'], steps=20)
        await asyncio.sleep(0.3)
        # Click the like button
        await page.mouse.click(coords['x'], coords['y'])
        await asyncio.sleep(0.5)
        # Check if we see the "Unlike" state
        try:
            await page.wait_for_selector("svg[aria-label*='Unlike']", timeout=2000)
            return True
        except:
            # Possibly the button changed quickly; let's see if "Like" is gone
            like_btn = await page.query_selector("svg[aria-label*='Like']")
            return not bool(like_btn)
    except:
        return False


# =============== Instagram Controller & Actions ===============

controller = Controller()  # override normal clicking

@controller.action(
    'Like Instagram post using mouse interaction',
    param_model=InstagramLikeAction
)
async def like_instagram_post(params: InstagramLikeAction, browser: BrowserContext):
    """Controller action to like an Instagram post with a custom mouse-based approach."""
    page = await browser.get_current_page()
    success = await instagram_like_with_mouse(page)
    if success:
        return ActionResult(
            extracted_content="Successfully liked via mouse interaction",
            include_in_memory=True
        )
    else:
        return ActionResult(error="Failed to like post via mouse approach")

# =============== Utility Functions ===============

def load_interactions() -> dict:
    """Load local record of posts we've already interacted with."""
    if os.path.exists(INTERACTIONS_FILE):
        try:
            with open(INTERACTIONS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading {INTERACTIONS_FILE}: {e}")
    return {"interacted_posts": []}

def save_interactions(data: dict):
    """Save the dictionary of interactions to a file."""
    with open(INTERACTIONS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def already_interacted(url: str, interactions: dict) -> bool:
    """Check if we've already interacted with a given post URL."""
    return url in interactions.get("interacted_posts", [])

def mark_interacted(url: str, interactions: dict):
    """Mark this post URL as interacted and save."""
    if "interacted_posts" not in interactions:
        interactions["interacted_posts"] = []
    interactions["interacted_posts"].append(url)
    save_interactions(interactions)


async def login_to_instagram(browser_context: BrowserContext) -> bool:
    """Automate the Instagram login process using the credentials from env vars."""
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        logger.error("Instagram credentials are not set in environment variables.")
        return False

    login_instructions = (
        "1. Go to instagram.com/login\n"
        "2. Wait for the login form\n"
        f"3. Enter username: {INSTAGRAM_USERNAME}\n"
        f"4. Enter password: {INSTAGRAM_PASSWORD}\n"
        "5. Click login\n"
        "6. If a 'Save Login Info' popup appears, choose 'Not Now'\n"
        "7. If 'Turn on Notifications' appears, choose 'Not Now'\n"
        "8. Return 'login successful' if you see the home feed, else 'login failed'"
    )

    model = ChatOpenAI(model="gpt-4o", temperature=0.0)
    agent = Agent(
        task=login_instructions,
        llm=model,
        browser_context=browser_context,
        generate_gif=False
    )
    history = await agent.run(max_steps=10)
    for action in history.action_results():
        if action.extracted_content and "login successful" in action.extracted_content.lower():
            return True
    return False


# Simple structure for collecting posts from explore
class ExplorePost(BaseModel):
    url: str
    shortText: str

class ExploreOutput(BaseModel):
    posts: List[ExplorePost]

@controller.action('CommentOnPost')
async def comment_on_post(comment: str, browser: BrowserContext):
    """
    Basic action to type a comment into the comment field and click 'Post'.
    We'll rely on the agent instructions to navigate to the post and open the comment field first.
    """
    page = await browser.get_current_page()
    # Try to locate comment field
    # Possibly: 'aria-label="Add a comment…"'
    try:
        comment_box = await page.wait_for_selector('textarea[aria-label*="Add a comment"]', timeout=3000)
        if not comment_box:
            return ActionResult(error="Could not find comment input field.")
        await comment_box.click()
        await comment_box.type(comment)
        await asyncio.sleep(1)
        # Find post button
        post_button = await page.query_selector('button[type="submit"][disabled="false"]') \
                      or await page.query_selector('button[type="submit"]')
        if not post_button:
            return ActionResult(error="Could not find post button.")
        await post_button.click()
        await asyncio.sleep(2)
        return ActionResult(extracted_content=f"Commented: {comment}", include_in_memory=True)
    except Exception as e:
        return ActionResult(error=f"Failed to comment: {str(e)}")


# =============== Main Flow ===============

async def explore_hashtag(hashtag: str, browser_context: BrowserContext) -> List[str]:
    """
    Instruct the agent to go to the explore page for #hashtag, gather ~5 post URLs.
    Return them as a list of strings.
    """
    task_instructions = (
        f"Go to the Instagram explore page for #{hashtag}, collect at least 5 unique posts. "
        "Return JSON with key 'posts', array of objects {url, shortText}. No extra text."
    )
    model = ChatOpenAI(model="gpt-4o", temperature=0.0)
    # We'll parse it with a param_model or output_model
    # so let's do a small "ExploreOutput" approach
    local_controller = Controller(output_model=ExploreOutput)
    agent = Agent(
        task=task_instructions,
        llm=model,
        browser_context=browser_context,
        controller=local_controller,
        generate_gif=False
    )
    history = await agent.run(max_steps=15)
    output = history.final_result()
    if not output:
        return []
    try:
        data = ExploreOutput.model_validate_json(output)
        return [p.url for p in data.posts]
    except Exception as e:
        logger.warning(f"Failed to parse ExploreOutput: {e}")
        return []


async def check_post_already_liked(page) -> bool:
    """Check if a post is already liked by looking for the red heart (Unlike button)."""
    try:
        # Look for the Unlike button (red heart)
        unlike_button = await page.wait_for_selector("svg[aria-label*='Unlike']", timeout=2000)
        return bool(unlike_button)
    except:
        return False

async def like_and_comment_flow(post_url: str, browser_context: BrowserContext):
    """
    Create an agent to open the post_url, follow the user if not following,
    like if not already liked, and post a comment.
    """
    # Ensure we have the full Instagram URL
    if not post_url.startswith('http'):
        full_url = f"https://www.instagram.com{post_url}"
    else:
        full_url = post_url

    # First navigate to the post and check if already liked
    page = await browser_context.get_current_page()
    await page.goto(full_url)
    await asyncio.sleep(2)  # Wait for the page to load properly
    
    # Check if post is already liked
    if await check_post_already_liked(page):
        logger.info(f"Post {post_url} is already liked, skipping interaction.")
        return

    # If not already liked, proceed with follow, like and comment
    instructions = (
        f"1. You are already on the post page {full_url}\n"
        "2. Look at the top of the post where the user's name is. If there's a 'Follow' button (not 'Following' or 'Requested'), click it.\n"
        "3. Use the action 'Like Instagram post using mouse interaction' to like the post.\n"
        "4. Then add a short comment about the post, using the 'CommentOnPost' action.\n"
        "   Use fewer than 15 words.\n"
        "Note: If you see 'Following' or 'Requested' instead of 'Follow', skip step 2.\n"
    )
    model = ChatOpenAI(model="gpt-4o", temperature=0.0)
    agent = Agent(
        task=instructions,
        llm=model,
        browser_context=browser_context,
        controller=controller,  # This includes our custom like action + comment action
        generate_gif=False
    )
    await agent.run(max_steps=15)


async def main():
    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True
        )
    )
    context = await browser.new_context(
        config=BrowserContextConfig(
            cookies_file=COOKIES_FILE,
            minimum_wait_page_load_time=1,
            maximum_wait_page_load_time=10
        )
    )

    try:
        logger.info("Attempting to log in...")
        logged_in = await login_to_instagram(context)
        if not logged_in:
            logger.error("Failed to log in. Aborting.")
            return

        # Attempt to save cookies after login
        await context.save_cookies()
        logger.info("Saved cookies after login.")

        # Load or init our interactions dictionary
        interactions_data = load_interactions()

        for hashtag in HASHTAGS_TO_EXPLORE:
            logger.info(f"Exploring hashtag: #{hashtag}")
            posts = await explore_hashtag(hashtag, context)
            logger.info(f"Found {len(posts)} posts from # {hashtag}")

            for post_url in posts:
                # Check if we already interacted
                if already_interacted(post_url, interactions_data):
                    logger.info(f"Already interacted with {post_url}, skipping.")
                    continue

                # Run the like & comment flow
                logger.info(f"Interacting with post: {post_url}")
                await like_and_comment_flow(post_url, context)

                # Mark as interacted
                mark_interacted(post_url, interactions_data)
                logger.info(f"Recorded interaction for {post_url}")

        logger.info("Done exploring hashtags.")

    finally:
        await context.close()
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())