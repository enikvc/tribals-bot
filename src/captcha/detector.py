"""
Captcha Detector - Monitors for captcha challenges and bot protection
"""
import asyncio
from typing import Set, Optional
from playwright.async_api import Page

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class CaptchaDetector:
    """Detects captcha challenges and bot protection across all pages"""
    
    def __init__(self, browser_manager):
        self.browser_manager = browser_manager
        self.monitoring = False
        self.detected_captcha = False
        self.monitored_pages: Set[Page] = set()
        
    async def start_monitoring(self):
        """Start monitoring for captchas and bot protection"""
        self.monitoring = True
        logger.info("👁️ Started captcha/bot protection monitoring")
        
        while self.monitoring:
            try:
                # Skip if we're already handling something
                if self.detected_captcha:
                    await asyncio.sleep(5)
                    continue
                    
                # Check all open pages
                for script_name, page in list(self.browser_manager.pages.items()):
                    if not page.is_closed():
                        # Check for bot protection page
                        if await self.check_for_bot_protection(page):
                            await self.handle_bot_protection(script_name, page)
                            break  # Handle one at a time
                        # Check for captcha
                        elif await self.check_page_for_captcha(page):
                            await self.handle_captcha_detection(script_name, page)
                            break  # Handle one at a time
                            
                await asyncio.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error in captcha monitoring: {e}")
                await asyncio.sleep(5)
                
    def stop(self):
        """Stop monitoring"""
        self.monitoring = False
        logger.info("👁️ Stopped captcha monitoring")
        
    async def check_for_bot_protection(self, page: Page) -> bool:
        """Check if bot protection page is shown"""
        # Don't check if we're already handling it
        if self.detected_captcha:
            return False
            
        try:
            # Check for the bot protection row with the button
            bot_protection = await page.query_selector('td.bot-protection-row')
            if bot_protection:
                # Check if the start button is present
                start_button = await page.query_selector('td.bot-protection-row a.btn.btn-default')
                if start_button:
                    button_text = await start_button.text_content()
                    if button_text and 'Inizio del controllo' in button_text:
                        logger.warning("🚨 Bot protection page detected with start button!")
                        return True
                        
            return False
            
        except Exception as e:
            logger.debug(f"Error checking for bot protection: {e}")
            return False
        
    async def check_page_for_captcha(self, page: Page) -> bool:
        """Check if page has captcha"""
        try:
            # Check for bot protection quest (Tribals specific)
            quest_selector = '#botprotection_quest[data-title="Protezione bot"]'
            quest_element = await page.query_selector(quest_selector)
            if quest_element:
                logger.warning("🚨 Bot protection quest detected!")
                return True
                
            # Check for captcha page block (without the start button)
            block_selector = 'td.bot-protection-row h2'
            block_element = await page.query_selector(block_selector)
            if block_element:
                text = await block_element.text_content()
                if text and 'Protezione bot' in text:
                    # Check if there's NO start button (captcha is active)
                    start_button = await page.query_selector('td.bot-protection-row a.btn.btn-default')
                    if not start_button:
                        logger.warning("🚨 Bot protection captcha active!")
                        return True
                    
            # Check for hCaptcha iframe
            captcha_selectors = [
                '.h-captcha',
                'iframe[src*="hcaptcha"]',
                'div[id*="hcaptcha"]',
                '[data-hcaptcha-widget-id]',
                'td.bot-protection-row .captcha .h-captcha'  # Specific to bot protection
            ]
            
            for selector in captcha_selectors:
                element = await page.query_selector(selector)
                if element:
                    try:
                        if await element.is_visible():
                            logger.warning(f"🚨 Captcha detected via {selector}")
                            return True
                    except:
                        # Element might be in iframe
                        logger.warning(f"🚨 Captcha detected via {selector} (in iframe)")
                        return True
                        
        except Exception as e:
            logger.debug(f"Error checking for captcha: {e}")
            
        return False
        
    async def handle_bot_protection(self, script_name: str, page: Page):
        """Handle bot protection page"""
        if self.detected_captcha:
            return  # Already handling
            
        self.detected_captcha = True
        logger.error(f"🚨 BOT PROTECTION PAGE DETECTED on {script_name}!")
        
        # Avoid circular import by checking if solver is already imported
        try:
            from .solver import CaptchaSolver
        except ImportError as e:
            logger.error(f"❌ Cannot import CaptchaSolver: {e}")
            return
        
        # Pause all automations (don't stop them completely to keep pages open)
        scheduler = getattr(self.browser_manager, 'scheduler', None)
        if scheduler:
            await scheduler.pause_all_automations("Bot protection detected")
            
        try:
            # Use solver to handle bot protection on the current page
            solver = CaptchaSolver(self.browser_manager.config)
            success = await solver.solve_bot_protection(page)
            
            if success:
                logger.info("✅ Bot protection passed successfully!")
                self.detected_captcha = False
                # Resume automations
                if scheduler:
                    await scheduler.resume_after_captcha()
            else:
                logger.error("❌ Failed to pass bot protection - manual intervention required")
                # Keep detected_captcha = True to prevent repeated attempts
        except Exception as e:
            logger.error(f"❌ Error handling bot protection: {e}", exc_info=True)
            self.detected_captcha = False  # Reset to allow retry
            
    async def handle_captcha_detection(self, script_name: str, page: Page):
        """Handle captcha detection"""
        if self.detected_captcha:
            return  # Already handling
            
        self.detected_captcha = True
        logger.error(f"🚨 CAPTCHA DETECTED on {script_name} page!")
        
        # Import solver here to avoid circular imports
        from .solver import CaptchaSolver
        
        # Pause all automations (don't stop them completely)
        scheduler = getattr(self.browser_manager, 'scheduler', None)
        if scheduler:
            await scheduler.pause_all_automations("Captcha detected")
            
        try:
            # Try to solve captcha
            solver = CaptchaSolver(self.browser_manager.config)
            success = await solver.solve_captcha(page)
            
            if success:
                logger.info("✅ Captcha solved successfully!")
                self.detected_captcha = False
                # Resume automations
                if scheduler:
                    await scheduler.resume_after_captcha()
            else:
                logger.error("❌ Failed to solve captcha - manual intervention required")
                # Keep detected_captcha = True to prevent repeated attempts
        except Exception as e:
            logger.error(f"❌ Error handling captcha: {e}", exc_info=True)
            self.detected_captcha = False  # Reset to allow retry