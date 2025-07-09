"""
Alternative Captcha Solver - Fallback when hcaptcha-challenger is not available
"""
import asyncio
from typing import Optional
from playwright.async_api import Page

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class CaptchaSolverFallback:
    """Fallback captcha solver - notifies user to solve manually"""
    
    def __init__(self, config):
        self.config = config
        
    async def solve_captcha(self, page: Page) -> bool:
        """Notify user to solve captcha manually"""
        logger.warning("🔧 Captcha detected - manual solving required")
        logger.warning("⏰ Please solve the captcha within 2 minutes")
        
        # Wait for user to solve (max 2 minutes)
        max_wait = 120  # seconds
        check_interval = 5  # seconds
        elapsed = 0
        
        while elapsed < max_wait:
            # Check if captcha is still present
            from .detector import CaptchaDetector
            detector = CaptchaDetector(None)
            
            if not await detector.check_page_for_captcha(page):
                logger.info("✅ Captcha solved manually!")
                return True
                
            await asyncio.sleep(check_interval)
            elapsed += check_interval
            
            if elapsed % 30 == 0:  # Remind every 30 seconds
                logger.warning(f"⏰ Still waiting for manual captcha solve... ({max_wait - elapsed}s remaining)")
        
        logger.error("❌ Captcha solve timeout - captcha was not solved in time")
        return False
