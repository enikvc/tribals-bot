"""
Anti-Detection Utilities - Human-like behavior simulation
"""
import asyncio
import random
import math
from typing import Optional, Tuple, List
from datetime import datetime, timedelta
from playwright.async_api import Page, ElementHandle

from .logger import setup_logger

logger = setup_logger(__name__)


class HumanBehavior:
    """Simulates human-like behavior patterns"""
    
    def __init__(self):
        self.last_action_time = datetime.now()
        self.action_count = 0
        self.session_start = datetime.now()
        
    async def natural_mouse_move(self, page: Page, target_x: float, target_y: float):
        """Move mouse naturally with bezier curves and variable speed"""
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
            
            # Sometimes double-click accidentally (rare)
            if random.random() < 0.01:
                await page.mouse.click(x, y)
                await asyncio.sleep(random.uniform(0.05, 0.1))
                
            # Actual click with slight position adjustment
            await page.mouse.click(
                x + random.uniform(-2, 2),
                y + random.uniform(-2, 2)
            )
            
            # Sometimes hold click slightly longer
            if random.random() < 0.1:
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
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < duration:
            # Small random movements
            x = random.randint(100, 1820)
            y = random.randint(100, 980)
            
            await self.natural_mouse_move(page, x, y)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
    async def human_scroll(self, page: Page, direction: str = 'random'):
        """Simulate human scrolling patterns"""
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
        if random.random() < 0.05:  # 5% chance
            logger.debug("Simulating tab switch")
            # Trigger blur event
            await page.evaluate("() => { document.activeElement?.blur(); }")
            await asyncio.sleep(random.uniform(2, 10))
            # Return focus
            await page.evaluate("() => { window.focus(); }")
            
    async def micro_pause(self):
        """Small thinking pauses between actions"""
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
    async def fatigue_adjustment(self) -> float:
        """Adjust delays based on session duration (simulate fatigue)"""
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
        session_duration = (datetime.now() - self.session_start).total_seconds() / 3600
        
        # Increasing chance of break over time
        break_chance = min(0.1 * session_duration, 0.5)
        
        return random.random() < break_chance
        
    def get_human_delay(self, base_min: float, base_max: float) -> float:
        """Get delay adjusted for fatigue and randomness"""
        fatigue_multiplier = 1.0
        session_duration = (datetime.now() - self.session_start).total_seconds() / 3600
        
        if session_duration > 1:
            fatigue_multiplier = 1 + (session_duration * 0.1)
            
        delay = random.uniform(base_min, base_max) * fatigue_multiplier
        
        # Occasionally much longer delays (distraction)
        if random.random() < 0.02:
            delay *= random.uniform(3, 5)
            
        return delay


