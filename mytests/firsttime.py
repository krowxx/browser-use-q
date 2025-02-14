from langchain_google_genai import ChatGoogleGenerativeAI
from browser_use import Agent
from dotenv import load_dotenv
import asyncio
from pydantic import SecretStr
import os

load_dotenv()

api_key = os.getenv('GEMINI_API_KEY')
if not api_key:
    raise ValueError('GEMINI_API_KEY is not set')

# Get credentials from environment variables
instagram_username = os.getenv('INSTAGRAM_USERNAME')
instagram_password = os.getenv('INSTAGRAM_PASSWORD')

if not instagram_username or not instagram_password:
    raise ValueError('Instagram credentials not set in environment variables')

llm = ChatGoogleGenerativeAI(model='gemini-2.0-flash', api_key=SecretStr(api_key))

async def main():
    agent = Agent(
        task=f"Go to instagram.com, login with the following username: {instagram_username} and password: {instagram_password}, then comment on the first 10 posts something nice",
        llm=llm,
    )
    result = await agent.run()
    print(result)

if __name__ == "__main__":
    asyncio.run(main())