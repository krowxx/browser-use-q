import asyncio
import json
import os
from typing import Optional
from pydantic import SecretStr
from datetime import datetime

from langchain_core.language_models.chat_models import BaseChatModel
from browser_use.agent.service import Agent
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.browser.browser import Browser, BrowserConfig
from langchain_google_genai import ChatGoogleGenerativeAI

# File paths for saving cookies and progress
COOKIES_FILE = "instagram_cookies.json"
PROGRESS_FILE = "instagrampgpt_progress.json"

def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    # Default progress structure
    return {
        "visited_posts": [],
        "actions": {},
        "scroll_positions": {},  # Track scroll positions for different pages
        "last_action_timestamp": None  # Track timing of last action
    }

def save_progress(progress: dict) -> None:
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)

async def login_to_instagram_or_use_cookie(browser_context: BrowserContext, llm: BaseChatModel) -> None:
    """
    Attempts to load cookies from file. If cookies exist, they are added to the current BrowserContext.
    Then, an Agent is run to verify the login status. If verification fails, the agent logs in using
    environment variables INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD. On success, cookies are saved.
    """
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "r") as f:
            cookies = json.load(f)
        try:
            session = await browser_context.get_session()
            await session.context.add_cookies(cookies)
            # Enhanced verification task with specific element checks
            verify_task = (
                "1. Navigate to instagram.com\n"
                "2. Look for these specific elements to confirm login:\n"
                "   - The Instagram logo in the sidebar\n"
                "   - Your profile picture in the navigation\n"
                "   - The 'Create' button\n"
                "3. If ALL elements are found, return 'logged in'\n"
                "4. If ANY elements are missing, return 'not logged in'"
            )
            verify_agent = Agent(task=verify_task, llm=llm, browser_context=browser_context, generate_gif=False)
            history = await verify_agent.run(max_steps=5)
            for action in history.action_results():
                if action.extracted_content and "logged in" in action.extracted_content.lower():
                    return
        except Exception:
            pass

    # Enhanced login task with specific element targeting and verification
    username = os.getenv("INSTAGRAM_USERNAME", "default_username")
    password = os.getenv("INSTAGRAM_PASSWORD", "default_password")
    login_task = (
        "Follow these precise steps to log in to Instagram:\n"
        "1. Navigate to instagram.com\n"
        "2. Wait for the login form to be fully loaded\n"
        "3. Click the username input field and enter: {INSTAGRAM_USERNAME}\n"
        "4. Click the password input field and enter: {ENVPASSWORD}\n"
        "5. Click the 'Log In' button\n"
        "6. Wait for the home feed to load\n"
        "7. Verify login by checking for:\n"
        "   - The Instagram logo in the sidebar\n"
        "   - Your profile picture\n"
        "   - The 'Create' button\n"
        "8. Return 'logged in' only if ALL verification elements are found"
    )
    formatted_task = login_task.format(INSTAGRAM_USERNAME=username, ENVPASSWORD=password)
    login_agent = Agent(task=formatted_task, llm=llm, browser_context=browser_context, generate_gif=False)
    history = await login_agent.run(max_steps=10)
    success = False
    for action in history.action_results():
        if action.extracted_content and "logged in" in action.extracted_content.lower():
            success = True
            break
    if success:
        session = await browser_context.get_session()
        cookies = await session.context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=2)
    else:
        raise Exception("Login failed via agent.")