class BrowserFingerprint:
    """Manages browser fingerprinting protection"""
    
    @staticmethod
    def get_enhanced_stealth_script() -> str:
        """Get enhanced stealth JavaScript to inject"""
        return """
        // Enhanced stealth mode
        (function() {
            // Override webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false
            });
            
            // Mock plugins realistically
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        {
                            name: 'Chrome PDF Plugin',
                            description: 'Portable Document Format',
                            filename: 'internal-pdf-viewer',
                            length: 1
                        },
                        {
                            name: 'Chrome PDF Viewer',
                            description: 'Portable Document Format',
                            filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                            length: 1
                        },
                        {
                            name: 'Native Client',
                            description: 'Native Client Executable',
                            filename: 'internal-nacl-plugin',
                            length: 2
                        }
                    ];
                    
                    plugins.forEach(p => {
                        p[0] = {
                            type: 'application/x-google-chrome-pdf',
                            suffixes: 'pdf',
                            description: 'Portable Document Format',
                            enabledPlugin: p
                        };
                    });
                    
                    plugins.item = index => plugins[index];
                    plugins.namedItem = name => plugins.find(p => p.name === name);
                    plugins.refresh = () => {};
                    
                    return plugins;
                }
            });
            
            // Hardware concurrency variation
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => {
                    const cores = [2, 4, 6, 8, 12, 16];
                    return cores[Math.floor(Math.random() * cores.length)];
                }
            });
            
            // Device memory
            if ('deviceMemory' in navigator) {
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => {
                        const memories = [2, 4, 8, 16];
                        return memories[Math.floor(Math.random() * memories.length)];
                    }
                });
            }
            
            // WebGL vendor/renderer
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter.apply(this, arguments);
            };
            
            const getParameter2 = WebGL2RenderingContext.prototype.getParameter;
            WebGL2RenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel Iris OpenGL Engine';
                }
                return getParameter2.apply(this, arguments);
            };
            
            // Battery API
            if ('getBattery' in navigator) {
                navigator.getBattery = async () => ({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 0.98,
                    addEventListener: () => {},
                    removeEventListener: () => {}
                });
            }
            
            // Connection info
            if ('connection' in navigator) {
                Object.defineProperty(navigator.connection, 'rtt', {
                    get: () => 50 + Math.floor(Math.random() * 100)
                });
            }
            
            // Chrome specific
            window.chrome = {
                app: {
                    isInstalled: false,
                    InstallState: {
                        DISABLED: 'disabled',
                        INSTALLED: 'installed',
                        NOT_INSTALLED: 'not_installed'
                    },
                    RunningState: {
                        CANNOT_RUN: 'cannot_run',
                        READY_TO_RUN: 'ready_to_run',
                        RUNNING: 'running'
                    }
                },
                runtime: {
                    OnInstalledReason: {
                        CHROME_UPDATE: 'chrome_update',
                        INSTALL: 'install',
                        SHARED_MODULE_UPDATE: 'shared_module_update',
                        UPDATE: 'update'
                    },
                    OnRestartRequiredReason: {
                        APP_UPDATE: 'app_update',
                        OS_UPDATE: 'os_update',
                        PERIODIC: 'periodic'
                    },
                    PlatformArch: {
                        ARM: 'arm',
                        ARM64: 'arm64',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformNaclArch: {
                        ARM: 'arm',
                        MIPS: 'mips',
                        MIPS64: 'mips64',
                        X86_32: 'x86-32',
                        X86_64: 'x86-64'
                    },
                    PlatformOs: {
                        ANDROID: 'android',
                        CROS: 'cros',
                        LINUX: 'linux',
                        MAC: 'mac',
                        OPENBSD: 'openbsd',
                        WIN: 'win'
                    },
                    RequestUpdateCheckStatus: {
                        NO_UPDATE: 'no_update',
                        THROTTLED: 'throttled',
                        UPDATE_AVAILABLE: 'update_available'
                    },
                    id: undefined,
                    connect: () => {},
                    sendMessage: () => {}
                },
                loadTimes: function() {
                    return {
                        requestTime: Date.now() / 1000 - 100,
                        startLoadTime: Date.now() / 1000 - 99,
                        commitLoadTime: Date.now() / 1000 - 98,
                        finishDocumentLoadTime: Date.now() / 1000 - 97,
                        finishLoadTime: Date.now() / 1000 - 96,
                        firstPaintTime: Date.now() / 1000 - 95,
                        firstPaintAfterLoadTime: 0,
                        navigationType: 'Other',
                        wasFetchedViaSpdy: false,
                        wasNpnNegotiated: true,
                        npnNegotiatedProtocol: 'h2',
                        wasAlternateProtocolAvailable: false,
                        connectionInfo: 'h2'
                    };
                },
                csi: function() {
                    return {
                        onloadT: Date.now(),
                        pageT: Date.now() - 1000,
                        startE: Date.now() - 2000,
                        tran: 15
                    };
                }
            };
            
            // Remove automation-related properties
            delete navigator.__proto__.webdriver;
            
            // Timezone spoofing
            const originalDateTimeFormat = Intl.DateTimeFormat;
            Intl.DateTimeFormat = function(...args) {
                if (args.length === 0) {
                    args.push('it-IT');
                }
                return originalDateTimeFormat.apply(this, args);
            };
            Intl.DateTimeFormat.prototype = originalDateTimeFormat.prototype;
            
            // Canvas fingerprinting protection (adds noise)
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(...args) {
                const context = this.getContext('2d');
                if (context) {
                    // Add invisible noise
                    const imageData = context.getImageData(0, 0, this.width, this.height);
                    for (let i = 0; i < imageData.data.length; i += 4) {
                        imageData.data[i] += Math.random() * 0.1;
                        imageData.data[i+1] += Math.random() * 0.1;
                        imageData.data[i+2] += Math.random() * 0.1;
                    }
                    context.putImageData(imageData, 0, 0);
                }
                return originalToDataURL.apply(this, args);
            };
            
            // Audio fingerprinting protection
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                const originalCreateOscillator = AudioContext.prototype.createOscillator;
                AudioContext.prototype.createOscillator = function() {
                    const oscillator = originalCreateOscillator.apply(this, arguments);
                    const originalConnect = oscillator.connect;
                    oscillator.connect = function() {
                        // Add slight frequency variation
                        if (oscillator.frequency) {
                            oscillator.frequency.value += Math.random() * 0.01;
                        }
                        return originalConnect.apply(this, arguments);
                    };
                    return oscillator;
                };
            }
            
            // Prevent toString detection
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === window.navigator.webdriver) {
                    return 'function webdriver() { [native code] }';
                }
                return originalToString.apply(this, arguments);
            };
            
            // Mock permissions realistically
            if (navigator.permissions) {
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = async (params) => {
                    if (params.name === 'notifications') {
                        return { state: 'prompt', onchange: null };
                    }
                    return originalQuery.apply(navigator.permissions, arguments);
                };
            }
        })();
        """


class NetworkBehavior:
    """Simulates realistic network behavior"""
    
    @staticmethod
    async def add_request_headers(route, request):
        """Add realistic headers to requests"""
        headers = request.headers.copy()
        
        # Add random referer sometimes
        if random.random() < 0.7 and 'referer' not in headers:
            headers['referer'] = request.url.split('?')[0]
            
        # Vary accept-encoding
        if random.random() < 0.1:
            headers['accept-encoding'] = 'gzip, deflate'
            
        # Add DNT header sometimes
        if random.random() < 0.3:
            headers['dnt'] = '1'
            
        # Realistic cache headers
        if random.random() < 0.5:
            headers['cache-control'] = random.choice([
                'max-age=0',
                'no-cache',
                'no-cache, no-store, must-revalidate'
            ])
            
        await route.continue_(headers=headers)
        
    @staticmethod
    async def simulate_network_conditions(page: Page):
        """Simulate variable network conditions"""
        if random.random() < 0.05:  # 5% chance of slow network
            await page.context.set_offline(True)
            await asyncio.sleep(random.uniform(0.5, 2))
            await page.context.set_offline(False)
            
    @staticmethod
    def get_random_user_agent() -> str:
        """Get a random realistic user agent"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
        ]
        return random.choice(user_agents)


class SessionBehavior:
    """Manages session-level behavior patterns"""
    
    def __init__(self):
        self.action_history: List[Tuple[datetime, str]] = []
        self.break_schedule = self._generate_break_schedule()
        
    def _generate_break_schedule(self) -> List[datetime]:
        """Generate random break times for the session"""
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