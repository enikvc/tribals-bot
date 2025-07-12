"""
Base Automation Class - Updated with shared anti-detection manager
"""
import asyncio
import random
import os
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from playwright.async_api import Page

from ..utils.logger import setup_logger
from ..utils.screenshot_manager import screenshot_manager

logger = setup_logger(__name__)


class BaseAutomation(ABC):
    """Base class for all automation scripts with human-like behavior"""
    
    def __init__(self, config: Dict[str, Any], browser_manager):
        self.config = config
        self.browser_manager = browser_manager
        self.script_config = config['scripts'][self.name]
        self.running = False
        self.paused = False
        self.page: Optional[Page] = None
        self.attempts = 0
        
        # Monitoring metrics
        self.run_count = 0
        self.error_count = 0
        self.last_run_time = None
        self.next_run_time = None
        self.start_time = None
        
        # Use shared anti-detection manager from browser_manager
        # This ensures all scripts share the same suspension state
        if hasattr(browser_manager, 'captcha_detector') and browser_manager.captcha_detector:
            self.anti_detection = browser_manager.captcha_detector.anti_detection_manager
            self.human = self.anti_detection.human
            self.session = self.anti_detection.session
        else:
            # Fallback if not initialized yet
            from ..utils.anti_detection import AntiDetectionManager
            self.anti_detection = AntiDetectionManager()
            self.human = self.anti_detection.human
            self.session = self.anti_detection.session
            
        # Get village ID from environment or use default
        self.village_id = os.getenv('TRIBALS_VILLAGE_ID', '306')
        
    @property
    @abstractmethod
    def name(self) -> str:
        """Script name"""
        pass
        
    @property
    @abstractmethod
    def url_pattern(self) -> str:
        """URL pattern for this script"""
        pass
        
    @abstractmethod
    async def run_automation(self):
        """Main automation logic - must be implemented by subclasses"""
        pass
        
    async def start(self):
        """Start the automation"""
        if self.running:
            logger.warning(f"⚠️ {self.name} is already running")
            return
            
        logger.info(f"🟢 Starting {self.name}")
        self.running = True
        self.attempts = 0
        self.start_time = datetime.now()
        
        try:
            # Get page
            self.page = await self.browser_manager.get_page(
                self.name, 
                self.build_url()
            )
            
            # Add initial human-like delay (only if not suspended)
            if not self.anti_detection.is_suspended():
                await self.human_delay(2000, 5000)
                
                # Initial random mouse movement
                await self.human.random_mouse_movement(self.page, 1.5)
            
            # Run automation loop
            while self.running and self.is_within_active_hours():
                try:
                    # Check for scheduled breaks (only if not suspended)
                    if not self.anti_detection.is_suspended():
                        should_break, break_duration = self.session.should_take_break()
                        if should_break:
                            logger.info(f"☕ Taking a {break_duration}s break")
                            await asyncio.sleep(break_duration)
                            # Simulate return with mouse movement
                            await self.human.random_mouse_movement(self.page, 2.0)
                        
                    await self.run_automation()
                    self.run_count += 1
                    self.last_run_time = datetime.now()
                    logger.debug(f"✅ {self.name} completed run #{self.run_count}")
                except Exception as e:
                    self.error_count += 1
                    logger.error(f"❌ Error in {self.name}: {e}", exc_info=True)
                    # Capture error screenshot
                    await self.capture_error_screenshot(str(e))
                    await asyncio.sleep(10)  # Wait before retry
                    
        except Exception as e:
            logger.error(f"❌ Fatal error in {self.name}: {e}", exc_info=True)
            await self.capture_error_screenshot(f"fatal_error_{str(e)}")
            self.running = False
            
    async def stop(self):
        """Stop the automation"""
        if not self.running:
            return
            
        logger.info(f"🔴 Stopping {self.name}")
        self.running = False
        
        # Close page
        await self.browser_manager.close_page(self.name)
        
    def is_within_active_hours(self) -> bool:
        """Check if current time is within active hours"""
        now = datetime.now()
        current_hour = now.hour
        
        start_hour = self.config['active_hours']['start']
        end_hour = self.config['active_hours']['end']
        
        if start_hour < end_hour:
            return start_hour <= current_hour < end_hour
        else:
            # Crosses midnight
            return current_hour >= start_hour or current_hour < end_hour
            
    def build_url(self) -> str:
        """Build URL for this script"""
        base_url = self.config['server']['base_url']
        return f"{base_url}/game.php?village={self.village_id}&{self.url_pattern}"
        
    async def human_delay(self, min_ms: int, max_ms: int):
        """Add human-like delay with fatigue adjustment"""
        # If suspended, use minimal delay
        if self.anti_detection.is_suspended():
            await asyncio.sleep(0.1)
            return
            
        delay = self.human.get_human_delay(min_ms / 1000, max_ms / 1000)
        
        # Apply session activity multiplier
        delay *= self.session.get_action_delay_multiplier()
        
        await asyncio.sleep(delay)
        
    async def click_with_delay(self, selector: str, min_delay: int = 100, max_delay: int = 300) -> bool:
        """Click element with human-like behavior"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=5000)
            if element:
                # Record action
                self.session.record_action('click')
                
                # Random mouse activity before click (only if not suspended)
                if not self.anti_detection.is_suspended() and random.random() < 0.3:
                    await self.human.random_mouse_movement(self.page, 0.5)
                
                # Human-like click
                success = await self.human.human_click(self.page, element)
                
                if success:
                    logger.debug(f"🖱️ Clicked {selector}")
                    
                    # Sometimes move mouse away after click (only if not suspended)
                    if not self.anti_detection.is_suspended() and random.random() < 0.2:
                        await self.human.random_mouse_movement(self.page, 0.3)
                        
                return success
        except Exception as e:
            logger.debug(f"Could not click {selector}: {e}")
        return False
        
    async def type_with_delay(self, selector: str, text: str, delay_per_char: int = 50) -> bool:
        """Type text with human-like behavior"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=5000)
            if element:
                # Record action
                self.session.record_action('type')
                
                # Click before typing
                await self.human.human_click(self.page, element)
                
                if not self.anti_detection.is_suspended():
                    await self.human.micro_pause()
                
                # Human-like typing
                await self.human.human_type(self.page, text)
                
                # Sometimes tab away (only if not suspended)
                if not self.anti_detection.is_suspended() and random.random() < 0.1:
                    await self.page.keyboard.press('Tab')
                    
                return True
        except Exception as e:
            logger.debug(f"Could not type in {selector}: {e}")
        return False
        
    async def wait_and_get_text(self, selector: str, timeout: int = 5000) -> Optional[str]:
        """Wait for element and get its text with reading simulation"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                text = await element.text_content()
                
                # Simulate reading time (only if not suspended)
                if not self.anti_detection.is_suspended() and text and len(text) > 20:
                    await self.human.reading_pause(len(text))
                    
                return text
        except:
            pass
        return None
        
    async def get_number_from_element(self, selector: str, default: int = 0) -> int:
        """Extract number from element text"""
        text = await self.wait_and_get_text(selector)
        if text:
            import re
            match = re.search(r'\d+', text)
            if match:
                return int(match.group())
        return default
        
    async def perform_random_actions(self):
        """Perform random human-like actions"""
        # Skip if suspended
        if self.anti_detection.is_suspended():
            return
            
        action = random.choice([
            'mouse_move',
            'scroll',
            'tab_switch',
            'nothing'
        ])
        
        if action == 'mouse_move':
            await self.human.random_mouse_movement(self.page, 1.0)
        elif action == 'scroll':
            await self.human.human_scroll(self.page)
        elif action == 'tab_switch':
            await self.human.random_tab_switch(self.page)
        # 'nothing' = just wait
        
    async def simulate_page_scan(self):
        """Simulate scanning/reading a page"""
        # Skip if suspended
        if self.anti_detection.is_suspended():
            return
            
        # Move mouse around as if reading
        for _ in range(random.randint(2, 4)):
            x = random.randint(200, 1600)
            y = random.randint(200, 800)
            await self.human.natural_mouse_move(self.page, x, y)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
        # Maybe scroll
        if random.random() < 0.5:
            await self.human.human_scroll(self.page)
            
    # Screenshot helper methods
    async def capture_error_screenshot(self, error_description: str) -> Optional[str]:
        """Capture screenshot when error occurs"""
        if self.page:
            return await screenshot_manager.capture_error(self.page, self.name, error_description)
        return None
        
    async def capture_automation_step(self, step: str) -> Optional[str]:
        """Capture screenshot of automation step"""
        if self.page:
            return await screenshot_manager.capture_automation(self.page, self.name, step)
        return None
        
    async def capture_page_state(self, state: str) -> Optional[str]:
        """Capture current page state"""
        if self.page:
            return await screenshot_manager.capture_page_state(self.page, self.name, state)
        return None
        
    async def capture_debug_screenshot(self, context: str) -> Optional[str]:
        """Capture debug screenshot"""
        if self.page:
            return await screenshot_manager.capture_debug(self.page, context)
        return None