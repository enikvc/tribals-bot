"""
Browser Manager - Fixed to avoid refresh after login
"""
import asyncio
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from contextlib import asynccontextmanager

from ..utils.logger import setup_logger
from ..utils.anti_detection import HumanBehavior, BrowserFingerprint, NetworkBehavior
from ..captcha.solver import CaptchaSolver
from ..captcha.detector import CaptchaDetector
from .login_handler import LoginHandler

logger = setup_logger(__name__)


class BrowserManager:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.captcha_detector = CaptchaDetector(self)
        self.anti_detection_manager = self.captcha_detector.anti_detection_manager
        self.login_handler = LoginHandler(config, self.anti_detection_manager)
        self.main_context: Optional[BrowserContext] = None
        self.scheduler = None  # Will be set by scheduler
        self.game_page = None  # Store reference to main game page
        
        # Setup persistent data directory
        self.user_data_dir = Path(config.get('browser', {}).get('user_data_dir', './browser_data'))
        self._ensure_data_directory()
        
    def _ensure_data_directory(self):
        """Ensure browser data directory exists with proper structure"""
        # Create main directory
        self.user_data_dir.mkdir(exist_ok=True, parents=True)
        
        # Create subdirectories
        subdirs = ['Default', 'Cache', 'Local Storage']
        for subdir in subdirs:
            (self.user_data_dir / subdir).mkdir(exist_ok=True)
            
        logger.info(f"📁 Browser data directory: {self.user_data_dir.absolute()}")
        
    async def initialize(self):
        """Initialize Playwright and browser with persistent storage"""
        logger.info("🌐 Initializing browser with persistent storage...")
        
        self.playwright = await async_playwright().start()
        
        browser_config = self.config.get('browser', {})
        
        # Use authentic Chrome user agent
        user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        
        # Check if incognito mode is enabled
        incognito_mode = os.getenv('INCOGNITO_MODE', 'false').lower() == 'true'
        
        if incognito_mode:
            logger.info("🥷 Incognito mode enabled - no persistent storage")
            # Launch browser without persistent context for incognito
            self.browser = await self.playwright.chromium.launch(
                headless=browser_config.get('headless', False),
                slow_mo=browser_config.get('slow_mo', 0),
                args=[
                    '--incognito',  # Force incognito mode
                    # Chrome flags for better stealth
                    '--disable-blink-features=AutomationControlled',
                    '--exclude-switches=enable-automation',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certificate-errors',
                    '--ignore-certificate-errors-spki-list',
                    '--disable-gpu',
                    '--allow-running-insecure-content',
                    '--no-zygote',
                    '--no-xshm',
                    '--deterministic-fetch',
                    '--disable-features=RendererCodeIntegrity',
                    '--enable-features=NetworkService,NetworkServiceInProcess',
                    '--disable-features=VizDisplayCompositor',
                    '--force-color-profile=srgb',
                    '--disable-extensions',
                    '--disable-plugins-discovery',
                    '--disable-default-apps',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--password-store=basic',
                    '--use-mock-keychain',
                    '--force-fieldtrials=*BackgroundTracing/default/',
                    '--flag-switches-begin',
                    '--flag-switches-end',
                    '--origin-trial-disabled-features=WebGPU',
                    # Additional stealth flags
                    '--disable-features=AutomationControlled',
                    '--disable-blink-features=AutomationControlled',
                    '--user-agent=' + user_agent
                ]
            )
            
            # Create a new context in incognito mode
            self.main_context = await self.browser.new_context(
                viewport=browser_config.get('viewport', {'width': 1440, 'height': 720}),
                screen={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                locale='en-US',
                timezone_id='Europe/Rome',
                permissions=['geolocation', 'notifications'],
                geolocation={'latitude': 41.9028, 'longitude': 12.4964},  # Rome
                color_scheme='light',
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                java_script_enabled=True,
                bypass_csp=True,
                accept_downloads=True,
                ignore_https_errors=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-CH-UA': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                    'Sec-CH-UA-Mobile': '?0',
                    'Sec-CH-UA-Platform': '"macOS"'
                }
            )
        else:
            logger.info("💾 Persistent mode enabled - data will be saved")
            # Launch browser using persistent context
            self.main_context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir.absolute()),
                headless=browser_config.get('headless', False),
                slow_mo=browser_config.get('slow_mo', 0),
                viewport=browser_config.get('viewport', {'width': 1440, 'height': 720}),
                screen={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                locale='en-US',
                timezone_id='Europe/Rome',
                permissions=['geolocation', 'notifications'],
                geolocation={'latitude': 41.9028, 'longitude': 12.4964},  # Rome
                color_scheme='light',
                device_scale_factor=1,
                is_mobile=False,
                has_touch=False,
                java_script_enabled=True,
                bypass_csp=True,
                accept_downloads=True,
                ignore_https_errors=True,
                # Authentic headers matching your session
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                    'Accept-Encoding': 'gzip, deflate, br, zstd',
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-CH-UA': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
                    'Sec-CH-UA-Mobile': '?0',
                    'Sec-CH-UA-Platform': '"macOS"'
                },
                args=[
                    # Chrome flags for better stealth
                    '--disable-blink-features=AutomationControlled',
                    '--exclude-switches=enable-automation',
                    '--disable-dev-shm-usage',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-position=0,0',
                    '--ignore-certificate-errors',
                    '--ignore-certificate-errors-spki-list',
                    '--disable-gpu',
                    '--allow-running-insecure-content',
                    '--no-zygote',
                    '--no-xshm',
                    '--deterministic-fetch',
                    '--disable-features=RendererCodeIntegrity',
                    '--enable-features=NetworkService,NetworkServiceInProcess',
                    '--disable-features=VizDisplayCompositor',
                    '--force-color-profile=srgb',
                    '--disable-extensions',
                    '--profile-directory=Default',
                    '--disable-plugins-discovery',
                    '--disable-default-apps',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--password-store=basic',
                    '--use-mock-keychain',
                    '--force-fieldtrials=*BackgroundTracing/default/',
                    '--flag-switches-begin',
                    '--flag-switches-end',
                    '--origin-trial-disabled-features=WebGPU',
                    # Additional stealth flags
                    '--disable-features=AutomationControlled',
                    '--disable-blink-features=AutomationControlled',
                    '--user-agent=' + user_agent
                ]
            )
        
        # Set up route interception for headers
        await self.main_context.route('**/*', self._intercept_requests)
        
        # Inject enhanced stealth scripts
        await self._inject_stealth_scripts(self.main_context)
        
        # Handle login
        logged_in = await self.login_handler.ensure_logged_in(self.main_context)
        if not logged_in:
            logger.error("❌ Failed to login - stopping bot")
            raise Exception("Login failed")
        
        # Clean up tabs and verify we have the game page
        await self._cleanup_and_verify_game_page()
        
        # Verify localStorage persistence
        await self._verify_and_log_storage()
        
        # Check for bot protection WITHOUT refreshing
        logger.info("🔍 Checking for bot protection before starting automations...")
        await self.check_initial_bot_protection()
        
        # Start captcha detection monitoring
        asyncio.create_task(self.captcha_detector.start_monitoring())
        
        logger.info("✅ Browser initialized with authentic headers")
        
    async def _cleanup_and_verify_game_page(self):
        """Clean up tabs and ensure we have one game page"""
        logger.debug(f"Current pages: {len(self.main_context.pages)}")
        
        game_page = None
        pages_to_close = []
        
        # Find the game page and mark others for closing
        for page in self.main_context.pages:
            logger.debug(f"Page URL: {page.url}")
            if 'tribals.it' in page.url and 'game.php' in page.url:
                if not game_page:
                    game_page = page
                    logger.info(f"✅ Found game page: {page.url}")
                else:
                    # Extra game page, mark for closing
                    pages_to_close.append(page)
            elif page.url == 'about:blank' or page.url == '':
                pages_to_close.append(page)
            else:
                # Other non-game pages
                pages_to_close.append(page)
        
        # Close extra pages
        for page in pages_to_close:
            try:
                await page.close()
                logger.debug(f"Closed extra page: {page.url}")
            except:
                pass
                
        # Store reference to the game page
        if game_page:
            self.game_page = game_page
            logger.info("✅ Game page ready, no refresh needed")
        else:
            logger.warning("⚠️ No game page found after login - this shouldn't happen")
        
    async def _intercept_requests(self, route, request):
        """Intercept and modify requests to add authentic headers"""
        headers = request.headers.copy()
        
        # Add/update headers to match authentic session
        headers.update({
            'sec-fetch-dest': 'document' if request.resource_type == 'document' else 'empty',
            'sec-fetch-mode': 'navigate' if request.is_navigation_request() else 'cors',
            'sec-fetch-site': 'same-origin',
            'priority': 'u=0, i' if request.resource_type == 'document' else 'u=1',
        })
        
        # Add referer if missing and not the first request
        if 'referer' not in headers and not request.is_navigation_request():
            headers['referer'] = request.url.split('?')[0]
        
        # For navigation requests, add sec-fetch-user
        if request.is_navigation_request():
            headers['sec-fetch-user'] = '?1'
            
        await route.continue_(headers=headers)
        
    async def _inject_stealth_scripts(self, context: BrowserContext):
        """Inject enhanced stealth scripts"""
        # Get enhanced stealth script
        stealth_script = BrowserFingerprint.get_enhanced_stealth_script()
        
        # Add additional stealth measures
        stealth_script += """
            // Override chrome detection
            Object.defineProperty(window, 'chrome', {
                writable: true,
                enumerable: true,
                configurable: true,
                value: {
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
                        connect: function() {},
                        sendMessage: function() {},
                        id: undefined
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
                }
            });
            
            // Monitor localStorage changes for debugging
            if (typeof(Storage) !== "undefined") {
                const originalSetItem = Storage.prototype.setItem;
                Storage.prototype.setItem = function(key, value) {
                    // Log script-related localStorage changes
                    if (key.includes('farmGod') || key.includes('FarmGod') || 
                        key.includes('troop') || key.includes('category') || 
                        key.includes('sendOrder') || key.includes('runTimes') ||
                        key.includes('keepHome') || key.includes('prioritise')) {
                        console.log(`[LocalStorage SET] ${key} = ${value?.substring ? value.substring(0, 100) + '...' : value}`);
                    }
                    return originalSetItem.apply(this, arguments);
                };
                
                // Log what's already in localStorage on page load
                window.addEventListener('load', () => {
                    console.log('[LocalStorage] Current script-related keys:');
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        if (key && (key.includes('farmGod') || key.includes('FarmGod') || 
                            key.includes('troop') || key.includes('category') || 
                            key.includes('sendOrder') || key.includes('runTimes') ||
                            key.includes('keepHome') || key.includes('prioritise') ||
                            key.includes('timeElement'))) {
                            const value = localStorage.getItem(key);
                            console.log(`  - ${key}: ${value?.length || 0} chars`);
                        }
                    }
                });
            }
            
            // Fix navigator permissions
            const originalQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({ state: 'granted' });
                }
                return originalQuery.apply(navigator.permissions, arguments);
            };
            
            // Override webdriver detection
            delete navigator.__proto__.webdriver;
            
            // Fix Chrome 138 specific fingerprints
            Object.defineProperty(navigator, 'userAgentData', {
                get: () => ({
                    brands: [
                        { brand: "Not)A;Brand", version: "8" },
                        { brand: "Chromium", version: "138" },
                        { brand: "Google Chrome", version: "138" }
                    ],
                    mobile: false,
                    platform: "macOS"
                })
            });
        """
        
        await context.add_init_script(stealth_script)
        
    async def _verify_and_log_storage(self):
        """Verify localStorage persistence"""
        try:
            # Get the current active page
            page = self.game_page
            
            if not page:
                # Fallback to any tribals page
                for p in self.main_context.pages:
                    if 'tribals.it' in p.url:
                        page = p
                        break
                        
            if not page:
                # Get or create a page
                if self.main_context.pages:
                    page = self.main_context.pages[0]
                else:
                    page = await self.main_context.new_page()
                    await page.goto('about:blank')
            
            # Check localStorage
            storage_data = await page.evaluate("""() => {
                const scriptKeys = [];
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    if (key && (key.includes('farmGod') || key.includes('FarmGod') || 
                        key.includes('troop') || key.includes('category') || 
                        key.includes('sendOrder') || key.includes('runTimes') ||
                        key.includes('keepHome') || key.includes('prioritise') ||
                        key.includes('timeElement'))) {
                        const value = localStorage.getItem(key);
                        scriptKeys.push({
                            key: key,
                            length: value ? value.length : 0,
                            preview: value ? value.substring(0, 50) : null
                        });
                    }
                }
                return {
                    totalKeys: localStorage.length,
                    scriptKeys: scriptKeys
                };
            }""")
            
            if storage_data['scriptKeys'].length > 0:
                logger.info(f"✅ Found {storage_data['scriptKeys'].length} script settings in localStorage:")
                for item in storage_data['scriptKeys']:
                    logger.info(f"  - {item['key']}: {item['length']} chars")
            else:
                logger.info("ℹ️ No script settings found yet (normal for first run)")
                logger.info(f"   Total localStorage keys: {storage_data['totalKeys']}")
                
        except Exception as e:
            logger.debug(f"Could not verify storage: {e}")
            
    async def check_initial_bot_protection(self):
        """Check and handle bot protection before starting automations"""
        # Use the game page we already have from login
        page = self.game_page
        
        if not page:
            # Fallback: try to find game page in context pages
            for p in self.main_context.pages:
                if 'tribals.it' in p.url and 'game.php' in p.url:
                    page = p
                    break
                    
        if not page:
            # This should not happen if login was successful
            logger.error("❌ No game page found after login!")
            raise Exception("No game page available")
            
        logger.debug(f"Checking bot protection on existing page: {page.url}")
            
        # Check for bot protection
        if await self.captcha_detector.check_for_bot_protection(page):
            logger.warning("🚨 Bot protection detected on initial check!")
            
            # Handle it before continuing
            from ..captcha.solver import CaptchaSolver
            solver = CaptchaSolver(self.config)
            
            success = await solver.solve_bot_protection(page)
            
            if not success:
                logger.error("❌ Failed to pass initial bot protection")
                raise Exception("Bot protection not resolved - cannot start automations")
            else:
                logger.info("✅ Initial bot protection passed!")
                
        # Also check for regular captcha
        elif await self.captcha_detector.check_page_for_captcha(page):
            logger.warning("🚨 Captcha detected on initial check!")
            
            from ..captcha.solver import CaptchaSolver
            solver = CaptchaSolver(self.config)
            
            success = await solver.solve_captcha(page)
            
            if not success:
                logger.error("❌ Failed to solve initial captcha")
                raise Exception("Captcha not resolved - cannot start automations")
            else:
                logger.info("✅ Initial captcha solved!")
        else:
            logger.info("✅ No bot protection or captcha detected - safe to proceed")
            
    async def get_page(self, script_name: str, url: Optional[str] = None) -> Page:
        """Get or create a page for a script"""
        # Check if we have a page for this script
        if script_name in self.pages:
            page = self.pages[script_name]
            if not page.is_closed():
                # Navigate if needed and URL provided
                if url and not page.url.startswith(url.split('?')[0]):
                    await page.goto(url, wait_until='domcontentloaded')
                return page
                
        # Create new page in persistent context
        page = await self.main_context.new_page()
        self.pages[script_name] = page
        
        # Set up console logging for debugging
        page.on('console', lambda msg: self._handle_console_message(script_name, msg))
        
        # Navigate to URL if provided
        if url:
            await page.goto(url, wait_until='domcontentloaded')
            # Give time for scripts to initialize
            await asyncio.sleep(1)
            
        return page
        
    def _handle_console_message(self, script_name: str, msg):
        """Handle console messages from pages"""
        text = msg.text
        # Only log localStorage-related messages
        if '[LocalStorage' in text:
            logger.debug(f"[{script_name}] {text}")
            
    async def close_page(self, script_name: str):
        """Close a page"""
        if script_name in self.pages:
            page = self.pages[script_name]
            if not page.is_closed():
                # Log storage state before closing
                try:
                    await self._log_page_storage(page, script_name)
                except:
                    pass
                await page.close()
            del self.pages[script_name]
            
    async def _log_page_storage(self, page: Page, script_name: str):
        """Log localStorage state for a page"""
        try:
            if 'tribals.it' not in page.url:
                return
                
            storage_info = await page.evaluate("""() => {
                const keys = [];
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    if (key && (key.includes('farmGod') || key.includes('FarmGod') || 
                        key.includes('troop') || key.includes('category') || 
                        key.includes('sendOrder') || key.includes('runTimes') ||
                        key.includes('keepHome') || key.includes('prioritise'))) {
                        keys.push(key);
                    }
                }
                return keys;
            }""")
            
            if storage_info:
                logger.debug(f"[{script_name}] Script localStorage keys on page close: {', '.join(storage_info)}")
                
        except:
            pass
            
    async def cleanup(self):
        """Cleanup browser resources"""
        logger.info("🧹 Cleaning up browser resources...")
        
        # Stop captcha detector
        self.captcha_detector.stop()
        
        # Log final storage state (only in persistent mode)
        incognito_mode = os.getenv('INCOGNITO_MODE', 'false').lower() == 'true'
        if not incognito_mode:
            try:
                await self._verify_and_log_storage()
            except:
                pass
        
        # Close all pages
        for name, page in list(self.pages.items()):
            if not page.is_closed():
                await page.close()
                
        # Close context - this saves all data
        if self.main_context:
            await self.main_context.close()
            
        # Close browser if in incognito mode
        if incognito_mode and hasattr(self, 'browser') and self.browser:
            await self.browser.close()
            
        # Stop playwright
        if self.playwright:
            await self.playwright.stop()
            
        if incognito_mode:
            logger.info("✅ Browser cleanup complete - incognito mode, no data saved")
        else:
            logger.info("✅ Browser cleanup complete - localStorage persisted")
        
    async def create_context(self, name: str) -> BrowserContext:
        """Always return main context"""
        return self.main_context
        
    async def close_all_tribals_pages(self):
        """Close all pages related to Tribals"""
        logger.warning("🚨 Closing all Tribals pages")
        
        for name, page in list(self.pages.items()):
            if not page.is_closed() and 'tribals.it' in page.url:
                await page.close()
                del self.pages[name]
                
    @asynccontextmanager
    async def page_for_script(self, script_name: str, url: str):
        """Context manager for script pages"""
        page = await self.get_page(script_name, url)
        try:
            yield page
        finally:
            # Keep page open to preserve session
            pass