async def open_new_users_post(browser_context: BrowserContext, llm: BaseChatModel) -> Optional[str]:
    """
    From the Instagram main feed, open the first unvisited user post.
    Uses a progress JSON file (instagrampgpt_progress.json) to track visited posts.
    Returns the new post URL if found, else None.
    """
    progress = load_progress()
    visited = set(progress.get("visited_posts", []))
    last_scroll = progress.get("scroll_positions", {}).get("main_feed", 0)
    
    task = (
        "Follow these steps to find and open a new post:\n"
        "1. On instagram.com main feed:\n"
        "   a. Wait for the feed to fully load\n"
        "   b. Start from the current scroll position\n"
        f"   c. Look for posts that are NOT in this list: {list(visited)}\n"
        "2. For each visible post:\n"
        "   a. Check if it's a regular post (not an ad or suggested content)\n"
        "   b. Ensure the post image/video is fully loaded\n"
        "   c. If it's not in the visited list, click it\n"
        "3. If no unvisited posts are visible:\n"
        "   a. Scroll down by 800 pixels\n"
        "   b. Wait 1-2 seconds for new content to load\n"
        "   c. Repeat steps 2-3 up to 5 times\n"
        "4. Once a new post is opened:\n"
        "   a. Wait for the post modal to fully load\n"
        "   b. Extract the post's URL from the browser address bar\n"
        "   c. Verify it's a valid Instagram post URL (should contain '/p/' or '/reel/')\n"
        "   d. Return ONLY the complete post URL, nothing else\n"
        "5. If no new posts found after 5 scroll attempts, return 'none'"
    )
    
    post_agent = Agent(task=task, llm=llm, browser_context=browser_context, generate_gif=False)
    history = await post_agent.run(max_steps=15)
    
    post_url = None
    for action in history.action_results():
        if action.extracted_content and action.extracted_content.strip().lower() != "none":
            url = action.extracted_content.strip()
            # Validate that it's an actual Instagram post URL
            if "/p/" in url or "/reel/" in url:
                post_url = url
                break
    
    if post_url:
        # Only save valid Instagram post URLs
        progress["visited_posts"].append(post_url)
        progress["last_opened_post"] = post_url
        # Update scroll position
        progress["scroll_positions"]["main_feed"] = last_scroll + 800
        progress["last_action_timestamp"] = datetime.now().isoformat()
        save_progress(progress)
        return post_url
    return None

async def close_current_post(browser_context: BrowserContext, llm: BaseChatModel) -> bool:
    """
    Closes the currently opened Instagram post modal.
    Returns True if successfully closed, False otherwise.
    """
    close_task = (
        "Follow these steps to close the current Instagram post:\n"
        "1. Look for the close button (usually an X in the top-right corner):\n"
        "   a. Ensure the post modal is still open\n"
        "   b. Locate the close button element\n"
        "2. Click the close button:\n"
        "   a. Ensure the button is clickable\n"
        "   b. Click it\n"
        "3. Verify the post is closed:\n"
        "   a. Wait for the modal to disappear\n"
        "   b. Confirm you can see the main feed again\n"
        "4. Return 'closed' if successful, 'failed' if not"
    )
    
    close_agent = Agent(task=close_task, llm=llm, browser_context=browser_context, generate_gif=False)
    history = await close_agent.run(max_steps=5)
    
    for action in history.action_results():
        if action.extracted_content and "closed" in action.extracted_content.lower():
            return True
    return False

async def like_post(browser_context: BrowserContext, llm: BaseChatModel, post_url: str) -> tuple[bool, bool]:
    """
    Attempts to like a post. Returns a tuple of (liked, already_liked).
    """
    like_task = (
        f"Follow these precise steps to like the post at {post_url}:\n"
        "1. Ensure the post is fully loaded:\n"
        "   a. Wait for the post image/video to be visible\n"
        "   b. Wait for ALL action buttons to be present\n"
        "   c. Ensure the post modal is stable (no loading indicators)\n"
        "2. Locate the like button (heart icon):\n"
        "   a. Look for the SVG heart icon in the action buttons area\n"
        "   b. If you see a red/filled heart, return 'already liked'\n"
        "   c. The empty heart icon should be black or gray\n"
        "3. Click the like button using these methods in order:\n"
        "   a. Try clicking the heart icon directly\n"
        "   b. If that fails, try clicking the button containing the heart\n"
        "   c. If that fails, try using keyboard Tab to focus and Enter to click\n"
        "   d. If that fails, try double-clicking the post image\n"
        "4. After each click attempt:\n"
        "   a. Wait for 1-2 seconds for the animation\n"
        "   b. Check if the heart is now red/filled\n"
        "   c. If red/filled, return 'liked'\n"
        "5. If none of the click methods work:\n"
        "   a. Try refreshing the page and repeat steps 1-4 once\n"
        "   b. If still unsuccessful, return 'failed'\n"
        "Remember: The heart icon must change color to confirm the like!"
    )
    
    like_agent = Agent(task=like_task, llm=llm, browser_context=browser_context, generate_gif=False)
    like_history = await like_agent.run(max_steps=15)
    liked = False
    already_liked = False
    
    for action in like_history.action_results():
        if action.extracted_content:
            if "liked" in action.extracted_content.lower():
                liked = True
                break
            elif "already liked" in action.extracted_content.lower():
                already_liked = True
                break
            elif "failed" in action.extracted_content.lower():
                # Try one more time with a more direct approach
                retry_task = (
                    f"Try these specific methods to like the post at {post_url}:\n"
                    "1. Look for elements with these attributes:\n"
                    "   - SVG path with heart shape\n"
                    "   - Button with aria-label containing 'like'\n"
                    "   - Any element with role='button' near the heart icon\n"
                    "2. For each found element:\n"
                    "   a. Try to click its center coordinates\n"
                    "   b. Wait 1-2 seconds\n"
                    "   c. Check if the heart turns red\n"
                    "3. If the heart turns red, return 'liked'\n"
                    "4. If no method works, return 'failed'"
                )
                retry_agent = Agent(task=retry_task, llm=llm, browser_context=browser_context, generate_gif=False)
                retry_history = await retry_agent.run(max_steps=10)
                
                for retry_action in retry_history.action_results():
                    if retry_action.extracted_content and "liked" in retry_action.extracted_content.lower():
                        liked = True
                        break
    
    return liked, already_liked

