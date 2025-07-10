"""
Anti-Detection Utilities - Human-like behavior simulation with captcha safety
"""
import asyncio
import random
import math
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from playwright.async_api import Page, ElementHandle

from .logger import setup_logger

logger = setup_logger(__name__)


class AntiDetectionManager:
    """Manages anti-detection behaviors with suspension capability"""
    
    def __init__(self):
        self.suspended = False
        self.suspension_reason = ""
        self.human = HumanBehavior(self)
        self.session = SessionBehavior(self)
        
    def suspend(self, reason: str = "captcha"):
        """Suspend all anti-detection behaviors"""
        self.suspended = True
        self.suspension_reason = reason
        logger.info(f"🛑 Anti-detection suspended: {reason}")
        
    def resume(self):
        """Resume anti-detection behaviors"""
        self.suspended = False
        self.suspension_reason = ""
        logger.info("▶️ Anti-detection resumed")
        
    def is_suspended(self) -> bool:
        """Check if behaviors are suspended"""
        return self.suspended


class HumanBehavior:
    """Simulates human-like behavior patterns with suspension support"""
    
    def __init__(self, manager: AntiDetectionManager):
        self.manager = manager
        self.last_action_time = datetime.now()
        self.action_count = 0
        self.session_start = datetime.now()
        
    async def natural_mouse_move(self, page: Page, target_x: float, target_y: float):
        """Move mouse naturally with bezier curves and variable speed"""
        # Skip if suspended
        if self.manager.is_suspended():
            # Direct move without animation during suspension
            await page.mouse.move(target_x, target_y)
            return
            
        try:
            # Get current position
            current_x = random.randint(0, 1920)  # Start from random position
            current_y = random.randint(0, 1080)
            
            # Calculate distance
            distance = math.sqrt((target_x - current_x)**2 + (target_y - current_y)**2)
            
            # More steps for longer distances
            steps = max(20, int(distance / 25))
            
            # Generate control points for bezier curve
            cp1_x = current_x + (target_x - current_x) * 0.25 + random.uniform(-50, 50)
            cp1_y = current_y + (target_y - current_y) * 0.25 + random.uniform(-50, 50)
            cp2_x = current_x + (target_x - current_x) * 0.75 + random.uniform(-50, 50)
            cp2_y = current_y + (target_y - current_y) * 0.75 + random.uniform(-50, 50)
            
            for i in range(steps + 1):
                t = i / steps
                
                # Bezier curve formula
                x = (1-t)**3 * current_x + 3*(1-t)**2*t * cp1_x + 3*(1-t)*t**2 * cp2_x + t**3 * target_x
                y = (1-t)**3 * current_y + 3*(1-t)**2*t * cp1_y + 3*(1-t)*t**2 * cp2_y + t**3 * target_y
                
                # Add small random jitter
                x += random.uniform(-2, 2)
                y += random.uniform(-2, 2)
                
                await page.mouse.move(x, y)
                
                # Variable speed - slower at start/end
                if i < 3 or i > steps - 3:
                    await asyncio.sleep(random.uniform(0.01, 0.02))
                else:
                    await asyncio.sleep(random.uniform(0.005, 0.01))
                    
        except Exception as e:
            logger.debug(f"Mouse move error: {e}")
            
    async def human_click(self, page: Page, element: Optional[ElementHandle] = None, 
                         x: Optional[float] = None, y: Optional[float] = None):
        """Click with human-like behavior"""
        # During suspension, do simple click
        if self.manager.is_suspended():
            if element:
                await element.click()
            elif x is not None and y is not None:
                await page.mouse.click(x, y)
            return True
            
        try:
            if element:
                box = await element.bounding_box()
                if box:
                    # Click somewhere inside element, not always center
                    x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
                    y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
                else:
                    return False
                    
            if x is None or y is None:
                return False
                
            # Move to position naturally
            await self.natural_mouse_move(page, x, y)
            
            # Small pause before click (human reaction time)
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Sometimes double-click accidentally (rare) - NOT during captcha
            if random.random() < 0.01 and not self.manager.is_suspended():
                await page.mouse.click(x, y)
                await asyncio.sleep(random.uniform(0.05, 0.1))
                
            # Actual click with slight position adjustment
            await page.mouse.click(
                x + random.uniform(-2, 2),
                y + random.uniform(-2, 2)
            )
            
            # Sometimes hold click slightly longer - NOT during captcha
            if random.random() < 0.1 and not self.manager.is_suspended():
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.15))
                await page.mouse.up()
                
            return True
            
        except Exception as e:
            logger.debug(f"Click error: {e}")
            return False
            
    async def human_type(self, page: Page, text: str, element: Optional[ElementHandle] = None):
        """Type with human-like patterns including mistakes and corrections"""
        if element:
            await self.human_click(page, element)
        
        # No typos during captcha/suspension
        if self.manager.is_suspended():
            await page.keyboard.type(text)
            return
        
        for i, char in enumerate(text):
            # Occasionally make typos (1% chance)
            if random.random() < 0.01 and i > 0 and i < len(text) - 1:
                # Type wrong character
                wrong_chars = 'asdfghjkl' if char.isalpha() else '1234567890'
                wrong_char = random.choice(wrong_chars)
                await page.keyboard.type(wrong_char)
                
                # Realize mistake after a moment
                await asyncio.sleep(random.uniform(0.2, 0.5))
                await page.keyboard.press('Backspace')
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # Type the character
            await page.keyboard.type(char)
            
            # Variable typing speed
            if char == ' ':
                # Longer pause on spaces
                await asyncio.sleep(random.uniform(0.05, 0.15))
            elif char in '.!?,;:':
                # Pause on punctuation
                await asyncio.sleep(random.uniform(0.1, 0.3))
            elif random.random() < 0.1:
                # Random longer pauses (thinking)
                await asyncio.sleep(random.uniform(0.2, 0.5))
            else:
                # Normal typing speed with variation
                base_delay = random.uniform(0.05, 0.15)
                # Faster typing for common words
                if i > 3 and text[i-3:i+1].lower() in ['the ', 'and ', 'ing ', 'ion ']:
                    base_delay *= 0.7
                await asyncio.sleep(base_delay)
                
    async def random_mouse_movement(self, page: Page, duration: float = 2.0):
        """Random idle mouse movements"""
        # Skip completely during suspension
        if self.manager.is_suspended():
            return
            
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < duration:
            # Small random movements
            x = random.randint(100, 1820)
            y = random.randint(100, 980)
            
            await self.natural_mouse_move(page, x, y)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
    async def human_scroll(self, page: Page, direction: str = 'random'):
        """Simulate human scrolling patterns"""
        # Skip during suspension
        if self.manager.is_suspended():
            return
            
        if direction == 'random':
            direction = random.choice(['up', 'down'])
            
        # Variable scroll amounts
        scroll_amount = random.randint(100, 500)
        if direction == 'up':
            scroll_amount = -scroll_amount
            
        # Sometimes scroll in small increments
        if random.random() < 0.3:
            increments = random.randint(2, 5)
            for _ in range(increments):
                await page.mouse.wheel(0, scroll_amount // increments)
                await asyncio.sleep(random.uniform(0.05, 0.15))
        else:
            await page.mouse.wheel(0, scroll_amount)
            
        # Sometimes overshoot and correct
        if random.random() < 0.1:
            await asyncio.sleep(random.uniform(0.2, 0.5))
            await page.mouse.wheel(0, -scroll_amount // 4)
            
    async def reading_pause(self, text_length: int):
        """Simulate reading time based on content length"""
        # Minimal pause during suspension
        if self.manager.is_suspended():
            await asyncio.sleep(0.1)
            return
            
        # Average reading speed: 200-300 words per minute
        words = text_length / 5  # Average word length
        reading_speed = random.uniform(200, 300)
        base_time = (words / reading_speed) * 60
        
        # Add variation
        actual_time = base_time * random.uniform(0.8, 1.2)
        
        # Sometimes skim (read faster)
        if random.random() < 0.2:
            actual_time *= 0.5
            
        await asyncio.sleep(max(0.5, actual_time))
        
    async def random_tab_switch(self, page: Page):
        """Simulate switching tabs (losing focus)"""
        # Never switch tabs during suspension
        if self.manager.is_suspended():
            return
            
        if random.random() < 0.05:  # 5% chance
            logger.debug("Simulating tab switch")
            # Trigger blur event
            await page.evaluate("() => { document.activeElement?.blur(); }")
            await asyncio.sleep(random.uniform(2, 10))
            # Return focus
            await page.evaluate("() => { window.focus(); }")
            
    async def micro_pause(self):
        """Small thinking pauses between actions"""
        if self.manager.is_suspended():
            return
            
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
    async def fatigue_adjustment(self) -> float:
        """Adjust delays based on session duration (simulate fatigue)"""
        if self.manager.is_suspended():
            return 1.0
            
        session_duration = (datetime.now() - self.session_start).total_seconds() / 3600
        
        # Increase delays over time
        if session_duration < 1:
            return 1.0
        elif session_duration < 2:
            return random.uniform(1.0, 1.2)
        elif session_duration < 4:
            return random.uniform(1.1, 1.4)
        else:
            return random.uniform(1.2, 1.6)
            
    async def random_break(self) -> bool:
        """Decide if it's time for a break"""
        # No breaks during suspension
        if self.manager.is_suspended():
            return False
            
        session_duration = (datetime.now() - self.session_start).total_seconds() / 3600
        
        # Increasing chance of break over time
        break_chance = min(0.1 * session_duration, 0.5)
        
        return random.random() < break_chance
        
    def get_human_delay(self, base_min: float, base_max: float) -> float:
        """Get delay adjusted for fatigue and randomness"""
        if self.manager.is_suspended():
            return 0  # No delay during suspension
            
        fatigue_multiplier = 1.0
        session_duration = (datetime.now() - self.session_start).total_seconds() / 3600
        
        if session_duration > 1:
            fatigue_multiplier = 1 + (session_duration * 0.1)
            
        delay = random.uniform(base_min, base_max) * fatigue_multiplier
        
        # Occasionally much longer delays (distraction)
        if random.random() < 0.02:
            delay *= random.uniform(3, 5)
            
        return delay


class SessionBehavior:
    """Manages session-level behavior patterns"""
    
    def __init__(self, manager: AntiDetectionManager):
        self.manager = manager
        self.action_history: List[Tuple[datetime, str]] = []
        self.break_schedule = self._generate_break_schedule()
        
    def _generate_break_schedule(self) -> List[datetime]:
        """Generate random break times for the session"""
        if self.manager.is_suspended():
            return []
            
        breaks = []
        current_time = datetime.now()
        
        for i in range(random.randint(2, 5)):  # 2-5 breaks per session
            break_time = current_time + timedelta(
                hours=random.uniform(0.5, 2),
                minutes=random.randint(0, 59)
            )
            breaks.append(break_time)
            
        return sorted(breaks)
        
    def should_take_break(self) -> Tuple[bool, int]:
        """Check if it's time for a break"""
        if self.manager.is_suspended():
            return False, 0
            
        now = datetime.now()
        
        for break_time in self.break_schedule:
            if now >= break_time:
                self.break_schedule.remove(break_time)
                duration = random.randint(60, 600)  # 1-10 minutes
                return True, duration
                
        return False, 0
        
    def record_action(self, action_type: str):
        """Record an action for pattern analysis"""
        self.action_history.append((datetime.now(), action_type))
        
        # Keep only last 100 actions
        if len(self.action_history) > 100:
            self.action_history = self.action_history[-100:]
            
    def get_action_delay_multiplier(self) -> float:
        """Get delay multiplier based on recent activity"""
        if self.manager.is_suspended():
            return 0
            
        if len(self.action_history) < 10:
            return 1.0
            
        # Check actions in last minute
        recent_actions = [
            a for a in self.action_history 
            if (datetime.now() - a[0]).total_seconds() < 60
        ]
        
        # Slow down if too many recent actions
        if len(recent_actions) > 20:
            return random.uniform(1.5, 2.0)
        elif len(recent_actions) > 10:
            return random.uniform(1.2, 1.5)
        else:
            return 1.0


# Placeholder for backwards compatibility
class NetworkBehavior:
    """Deprecated - no longer needed since we use authentic headers"""
    pass


# Browser fingerprint still needed for webdriver detection, but no header/UA manipulation
class BrowserFingerprint:
    """Manages browser fingerprinting protection - ONLY JavaScript injection"""
    
    @staticmethod
    def get_enhanced_stealth_script() -> str:
        """Get enhanced stealth JavaScript to inject - focuses on webdriver detection only"""
        return """
        // Enhanced stealth mode - webdriver detection only
        (function() {
            // Override webdriver detection
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Remove automation-related properties
            delete navigator.__proto__.webdriver;
            
            // Chrome automation detection
            if (window.chrome) {
                Object.defineProperty(window.chrome, 'runtime', {
                    get: () => ({
                        connect: () => {},
                        sendMessage: () => {},
                        id: undefined
                    })
                });
            }
            
            // Prevent toString detection for webdriver
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === window.navigator.webdriver) {
                    return 'function webdriver() { [native code] }';
                }
                return originalToString.apply(this, arguments);
            };
            
            // Remove common automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        })();
        """