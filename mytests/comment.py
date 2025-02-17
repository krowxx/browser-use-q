import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig

load_dotenv()

# Set the Instagram post URL here (replace POST_ID with the actual post ID)
POST_URL = "https://www.instagram.com/p/DGGvOnfI23G/"

# Path to the cookies file (ensure this file exists with valid Instagram cookies)
COOKIES_FILE = os.path.join("instagram_4thtest_cookies.json")

# Define a simple task that instructs the agent to:
# 1. Start at the provided post URL.
# 2. Like the post.
# 3. Post a relevant comment based on the post content.
task = (
    f"Start at the Instagram post URL {POST_URL}. "
    "Like the post and post a relevant comment that reflects the content of the post."
)

async def verify_login(context: BrowserContext, llm: ChatGoogleGenerativeAI) -> bool:
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

async def main():
    # Initialize the language model
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.0)
    
    # Initialize browser with proper configuration
    browser_config = BrowserConfig(
        headless=False,
        disable_security=True,
        _force_keep_browser_alive=True
    )
    browser = Browser(config=browser_config)
    
    try:
        # Create a browser context with cookie handling
        context_config = BrowserContextConfig(
            cookies_file=COOKIES_FILE,
            _force_keep_context_alive=True
        )
        context = await browser.new_context(config=context_config)
        
        # Verify login status
        is_logged_in = await verify_login(context, llm)
        if not is_logged_in:
            print("Error: Not logged in to Instagram. Please ensure valid cookies in the cookie file.")
            return
        
        # Create the agent using the browser context
        agent = Agent(
            task=task,
            llm=llm,
            browser_context=context,
        )
        
        # Run the agent
        await agent.run(max_steps=10)
        
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        # Ensure proper cleanup
        if 'context' in locals():
            await context.close()
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())