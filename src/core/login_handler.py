"""
Login Handler - Fixed to keep page open after login
"""
import asyncio
import random
import os
import math
from typing import Optional, Dict, Any, Tuple
from playwright.async_api import Page, BrowserContext, ElementHandle

from ..utils.logger import setup_logger
from ..captcha.solver import CaptchaSolver

logger = setup_logger(__name__)


class LoginHandler:
    """Handles login to Tribals with anti-detection measures"""
    
    def __init__(self, config: Dict[str, Any], anti_detection_manager=None):
        self.config = config
        self.username = config.get('username') or os.getenv('TRIBALS_USERNAME')
        self.password = config.get('password') or os.getenv('TRIBALS_PASSWORD')
        self.captcha_solver = CaptchaSolver(config, anti_detection_manager)
        
        # Parse server from config
        server_url = config.get('server', {}).get('base_url', 'https://it94.tribals.it')
        import re
        match = re.search(r'https://([a-z]+)(\d+)\.tribals\.([a-z.]+)', server_url)
        
        if match:
            self.server_prefix = match.group(1)  # 'it'
            self.server_number = match.group(2)   # '94'
            self.direct_play_url = f"https://www.tribals.it/page/play/{self.server_prefix}{self.server_number}"
        else:
            # Fallback
            self.server_prefix = 'it'
            self.server_number = '94'
            self.direct_play_url = "https://www.tribals.it/page/play/it94"
            
        logger.info(f"🎯 Configured for server: {self.server_prefix}{self.server_number}")
        logger.info(f"🔗 Direct play URL: {self.direct_play_url}")
        
    async def ensure_logged_in(self, context: BrowserContext) -> bool:
        """Ensure user is logged in using direct play link"""
        # Check if we already have a page open
        page = None
        if context.pages:
            # Use existing page if available
            page = context.pages[0]
        else:
            # Create new page
            page = await context.new_page()
            
        try:
            logger.info(f"🔗 Checking login status via: {self.direct_play_url}")
            await page.goto(self.direct_play_url, wait_until='networkidle', timeout=30000)
            await self._human_delay(2, 3)
            
            # Check where we ended up
            current_url = page.url
            logger.info(f"📄 Current page: {current_url}")
            
            # If we're in the game, we're logged in!
            if 'game.php' in current_url:
                logger.info("✅ Already logged in and in game!")
                # Don't close the page - we'll use it
                return True
                
            # If we're on login page, we need to login
            if await self._is_login_page(page):
                logger.info("🔐 Login required")
                # Perform login on the same page
                return await self._perform_login(page)
                
            # Unexpected state - try login
            logger.warning(f"⚠️ Unexpected state, attempting login. URL: {current_url}")
            return await self._perform_login(page)
            
        except Exception as e:
            logger.error(f"❌ Error checking login status: {e}")
            return False
        
    async def login(self, context: BrowserContext) -> bool:
        """Perform login using direct play link"""
        logger.info("🔐 Starting login process...")
        
        # This method is now deprecated - use ensure_logged_in instead
        return await self.ensure_logged_in(context)
            
    async def _is_login_page(self, page: Page) -> bool:
        """Check if we're on the login page"""
        login_indicators = [
            '#user',
            '#password', 
            'a.btn-login',
            'form[action*="login"]'
        ]
        
        for selector in login_indicators:
            if await page.query_selector(selector):
                return True
                
        return False
        
    async def _perform_login(self, page: Page) -> bool:
        """Perform the actual login"""
        if not self.username or not self.password:
            logger.warning("⚠️ No credentials provided - please login manually")
            return await self._wait_for_manual_login(page)
            
        logger.info("🤖 Performing automated login...")
        
        try:
            # Fill login form with human-like behavior
            username_field = await page.wait_for_selector('#user', timeout=5000)
            if not username_field:
                logger.error("❌ Username field not found")
                return False
                
            # Click username field
            await username_field.click()
            await self._human_delay(0.5, 1)
            
            # Type username
            await self._human_type(page, '#user', self.username)
            await self._human_delay(0.5, 1.5)
            
            # Tab to password field
            await page.keyboard.press('Tab')
            await self._human_delay(0.3, 0.8)
            
            # Type password
            await self._human_type(page, '#password', self.password)
            await self._human_delay(0.5, 1)
            
            # Find login button
            login_button = await page.query_selector('a.btn-login')
            if not login_button:
                logger.error("❌ Login button not found")
                return False
                
            # Move mouse naturally to button
            await self._natural_mouse_move(page, login_button)
            await self._human_delay(0.3, 0.6)
            
            # Use captcha solver to handle login + captcha
            logger.info("🔧 Initiating login with captcha handling...")
            solved = await self.captcha_solver.solve_captcha(page)
            
            if not solved:
                logger.error("❌ Failed to complete login/captcha")
                return False
                
            # Wait for page to load after login
            logger.info("⏳ Waiting for login to complete...")
            await self._human_delay(3, 5)
            
            # Check for errors first
            error = await self._check_for_errors(page)
            if error:
                logger.error(f"❌ Login error: {error}")
                return False
            
            # Check if we're now in the game
            if 'game.php' in page.url:
                logger.info("✅ Successfully logged in and in game!")
                return True
                
            # If not in game yet, try navigating to direct play link again
            logger.info("🔄 Navigating to game via direct play link...")
            await page.goto(self.direct_play_url, wait_until='networkidle', timeout=30000)
            await self._human_delay(2, 3)
            
            # Now check if we're in the game
            if 'game.php' in page.url:
                logger.info("✅ Successfully entered game!")
                return True
            else:
                # One more attempt with longer wait
                logger.warning("⚠️ Not in game yet, waiting longer...")
                await self._human_delay(3, 5)
                
                if 'game.php' in page.url:
                    logger.info("✅ Successfully entered game!")
                    return True
                else:
                    logger.error(f"❌ Failed to enter game. URL: {page.url}")
                    await page.screenshot(path="game_entry_failed.png")
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Login failed: {e}", exc_info=True)
            return False
            
    async def _wait_for_manual_login(self, page: Page) -> bool:
        """Wait for user to login manually"""
        logger.info("⏰ Waiting for manual login (max 5 minutes)...")
        logger.info("💡 Please login and you'll be redirected to the game automatically")
        
        try:
            # Wait for game.php in URL
            await page.wait_for_function(
                """() => window.location.href.includes('game.php')""",
                timeout=300000  # 5 minutes
            )
            
            logger.info("✅ Manual login successful!")
            return True
            
        except Exception as e:
            logger.error("❌ Manual login timeout")
            return False
            
    async def _check_for_errors(self, page: Page) -> Optional[str]:
        """Check for error messages on page"""
        error_selectors = [
            '.error-message',
            '.error_box',
            '.error',
            '[class*="error"]',
            '.warn'
        ]
        
        for selector in error_selectors:
            element = await page.query_selector(selector)
            if element:
                try:
                    text = await element.text_content()
                    if text and text.strip() and len(text.strip()) > 3:
                        return text.strip()
                except:
                    pass
                    
        return None
        
    async def _human_delay(self, min_seconds: float, max_seconds: float):
        """Add human-like delay"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
        
    async def _human_type(self, page: Page, selector: str, text: str):
        """Type text with human-like delays"""
        element = await page.wait_for_selector(selector, timeout=5000)
        if not element:
            raise Exception(f"Element {selector} not found")
            
        # Clear existing text
        await element.click()
        await page.keyboard.press('Control+A')
        await page.keyboard.press('Delete')
        
        # Type with variable delays
        for i, char in enumerate(text):
            # Occasionally make a typo (0.5% chance)
            if random.random() < 0.005 and i > 0 and i < len(text) - 1:
                # Type wrong character
                wrong_char = random.choice('asdfghjkl')
                await page.keyboard.type(wrong_char)
                await asyncio.sleep(random.uniform(0.1, 0.3))
                
                # Delete and correct
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.05, 0.15))
                
            # Type the character
            await page.keyboard.type(char)
            
            # Variable delay
            if char == ' ':
                delay = random.uniform(0.1, 0.2)
            elif random.random() < 0.1:  # 10% chance of longer pause
                delay = random.uniform(0.2, 0.4)
            else:
                delay = random.uniform(0.05, 0.15)
                
            await asyncio.sleep(delay)
            
    async def _natural_mouse_move(self, page: Page, element: ElementHandle):
        """Move mouse naturally to element"""
        try:
            # Get element position
            box = await element.bounding_box()
            if not box:
                return
                
            # Target somewhere inside element (not exact center)
            target_x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
            target_y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
            
            # Simple curved movement
            steps = random.randint(10, 20)
            for i in range(steps + 1):
                progress = i / steps
                # Add slight curve
                curve = math.sin(progress * math.pi) * random.uniform(-30, 30)
                
                x = target_x * progress + curve
                y = target_y * progress + curve
                
                await page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.01, 0.03))
                
        except Exception as e:
            logger.debug(f"Mouse move error (non-critical): {e}")
            # Not critical, continue