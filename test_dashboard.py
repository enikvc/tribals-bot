#!/usr/bin/env python3
"""
Test Dashboard - Simple test to verify dashboard functionality
"""
import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.config_manager import ConfigManager
from src.dashboard.server import DashboardServer
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class MockScheduler:
    """Mock scheduler for testing dashboard"""
    
    def __init__(self):
        self.running = True
        self.paused = False
        self.emergency_stopped = False
        self.in_sleep_mode = False
        self.automations = {
            'auto_buyer': MockAutomation('auto_buyer'),
            'auto_farmer': MockAutomation('auto_farmer'),
            'auto_scavenger': MockAutomation('auto_scavenger')
        }
        self.browser_manager = MockBrowserManager()
    
    def is_within_active_hours(self):
        return True
    
    async def emergency_stop(self, reason):
        logger.info(f"Mock emergency stop: {reason}")
        self.emergency_stopped = True
    
    async def pause_all_automations(self, reason):
        logger.info(f"Mock pause all: {reason}")
        self.paused = True
    
    async def resume_after_captcha(self):
        logger.info("Mock resume after captcha")
        self.paused = False
        self.emergency_stopped = False


class MockAutomation:
    """Mock automation for testing"""
    
    def __init__(self, name):
        self.name = name
        self.running = name == 'auto_scavenger'  # Only scavenger enabled in config
        self.paused = False
        self.run_count = 42
        self.error_count = 1
        self.last_run_time = "2024-07-12T10:30:00"
        self.next_run_time = "2024-07-12T10:45:00"
    
    async def start(self):
        logger.info(f"Mock start {self.name}")
        self.running = True
    
    async def stop(self):
        logger.info(f"Mock stop {self.name}")
        self.running = False


class MockBrowserManager:
    """Mock browser manager for testing"""
    
    def __init__(self):
        self.browser = True  # Simulate browser connected
        self.pages = ['page1', 'page2']  # Simulate open pages
        self.stealth_active = True


async def test_dashboard():
    """Test the dashboard server"""
    try:
        # Load config
        config_manager = ConfigManager()
        
        # Create mock scheduler
        scheduler = MockScheduler()
        
        # Create dashboard
        dashboard = DashboardServer(scheduler, config_manager)
        
        # Start dashboard
        await dashboard.start(host="127.0.0.1", port=8080)
        
        logger.info("🌐 Dashboard test server started at http://127.0.0.1:8080")
        logger.info("📱 Open the URL in your browser to test the dashboard")
        logger.info("🛑 Press Ctrl+C to stop the test server")
        
        # Keep running until interrupted
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("⏹️ Stopping test server...")
        finally:
            await dashboard.stop()
            
    except Exception as e:
        logger.error(f"❌ Dashboard test failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_dashboard())