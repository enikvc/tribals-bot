"""
Browser Manager - Enhanced Stealth Mode with Real Chrome
"""
import asyncio
import os
import sys
import platform
import subprocess
import json
import shutil
import time
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


class StealthBrowserManager:
    """Ultra-stealth browser manager using real Chrome installation"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.main_context: Optional[BrowserContext] = None
        self.contexts: Dict[str, BrowserContext] = {}
        self.pages: Dict[str, Page] = {}
        self.game_page: Optional[Page] = None
        self.scheduler = None
        
        # Initialize components
        self.anti_detection_manager = AntiDetectionManager()
        self.captcha_detector = CaptchaDetector(self)
        self.captcha_detector.anti_detection_manager = self.anti_detection_manager
        self.login_handler = LoginHandler(config, self.anti_detection_manager)
        
        # Session tracking
        self._known_pages: Set[Page] = set()
        self._monitor_task: Optional[asyncio.Task] = None
        self._initialized = False
        
        # Get real Chrome profile path
        self.chrome_profile_path = self._get_chrome_profile_path()
        self.user_data_dir = Path(config.get('browser', {}).get('user_data_dir', './browser_data'))
        self.incognito_mode = os.getenv('INCOGNITO_MODE', 'false').lower() == 'true'
        self.test_hcaptcha = os.getenv('TEST_HCAPTCHA', 'false').lower() == 'true'
        
        # Prepare profile
        self._prepare_browser_profile()
        
    def _get_chrome_profile_path(self) -> Path:
        """Get the real Chrome user profile path"""
        system = platform.system()
        home = Path.home()
        
        if system == "Windows":
            return home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
        elif system == "Darwin":  # macOS
            return home / "Library" / "Application Support" / "Google" / "Chrome"
        else:  # Linux
            return home / ".config" / "google-chrome"
            
    def _prepare_browser_profile(self):
        """Prepare browser profile by copying from real Chrome"""
        if self.incognito_mode:
            logger.info("🥷 Incognito mode - no profile preparation needed")
            return
            
        # Create user data directory
        self.user_data_dir.mkdir(exist_ok=True, parents=True)
        
        # Check if we already have a profile
        default_profile = self.user_data_dir / "Default"
        if default_profile.exists() and (default_profile / "Preferences").exists():
            logger.info("✅ Browser profile already exists")
            return
            
        # Copy essential files from real Chrome profile
        logger.info("📁 Preparing browser profile from real Chrome...")
        
        try:
            if self.chrome_profile_path.exists():
                # Create Default profile directory
                default_profile.mkdir(exist_ok=True, parents=True)
                
                # Essential files to copy (without sensitive data)
                files_to_copy = [
                    "Preferences",
                    "Local State"
                ]
                
                # Copy files
                for file_name in files_to_copy:
                    src = self.chrome_profile_path / "Default" / file_name
                    if src.exists():
                        dst = default_profile / file_name
                        shutil.copy2(src, dst)
                        logger.debug(f"✅ Copied {file_name}")
                        
                # Modify preferences to remove personal data but keep settings
                self._clean_preferences(default_profile / "Preferences")
                
                logger.info("✅ Browser profile prepared successfully")
            else:
                logger.warning("⚠️ Chrome profile not found, creating new profile")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not copy Chrome profile: {e}")
            
    def _clean_preferences(self, pref_file: Path):
        """Clean preferences file to remove personal data"""
        if not pref_file.exists():
            return
            
        try:
            with open(pref_file, 'r', encoding='utf-8') as f:
                prefs = json.load(f)
                
            # Remove personal data but keep browser settings
            sensitive_keys = [
                'account_info',
                'autofill',
                'credentials_enable_service',
                'credentials_enable_autosignin',
                'profile',
                'signin',
                'sync'
            ]
            
            for key in sensitive_keys:
                prefs.pop(key, None)
                
            # Ensure webdriver is not detected
            if 'webdriver' in prefs:
                del prefs['webdriver']
                
            # Write back
            with open(pref_file, 'w', encoding='utf-8') as f:
                json.dump(prefs, f, indent=2)
                
        except Exception as e:
            logger.debug(f"Could not clean preferences: {e}")
            
    def _get_real_chrome_path(self) -> Optional[str]:
        """Get the actual Chrome executable path"""
        system = platform.system()
        
        if system == "Windows":
            paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe")
            ]
        elif system == "Darwin":  # macOS
            paths = [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Google Chrome Beta.app/Contents/MacOS/Google Chrome Beta",
                "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
                os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            ]
        else:  # Linux
            paths = [
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome-beta",
                "/usr/bin/google-chrome-unstable",
                "/opt/google/chrome/google-chrome",
                "/usr/local/bin/google-chrome",
                shutil.which("google-chrome"),
                shutil.which("google-chrome-stable")
            ]
            
        # Find the first existing path
        for path in paths:
            if path and os.path.exists(path):
                logger.info(f"✅ Found Chrome at: {path}")
                return path
                
        # Try to find using 'which' or 'where' command
        try:
            if system == "Windows":
                result = subprocess.run(['where', 'chrome'], capture_output=True, text=True)
            else:
                result = subprocess.run(['which', 'google-chrome'], capture_output=True, text=True)
                
            if result.returncode == 0 and result.stdout.strip():
                path = result.stdout.strip().split('\n')[0]
                if os.path.exists(path):
                    logger.info(f"✅ Found Chrome via command: {path}")
                    return path
        except:
            pass
            
        logger.error("❌ Chrome executable not found!")
        return None
        
    def _get_stealth_args(self) -> List[str]:
        """Get ultra-stealth arguments for Chrome"""
        args = [
            # Critical stealth flags
            '--disable-blink-features=AutomationControlled',
            '--disable-features=AutomationControlled',
            '--exclude-switches=enable-automation',
            '--disable-infobars',
            
            # Disable automation extension
            '--disable-extensions-except=',
            '--disable-default-apps',
            
            # Window settings
            '--start-maximized',
            '--disable-features=TranslateUI,BlinkGenPropertyTrees,IsolateOrigins,site-per-process,WindowOcclusionTracking',
            '--disable-session-crashed-bubble',
            '--disable-features=CalculateNativeWinOcclusion',
            
            # WebGL support - CRITICAL
            '--use-gl=angle',  # Use ANGLE for better WebGL support
            '--use-angle=gl',
            '--enable-webgl',
            '--enable-webgl2',
            '--ignore-gpu-blocklist',
            '--enable-gpu-rasterization',
            '--enable-accelerated-2d-canvas',
            '--enable-unsafe-webgpu',
            
            # Performance and rendering
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--no-first-run',
            '--no-zygote',
            '--disable-software-rasterizer',
            '--disable-dev-tools',
            
            # Features to disable
            '--disable-features=TranslateUI,BlinkGenPropertyTrees,IsolateOrigins,site-per-process',
            '--disable-ipc-flooding-protection',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-hang-monitor',
            '--disable-prompt-on-repost',
            '--disable-sync',
            '--disable-domain-reliability',
            '--disable-background-networking',
            '--disable-remote-fonts',
            '--disable-component-update',
            '--disable-client-side-phishing-detection',
            '--disable-oopr-debug-crash-dump',
            
            # Privacy
            '--disable-features=Reporting',
            '--disable-crash-reporter',
            '--disable-breakpad',
            '--disable-features=InterestCohortAPI',
            '--disable-features=FlocIdComputedEventLogging',
            '--disable-features=MediaRouter',
            '--enable-features=NetworkService,NetworkServiceInProcess',
            
            # Misc
            '--no-pings',
            '--no-default-browser-check',
            '--disable-default-apps',
            '--disable-popup-blocking',
            '--disable-translate',
            '--metrics-recording-only',
            '--safebrowsing-disable-auto-update',
            '--password-store=basic',
            '--use-mock-keychain',
            '--force-color-profile=srgb',
            '--disable-features=RendererCodeIntegrity',
            '--disable-features=OptimizationHints',
            
            # User agent override
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
        ]
        
        # Platform specific adjustments
        if platform.system() == "Darwin":  # macOS
            # macOS specific WebGL settings
            args.extend([
                '--use-gl=angle',
                '--use-angle=gl'
            ])
        elif platform.system() == "Linux":
            # Linux specific settings
            args.extend([
                '--use-gl=desktop',
                '--enable-features=VaapiVideoDecoder'
            ])
        elif platform.system() == "Windows":
            args.append('--disable-features=RendererCodeIntegrity')
            
        return args
        
    def _get_enhanced_context_options(self) -> Dict[str, Any]:
        """Get context options that match real browser exactly"""
        # Get real screen dimensions
        try:
            if platform.system() == "Windows":
                import tkinter
                root = tkinter.Tk()
                screen_width = root.winfo_screenwidth()
                screen_height = root.winfo_screenheight()
                root.destroy()
            else:
                # Default for other systems
                screen_width = 1920
                screen_height = 1080
        except:
            screen_width = 1920
            screen_height = 1080
            
        # Get system locale
        import locale
        system_locale = locale.getdefaultlocale()[0] or 'en-US'
        system_locale = system_locale.replace('_', '-')
        
        # Browser viewport (slightly smaller than screen)
        viewport_width = min(1600, screen_width - 100)
        viewport_height = min(900, screen_height - 100)
        
        return {
            'viewport': {'width': viewport_width, 'height': viewport_height},
            'screen': {'width': screen_width, 'height': screen_height},
            'user_agent': self._get_real_user_agent(),
            'locale': os.getenv('BROWSER_LOCALE', system_locale),
            'timezone_id': self._get_system_timezone(),
            'permissions': [],  # Don't pre-grant permissions
            'geolocation': None,  # Don't set geolocation
            'color_scheme': 'light',
            'device_scale_factor': self._get_device_scale_factor(),
            'is_mobile': False,
            'has_touch': False,
            'java_script_enabled': True,
            'accept_downloads': True,
            'ignore_https_errors': True,
            'bypass_csp': True,
            'extra_http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': f'{system_locale},en-US;q=0.9,en;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }
        }
        
    def _get_real_user_agent(self) -> str:
        """Get the actual Chrome user agent for current version"""
        # Try to get Chrome version
        chrome_version = self._get_chrome_version()
        
        system = platform.system()
        if system == "Windows":
            os_string = "Windows NT 10.0; Win64; x64"
        elif system == "Darwin":
            os_string = "Macintosh; Intel Mac OS X 10_15_7"
        else:
            os_string = "X11; Linux x86_64"
            
        return f"Mozilla/5.0 ({os_string}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome_version} Safari/537.36"
        
    def _get_chrome_version(self) -> str:
        """Get actual Chrome version"""
        try:
            chrome_path = self._get_real_chrome_path()
            if not chrome_path:
                return "131.0.0.0"
                
            if platform.system() == "Windows":
                try:
                    # Try to get version from exe properties
                    import win32api
                    info = win32api.GetFileVersionInfo(chrome_path, '\\')
                    ms = info['FileVersionMS']
                    ls = info['FileVersionLS']
                    version = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
                    return version
                except:
                    pass
                    
            # For macOS and Linux, use --version flag
            try:
                result = subprocess.run([chrome_path, '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    # Parse version from output like "Google Chrome 131.0.6778.85"
                    version_str = result.stdout.strip()
                    import re
                    match = re.search(r'(\d+\.\d+\.\d+\.\d+)', version_str)
                    if match:
                        return match.group(1)
            except:
                pass
                
        except Exception as e:
            logger.debug(f"Could not get Chrome version: {e}")
            
        return "131.0.0.0"  # Fallback
        
    def _get_system_timezone(self) -> str:
        """Get system timezone"""
        try:
            if platform.system() == "Windows":
                import winreg
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\TimeZoneInformation") as key:
                    tz_name, _ = winreg.QueryValueEx(key, "TimeZoneKeyName")
                    return tz_name
            else:
                # Unix systems
                if os.path.exists('/etc/timezone'):
                    with open('/etc/timezone', 'r') as f:
                        return f.read().strip()
                elif os.path.exists('/etc/localtime'):
                    # Try to resolve symlink
                    import subprocess
                    result = subprocess.run(['readlink', '-f', '/etc/localtime'], capture_output=True, text=True)
                    if result.returncode == 0:
                        # Extract timezone from path like /usr/share/zoneinfo/Europe/Rome
                        path = result.stdout.strip()
                        if '/zoneinfo/' in path:
                            return path.split('/zoneinfo/')[-1]
        except:
            pass
            
        return 'Europe/Rome'  # Fallback for Italian server
        
    def _get_device_scale_factor(self) -> float:
        """Get actual device scale factor"""
        try:
            if platform.system() == "Windows":
                import ctypes
                # Get DPI awareness
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                hdc = ctypes.windll.user32.GetDC(0)
                dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                ctypes.windll.user32.ReleaseDC(0, hdc)
                return dpi / 96.0
        except:
            pass
            
        return 1.0
        
    async def _inject_ultra_stealth_scripts(self, context: BrowserContext):
        """Inject enhanced stealth scripts that perfectly mimic real Chrome"""
        stealth_script = """
        // Ultra stealth mode - Undetectable
        (function() {
            'use strict';
            
            // First, delete all traces of automation
            const deleteFromWindow = [
                '_phantom', 'phantom', 'callPhantom', '_selenium', 'callSelenium', 
                '__webdriver_evaluate', '__selenium_evaluate', '__webdriver_script_function',
                '__webdriver_script_func', '__webdriver_script_fn', '__fxdriver_evaluate',
                '__driver_unwrapped', '__webdriver_unwrapped', '__driver_evaluate',
                '__selenium_unwrapped', '__fxdriver_unwrapped', '_Selenium_IDE_Recorder',
                '__nightmareNavigate', '_eventRecorder', 'domAutomation', 'domAutomationController',
                '__lastWatirAlert', '__lastWatirConfirm', '__lastWatirPrompt', 'CalypsoAccount',
                'cdc_adoQpoasnfa76pfcZLmcfl_Array', 'cdc_adoQpoasnfa76pfcZLmcfl_Object',
                'cdc_adoQpoasnfa76pfcZLmcfl_Promise', 'cdc_adoQpoasnfa76pfcZLmcfl_Proxy',
                'cdc_adoQpoasnfa76pfcZLmcfl_Symbol', 'cdc_adoQpoasnfa76pfcZLmcfl_JSON',
                'geb', 'awesomium', '$chrome_asyncScriptInfo', '$cdc_asdjflasutopfhvcZLmcfl_',
                'webdriver', 'driver', 'selenium',
                // Additional phantom-related properties
                '__phantomas', '_phantom', 'phantom', 'callPhantom',
                '_phantomChildren', '_phantomProps', 'phantomjs'
            ];
            
            deleteFromWindow.forEach(prop => {
                try { 
                    delete window[prop];
                    delete document[prop];
                    delete navigator[prop];
                } catch(e) {}
            });
            
            // Prevent phantom properties from being defined
            const blockProperties = ['phantom', '_phantom', 'callPhantom', '__phantomas', 'phantomjs'];
            blockProperties.forEach(prop => {
                try {
                    Object.defineProperty(window, prop, {
                        get: function() { return undefined; },
                        set: function() {},
                        enumerable: false,
                        configurable: false
                    });
                } catch(e) {}
            });
            
            // Override webdriver property without recursion
            try {
                // Get the Navigator prototype
                const NavigatorPrototype = Object.getPrototypeOf(navigator);
                
                // Delete existing webdriver property from all possible locations
                delete NavigatorPrototype.webdriver;
                delete navigator.webdriver;
                delete window.navigator.webdriver;
                
                // Use Object.defineProperty on the prototype
                Object.defineProperty(NavigatorPrototype, 'webdriver', {
                    get: function() { return false; },
                    set: function() {},
                    enumerable: false,
                    configurable: false
                });
            } catch (e) {
                console.warn('Could not override webdriver property:', e);
            }
            
            // Chrome object must exist and be complete
            if (!window.chrome) {
                window.chrome = {};
            }
            
            // Define chrome properties without getters to avoid recursion
            window.chrome.app = {
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
                },
                getDetails: () => null,
                getIsInstalled: () => false,
                installState: () => 'not_installed',
                runningState: () => 'cannot_run'
            };
            
            window.chrome.runtime = {
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
            };
            
            window.chrome.csi = () => ({
                onloadT: Date.now(),
                pageT: Date.now() + Math.random() * 100,
                startE: Date.now() - Math.random() * 1000,
                tran: 15
            });
            
            window.chrome.loadTimes = () => ({
                commitLoadTime: Date.now() / 1000 - Math.random() * 10,
                connectionInfo: 'h2',
                finishDocumentLoadTime: Date.now() / 1000 - Math.random() * 10,
                finishLoadTime: Date.now() / 1000 - Math.random() * 10,
                firstPaintAfterLoadTime: 0,
                firstPaintTime: Date.now() / 1000 - Math.random() * 10,
                navigationType: 'Other',
                npnNegotiatedProtocol: 'h2',
                requestTime: Date.now() / 1000 - Math.random() * 10,
                startLoadTime: Date.now() / 1000 - Math.random() * 10,
                wasAlternateProtocolAvailable: false,
                wasFetchedViaSpdy: true,
                wasNpnNegotiated: true
            });
            
            window.chrome.webstore = {
                install: () => {},
                onDownloadProgress: {},
                onInstallStageChanged: {}
            };
            
            // Permissions should work like real Chrome
            if (navigator.permissions && navigator.permissions.query) {
                const originalQuery = navigator.permissions.query;
                navigator.permissions.query = function(parameters) {
                    if (parameters.name === 'webdriver') {
                        return Promise.reject(new Error('Unknown permission'));
                    }
                    return originalQuery.apply(this, arguments);
                };
            }
            
            // Plugin detection - define once without getters
            const pluginData = [
                {
                    name: 'PDF Viewer',
                    description: 'Portable Document Format',
                    filename: 'internal-pdf-viewer',
                    mimeTypes: [{
                        type: 'application/pdf',
                        suffixes: 'pdf',
                        description: 'Portable Document Format'
                    }]
                },
                {
                    name: 'Chrome PDF Viewer',
                    description: 'Portable Document Format',
                    filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                    mimeTypes: [{
                        type: 'application/x-google-chrome-pdf',
                        suffixes: 'pdf',
                        description: 'Portable Document Format'
                    }]
                },
                {
                    name: 'Chromium PDF Plugin',
                    description: 'Portable Document Format',
                    filename: 'internal-pdf-viewer',
                    mimeTypes: [{
                        type: 'application/x-nacl',
                        suffixes: '',
                        description: 'Native Client Executable'
                    }]
                },
                {
                    name: 'Microsoft Edge PDF Viewer',
                    description: 'Portable Document Format',
                    filename: 'internal-pdf-viewer',
                    mimeTypes: [{
                        type: 'application/pdf',
                        suffixes: 'pdf',
                        description: 'Portable Document Format'
                    }]
                },
                {
                    name: 'WebKit built-in PDF',
                    description: 'Portable Document Format',
                    filename: 'internal-pdf-viewer',
                    mimeTypes: [{
                        type: 'application/pdf',
                        suffixes: 'pdf',
                        description: 'Portable Document Format'
                    }]
                }
            ];
            
            // Create plugins
            const plugins = [];
            pluginData.forEach((p, index) => {
                const plugin = Object.create(Plugin.prototype);
                plugin.name = p.name;
                plugin.description = p.description;
                plugin.filename = p.filename;
                plugin.length = p.mimeTypes.length;
                
                p.mimeTypes.forEach((mt, mtIndex) => {
                    const mimeType = Object.create(MimeType.prototype);
                    mimeType.type = mt.type;
                    mimeType.suffixes = mt.suffixes;
                    mimeType.description = mt.description;
                    mimeType.enabledPlugin = plugin;
                    plugin[mtIndex] = mimeType;
                });
                
                plugins.push(plugin);
            });
            
            // Override navigator.plugins
            Object.defineProperty(navigator, 'plugins', {
                get: function() {
                    const arr = Object.create(PluginArray.prototype);
                    plugins.forEach((p, i) => {
                        arr[i] = p;
                        arr[p.name] = p;
                    });
                    arr.length = plugins.length;
                    arr.item = function(i) { return this[i]; };
                    arr.namedItem = function(name) { return this[name]; };
                    arr.refresh = function() {};
                    return arr;
                },
                enumerable: true,
                configurable: false
            });
            
            // Fix Notification permissions
            if (window.Notification) {
                const OriginalNotification = window.Notification;
                const notificationPermission = 'default';
                
                // Override Notification
                window.Notification = function(...args) {
                    return new OriginalNotification(...args);
                };
                
                // Copy static properties
                window.Notification.permission = notificationPermission;
                window.Notification.requestPermission = OriginalNotification.requestPermission;
                
                // Copy prototype
                window.Notification.prototype = OriginalNotification.prototype;
            }
            
            // WebGL - Force enable and patch all methods
            try {
                // First, ensure WebGL is available
                if (!window.WebGLRenderingContext) {
                    console.warn('WebGL not available in this browser');
                }
                
                // Store original getContext before any modifications
                const originalGetContext = HTMLCanvasElement.prototype.getContext;
                const contexts = new WeakMap();
                
                // Override getContext completely
                HTMLCanvasElement.prototype.getContext = function(contextType, contextAttributes) {
                    console.log('getContext called with:', contextType);
                    
                    // For WebGL contexts, ensure they work
                    if (contextType === 'webgl' || contextType === 'webgl2' || contextType === 'experimental-webgl') {
                        // Try to get context with specific attributes
                        const attrs = contextAttributes || {
                            alpha: true,
                            depth: true,
                            stencil: false,
                            antialias: true,
                            premultipliedAlpha: true,
                            preserveDrawingBuffer: false,
                            powerPreference: 'default',
                            failIfMajorPerformanceCaveat: false,
                            desynchronized: false
                        };
                        
                        // Try different context types
                        let context = null;
                        const contextTypes = ['webgl2', 'webgl', 'experimental-webgl'];
                        
                        for (const type of contextTypes) {
                            try {
                                context = originalGetContext.call(this, type, attrs);
                                if (context) break;
                            } catch (e) {
                                console.warn(`Failed to create ${type} context:`, e);
                            }
                        }
                        
                        if (!context) {
                            console.error('Failed to create any WebGL context');
                            // Return a mock context as last resort
                            context = {
                                canvas: this,
                                drawingBufferWidth: this.width,
                                drawingBufferHeight: this.height,
                                getParameter: function(param) {
                                    if (param === 37445) return 'Intel Inc.';
                                    if (param === 37446) return 'Intel Iris OpenGL Engine';
                                    if (param === 7936) return 'WebKit';
                                    if (param === 7937) return 'WebKit WebGL';
                                    if (param === 7938) return '2.0';
                                    if (param === 35724) return 'WebGL GLSL ES 1.0';
                                    return 0;
                                },
                                getExtension: function(name) {
                                    if (name === 'WEBGL_debug_renderer_info') {
                                        return {
                                            UNMASKED_VENDOR_WEBGL: 37445,
                                            UNMASKED_RENDERER_WEBGL: 37446
                                        };
                                    }
                                    return null;
                                },
                                getSupportedExtensions: function() {
                                    return ['WEBGL_debug_renderer_info'];
                                },
                                getContextAttributes: function() {
                                    return attrs;
                                }
                            };
                        } else {
                            // Wrap real context
                            const originalGetParameter = context.getParameter.bind(context);
                            const originalGetExtension = context.getExtension.bind(context);
                            
                            context.getParameter = function(param) {
                                console.log('getParameter called with:', param);
                                if (param === 37445) return 'Intel Inc.';
                                if (param === 37446) return 'Intel Iris OpenGL Engine';
                                try {
                                    return originalGetParameter(param);
                                } catch (e) {
                                    return 0;
                                }
                            };
                            
                            context.getExtension = function(name) {
                                console.log('getExtension called with:', name);
                                if (name === 'WEBGL_debug_renderer_info') {
                                    return {
                                        UNMASKED_VENDOR_WEBGL: 37445,
                                        UNMASKED_RENDERER_WEBGL: 37446
                                    };
                                }
                                try {
                                    return originalGetExtension(name);
                                } catch (e) {
                                    return null;
                                }
                            };
                        }
                        
                        contexts.set(this, context);
                        return context;
                    }
                    
                    // For other context types, use original
                    return originalGetContext.call(this, contextType, contextAttributes);
                };
                
                // Also patch the WebGL prototypes if they exist
                if (window.WebGLRenderingContext) {
                    const proto = WebGLRenderingContext.prototype;
                    const originalGetParameter = proto.getParameter;
                    
                    proto.getParameter = function(param) {
                        if (param === 37445) return 'Intel Inc.';
                        if (param === 37446) return 'Intel Iris OpenGL Engine';
                        return originalGetParameter.call(this, param);
                    };
                    
                    // Ensure getExtension works
                    const originalGetExtension = proto.getExtension;
                    proto.getExtension = function(name) {
                        if (name === 'WEBGL_debug_renderer_info') {
                            return {
                                UNMASKED_VENDOR_WEBGL: 37445,
                                UNMASKED_RENDERER_WEBGL: 37446
                            };
                        }
                        return originalGetExtension.call(this, name);
                    };
                }
                
                if (window.WebGL2RenderingContext) {
                    const proto = WebGL2RenderingContext.prototype;
                    const originalGetParameter = proto.getParameter;
                    
                    proto.getParameter = function(param) {
                        if (param === 37445) return 'Intel Inc.';
                        if (param === 37446) return 'Intel Iris OpenGL Engine';
                        return originalGetParameter.call(this, param);
                    };
                }
                
                // Test WebGL immediately
                try {
                    const testCanvas = document.createElement('canvas');
                    const testContext = testCanvas.getContext('webgl') || testCanvas.getContext('experimental-webgl');
                    if (testContext) {
                        console.log('WebGL test successful');
                    } else {
                        console.warn('WebGL test failed - no context');
                    }
                } catch (e) {
                    console.error('WebGL test error:', e);
                }
                
            } catch(e) {
                console.error('Critical error in WebGL override:', e);
            }
            
            // Override toString to prevent detection
            const nativeToStringFunction = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.permissions.query) {
                    return 'function query() { [native code] }';
                }
                if (this === WebGLRenderingContext.prototype.getParameter) {
                    return 'function getParameter() { [native code] }';
                }
                if (window.WebGL2RenderingContext && this === WebGL2RenderingContext.prototype.getParameter) {
                    return 'function getParameter() { [native code] }';
                }
                return nativeToStringFunction.call(this);
            };
            
            // Simple property overrides without getters
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                value: 8,
                writable: false,
                enumerable: true,
                configurable: false
            });
            
            Object.defineProperty(navigator, 'deviceMemory', {
                value: 8,
                writable: false,
                enumerable: true,
                configurable: false
            });
            
            // Fix language detection - ensure it works everywhere
            const originalLanguageGetter = Object.getOwnPropertyDescriptor(Navigator.prototype, 'language');
            Object.defineProperty(navigator, 'language', {
                get: function() { return 'it-IT'; },
                enumerable: true,
                configurable: false
            });
            
            Object.defineProperty(navigator, 'languages', {
                get: function() { return ['it-IT', 'it', 'en-US', 'en']; },
                enumerable: true,
                configurable: false
            });
            
            // Connection info
            if (!navigator.connection) {
                Object.defineProperty(navigator, 'connection', {
                    value: {
                        downlink: 10,
                        effectiveType: '4g',
                        rtt: 50,
                        saveData: false,
                        addEventListener: () => {},
                        removeEventListener: () => {},
                        dispatchEvent: () => true
                    },
                    writable: false,
                    enumerable: true,
                    configurable: false
                });
            }
            
            // MediaDevices
            if (navigator.mediaDevices && navigator.mediaDevices.enumerateDevices) {
                navigator.mediaDevices.enumerateDevices = async () => {
                    return [
                        {
                            deviceId: "default",
                            kind: "audioinput",
                            label: "Default - Microphone (Realtek(R) Audio)",
                            groupId: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                        },
                        {
                            deviceId: "communications",
                            kind: "audioinput",
                            label: "Communications - Microphone (Realtek(R) Audio)",
                            groupId: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
                        },
                        {
                            deviceId: "default",
                            kind: "audiooutput",
                            label: "Default - Speakers (Realtek(R) Audio)",
                            groupId: "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890"
                        }
                    ];
                };
            }
            
            // Battery API
            if (navigator.getBattery) {
                navigator.getBattery = () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1.0,
                    addEventListener: () => {},
                    removeEventListener: () => {},
                    dispatchEvent: () => true
                });
            }
            
            // Remove Playwright specific properties
            delete window.__playwright;
            delete window.__pw_manual;
            delete window.__PW_inspect;
            delete window.playwright;
            
            // Additional anti-detection measures
            // Prevent stack trace analysis
            const originalError = Error;
            window.Error = function(...args) {
                const error = new originalError(...args);
                // Clean stack traces that might reveal automation
                if (error.stack) {
                    error.stack = error.stack
                        .split('\n')
                        .filter(line => !line.includes('playwright') && !line.includes('puppeteer'))
                        .join('\n');
                }
                return error;
            };
            window.Error.prototype = originalError.prototype;
            
            // Prevent timing attacks
            const originalDateNow = Date.now;
            let lastTime = originalDateNow();
            Date.now = function() {
                // Add small random variance to prevent timing fingerprinting
                const now = originalDateNow();
                if (now - lastTime < 5) {
                    return lastTime;
                }
                lastTime = now + (Math.random() * 2 - 1);
                return Math.floor(lastTime);
            };
            
            // Hide automation in error messages
            const originalToString = Error.prototype.toString;
            Error.prototype.toString = function() {
                const result = originalToString.call(this);
                if (result.includes('playwright') || result.includes('puppeteer')) {
                    return 'Error';
                }
                return result;
            };
            
            // Freeze important objects to prevent modification
            try {
                Object.freeze(Navigator.prototype);
                Object.freeze(Window.prototype);
                Object.freeze(Document.prototype);
            } catch(e) {}
        })();
        """
        
        await context.add_init_script(stealth_script)
        logger.info("💉 Injected ultra-stealth scripts")
        
        # Store the stealth script for later re-application
        self._stealth_script = stealth_script
        
        # Inject sniper interface script
        await self._inject_sniper_interface(context)
    
    async def _inject_sniper_interface(self, context: BrowserContext):
        """Inject the sniper interface script into browser context"""
        try:
            # Read the sniper interface script
            script_path = Path(__file__).parent.parent / "browser_extensions" / "sniper_interface.js"
            
            if script_path.exists():
                with open(script_path, 'r', encoding='utf-8') as f:
                    sniper_script = f.read()
                
                await context.add_init_script(sniper_script)
                logger.info("🎯 Injected sniper interface script")
            else:
                logger.warning(f"⚠️ Sniper interface script not found at {script_path}")
                
        except Exception as e:
            logger.error(f"❌ Failed to inject sniper interface: {e}")
    
    async def reapply_stealth_to_page(self, page: Page):
        """Re-apply the same full stealth script to a specific page after reload"""
        try:
            if hasattr(self, '_stealth_script'):
                # Use add_init_script approach for consistency, but inject into existing page
                # by executing the script as a function
                await page.add_script_tag(content=self._stealth_script)
                logger.debug("✅ Re-applied full stealth script successfully")
            else:
                logger.warning("⚠️ Stealth script not available for re-application")
                
        except Exception as e:
            logger.warning(f"⚠️ Could not re-apply stealth modifications via script tag: {e}")
            # Fallback: try a simpler approach
            try:
                # Extract just the essential parts for evaluation
                essential_script = """
                (function() {
                    try {
                        // Override webdriver
                        Object.defineProperty(Object.getPrototypeOf(navigator), 'webdriver', {
                            get: () => false, enumerable: false, configurable: false
                        });
                        
                        // Remove automation traces
                        ['webdriver', 'driver', 'selenium', '__playwright', '__pw_manual'].forEach(prop => {
                            try { delete window[prop]; delete navigator[prop]; } catch(e) {}
                        });
                        
                        // Ensure chrome exists
                        if (!window.chrome) window.chrome = { app: { isInstalled: false }, runtime: {} };
                        
                        console.log('Essential stealth reapplied');
                    } catch(e) { console.warn('Stealth reapplication error:', e); }
                })();
                """
                await page.evaluate(essential_script)
                logger.debug("✅ Applied essential stealth via fallback")
            except Exception as fallback_error:
                logger.debug(f"Fallback also failed: {fallback_error}")
                # Continue anyway - page might still work
        
        # Also reapply sniper interface if on attack confirmation page
        try:
            if 'screen=place&try=confirm' in page.url:
                await self._reapply_sniper_interface(page)
        except Exception as e:
            logger.debug(f"Could not reapply sniper interface: {e}")
    
    async def _reapply_sniper_interface(self, page: Page):
        """Re-apply sniper interface to a specific page"""
        try:
            script_path = Path(__file__).parent.parent / "browser_extensions" / "sniper_interface.js"
            
            if script_path.exists():
                with open(script_path, 'r', encoding='utf-8') as f:
                    sniper_script = f.read()
                
                await page.add_script_tag(content=sniper_script)
                logger.debug("🎯 Re-applied sniper interface script")
        except Exception as e:
            logger.debug(f"Failed to reapply sniper interface: {e}")
        
    async def initialize(self):
        """Initialize browser with maximum stealth"""
        if self._initialized:
            logger.warning("⚠️ Browser manager already initialized")
            return
            
        logger.info("🌐 Initializing stealth browser...")
        
        try:
            self.playwright = await async_playwright().start()
            
            # Get Chrome path
            chrome_path = self._get_real_chrome_path()
            if not chrome_path:
                raise Exception("Chrome not found! Please install Google Chrome.")
                
            # Prepare launch options
            browser_config = self.config.get('browser', {})
            stealth_args = self._get_stealth_args()
            context_options = self._get_enhanced_context_options()
            
            launch_options = {
                'headless': False,  # Never run headless
                'executable_path': chrome_path,
                'args': stealth_args,
                'ignore_default_args': [
                    '--enable-automation',
                    '--enable-blink-features=AutomationControlled'
                ],
                'handle_sigint': False,
                'handle_sigterm': False,
                'handle_sighup': False
            }
            
            # Slow motion for more human-like behavior
            if browser_config.get('slow_mo'):
                launch_options['slow_mo'] = browser_config['slow_mo']
                
            # Launch browser
            if self.incognito_mode:
                logger.info("🥷 Launching Chrome in incognito mode...")
                self.browser = await self.playwright.chromium.launch(**launch_options)
                self.main_context = await self.browser.new_context(
                    **context_options,
                    no_viewport=False
                )
            else:
                logger.info("💾 Launching Chrome with persistent profile...")
                # Use launch_persistent_context for profile persistence
                self.main_context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir.absolute()),
                    **launch_options,
                    **context_options,
                    no_viewport=False
                )
                
            # Inject stealth scripts
            await self._inject_ultra_stealth_scripts(self.main_context)
            
            # Set up request interception
            await self.main_context.route('**/*', self._handle_request)
            
            # Verify stealth
            await self._verify_stealth_enhanced()
            
            # Note: Automatic hCaptcha test removed to avoid interfering with game operations
            # Use dashboard test button for manual testing
            
            # Handle login
            logged_in = await self.login_handler.ensure_logged_in(self.main_context)
            if not logged_in:
                raise Exception("Login failed")
                
            # Clean up and setup
            await self._cleanup_and_verify_game_page()
            
            # Verify storage
            if not self.incognito_mode:
                await self._verify_storage_persistence()
                
            # Check for initial protection
            await self._check_initial_protection()
            
            # Start monitoring
            asyncio.create_task(self.captcha_detector.start_monitoring())
            self._monitor_task = asyncio.create_task(self._monitor_pages())
            
            self._initialized = True
            logger.info("✅ Stealth browser initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize browser: {e}", exc_info=True)
            await self.cleanup()
            raise
            
    async def _test_hcaptcha(self):
        """Quick test to verify captcha solver and detector are working"""
        logger.info("🧪 Quick hCaptcha test - checking solver and detector...")
        
        try:
            # Test 1: Check if captcha solver is properly configured
            from ..captcha.solver import CaptchaSolver
            test_solver = CaptchaSolver(self.config, self.anti_detection_manager)
            logger.info("✅ Captcha solver initialized successfully")
            
            # Test 2: Check if hcaptcha-challenger is available
            try:
                import hcaptcha_challenger
                logger.info("✅ hcaptcha-challenger library available")
            except ImportError:
                logger.error("❌ hcaptcha-challenger library not available")
                return
            
            # Test 3: Check if Gemini API key is configured
            gemini_key = os.getenv('GEMINI_API_KEY')
            if gemini_key and len(gemini_key) > 10:
                logger.info("✅ Gemini API key configured")
            else:
                logger.warning("⚠️ Gemini API key not configured - manual solving only")
            
            # Test 4: Check captcha detector availability (it starts later in the process)
            if hasattr(self, 'captcha_detector') and self.captcha_detector:
                logger.info("✅ Captcha detector initialized (will start monitoring after browser setup)")
            else:
                logger.warning("⚠️ Captcha detector not available")
            
            # Test 5: Quick browser capabilities test
            test_page = await self.main_context.new_page()
            await test_page.goto('data:text/html,<html><body><h1>Test Page</h1><iframe src="about:blank"></iframe></body></html>')
            
            # Check if we can detect iframes
            iframe_count = await test_page.evaluate("document.querySelectorAll('iframe').length")
            if iframe_count > 0:
                logger.info("✅ Browser can detect iframes")
            else:
                logger.warning("⚠️ Browser iframe detection issue")
            
            await test_page.close()
            
            # Test 6: Anti-detection manager
            if hasattr(self, 'anti_detection_manager'):
                logger.info("✅ Anti-detection manager available")
                # Test suspend/resume
                original_state = self.anti_detection_manager.suspended
                self.anti_detection_manager.suspend("test")
                if self.anti_detection_manager.suspended:
                    logger.info("✅ Anti-detection suspend works")
                    self.anti_detection_manager.resume()
                    if not self.anti_detection_manager.suspended:
                        logger.info("✅ Anti-detection resume works")
                    else:
                        logger.warning("⚠️ Anti-detection resume failed")
                else:
                    logger.warning("⚠️ Anti-detection suspend failed")
                # Restore original state
                if original_state and not self.anti_detection_manager.suspended:
                    self.anti_detection_manager.suspend("restore")
            
            logger.info("🧪 ✅ hCaptcha test completed - All components ready!")
            logger.info("💡 To test actual solving, visit https://accounts.hcaptcha.com/demo manually")
            logger.info("💡 Or use the dashboard button to run a live test")
            
        except Exception as e:
            logger.error(f"❌ hCaptcha test failed: {e}", exc_info=True)
    
    async def test_hcaptcha_live(self):
        """Simple hCaptcha demo test - opens demo site for manual testing"""
        logger.info("🧪 Opening hCaptcha demo site for testing...")
        
        try:
            # Create a new page for testing
            test_page = await self.main_context.new_page()
            
            # Navigate to hCaptcha demo
            await test_page.goto('https://accounts.hcaptcha.com/demo', wait_until='domcontentloaded')
            
            # Take a screenshot
            await screenshot_manager.capture_debug(test_page, "hcaptcha_demo_opened")
            
            logger.info("✅ hCaptcha demo page opened")
            logger.info("💡 You can manually test captcha solving by clicking the checkbox")
            logger.info("💡 Close the tab when done testing")
            
            return test_page
            
        except Exception as e:
            logger.error(f"❌ Failed to open hCaptcha demo: {e}", exc_info=True)
            return None
    
    async def _open_dashboard_page(self):
        """Open the dashboard page in a new tab (with retry logic)"""
        try:
            # Get dashboard configuration
            dashboard_config = self.config.get('dashboard', {})
            dashboard_host = dashboard_config.get('host', '127.0.0.1')
            dashboard_port = dashboard_config.get('port', 8080)
            dashboard_url = f"http://{dashboard_host}:{dashboard_port}"
            
            # Wait a moment for dashboard server to be ready
            await asyncio.sleep(2)
            
            # Retry a few times in case dashboard server is still starting
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    # Create a new page for the dashboard
                    dashboard_page = await self.main_context.new_page()
                    
                    # Navigate to dashboard
                    logger.info(f"🌐 Opening dashboard at {dashboard_url} (attempt {attempt + 1})")
                    await dashboard_page.goto(dashboard_url, wait_until='domcontentloaded', timeout=5000)
                    
                    # Take a screenshot
                    await screenshot_manager.capture_debug(dashboard_page, "dashboard_opened")
                    
                    logger.info("✅ Dashboard page opened successfully")
                    return  # Success!
                    
                except Exception as retry_error:
                    logger.debug(f"Dashboard open attempt {attempt + 1} failed: {retry_error}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)  # Wait before retry
                    else:
                        raise retry_error  # Last attempt failed
            
        except Exception as e:
            logger.warning(f"⚠️ Could not open dashboard page after {max_retries} attempts: {e}")
            logger.info(f"💡 You can manually open the dashboard at http://127.0.0.1:8080")
            # Don't fail browser initialization if dashboard opening fails
            
    async def _handle_request(self, route: Route, request: Request):
        """Handle requests to ensure authenticity"""
        headers = dict(request.headers)
        
        # Remove automation headers
        headers_to_remove = [
            'x-devtools-emulate-network-conditions-client-id',
            'x-devtools-request-id',
            'x-automation-override'
        ]
        
        for header in headers_to_remove:
            headers.pop(header, None)
            
        # Ensure proper headers based on navigation
        if request.is_navigation_request():
            headers['sec-fetch-dest'] = 'document'
            headers['sec-fetch-mode'] = 'navigate'
            headers['sec-fetch-user'] = '?1'
            headers['upgrade-insecure-requests'] = '1'
            
        # Continue with modified headers
        await route.continue_(headers=headers)
        
    async def _verify_stealth_enhanced(self):
        """Enhanced stealth verification"""
        page = None
        try:
            page = await self.main_context.new_page()
            
            # Test comprehensive detection
            detection_tests = await page.evaluate("""
                async () => {
                    const tests = {
                        webdriver: navigator.webdriver,
                        headless: navigator.headless || false,
                        chrome: !!window.chrome,
                        chrome_runtime: !!(window.chrome && window.chrome.runtime),
                        permissions: typeof navigator.permissions !== 'undefined',
                        plugins_length: navigator.plugins.length,
                        languages: navigator.languages.length > 0,
                        webgl_vendor: null,
                        user_agent: navigator.userAgent,
                        platform: navigator.platform,
                        hardware_concurrency: navigator.hardwareConcurrency,
                        device_memory: navigator.deviceMemory || 0,
                        connection: !!(navigator.connection),
                        bluetooth: !!(navigator.bluetooth),
                        usb: !!(navigator.usb),
                        media_devices: !!(navigator.mediaDevices),
                        battery: typeof navigator.getBattery === 'function',
                        automation_strings: 0,
                        playwright_specific: false
                    };
                    
                    // Check WebGL
                    try {
                        const canvas = document.createElement('canvas');
                        const gl = canvas.getContext('webgl');
                        if (gl) {
                            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                            if (debugInfo) {
                                tests.webgl_vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
                            }
                        }
                    } catch (e) {}
                    
                    // Check for automation strings
                    const automationStrings = [
                        'webdriver', '__webdriver', '_selenium', '__selenium',
                        'callPhantom', '_phantom', '__nightmare', 'domAutomation',
                        'domAutomationController', '__$webdriverAsyncExecutor'
                    ];
                    
                    for (const prop of automationStrings) {
                        if (prop in window || prop in document) {
                            tests.automation_strings++;
                        }
                    }
                    
                    // Check for Playwright
                    tests.playwright_specific = !!(
                        window.__playwright || window.__pw_manual || 
                        window.__PW_inspect || window.playwright
                    );
                    
                    return tests;
                }
            """)
            
            # Log results
            logger.info("🔍 Stealth verification results:")
            logger.info(f"  ✓ Webdriver: {detection_tests['webdriver']} (should be false)")
            logger.info(f"  ✓ Chrome exists: {detection_tests['chrome']} (should be true)")
            logger.info(f"  ✓ Plugins: {detection_tests['plugins_length']} (should be > 0)")
            logger.info(f"  ✓ Languages: {detection_tests['languages']} (should be true)")
            logger.info(f"  ✓ WebGL vendor: {detection_tests['webgl_vendor']}")
            logger.info(f"  ✓ Platform: {detection_tests['platform']}")
            logger.info(f"  ✓ Automation strings: {detection_tests['automation_strings']} (should be 0)")
            logger.info(f"  ✓ Playwright detected: {detection_tests['playwright_specific']} (should be false)")
            
            # Warnings
            if detection_tests['webdriver']:
                logger.warning("⚠️ Webdriver property still detectable!")
            if detection_tests['automation_strings'] > 0:
                logger.warning(f"⚠️ Found {detection_tests['automation_strings']} automation strings!")
            if detection_tests['playwright_specific']:
                logger.warning("⚠️ Playwright specific properties detected!")
                
            # Test with external detector
            logger.info("🌐 Testing with external detector...")
            await page.goto('https://bot.sannysoft.com', wait_until='networkidle')
            await asyncio.sleep(2)
            
            # Take screenshot for verification
            await page.screenshot(path='stealth_test.png')
            logger.info("📸 Stealth test screenshot saved as stealth_test.png")
            
        except Exception as e:
            logger.error(f"Stealth verification error: {e}")
        finally:
            if page and not page.is_closed():
                await page.close()
                
    # Include all other methods from the original browser manager
    # (_cleanup_and_verify_game_page, _verify_storage_persistence, etc.)
    # Just copy them as-is since they don't need modification
    
    async def _cleanup_and_verify_game_page(self):
        """Clean up extra tabs and ensure we have game page"""
        logger.debug(f"📑 Current pages: {len(self.main_context.pages)}")
        
        game_page = None
        pages_to_close = []
        
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
                
        for page in pages_to_close:
            try:
                await page.close()
                logger.debug(f"🗑️ Closed extra page")
            except:
                pass
                
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


# Create an alias for backward compatibility
BrowserManager = StealthBrowserManager