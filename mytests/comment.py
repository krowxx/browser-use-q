import os
import asyncio
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.controller.service import Controller
from mytests.like_with_mouse import instagram_like_with_mouse, InstagramLikeAction

load_dotenv()

# Set the Instagram post URL here (replace POST_ID with the actual post ID)
POST_URL = "https://www.instagram.com/p/DFXUCXYigM7/?img_index=1"

# Path to the cookies file (ensure this file exists with valid Instagram cookies)
COOKIES_FILE = os.path.join("insta_cookie.json")

# Initialize controller with custom Instagram actions
controller = Controller(exclude_actions=['click_element'])  # Prevent normal clicking

@controller.action(
    'Like Instagram post using mouse interaction',
    param_model=InstagramLikeAction
)
async def like_instagram_post(params: InstagramLikeAction, browser: BrowserContext):
    return await instagram_like_with_mouse(browser)

# Define a simple task that instructs the agent to:
# 1. Start at the provided post URL.
# 2. Like the post using our custom action.
# 3. Post a relevant comment based on the post content.
task = (
    f"Start at the Instagram post URL {POST_URL}. "
    "IMPORTANT: To like the post, you MUST use the 'Like Instagram post using mouse interaction' action - "
    "do NOT try to click the like button directly as it won't work. "
    "After liking, post a relevant comment that reflects the content of the post."
)

async def verify_login(context: BrowserContext, llm: ChatGoogleGenerativeAI | ChatOpenAI) -> bool:
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
    #llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.0)
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

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
        
        # Create the agent using the browser context and our custom controller
        agent = Agent(
            task=task,
            llm=llm,
            browser_context=context,
            controller=controller  # Use our custom controller with Instagram actions
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