"""
Browser Manager - Optimized with enhanced stealth and bug fixes
"""
import asyncio
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from datetime import datetime
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Route, Request
from contextlib import asynccontextmanager

from ..utils.logger import setup_logger
from ..utils.anti_detection import AntiDetectionManager, BrowserFingerprint
from ..utils.screenshot_manager import screenshot_manager
from ..captcha.detector import CaptchaDetector
from .login_handler import LoginHandler

logger = setup_logger(__name__)


class BrowserManager:
    """Manages browser instances with enhanced stealth and persistence"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.main_context: Optional[BrowserContext] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.game_page: Optional[Page] = None
        self.scheduler = None  # Will be set by scheduler
        
        # Initialize components
        self.anti_detection_manager = AntiDetectionManager()
        self.captcha_detector = CaptchaDetector(self)
        self.captcha_detector.anti_detection_manager = self.anti_detection_manager
        self.login_handler = LoginHandler(config, self.anti_detection_manager)
        
        # Session tracking
        self._known_pages: Set[Page] = set()
        self._monitor_task: Optional[asyncio.Task] = None
        self._initialized = False
        
        # Setup persistent data directory
        self.user_data_dir = Path(config.get('browser', {}).get('user_data_dir', './browser_data'))
        self.incognito_mode = os.getenv('INCOGNITO_MODE', 'false').lower() == 'true'
        self._ensure_data_directory()
        
    def _ensure_data_directory(self):
        """Ensure browser data directory exists with proper structure"""
        if not self.incognito_mode:
            # Create main directory
            self.user_data_dir.mkdir(exist_ok=True, parents=True)
            
            # Create subdirectories for Chrome profile
            subdirs = ['Default', 'Default/Cache', 'Default/Local Storage', 'Default/Session Storage']
            for subdir in subdirs:
                (self.user_data_dir / subdir).mkdir(exist_ok=True, parents=True)
                
            logger.info(f"📁 Browser data directory: {self.user_data_dir.absolute()}")
        else:
            logger.info("🥷 Incognito mode - no persistent storage")
            
    def _get_stealth_args(self) -> List[str]:
        """Get comprehensive stealth arguments for Chrome"""
        return [
            # Critical: Hide automation
            '--disable-blink-features=AutomationControlled',
            '--exclude-switches=enable-automation',
            '--disable-infobars',
            
            # Performance and stability
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-accelerated-2d-canvas',
            '--no-first-run',
            '--no-zygote',
            # '--single-process',
            '--disable-gpu',
            
            # Privacy and security
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--allow-running-insecure-content',
            '--ignore-certificate-errors',
            '--ignore-certificate-errors-spki-list',
            
            # Disable unwanted features
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-features=BlinkGenPropertyTrees',
            '--disable-ipc-flooding-protection',
            '--disable-default-apps',
            '--disable-extensions',
            '--disable-component-extensions-with-background-pages',
            '--disable-background-networking',
            '--disable-sync',
            '--metrics-recording-only',
            '--disable-features=ImprovedCookieControls,LazyFrameLoading,GlobalMediaControls',
            '--disable-hang-monitor',
            '--disable-prompt-on-repost',
            '--disable-domain-reliability',
            '--disable-features=AudioServiceOutOfProcess',
            '--disable-print-preview',
            '--disable-speech-api',
            '--disable-canvas-aa',
            
            # Window and display
            '--window-position=0,0',
            '--force-color-profile=srgb',
            
            # Misc optimizations
            '--password-store=basic',
            '--use-mock-keychain',
            '--export-tagged-pdf',
            '--no-pings',
            '--enable-automation=false',
            '--disable-field-trial-config',
            '--disable-background-mode',
            '--disable-breakpad',
            '--disable-component-update',
            '--disable-features=OptimizationHints',
            '--disable-features=DialMediaRouteProvider',
            '--disable-features=CalculateNativeWinOcclusion',
            '--disable-features=InterestFeedContentSuggestions',
            '--disable-features=CertificateTransparencyComponentUpdater'
        ]
        
    def _get_context_options(self) -> Dict[str, Any]:
        """Get context options with authentic browser configuration"""
        browser_config = self.config.get('browser', {})
        user_agent = os.getenv('USER_AGENT', 
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
        )
        
        return {
            'viewport': browser_config.get('viewport', {'width': 1440, 'height': 720}),
            'screen': {'width': 1920, 'height': 1080},
            'user_agent': user_agent,
            'locale': os.getenv('BROWSER_LOCALE', 'it-IT'),
            'timezone_id': 'Europe/Rome',
            'permissions': ['geolocation', 'notifications'],
            'geolocation': {'latitude': 41.9028, 'longitude': 12.4964},  # Rome
            'color_scheme': 'light',
            'device_scale_factor': 1,
            'is_mobile': False,
            'has_touch': False,
            'java_script_enabled': True,
            'bypass_csp': True,
            'accept_downloads': True,
            'ignore_https_errors': True,
            'extra_http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Cache-Control': 'max-age=0',
                'sec-ch-ua': '"Not)A;Brand";v="99", "Google Chrome";v="138", "Chromium";v="138"',
                'sec-ch-ua-mobile': '?0',
                'sec-ch-ua-platform': '"macOS"',
            }
        }
        
    async def initialize(self):
        """Initialize Playwright and browser with enhanced stealth"""
        if self._initialized:
            logger.warning("⚠️ Browser manager already initialized")
            return
            
        logger.info("🌐 Initializing browser with enhanced stealth...")
        
        try:
            self.playwright = await async_playwright().start()
            
            browser_config = self.config.get('browser', {})
            stealth_args = self._get_stealth_args()
            context_options = self._get_context_options()
            
            if self.incognito_mode:
                logger.info("🥷 Launching in incognito mode...")
                # Launch browser in incognito
                self.browser = await self.playwright.chromium.launch(
                    headless=browser_config.get('headless', False),
                    slow_mo=browser_config.get('slow_mo', 0),
                    args=['--incognito'] + stealth_args,
                    channel='chrome' if os.path.exists('/usr/bin/google-chrome') else None
                )
                
                # Create incognito context
                self.main_context = await self.browser.new_context(**context_options)
            else:
                logger.info("💾 Launching with persistent storage...")
                # Launch persistent context
                self.main_context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir.absolute()),
                    headless=browser_config.get('headless', False),
                    slow_mo=browser_config.get('slow_mo', 0),
                    args=stealth_args,
                    channel='chrome' if os.path.exists('/usr/bin/google-chrome') else None,
                    **context_options
                )
            
            # Set up route interception for authentic behavior
            await self.main_context.route('**/*', self._intercept_requests)
            
            # Inject comprehensive stealth scripts
            await self._inject_stealth_scripts(self.main_context)
            
            # Verify stealth
            await self._verify_stealth()
            
            # Handle login
            logged_in = await self.login_handler.ensure_logged_in(self.main_context)
            if not logged_in:
                raise Exception("Login failed")
            
            # Clean up tabs and get game page
            await self._cleanup_and_verify_game_page()
            
            # Verify storage persistence
            if not self.incognito_mode:
                await self._verify_storage_persistence()
            
            # Check for initial bot protection
            await self._check_initial_protection()
            
            # Start monitoring tasks
            asyncio.create_task(self.captcha_detector.start_monitoring())
            self._monitor_task = asyncio.create_task(self._monitor_pages())
            
            self._initialized = True
            logger.info("✅ Browser initialized successfully with enhanced stealth")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize browser: {e}", exc_info=True)
            await self.cleanup()
            raise
            
    async def _inject_stealth_scripts(self, context: BrowserContext):
        """Inject comprehensive stealth scripts"""
        stealth_script = """
        // Comprehensive stealth mode
        (function() {
            'use strict';
            
            // Remove webdriver property completely
            const newProto = navigator.__proto__;
            delete newProto.webdriver;
            navigator.__proto__ = newProto;
            
            // Override the webdriver property more thoroughly
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
                configurable: false,
                enumerable: false
            });
            
            // Remove automation indicators
            ['cdc_adoQpoasnfa76pfcZLmcfl_Array',
             'cdc_adoQpoasnfa76pfcZLmcfl_Promise', 
             'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
             'cdc_adoQpoasnfa76pfcZLmcfl_Object',
             'cdc_adoQpoasnfa76pfcZLmcfl_JSON',
             'cdc_adoQpoasnfa76pfcZLmcfl_Proxy',
             '$cdc_asdjflasutopfhvcZLmcfl_',
             '$chrome_asyncScriptInfo',
             '__$webdriverAsyncExecutor',
             '__driver_evaluate',
             '__driver_unwrapped',
             '__fxdriver_evaluate',
             '__fxdriver_unwrapped',
             '__lastWatirAlert',
             '__lastWatirConfirm',
             '__lastWatirPrompt',
             '__selenium_evaluate',
             '__selenium_unwrapped',
             '__webdriver_evaluate',
             '__webdriver_func',
             '__webdriver_script_fn',
             '__webdriver_script_func',
             '__webdriver_script_function',
             '__webdriver_unwrapped',
             '_Selenium_IDE_Recorder',
             'calledPhantom',
             'domAutomation',
             'domAutomationController'
            ].forEach(prop => {
                try { delete window[prop]; } catch(e) {}
            });
            
            // Chrome object enhancement
            if (!window.chrome) {
                window.chrome = {};
            }
            
            window.chrome = new Proxy(window.chrome, {
                has: (target, key) => {
                    return key in target;
                },
                get: (target, key) => {
                    if (key === 'runtime') {
                        return {
                            connect: () => {},
                            sendMessage: () => {},
                            onMessage: {
                                addListener: () => {}
                            },
                            id: undefined,
                            getManifest: () => undefined
                        };
                    }
                    if (key === 'app') {
                        return {
                            isInstalled: false,
                            getDetails: () => null,
                            getIsInstalled: () => false,
                            installState: () => 'not_installed',
                            runningState: () => 'cannot_run'
                        };
                    }
                    if (key === 'csi') {
                        return () => ({
                            onloadT: Date.now(),
                            pageT: Date.now() - Math.random() * 1000,
                            startE: Date.now() - Math.random() * 2000,
                            tran: 15
                        });
                    }
                    if (key === 'loadTimes') {
                        return () => ({
                            requestTime: Date.now() / 1000 - Math.random() * 100,
                            startLoadTime: Date.now() / 1000 - Math.random() * 99,
                            commitLoadTime: Date.now() / 1000 - Math.random() * 98,
                            finishDocumentLoadTime: Date.now() / 1000 - Math.random() * 97,
                            finishLoadTime: Date.now() / 1000 - Math.random() * 96,
                            firstPaintTime: Date.now() / 1000 - Math.random() * 95,
                            firstPaintAfterLoadTime: 0,
                            navigationType: 'Other',
                            wasFetchedViaSpdy: false,
                            wasNpnNegotiated: true,
                            npnNegotiatedProtocol: 'h2',
                            wasAlternateProtocolAvailable: false,
                            connectionInfo: 'h2'
                        });
                    }
                    return target[key];
                }
            });
            
            // Plugin spoofing
            Object.defineProperty(navigator, 'plugins', {
                get: () => {
                    const plugins = [
                        {
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin",
                            0: {
                                description: "Portable Document Format",
                                enabledPlugin: Plugin,
                                suffixes: "pdf",
                                type: "application/x-google-chrome-pdf"
                            }
                        },
                        {
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Viewer",
                            0: {
                                description: "Portable Document Format",
                                enabledPlugin: Plugin,
                                suffixes: "pdf",
                                type: "application/pdf"
                            }
                        },
                        {
                            description: "Native Client Executable",
                            filename: "internal-nacl-plugin",
                            length: 2,
                            name: "Native Client",
                            0: {
                                description: "Native Client Executable",
                                enabledPlugin: Plugin,
                                suffixes: "",
                                type: "application/x-nacl"
                            },
                            1: {
                                description: "Portable Native Client Executable",
                                enabledPlugin: Plugin,
                                suffixes: "",
                                type: "application/x-pnacl"
                            }
                        }
                    ];
                    
                    plugins.forEach(plugin => {
                        plugin.__proto__ = PluginArray.prototype;
                    });
                    
                    return plugins;
                }
            });
            
            // Languages enhancement
            Object.defineProperty(navigator, 'languages', {
                get: () => ['it-IT', 'it', 'en-US', 'en']
            });
            
            // Platform spoofing
            Object.defineProperty(navigator, 'platform', {
                get: () => 'MacIntel'
            });
            
            // Hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });
            
            // Device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
            
            // WebGL vendor spoofing
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
            
            // Permissions spoofing
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({ state: 'granted' });
                }
                return originalQuery.apply(navigator.permissions, arguments);
            };
            
            // Connection spoofing
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 100,
                    downlink: 10,
                    saveData: false
                })
            });
            
            // Battery spoofing
            navigator.getBattery = () => {
                return Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1,
                    addEventListener: () => {},
                    removeEventListener: () => {}
                });
            };
            
            // Media devices
            if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
                navigator.mediaDevices.enumerateDevices = async () => {
                    return [
                        {
                            deviceId: "default",
                            kind: "audioinput",
                            label: "Default - MacBook Pro Microphone (Built-in)",
                            groupId: "default"
                        }
                    ];
                };
            }
            
            // Override toString methods to prevent detection
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === window.navigator.webdriver) {
                    return 'function webdriver() { [native code] }';
                }
                return originalToString.apply(this, arguments);
            };
            
            // Monitor for localStorage changes (debugging)
            if (typeof(Storage) !== "undefined") {
                const originalSetItem = Storage.prototype.setItem;
                Storage.prototype.setItem = function(key, value) {
                    if (key.includes('farmGod') || key.includes('FarmGod') || 
                        key.includes('troop') || key.includes('category') || 
                        key.includes('sendOrder') || key.includes('runTimes') ||
                        key.includes('keepHome') || key.includes('prioritise')) {
                        console.log(`[LocalStorage SET] ${key} = ${value?.substring ? value.substring(0, 100) + '...' : value}`);
                    }
                    return originalSetItem.apply(this, arguments);
                };
            }
        })();
        """
        
        # Add additional stealth from BrowserFingerprint if available
        if hasattr(BrowserFingerprint, 'get_enhanced_stealth_script'):
            stealth_script += BrowserFingerprint.get_enhanced_stealth_script()
        
        await context.add_init_script(stealth_script)
        
    async def _intercept_requests(self, route: Route, request: Request):
        """Intercept and modify requests for authentic behavior"""
        headers = request.headers.copy()
        
        # Update headers based on request type
        resource_type = request.resource_type
        
        # Common headers
        headers.update({
            'sec-fetch-dest': self._get_fetch_dest(resource_type),
            'sec-fetch-mode': 'navigate' if request.is_navigation_request() else 'cors',
            'sec-fetch-site': self._get_fetch_site(request.url, headers.get('referer', '')),
        })
        
        # Navigation-specific headers
        if request.is_navigation_request():
            headers['sec-fetch-user'] = '?1'
            headers['upgrade-insecure-requests'] = '1'
            
        # Add referer if missing
        if 'referer' not in headers and not request.is_navigation_request():
            headers['referer'] = request.url.split('?')[0]
            
        # Remove problematic headers
        headers.pop('x-devtools-emulate-network-conditions-client-id', None)
        headers.pop('x-devtools-request-id', None)
        
        await route.continue_(headers=headers)
        
    def _get_fetch_dest(self, resource_type: str) -> str:
        """Get appropriate sec-fetch-dest header"""
        mapping = {
            'document': 'document',
            'stylesheet': 'style',
            'script': 'script',
            'image': 'image',
            'font': 'font',
            'xhr': 'empty',
            'fetch': 'empty',
            'websocket': 'websocket',
        }
        return mapping.get(resource_type, 'empty')
        
    def _get_fetch_site(self, url: str, referer: str) -> str:
        """Get appropriate sec-fetch-site header"""
        if not referer:
            return 'none'
            
        from urllib.parse import urlparse
        url_domain = urlparse(url).netloc
        referer_domain = urlparse(referer).netloc
        
        if url_domain == referer_domain:
            return 'same-origin'
        elif url_domain.endswith(referer_domain) or referer_domain.endswith(url_domain):
            return 'same-site'
        else:
            return 'cross-site'
            
    async def _verify_stealth(self):
        """Verify stealth measures are working"""
        page = None
        try:
            # Create a test page
            page = await self.main_context.new_page()
            
            # Check webdriver property
            is_webdriver = await page.evaluate('navigator.webdriver')
            logger.info(f"🔍 Webdriver detection: {is_webdriver}")
            
            # Check for automation properties
            automation_props = await page.evaluate("""
                () => {
                    const props = [
                        'navigator.webdriver',
                        'window.cdc_adoQpoasnfa76pfcZLmcfl_Array',
                        'window.cdc_adoQpoasnfa76pfcZLmcfl_Promise',
                        'window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
                        'window.chrome.runtime.id'
                    ];
                    
                    const detected = {};
                    for (const prop of props) {
                        try {
                            detected[prop] = eval(prop) !== undefined;
                        } catch(e) {
                            detected[prop] = false;
                        }
                    }
                    return detected;
                }
            """)
            
            logger.debug(f"🔍 Automation properties check: {automation_props}")
            
            # Check plugins
            plugins_count = await page.evaluate('navigator.plugins.length')
            logger.debug(f"🔍 Plugins count: {plugins_count}")
            
            if is_webdriver:
                logger.warning("⚠️ Webdriver property still detectable!")
            else:
                logger.info("✅ Stealth measures verified - webdriver not detected")
                
        except Exception as e:
            logger.error(f"Error verifying stealth: {e}")
        finally:
            if page and not page.is_closed():
                await page.close()
                
    async def _cleanup_and_verify_game_page(self):
        """Clean up extra tabs and ensure we have game page"""
        logger.debug(f"📑 Current pages: {len(self.main_context.pages)}")
        
        game_page = None
        pages_to_close = []
        
        # Find game page and identify extras
        for page in self.main_context.pages:
            try:
                if page.is_closed():
                    continue
                    
                url = page.url
                logger.debug(f"  - Page: {url[:80]}...")
                
                if 'tribals.it' in url and 'game.php' in url:
                    if not game_page:
                        game_page = page
                        logger.info(f"✅ Found game page")
                    else:
                        pages_to_close.append(page)
                elif url == 'about:blank' or not url:
                    pages_to_close.append(page)
            except:
                pass
                
        # Close extra pages
        for page in pages_to_close:
            try:
                await page.close()
                logger.debug(f"🗑️ Closed extra page")
            except:
                pass
                
        # Store game page reference
        if game_page:
            self.game_page = game_page
            self._known_pages.add(game_page)
            logger.info("✅ Game page ready")
        else:
            logger.warning("⚠️ No game page found after login")
            
    async def _verify_storage_persistence(self):
        """Verify localStorage persistence"""
        try:
            page = self.game_page or (self.main_context.pages[0] if self.main_context.pages else None)
            if not page:
                return
                
            storage_info = await page.evaluate("""
                () => {
                    const scriptKeys = [];
                    const allKeys = [];
                    
                    for (let i = 0; i < localStorage.length; i++) {
                        const key = localStorage.key(i);
                        allKeys.push(key);
                        
                        if (key && (key.includes('farmGod') || key.includes('FarmGod') || 
                            key.includes('troop') || key.includes('category') || 
                            key.includes('sendOrder') || key.includes('runTimes') ||
                            key.includes('keepHome') || key.includes('prioritise') ||
                            key.includes('timeElement'))) {
                            const value = localStorage.getItem(key);
                            scriptKeys.push({
                                key: key,
                                length: value ? value.length : 0
                            });
                        }
                    }
                    
                    return {
                        totalKeys: localStorage.length,
                        scriptKeys: scriptKeys,
                        sampleKeys: allKeys.slice(0, 5)
                    };
                }
            """)
            
            logger.info(f"💾 LocalStorage: {storage_info['totalKeys']} total keys")
            if storage_info['scriptKeys']:
                logger.info(f"✅ Found {len(storage_info['scriptKeys'])} script settings")
                for item in storage_info['scriptKeys']:
                    logger.debug(f"  - {item['key']}: {item['length']} chars")
            else:
                logger.info("ℹ️ No script settings found (normal for first run)")
                
        except Exception as e:
            logger.debug(f"Storage verification error: {e}")
            
    async def _check_initial_protection(self):
        """Check for captcha/bot protection before starting"""
        if not self.game_page:
            logger.warning("⚠️ No game page for protection check")
            return
            
        logger.info("🔍 Checking for initial protection...")
        
        # Check bot protection
        if await self.captcha_detector.check_for_bot_protection(self.game_page):
            logger.warning("🚨 Bot protection detected!")
            
            from ..captcha.solver import CaptchaSolver
            solver = CaptchaSolver(self.config, self.anti_detection_manager)
            
            success = await solver.solve_bot_protection(self.game_page)
            if not success:
                raise Exception("Bot protection not resolved")
                
        # Check captcha
        elif await self.captcha_detector.check_page_for_captcha(self.game_page):
            logger.warning("🚨 Captcha detected!")
            
            from ..captcha.solver import CaptchaSolver
            solver = CaptchaSolver(self.config, self.anti_detection_manager)
            
            success = await solver.solve_captcha(self.game_page)
            if not success:
                raise Exception("Captcha not resolved")
        else:
            logger.info("✅ No protection detected - safe to proceed")
            
    async def _monitor_pages(self):
        """Monitor all browser pages for changes"""
        while self._initialized:
            try:
                if self.main_context:
                    current_pages = set(self.main_context.pages)
                    new_pages = current_pages - self._known_pages
                    
                    for page in new_pages:
                        if not page.is_closed():
                            logger.info(f"🆕 New tab detected: {page.url[:50]}...")
                            self._known_pages.add(page)
                            
                            # Set up console monitoring
                            page.on('console', lambda msg: self._handle_console_message('new_tab', msg))
                            
                    # Clean up closed pages
                    self._known_pages = {p for p in self._known_pages if not p.is_closed()}
                    
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.debug(f"Page monitoring error: {e}")
                await asyncio.sleep(5)
                
    def _handle_console_message(self, source: str, msg):
        """Handle console messages from pages"""
        text = msg.text
        # Only log important messages
        if '[LocalStorage' in text or 'Error' in text or 'Warning' in text:
            logger.debug(f"[{source}] Console: {text}")
            
    async def get_page(self, script_name: str, url: Optional[str] = None) -> Page:
        """Get or create a page for a script"""
        # Check existing page
        if script_name in self.pages:
            page = self.pages[script_name]
            if not page.is_closed():
                # Navigate if needed
                if url and not page.url.startswith(url.split('?')[0]):
                    await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                return page
            else:
                # Clean up closed page
                del self.pages[script_name]
                
        # Create new page
        page = await self.main_context.new_page()
        self.pages[script_name] = page
        self._known_pages.add(page)
        
        # Set up monitoring
        page.on('console', lambda msg: self._handle_console_message(script_name, msg))
        
        # Navigate if URL provided
        if url:
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=30000)
                await asyncio.sleep(1)  # Let scripts initialize
            except Exception as e:
                logger.error(f"Navigation error for {script_name}: {e}")
                await page.close()
                del self.pages[script_name]
                raise
                
        return page
        
    async def close_page(self, script_name: str):
        """Close a page and clean up"""
        if script_name in self.pages:
            page = self.pages[script_name]
            try:
                if not page.is_closed():
                    # Log storage state before closing
                    await self._log_page_storage(page, script_name)
                    await page.close()
            except Exception as e:
                logger.debug(f"Error closing page {script_name}: {e}")
            finally:
                del self.pages[script_name]
                self._known_pages.discard(page)
                
    async def _log_page_storage(self, page: Page, script_name: str):
        """Log localStorage state for debugging"""
        if self.incognito_mode:
            return
            
        try:
            if 'tribals.it' not in page.url:
                return
                
            storage_keys = await page.evaluate("""
                () => {
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
                }
            """)
            
            if storage_keys:
                logger.debug(f"[{script_name}] Script localStorage on close: {', '.join(storage_keys)}")
                
        except:
            pass
            
    def get_all_tribals_pages(self) -> List[Page]:
        """Get all open Tribals pages"""
        pages = []
        
        if self.main_context:
            for page in self.main_context.pages:
                try:
                    if not page.is_closed() and 'tribals.it' in page.url:
                        pages.append(page)
                except:
                    pass
                    
        return pages
        
    async def create_context(self, name: str) -> BrowserContext:
        """Create a new context (always returns main context)"""
        return self.main_context
        
    async def close_all_tribals_pages(self):
        """Emergency close all Tribals pages"""
        logger.warning("🚨 Closing all Tribals pages")
        
        # Close registered pages
        for name in list(self.pages.keys()):
            await self.close_page(name)
            
        # Close any other Tribals pages
        if self.main_context:
            for page in self.main_context.pages:
                try:
                    if not page.is_closed() and 'tribals.it' in page.url:
                        await page.close()
                except:
                    pass
                    
    @asynccontextmanager
    async def page_for_script(self, script_name: str, url: str):
        """Context manager for script pages"""
        page = await self.get_page(script_name, url)
        try:
            yield page
        finally:
            # Keep page open to preserve session
            pass
            
    async def cleanup(self):
        """Cleanup browser resources"""
        logger.info("🧹 Cleaning up browser resources...")
        
        try:
            # Stop monitoring
            if self._monitor_task:
                self._monitor_task.cancel()
                
            # Stop captcha detector
            if hasattr(self, 'captcha_detector'):
                self.captcha_detector.stop()
            
            # Save storage state
            if not self.incognito_mode and self._initialized:
                await self._verify_storage_persistence()
            
            # Close all pages
            for name in list(self.pages.keys()):
                await self.close_page(name)
                
            # Close context
            if self.main_context:
                await self.main_context.close()
                
            # Close browser (for incognito)
            if self.incognito_mode and self.browser:
                await self.browser.close()
                
            # Stop playwright
            if self.playwright:
                await self.playwright.stop()
                
            self._initialized = False
            
            mode = "incognito" if self.incognito_mode else "persistent"
            logger.info(f"✅ Browser cleanup complete ({mode} mode)")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)

    async def close_browser_for_sleep(self):
        """Close browser completely for sleep mode"""
        logger.info("🛌 Closing browser for sleep mode...")
        
        try:
            # Stop all monitoring first
            if self._monitor_task:
                self._monitor_task.cancel()
                try:
                    await self._monitor_task
                except asyncio.CancelledError:
                    pass
                    
            # Stop captcha detector
            if hasattr(self, 'captcha_detector'):
                self.captcha_detector.stop()
            
            # Close all pages
            logger.info("📑 Closing all pages...")
            for name in list(self.pages.keys()):
                await self.close_page(name)
                
            # Close any remaining pages in context
            if self.main_context:
                remaining_pages = list(self.main_context.pages)
                for page in remaining_pages:
                    try:
                        if not page.is_closed():
                            await page.close()
                    except:
                        pass
                        
            # Close context
            if self.main_context:
                logger.info("🔌 Closing browser context...")
                await self.main_context.close()
                self.main_context = None
                
            # Close browser (for incognito mode)
            if self.incognito_mode and self.browser:
                logger.info("🔌 Closing incognito browser...")
                await self.browser.close()
                self.browser = None
                
            # Stop playwright
            if self.playwright:
                logger.info("🎭 Stopping playwright...")
                await self.playwright.stop()
                self.playwright = None
                
            self._initialized = False
            self._known_pages.clear()
            self.pages.clear()
            self.game_page = None
            
            logger.info("✅ Browser closed for sleep mode")
            
        except Exception as e:
            logger.error(f"❌ Error closing browser for sleep: {e}", exc_info=True)
            # Force cleanup
            self._initialized = False
            self.playwright = None
            self.browser = None
            self.main_context = None
            
    async def reinitialize_after_sleep(self):
        """Reinitialize browser after sleep mode"""
        logger.info("🔄 Reinitializing browser after sleep...")
        
        try:
            # Make sure everything is cleaned up first
            if self._initialized:
                await self.cleanup()
                
            # Wait a bit to ensure clean state
            await asyncio.sleep(2)
            
            # Reinitialize
            await self.initialize()
            
            logger.info("✅ Browser reinitialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to reinitialize browser: {e}", exc_info=True)
            raise