async def like_and_comment_post(browser_context: BrowserContext, llm: BaseChatModel, post_url: str) -> None:
    """
    Likes and comments on the specified Instagram post.
    First attempts to like the post, then if successful or already liked, attempts to comment.
    """
    if not post_url or not isinstance(post_url, str) or not ("/p/" in post_url or "/reel/" in post_url):
        print(f"Warning: Invalid post URL: {post_url}")
        return

    progress = load_progress()
    
    # First, attempt to like the post
    liked, already_liked = await like_post(browser_context, llm, post_url)
    
    # Track the action immediately after liking
    action_data = {
        "liked": liked,
        "already_liked": already_liked,
        "commented": False,
        "comment_text": "",
        "timestamp": datetime.now().isoformat()
    }
    
    # Only proceed with commenting if we successfully liked or it was already liked
    if liked or already_liked:
        comment_text = "Nice post! 🙌"
        comment_task = (
            f"Follow these steps to comment on the post at {post_url}:\n"
            "1. Locate the comment section:\n"
            "   a. Look for the comment input field\n"
            "   b. If not visible, scroll the post modal\n"
            "2. Click the comment input field\n"
            f"3. Type exactly: '{comment_text}'\n"
            "4. Look for the 'Post' or 'Share' button:\n"
            "   a. Ensure it's enabled (usually turns blue)\n"
            "   b. Click it to submit\n"
            "5. Verify the comment:\n"
            "   a. Wait for the comment to appear\n"
            "   b. Check that it matches our text\n"
            "   c. Return 'commented' if successful"
        )
        comment_agent = Agent(task=comment_task, llm=llm, browser_context=browser_context, generate_gif=False)
        comment_history = await comment_agent.run(max_steps=15)
        
        for action in comment_history.action_results():
            if action.extracted_content and "commented" in action.extracted_content.lower():
                action_data["commented"] = True
                action_data["comment_text"] = comment_text
                break
    else:
        action_data["error"] = "Failed to like post after multiple attempts"
        print(f"Warning: Failed to like post {post_url} after multiple attempts")
    
    # Update progress with the final status
    progress.setdefault("actions", {})[post_url] = action_data
    save_progress(progress)

async def run_instagramgpt(browser_context: BrowserContext, llm: BaseChatModel) -> None:
    """
    Main runner function for the INSTAGRAMGPT workflow.
    It first logs in (or loads cookies) and then repeatedly:
      - Opens a new unvisited user post from the main feed.
      - Likes and comments on that post.
      - Closes the post and moves to the next one.
    The loop ends when no new posts are found.
    """
    await login_to_instagram_or_use_cookie(browser_context, llm)
    
    while True:
        post_url = await open_new_users_post(browser_context, llm)
        if not post_url:
            print("No new posts found. Stopping workflow.")
            break
            
        # Process the current post
        await like_and_comment_post(browser_context, llm, post_url)
        
        # Close the current post
        if not await close_current_post(browser_context, llm):
            print("Warning: Failed to close post. Attempting to continue...")
            # You might want to add additional recovery logic here if needed
        
        # Wait briefly before processing the next post
        await asyncio.sleep(5)

# If run as a standalone script, provide a simple runner.
if __name__ == "__main__":
    import argparse
    from langchain_openai import ChatOpenAI

    parser = argparse.ArgumentParser()
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()

    # Setup browser and context with appropriate configurations
    browser = Browser(
        config=BrowserConfig(
            headless=args.headless,
            disable_security=True
        )
    )

    async def main():
        api_key = os.getenv("GEMINI_API_KEY")
        context = await browser.new_context(config=BrowserContextConfig(cookies_file=COOKIES_FILE))
        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=SecretStr(api_key) if api_key else None)  # Replace with desired LLM configuration
        await run_instagramgpt(context, llm)
        await context.close()
        await browser.close()
    asyncio.run(main())