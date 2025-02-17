import asyncio
import logging
from browser_use.agent.views import ActionResult
from browser_use.browser.context import BrowserContext
from browser_use.controller.views import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)

class InstagramLikeAction(BaseModel):
    """Parameters for Instagram like action"""
    index: Optional[int] = None  # Optional because we might find the SVG directly

async def find_like_button_coordinates(page):
    """Find the like button's coordinates using Instagram's specific SVG structure."""
    try:
        # Use a flexible selector that matches any svg with 'Like' in the aria-label
        like_button = await page.wait_for_selector("svg[aria-label*='Like']", timeout=5000)
        if not like_button:
            # Try an alternative selector if needed
            like_button = await page.wait_for_selector("svg[aria-label*='Like'][width='24']", timeout=5000)
        
        if like_button:
            # Get the bounding box of the like button
            box = await like_button.bounding_box()
            if box:
                return {
                    'x': box['x'] + box['width'] / 2,
                    'y': box['y'] + box['height'] / 2
                }
    except Exception as e:
        logger.debug(f"Failed to find like button coordinates: {str(e)}")
    return None

async def instagram_like_with_mouse(browser: BrowserContext) -> ActionResult:
    """
    Custom action to like an Instagram post using precise mouse movements.
    This simulates human-like behavior and targets the specific SVG element.
    """
    try:
        page = await browser.get_current_page()
        
        # Find the like button coordinates
        coords = await find_like_button_coordinates(page)
        if not coords:
            return ActionResult(error="Could not find Instagram like button coordinates")

        # Move mouse to the like button with human-like motion
        await page.mouse.move(coords['x'], coords['y'], steps=20)  # Gradual movement
        
        # Small random-like pause to simulate human behavior
        await asyncio.sleep(0.3)
        
        # Click the like button
        await page.mouse.click(coords['x'], coords['y'])
        
        # Wait for any animations to complete
        await asyncio.sleep(0.5)
        
        # Verify the like was successful by checking if the SVG changed to indicate an unlike state
        try:
            unlike_svg = await page.wait_for_selector("svg[aria-label*='Unlike']", timeout=2000)
            if unlike_svg:
                return ActionResult(
                    extracted_content="Successfully liked the post using mouse interaction",
                    include_in_memory=True
                )
        except:
            # If we can't find the Unlike button, try to verify by checking if the original Like button is gone
            try:
                like_button = await page.wait_for_selector("svg[aria-label*='Like']", timeout=500)
                if not like_button:
                    return ActionResult(
                        extracted_content="Like action appears successful - Like button is no longer present",
                        include_in_memory=True
                    )
            except:
                pass
        
        return ActionResult(error="Like action completed but could not verify success")
        
    except Exception as e:
        logger.error(f"Error during Instagram like action: {str(e)}")
        return ActionResult(error=f"Failed to like post: {str(e)}") 