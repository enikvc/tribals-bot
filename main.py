#!/usr/bin/env python3
"""
Tribals Bot - Main entry point with screenshot management
"""
import asyncio
import signal
import sys
import os
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.browser_manager import BrowserManager
from src.core.config_manager import ConfigManager
from src.core.scheduler import Scheduler
from src.utils.logger import setup_logger
from src.utils.discord_webhook import DiscordNotifier
from src.utils.screenshot_manager import screenshot_manager
from src.vendor.download_scripts import download_external_scripts

logger = setup_logger(__name__)


class TribalsBot:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        self.browser_manager = None
        self.scheduler = None
        self.discord = DiscordNotifier(self.config.get('discord_webhook'))
        self.running = False
        self._shutdown_event = asyncio.Event()
        
    async def initialize(self):
        """Initialize the bot components"""
        logger.info("🚀 Initializing Tribals Bot...")
        
        try:
            # Create directories
            self._create_directories()
            
            # Download external scripts
            await download_external_scripts()
            
            # Verify required files exist
            required_files = [
                'vendor/farmgod.js',
                'vendor/massScavenge.js'
            ]
            
            for file_path in required_files:
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Required file missing: {file_path}")
            
            # Initialize browser
            self.browser_manager = BrowserManager(self.config)
            await self.browser_manager.initialize()
            
            # Initialize scheduler
            self.scheduler = Scheduler(self.config, self.browser_manager)
            
            # Clean up old screenshots (older than 7 days)
            screenshot_manager.cleanup_old_screenshots(7)
            
            # Log screenshot stats
            stats = screenshot_manager.get_stats()
            if stats['total_files'] > 0:
                logger.info(f"📸 Screenshot storage: {stats['total_files']} files ({stats['total_size_mb']:.1f} MB)")
            
            logger.info("✅ Initialization complete")
            
        except Exception as e:
            logger.error(f"❌ Initialization failed: {e}", exc_info=True)
            await self.discord.send_error("Bot initialization failed", str(e))
            raise
        
    def _create_directories(self):
        """Create all necessary directories"""
        dirs = [
            'logs',
            'vendor', 
            'browser_data',
            'screenshots',
            'screenshots/errors',
            'screenshots/captcha',
            'screenshots/automation',
            'screenshots/debug',
            'screenshots/login',
            'screenshots/bot_protection'
        ]
        
        for dir_name in dirs:
            Path(dir_name).mkdir(parents=True, exist_ok=True)
            
        logger.debug("📁 All directories created")
        
    async def start(self):
        """Start the bot"""
        self.running = True
        logger.info("🟢 Starting Tribals Bot")
        
        try:
            # Start scheduler
            await self.scheduler.start()
            
            # Send startup notification
            await self.discord.send_success(
                "🤖 Bot Started",
                f"Tribals Bot started successfully at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            # Wait until shutdown is requested
            await self._shutdown_event.wait()
                
        except KeyboardInterrupt:
            logger.info("⚠️ Keyboard interrupt received")
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
            await self.discord.send_error("Fatal error occurred", str(e))
            raise
        finally:
            await self.stop()
            
    async def stop(self):
        """Stop the bot gracefully"""
        if not self.running:
            return
            
        logger.info("🔴 Stopping Tribals Bot...")
        self.running = False
        
        try:
            if self.scheduler:
                await self.scheduler.stop()
                
            if self.browser_manager:
                await self.browser_manager.cleanup()
                
            # Clean up old screenshots on shutdown
            screenshot_manager.cleanup_old_screenshots(7)
            
            # Log final screenshot stats
            stats = screenshot_manager.get_stats()
            if stats['total_files'] > 0:
                logger.info(f"📸 Final screenshot count: {stats['total_files']} files ({stats['total_size_mb']:.1f} MB)")
                
            # Send shutdown notification
            await self.discord.send_alert(
                "🛑 Bot Stopped",
                f"Tribals Bot stopped at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)
            
        logger.info("👋 Tribals Bot stopped")
        
    def handle_signal(self, signum, frame):
        """Handle system signals"""
        logger.info(f"📡 Received signal {signum}")
        self._shutdown_event.set()
        

async def main():
    """Main entry point"""
    # Check Python version
    if sys.version_info < (3, 8):
        logger.error("❌ Python 3.8 or higher is required")
        sys.exit(1)
        
    bot = TribalsBot()
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, bot.handle_signal)
    signal.signal(signal.SIGTERM, bot.handle_signal)
    
    # Handle Windows signals
    if sys.platform == 'win32':
        import win32api
        import win32con
        
        def win_handler(ctrl_type):
            if ctrl_type in (win32con.CTRL_C_EVENT, win32con.CTRL_BREAK_EVENT):
                bot.handle_signal(ctrl_type, None)
                return True
            return False
            
        try:
            win32api.SetConsoleCtrlHandler(win_handler, True)
        except:
            pass  # win32api not available
    
    try:
        await bot.initialize()
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Failed to start bot: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure cleanup
        if bot.running:
            await bot.stop()


if __name__ == "__main__":
    # Set event loop policy for Windows
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)