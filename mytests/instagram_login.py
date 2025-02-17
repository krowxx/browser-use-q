import os
import asyncio
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser
from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig

# Load environment variables
load_dotenv()

# Constants
COOKIES_FILE = "insta_cookie.json"
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

async def login_to_instagram() -> bool:
    """
    Create an agent to log in to Instagram using credentials from environment variables.
    Returns True if login is successful, False otherwise.
    """
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        print("Error: Instagram credentials not found in environment variables")
        return False

    # Initialize the language model
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0)

    # Create browser and context
    browser = Browser(
        config=BrowserConfig(
            headless=False,
            disable_security=True,
        )
    )
    context_config = BrowserContextConfig(
        cookies_file=COOKIES_FILE
    )
    context: BrowserContext = await browser.new_context(config=context_config)

    try:
        login_task = (
            "1. Go to instagram.com/login\n"
            "2. Wait for the login form to load\n"
            "3. Enter the username and password:\n"
            f"   Username: {INSTAGRAM_USERNAME}\n"
            f"   Password: {INSTAGRAM_PASSWORD}\n"
            "4. Click the login button\n"
            "5. Wait for the home feed to load\n"
            "6. If you see a 'Save Login Info' popup, click 'Not Now'\n"
            "7. If you see a 'Turn on Notifications' popup, click 'Not Now'\n"
            "8. Return 'login successful' if you see the home feed, otherwise return 'login failed'"
        )

        agent = Agent(
            task=login_task,
            llm=llm,
            browser_context=context,
            generate_gif=False
        )

        history = await agent.run(max_steps=10)
        
        for action in history.action_results():
            if action.extracted_content and "login successful" in action.extracted_content.lower():
                # Save cookies after successful login
                await context.save_cookies()
                print("Successfully logged in to Instagram and saved cookies")
                return True
        
        print("Failed to log in to Instagram")
        return False

    except Exception as e:
        print(f"Error during login: {str(e)}")
        return False
    finally:
        await context.close()
        await browser.close()

async def main():
    await login_to_instagram()

if __name__ == "__main__":
    asyncio.run(main()) 