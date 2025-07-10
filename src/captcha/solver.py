"""
Captcha Solver - Fixed to handle login captcha with button workaround
"""
import asyncio
import os
from typing import Optional
from playwright.async_api import Page, Frame, Locator

from ..utils.logger import setup_logger
from ..utils.screenshot_manager import screenshot_manager

logger = setup_logger(__name__)

# Try to import hcaptcha-challenger with correct imports
try:
    from hcaptcha_challenger import AgentV, AgentConfig
    from hcaptcha_challenger.models import ChallengeSignal
    HCAPTCHA_AVAILABLE = True
    logger.info("✅ hcaptcha-challenger is available")
except ImportError as e:
    HCAPTCHA_AVAILABLE = False
    logger.error(f"❌ hcaptcha-challenger not available: {e}")
    logger.error("   Install with: pip install hcaptcha-challenger")
    # Define a fallback ChallengeSignal if not available
    class ChallengeSignal:
        SUCCESS = "success"
        FAILURE = "failure"


class CaptchaSolver:
    """Solves hCaptcha using hcaptcha-challenger"""
    
    def __init__(self, config, anti_detection_manager=None):
        self.config = config
        self.max_retries = config.get('captcha', {}).get('max_retries', 3)
        self.timeout = config.get('captcha', {}).get('solver_timeout', 180)
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.force_manual = os.getenv('FORCE_MANUAL_CAPTCHA', 'false').lower() == 'true'
        self.anti_detection = anti_detection_manager
        
        if HCAPTCHA_AVAILABLE and self.gemini_api_key:
            logger.info(f"✅ Gemini API key configured: {self.gemini_api_key[:10]}...")
        else:
            if not HCAPTCHA_AVAILABLE:
                logger.error("❌ hcaptcha-challenger not installed!")
            if not self.gemini_api_key:
                logger.error("❌ GEMINI_API_KEY not found in environment!")
                logger.error("   Set: export GEMINI_API_KEY=your_key_here")
                logger.error("   Get key: https://aistudio.google.com/app/apikey")
                
    async def monitor_captcha_frame(self, page: Page) -> Optional[Frame]:
        """Monitor and return the active captcha challenge frame"""
        # Look for the challenge frame
        for frame in page.frames:
            if 'hcaptcha.com' in frame.url and 'challenge' in frame.url:
                return frame
        return None
        
    async def is_multi_challenge(self, page: Page) -> bool:
        """Check if this is a multi-challenge captcha"""
        try:
            challenge_frame = await self.monitor_captcha_frame(page)
            if challenge_frame:
                # Look for progress indicator
                progress_elem = await challenge_frame.query_selector('.challenge-progress')
                if progress_elem:
                    text = await progress_elem.text_content()
                    if text and ('2' in text or '/' in text):
                        logger.info(f"📊 Multi-challenge detected: {text}")
                        return True
        except:
            pass
        return False
                
    async def solve_bot_protection(self, page: Page) -> bool:
        """Handle the bot protection page or quest"""
        logger.info("🤖 Handling bot protection...")
        
        # SUSPEND ANTI-DETECTION
        if self.anti_detection:
            self.anti_detection.suspend("bot_protection")
            logger.info("🛑 Anti-detection suspended for bot protection")
        
        # Capture initial state
        await screenshot_manager.capture_bot_protection(page, "initial_state")
        
        try:
            # Make sure page is ready
            await page.wait_for_load_state('networkidle', timeout=5000)
            
            # Check if this is the quest div (clicking it starts captcha directly)
            quest_element = await page.query_selector('#botprotection_quest')
            if quest_element:
                logger.info("📋 Found bot protection quest - clicking to start captcha")
                
                # Capture before clicking quest
                await screenshot_manager.capture_bot_protection(page, "before_quest_click")
                
                # Click the quest div to start captcha directly
                await quest_element.click()
                logger.info("✅ Clicked bot protection quest - captcha should appear")
                
                # Wait for captcha to appear
                await asyncio.sleep(3)
                
                # Capture after quest click
                await screenshot_manager.capture_bot_protection(page, "after_quest_click")
                
                # Now solve the captcha that appears
                return await self._solve_bot_protection_captcha(page)
                
            # Otherwise, look for the "Start bot protection check" button (full page version)
            start_button_selector = 'td.bot-protection-row a.btn.btn-default'
            start_button = await page.wait_for_selector(start_button_selector, timeout=10000)
            
            if start_button:
                button_text = await start_button.text_content()
                logger.info(f"📋 Found button: {button_text}")
                
                # Capture before clicking
                await screenshot_manager.capture_bot_protection(page, "before_button_click")
                
                # Click the button
                await start_button.click()
                logger.info("✅ Clicked bot protection start button")
                
                # Wait for hCaptcha to load properly
                logger.info("⏳ Waiting for hCaptcha to load...")
                await asyncio.sleep(3)
                
                # Capture after button click
                await screenshot_manager.capture_bot_protection(page, "after_button_click")
                
                # Wait for hCaptcha iframe to appear
                try:
                    # Look for the hcaptcha container or iframe
                    hcaptcha_selectors = [
                        'td.bot-protection-row .captcha iframe[src*="hcaptcha.com"]',
                        '.captcha iframe[src*="hcaptcha.com"]',
                        'iframe[src*="hcaptcha.com"][data-hcaptcha-widget-id]',
                        'div[data-hcaptcha-widget-id]',
                        '.h-captcha iframe'
                    ]
                    
                    hcaptcha_found = False
                    for selector in hcaptcha_selectors:
                        element = await page.wait_for_selector(selector, timeout=5000)
                        if element:
                            logger.info(f"✅ Found hCaptcha via selector: {selector}")
                            hcaptcha_found = True
                            break
                except:
                    logger.warning("⚠️ hCaptcha iframe not found with standard selectors")
                
                # Give it more time to fully load
                await asyncio.sleep(2)
                
                # Capture hCaptcha loaded state
                await screenshot_manager.capture_bot_protection(page, "hcaptcha_loaded")
                
                # Check if it's multi-challenge and force manual if configured
                if self.force_manual or await self.is_multi_challenge(page):
                    logger.warning("🔄 Multi-challenge or manual mode - switching to manual solving")
                    return await self._solve_manually(page)
                
                # Now solve the captcha that appears
                return await self._solve_bot_protection_captcha(page)
            else:
                logger.error("❌ Bot protection start button not found")
                await screenshot_manager.capture_bot_protection(page, "button_not_found")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error handling bot protection: {e}", exc_info=True)
            await screenshot_manager.capture_bot_protection(page, f"error_{str(e)[:30]}")
            # Try manual solve as fallback
            return await self._solve_manually(page)
        finally:
            # ALWAYS RESUME ANTI-DETECTION
            if self.anti_detection:
                self.anti_detection.resume()
                logger.info("▶️ Anti-detection resumed after bot protection")
            
    async def _solve_bot_protection_captcha(self, page: Page) -> bool:
        """Solve the captcha that appears after clicking bot protection button"""
        logger.info("🔧 Solving bot protection captcha...")
        
        if not HCAPTCHA_AVAILABLE or not self.gemini_api_key:
            logger.warning("⚠️ Automatic solving not available, falling back to manual")
            return await self._solve_manually(page)
            
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔄 Attempt {attempt + 1}/{self.max_retries}")
                
                # Capture attempt state
                await screenshot_manager.capture_captcha(page, f"attempt_{attempt + 1}")
                
                # Initialize AgentV with configuration
                agent_config = AgentConfig(
                    GEMINI_API_KEY=self.gemini_api_key,
                    EXECUTION_TIMEOUT=self.config.get('captcha', {}).get('response_timeout', 180),
                    RESPONSE_TIMEOUT=self.config.get('captcha', {}).get('response_timeout', 180),
                    RETRY_ON_FAILURE=True,
                    WAIT_FOR_CHALLENGE_VIEW_TO_RENDER_MS=5000,
                    enable_challenger_debug=True,
                    screenshot_timeout=60000,
                    element_timeout=60000,
                    click_precision_padding=10,
                    verify_click_success=True,
                    max_click_attempts=3,
                    iframe_stability_delay=1000
                )
                
                # Create agent instance
                agent = AgentV(page=page, agent_config=agent_config)
                
                # Capture before checkbox click
                await screenshot_manager.capture_captcha(page, "before_checkbox")
                
                # Try to click checkbox
                checkbox_clicked = False
                
                # Method 1: Let AgentV find it
                try:
                    await agent.robotic_arm.click_checkbox()
                    checkbox_clicked = True
                    logger.info("✅ Clicked checkbox using AgentV")
                except Exception as e:
                    logger.warning(f"⚠️ AgentV checkbox click failed: {e}")
                
                if not checkbox_clicked:
                    logger.error("❌ Could not click hCaptcha checkbox")
                    await screenshot_manager.capture_captcha(page, "checkbox_click_failed")
                    return await self._solve_manually(page)
                
                # Capture after checkbox click
                await screenshot_manager.capture_captcha(page, "after_checkbox")
                
                # Wait a bit after clicking checkbox
                await asyncio.sleep(3)
                
                # Check if it's multi-challenge after checkbox click
                if await self.is_multi_challenge(page):
                    logger.warning("🔄 Multi-challenge captcha detected after checkbox click")
                    await screenshot_manager.capture_captcha(page, "multi_challenge_detected")
                    return await self._solve_manually(page)
                
                # Now wait for and solve the challenge
                logger.info("⏳ Waiting for challenge to appear...")
                
                result = None
                try:
                    result = await asyncio.wait_for(
                        agent.wait_for_challenge(),
                        timeout=180
                    )
                    logger.info(f"📊 Challenge result: {result}")
                except asyncio.TimeoutError:
                    logger.warning("⏱️ Challenge wait timed out")
                    await screenshot_manager.capture_captcha(page, "challenge_timeout")
                except Exception as challenge_error:
                    logger.error(f"❌ Challenge error: {challenge_error}")
                    await screenshot_manager.capture_captcha(page, "challenge_error")
                    
                # Wait for result to process
                await asyncio.sleep(3)
                
                # Capture final state
                await screenshot_manager.capture_captcha(page, f"attempt_{attempt + 1}_result")
                
                # Check success conditions
                success = False
                
                if result == ChallengeSignal.SUCCESS or result == "success":
                    logger.info("✅ Challenge reported success!")
                    success = True
                
                # Check if bot protection is gone
                if not await self._is_bot_protection_active(page):
                    logger.info("✅ Bot protection is gone!")
                    success = True
                    
                # Check if we're in the game
                if "game.php" in page.url and "screen=" in page.url:
                    logger.info("✅ Successfully in game!")
                    success = True
                    
                if success:
                    await screenshot_manager.capture_captcha(page, "success")
                    return True
                else:
                    logger.warning(f"⚠️ Challenge not successful: {result}")
                    
            except Exception as e:
                logger.error(f"❌ Error solving captcha: {e}", exc_info=True)
                await screenshot_manager.capture_captcha(page, f"error_attempt_{attempt + 1}")
                
            # Wait before retry
            if attempt < self.max_retries - 1:
                logger.info(f"⏳ Waiting 5s before retry...")
                await asyncio.sleep(5)
                
        logger.error("❌ Failed to solve captcha after all attempts")
        await screenshot_manager.capture_captcha(page, "all_attempts_failed")
        return await self._solve_manually(page)
        
    async def solve_captcha(self, page: Page, is_bot_protection: bool = False) -> bool:
        """Attempt to solve captcha on page (for login) - WORKAROUND: USE LOGIN BUTTON AS CHECKBOX"""
        logger.info(f"🔧 Attempting to solve login captcha...")
        
        # SUSPEND ANTI-DETECTION
        if self.anti_detection:
            self.anti_detection.suspend("login_captcha")
            logger.info("🛑 Anti-detection suspended for login captcha")
        
        # Capture initial state
        await screenshot_manager.capture_captcha(page, "login_initial")
        
        try:
            if not HCAPTCHA_AVAILABLE or not self.gemini_api_key or self.force_manual:
                logger.warning("⚠️ Automatic solving not available or disabled, using manual")
                return await self._solve_manually_login(page)
                
            # WORKAROUND: Override the AgentV's checkbox detection to use login button
            logger.info("🎯 Using login button workaround for instant challenge...")
            
            # Check if it's multi-challenge before attempting
            if await self.is_multi_challenge(page):
                logger.warning("🔄 Multi-challenge captcha detected")
                return await self._solve_manually_login(page)
            
            # Check if captcha is already active (from previous attempt)
            captcha_already_active = await self._is_captcha_challenge_present(page)
            
            for attempt in range(self.max_retries):
                try:
                    logger.info(f"🔄 Captcha solve attempt {attempt + 1}/{self.max_retries}")
                    
                    # Initialize AgentV with configuration
                    agent_config = AgentConfig(
                        GEMINI_API_KEY=self.gemini_api_key,
                        EXECUTION_TIMEOUT=180,
                        RESPONSE_TIMEOUT=180,
                        RETRY_ON_FAILURE=True,
                        WAIT_FOR_CHALLENGE_VIEW_TO_RENDER_MS=2000,  # Reduced since challenge appears fast
                        enable_challenger_debug=True,
                        screenshot_timeout=60000,
                        element_timeout=60000,
                        click_precision_padding=10,
                        verify_click_success=True,
                        max_click_attempts=3,
                        iframe_stability_delay=1000
                    )
                    
                    # Create agent instance
                    agent = AgentV(page=page, agent_config=agent_config)
                    
                    # WORKAROUND: Override the checkbox click to click login button instead
                    original_click_checkbox = agent.robotic_arm.click_checkbox
                    
                    async def click_login_as_checkbox():
                        """Click login button instead of checkbox"""
                        # Only click if captcha not already active
                        if not captcha_already_active:
                            logger.info("🎯 Clicking login button (as checkbox workaround)...")
                            login_btn = await page.query_selector('a.btn-login')
                            if login_btn:
                                await login_btn.click()
                                logger.info("✅ Clicked login button via workaround")
                                # Wait for challenge to appear
                                await asyncio.sleep(2)
                            else:
                                logger.error("❌ Login button not found for workaround")
                                raise Exception("Login button not found")
                        else:
                            logger.info("🎯 Captcha already active, skipping login button click")
                            # Just wait a bit
                            await asyncio.sleep(1)
                    
                    # Replace the checkbox click method
                    agent.robotic_arm.click_checkbox = click_login_as_checkbox
                    
                    try:
                        # Now let AgentV handle it normally - it will click login and solve
                        logger.info("🤖 Starting AgentV with login button workaround...")
                        await agent.robotic_arm.click_checkbox()  # This will click login button
                        
                        # Wait for and solve challenge
                        result = await asyncio.wait_for(
                            agent.wait_for_challenge(),
                            timeout=180  # Increased to 3 minutes for multi-challenges
                        )
                        logger.info(f"📊 Challenge result: {result}")
                        
                        # Check if successful
                        if result == ChallengeSignal.SUCCESS:
                            logger.info("✅ Challenge solved successfully!")
                            # Just return true - let login handler handle navigation
                            return True
                        else:
                            logger.warning(f"⚠️ Challenge not successful: {result}")
                            # Check if it became multi-challenge
                            if await self.is_multi_challenge(page):
                                logger.warning("🔄 Captcha became multi-challenge during solve")
                                return await self._solve_manually_login(page)
                            
                    except asyncio.TimeoutError:
                        logger.warning("⏱️ Challenge timeout")
                        await screenshot_manager.capture_captcha(page, f"timeout_{attempt}")
                    except Exception as e:
                        logger.error(f"❌ Challenge error: {e}")
                        await screenshot_manager.capture_captcha(page, f"error_{attempt}")
                        
                except Exception as e:
                    logger.error(f"❌ Attempt {attempt + 1} failed: {e}", exc_info=True)
                    
                # Restore original method for next attempt
                if 'original_click_checkbox' in locals():
                    agent.robotic_arm.click_checkbox = original_click_checkbox
                    
                # Update captcha state for next attempt
                captcha_already_active = await self._is_captcha_challenge_present(page)
                
                # Wait before retry
                if attempt < self.max_retries - 1:
                    logger.info(f"⏳ Waiting 5s before retry...")
                    await asyncio.sleep(5)
                    
            logger.error("❌ Failed to solve captcha after all attempts")
            return await self._solve_manually_login(page)
            
        finally:
            # ALWAYS RESUME ANTI-DETECTION
            if self.anti_detection:
                self.anti_detection.resume()
                logger.info("▶️ Anti-detection resumed after login captcha")
                
    async def _find_hcaptcha_iframe(self, page: Page) -> Optional[Frame]:
        """Find the hCaptcha iframe on the page"""
        # Check all frames
        for frame in page.frames:
            if 'hcaptcha.com' in frame.url:
                logger.debug(f"Found hCaptcha frame: {frame.url}")
                return frame
                
        # Also check for iframe elements
        iframe_selectors = [
            'iframe[src*="hcaptcha.com"]',
            'iframe[data-hcaptcha-widget-id]',
            '.h-captcha iframe',
            'div[data-hcaptcha-widget-id] iframe'
        ]
        
        for selector in iframe_selectors:
            iframe = await page.query_selector(selector)
            if iframe:
                logger.debug(f"Found hCaptcha iframe via selector: {selector}")
                # Get the frame from the iframe element
                frame_element = await iframe.content_frame()
                if frame_element:
                    return frame_element
                    
        return None
        
    async def _find_hcaptcha_frame(self, page: Page) -> Optional[Frame]:
        """Find the hCaptcha frame (not challenge frame)"""
        for frame in page.frames:
            if 'hcaptcha.com' in frame.url and 'hcaptcha.html' in frame.url:
                return frame
        return None
        
    async def _solve_manually_login(self, page: Page) -> bool:
        """Manual solve specifically for login page"""
        logger.warning("=" * 60)
        logger.warning("⚠️  MANUAL LOGIN CAPTCHA SOLVE REQUIRED")
        logger.warning("=" * 60)
        logger.warning("Please solve the captcha in the browser window")
        logger.warning("The bot will continue once you're logged in")
        logger.warning("=" * 60)
        
        # Play notification sound
        try:
            if os.name == 'posix':  # macOS/Linux
                os.system('afplay /System/Library/Sounds/Glass.aiff 2>/dev/null || echo -e "\\a"')
            elif os.name == 'nt':  # Windows
                import winsound
                winsound.Beep(1000, 500)
        except:
            pass
            
        # Wait for login to complete
        max_wait = self.timeout
        check_interval = 2
        elapsed = 0
        
        while elapsed < max_wait:
            # Check if we're logged in (reached game.php)
            if "game.php" in page.url:
                logger.info("✅ Manual login successful!")
                return True
                
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            if elapsed % 15 == 0:  # Remind every 15 seconds
                remaining = max_wait - elapsed
                logger.warning(f"⏰ Waiting for manual login... ({remaining}s remaining)")
                
        logger.error("❌ Login timeout")
        return False
        
    async def _is_bot_protection_active(self, page: Page) -> bool:
        """Check if bot protection is still active"""
        try:
            # First check URL - if we're in game with a screen, we passed
            if "game.php" in page.url and "screen=" in page.url and "intro" not in page.url:
                logger.debug("In game with screen - bot protection passed")
                return False
                
            # Check if bot protection elements are present
            bot_protection = await page.query_selector('td.bot-protection-row')
            if bot_protection:
                # Check if it's the initial page with button or active captcha
                start_button = await page.query_selector('td.bot-protection-row a.btn.btn-default')
                captcha_div = await page.query_selector('td.bot-protection-row .captcha')
                
                if start_button or captcha_div:
                    return True
                    
            # Check for the quest notification
            quest = await page.query_selector('#botprotection_quest')
            if quest:
                return True
                
            return False
        except:
            return False
            
    async def _is_captcha_challenge_present(self, page: Page) -> bool:
        """Check if captcha challenge is present on page"""
        try:
            # Check for bot protection elements
            bot_protection = await page.query_selector('td.bot-protection-row')
            if bot_protection:
                # Check if there's a captcha in the bot protection
                captcha_div = await page.query_selector('td.bot-protection-row .captcha')
                if captcha_div:
                    # Check if it has hCaptcha
                    hcaptcha = await captcha_div.query_selector('.h-captcha')
                    if hcaptcha:
                        logger.debug("Found hCaptcha in bot protection")
                        return True
                        
            # Look for hCaptcha challenge frame
            challenge_frame = None
            for frame in page.frames:
                if 'hcaptcha.com' in frame.url and 'challenge' in frame.url:
                    logger.debug(f"Found hCaptcha challenge frame: {frame.url}")
                    challenge_frame = frame
                    break
                    
            if challenge_frame:
                try:
                    challenge_view = await challenge_frame.query_selector('.challenge-view')
                    if challenge_view:
                        logger.debug("Found challenge view in frame")
                        return True
                except:
                    pass
                    
            # Check main page for captcha elements
            captcha_selectors = [
                'iframe[src*="hcaptcha.com"][src*="challenge"]',
                'div.h-captcha iframe',
                '.h-captcha',
                '[data-hcaptcha-widget-id]'
            ]
            
            for selector in captcha_selectors:
                element = await page.query_selector(selector)
                if element:
                    try:
                        is_visible = await element.is_visible()
                        if is_visible:
                            logger.debug(f"Found visible captcha element: {selector}")
                            return True
                    except:
                        pass
                        
            # Check if we've successfully passed
            if "game.php" in page.url:
                logger.debug("On game page - no captcha")
                return False
                
        except Exception as e:
            logger.debug(f"Error checking for captcha: {e}")
            
        return False
        
    async def _solve_manually(self, page: Page) -> bool:
        """Fallback - notify user to solve manually"""
        logger.warning("=" * 60)
        logger.warning("⚠️  MANUAL CAPTCHA SOLVE REQUIRED")
        logger.warning("=" * 60)
        logger.warning("Please solve the captcha in the browser window")
        logger.warning("The bot will continue automatically once solved")
        logger.warning("=" * 60)
        
        # Capture manual solve state
        await screenshot_manager.capture_captcha(page, "manual_solve_required")
        
        # Play notification sound
        try:
            if os.name == 'posix':  # macOS/Linux
                os.system('afplay /System/Library/Sounds/Glass.aiff 2>/dev/null || echo -e "\\a"')
            elif os.name == 'nt':  # Windows
                import winsound
                winsound.Beep(1000, 500)
        except:
            pass
            
        # Wait for user to solve
        max_wait = self.timeout
        check_interval = 3
        elapsed = 0
        
        while elapsed < max_wait:
            # Check if captcha/bot protection is gone
            if not await self._is_captcha_challenge_present(page) and not await self._is_bot_protection_active(page):
                logger.info("✅ Captcha/bot protection solved manually!")
                await screenshot_manager.capture_captcha(page, "manual_solve_success")
                return True
                    
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            if elapsed % 15 == 0:  # Remind every 15 seconds
                remaining = max_wait - elapsed
                logger.warning(f"⏰ Waiting for manual solve... ({remaining}s remaining)")
                
        logger.error("❌ Captcha solve timeout")
        await screenshot_manager.capture_captcha(page, "manual_solve_timeout")
        return False