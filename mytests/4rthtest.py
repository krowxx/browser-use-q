from __future__ import annotations

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Optional
from pydantic import SecretStr

# Adjust Python path if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from browser_use.agent.prompts import SystemPrompt
from browser_use.agent.service import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.agent.views import AgentHistoryList

load_dotenv()

COOKIES_FILE = "instagram_4thtest_cookies.json"
PROGRESS_FILE = "instagrampgpt_progress_4thtest.json"

class InstagramSystemPrompt(SystemPrompt):
    """
    Custom system prompt class for Instagram tasks. Adds specific 
    instructions about Instagram UI elements, e.g. roles, aria-label, etc.
    """
    def important_rules(self) -> str:
        original_rules = super().important_rules()
        new_rule = (
            "\n11. For Instagram interactions: "
            "Focus on identifying correct buttons (like hearts or comment fields) "
            "using attributes such as [aria-label, data-testid, class, alt, role]. "
            "Wait between actions to allow UI to load. "
            "If something fails, provide a short error message and continue."
        )
        return original_rules + new_rule


def load_progress() -> dict:
    """Load progress data (visited posts, etc.) from JSON file."""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {
        "visited_posts": [],
        "num_likes": 0,
        "actions": {}
    }


def save_progress(progress: dict) -> None:
    """Persist updated progress data to JSON file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


async def login_if_needed(llm: ChatOpenAI | ChatGoogleGenerativeAI, context: BrowserContext) -> None:
    """
    1. Load cookies if available.
    2. Check if user is already logged in.
    3. If not logged in, attempt normal login with environment credentials.
    4. Save updated cookies if successful.
    """
    # 1) Attempt to load existing cookies
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE, "r") as f:
            cookies = json.load(f)
        session = await context.get_session()
        await session.context.add_cookies(cookies)

    # 2) Check if we are already logged in
    verify_task = (
        "Go to https://www.instagram.com. "
        "Check if user is logged in by seeing icons like 'Home', 'Create', or a 'Profile' button. "
        "If you confirm user is logged in, return 'login confirmed'. Otherwise return 'not logged in'."
    )
    verify_agent = Agent(
        task=verify_task,
        llm=llm,
        browser_context=context,
        system_prompt_class=InstagramSystemPrompt,
        use_vision=True,
        max_actions_per_step=10
    )
    verify_hist = await verify_agent.run(max_steps=5)

    is_logged_in = False
    for actres in verify_hist.action_results():
        if actres.extracted_content and "login confirmed" in actres.extracted_content.lower():
            is_logged_in = True
            break

    # 3) If not logged in, attempt normal login
    if not is_logged_in:
        username = os.getenv("INSTAGRAM_USERNAME", "")
        password = os.getenv("INSTAGRAM_PASSWORD", "")
        if not username or not password:
            raise ValueError("INSTAGRAM_USERNAME or INSTAGRAM_PASSWORD not set in environment.")

        login_task = (
            "You are on Instagram. If you see a login form, use username <secret>insta_user</secret> "
            "and password <secret>insta_pass</secret> to log in. If login is successful, return 'login success'. "
            "If already logged in, return 'login confirmed'."
        )
        login_agent = Agent(
            task=login_task,
            llm=llm,
            browser_context=context,
            system_prompt_class=InstagramSystemPrompt,
            use_vision=True,
            sensitive_data={"insta_user": username, "insta_pass": password},
            max_actions_per_step=15
        )
        login_hist = await login_agent.run(max_steps=10)

        # Check success
        for step in login_hist.action_results():
            if step.extracted_content and ("login success" in step.extracted_content.lower()
                                           or "login confirmed" in step.extracted_content.lower()):
                is_logged_in = True
                break

    # 4) Save cookies if logged in
    if is_logged_in:
        session = await context.get_session()
        new_cookies = await session.context.cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(new_cookies, f, indent=2)
    else:
        raise RuntimeError("Unable to confirm Instagram login.")


async def like_and_comment_cycle(
    llm: ChatOpenAI | ChatGoogleGenerativeAI,
    context: BrowserContext,
    max_posts: int = 10
) -> None:
    """
    Main repeated cycle:
      - For up to `max_posts`, attempt:
        1. Scroll the feed to find a new post (not in visited_posts).
        2. If found, open it, like, comment, close.
        3. Update progress file. If no new post found, break.
    """
    for _ in range(max_posts):
        progress = load_progress()
        if progress["num_likes"] >= 10:
            print("Reached 10 total likes. Stopping cycle.")
            break

        cycle_task = (
            "1. Scroll your Instagram feed to find the first post that is not in this visited list:\n"
            f"{progress['visited_posts']}\n"
            "2. Open the post. If no new post is found, return 'no new post'.\n"
            "3. Like it if it's not liked yet. If it's already liked, just note 'already liked'.\n"
            "4. Add a short comment 'Nice post!'.\n"
            "5. Return the post URL and actions taken (liked or already liked, commented). Then close the post.\n"
        )
        agent = Agent(
            task=cycle_task,
            llm=llm,
            browser_context=context,
            system_prompt_class=InstagramSystemPrompt,
            use_vision=True,
            max_actions_per_step=15
        )
        cycle_hist = await agent.run(max_steps=12)

        found_post = None
        found_liked_status = "unknown"
        found_commented_status = "unknown"

        # parse results
        for step in cycle_hist.action_results():
            if step.extracted_content:
                content_lower = step.extracted_content.lower()
                if "no new post" in content_lower:
                    print("Agent sees no new post. Stopping.")
                    return
                # Attempt to parse post URL
                if "/p/" in step.extracted_content or "/reel/" in step.extracted_content:
                    found_post = step.extracted_content.strip()

                if "liked" in content_lower:
                    found_liked_status = "liked"
                elif "already liked" in content_lower:
                    found_liked_status = "already liked"

                if "commented" in content_lower or "nice post!" in content_lower:
                    found_commented_status = "commented"

        if not found_post:
            print("No post URL identified. Possibly no new post. Stop cycle.")
            return

        # Update progress
        visited = set(progress["visited_posts"])
        visited.add(found_post)
        progress["visited_posts"] = list(visited)

        if found_liked_status in ("liked", "already liked"):
            progress["num_likes"] += 1

        progress["actions"][found_post] = {
            "liked_status": found_liked_status,
            "commented_status": found_commented_status,
            "timestamp": datetime.now().isoformat()
        }
        save_progress(progress)
        print(f"Post: {found_post} => Liked: {found_liked_status}, Commented: {found_commented_status}")

    print("Like/comment cycle finished.")


async def main():
    """
    Main entry point:
      - Create browser & context
      - Log in if needed
      - Like/Comment cycle for up to 10 posts
    """
    # Choose your LLM (either ChatGoogleGenerativeAI or ChatOpenAI)
    # Example with Google Generative AI:
    # aggregator_llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", api_key=SecretStr(os.getenv("GEMINI_API_KEY","")))

    # Or an OpenAI model (like GPT-4o):
    aggregator_llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0.0
    )

    # Set up browser config
    browser = Browser(
        config=BrowserConfig(
            headless=False,  # Visible to debug interactions
            disable_security=True,
            new_context_config=BrowserContextConfig(
                cookies_file=COOKIES_FILE,
                allowed_domains=["instagram.com", "www.instagram.com"],
                viewport_expansion=300,
                minimum_wait_page_load_time=2.0,
                maximum_wait_page_load_time=10.0,
                wait_between_actions=2.0,
            ),
        )
    )

    async with await browser.new_context() as context:
        await login_if_needed(aggregator_llm, context)
        await like_and_comment_cycle(aggregator_llm, context, max_posts=10)

    print("Done. Final progress:")
    final_progress = load_progress()
    print(json.dumps(final_progress, indent=2))

    await browser.close()


if __name__ == "__main__":
    asyncio.run(main())