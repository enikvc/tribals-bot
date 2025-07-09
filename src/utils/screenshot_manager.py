"""
Screenshot Manager - Centralized screenshot handling with organized storage
"""
import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional
from playwright.async_api import Page

from .logger import setup_logger

logger = setup_logger(__name__)


class ScreenshotManager:
    """Manages screenshot capture and storage organization"""
    
    def __init__(self, base_dir: str = "screenshots"):
        self.base_dir = Path(base_dir)
        self.ensure_directories()
        
    def ensure_directories(self):
        """Create screenshot directory structure"""
        # Main directories
        dirs = [
            self.base_dir,
            self.base_dir / "errors",
            self.base_dir / "captcha",
            self.base_dir / "automation",
            self.base_dir / "debug",
            self.base_dir / "login",
            self.base_dir / "bot_protection"
        ]
        
        for dir_path in dirs:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        logger.debug(f"📁 Screenshot directories ready: {self.base_dir}")
        
    def get_filename(self, category: str, script_name: str = "", description: str = "") -> str:
        """Generate organized filename with timestamp"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        parts = [timestamp]
        if script_name:
            parts.append(script_name)
        if description:
            # Clean description for filename
            clean_desc = "".join(c for c in description if c.isalnum() or c in "._-")[:30]
            parts.append(clean_desc)
            
        filename = "_".join(parts) + ".png"
        return filename
        
    def get_filepath(self, category: str, filename: str) -> Path:
        """Get full filepath for category"""
        return self.base_dir / category / filename
        
    async def capture_error(self, page: Page, script_name: str, error_description: str) -> Optional[str]:
        """Capture error screenshot"""
        try:
            filename = self.get_filename("errors", script_name, error_description)
            filepath = self.get_filepath("errors", filename)
            
            await page.screenshot(path=str(filepath), full_page=True)
            logger.debug(f"📸 Error screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to capture error screenshot: {e}")
            return None
            
    async def capture_captcha(self, page: Page, captcha_type: str = "unknown") -> Optional[str]:
        """Capture captcha screenshot"""
        try:
            filename = self.get_filename("captcha", "", captcha_type)
            filepath = self.get_filepath("captcha", filename)
            
            await page.screenshot(path=str(filepath))
            logger.debug(f"📸 Captcha screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to capture captcha screenshot: {e}")
            return None
            
    async def capture_automation(self, page: Page, script_name: str, step: str) -> Optional[str]:
        """Capture automation step screenshot"""
        try:
            filename = self.get_filename("automation", script_name, step)
            filepath = self.get_filepath("automation", filename)
            
            await page.screenshot(path=str(filepath))
            logger.debug(f"📸 Automation screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to capture automation screenshot: {e}")
            return None
            
    async def capture_debug(self, page: Page, context: str) -> Optional[str]:
        """Capture debug screenshot"""
        try:
            filename = self.get_filename("debug", "", context)
            filepath = self.get_filepath("debug", filename)
            
            await page.screenshot(path=str(filepath), full_page=True)
            logger.debug(f"📸 Debug screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to capture debug screenshot: {e}")
            return None
            
    async def capture_login(self, page: Page, step: str) -> Optional[str]:
        """Capture login process screenshot"""
        try:
            filename = self.get_filename("login", "", step)
            filepath = self.get_filepath("login", filename)
            
            await page.screenshot(path=str(filepath))
            logger.debug(f"📸 Login screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to capture login screenshot: {e}")
            return None
            
    async def capture_bot_protection(self, page: Page, step: str) -> Optional[str]:
        """Capture bot protection screenshot"""
        try:
            filename = self.get_filename("bot_protection", "", step)
            filepath = self.get_filepath("bot_protection", filename)
            
            await page.screenshot(path=str(filepath), full_page=True)
            logger.debug(f"📸 Bot protection screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to capture bot protection screenshot: {e}")
            return None
            
    async def capture_page_state(self, page: Page, script_name: str, state: str) -> Optional[str]:
        """Capture general page state"""
        try:
            filename = self.get_filename("debug", script_name, f"state_{state}")
            filepath = self.get_filepath("debug", filename)
            
            await page.screenshot(path=str(filepath))
            logger.debug(f"📸 Page state screenshot saved: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Failed to capture page state screenshot: {e}")
            return None
            
    def cleanup_old_screenshots(self, days: int = 7):
        """Clean up screenshots older than specified days"""
        import time
        
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        removed_count = 0
        
        try:
            for category_dir in self.base_dir.iterdir():
                if category_dir.is_dir():
                    for screenshot in category_dir.glob("*.png"):
                        if screenshot.stat().st_mtime < cutoff_time:
                            screenshot.unlink()
                            removed_count += 1
                            
            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} old screenshots")
                
        except Exception as e:
            logger.error(f"Error cleaning up screenshots: {e}")
            
    def get_stats(self) -> dict:
        """Get screenshot storage statistics"""
        stats = {
            "total_files": 0,
            "total_size_mb": 0,
            "by_category": {}
        }
        
        try:
            for category_dir in self.base_dir.iterdir():
                if category_dir.is_dir():
                    files = list(category_dir.glob("*.png"))
                    size = sum(f.stat().st_size for f in files)
                    
                    stats["by_category"][category_dir.name] = {
                        "files": len(files),
                        "size_mb": round(size / (1024 * 1024), 2)
                    }
                    
                    stats["total_files"] += len(files)
                    stats["total_size_mb"] += size
                    
            stats["total_size_mb"] = round(stats["total_size_mb"] / (1024 * 1024), 2)
            
        except Exception as e:
            logger.error(f"Error getting screenshot stats: {e}")
            
        return stats


# Global screenshot manager instance
screenshot_manager = ScreenshotManager()


# Convenience functions for easy imports
async def capture_error_screenshot(page: Page, script_name: str, error: str) -> Optional[str]:
    """Convenience function for error screenshots"""
    return await screenshot_manager.capture_error(page, script_name, error)


async def capture_captcha_screenshot(page: Page, captcha_type: str = "unknown") -> Optional[str]:
    """Convenience function for captcha screenshots"""
    return await screenshot_manager.capture_captcha(page, captcha_type)


async def capture_debug_screenshot(page: Page, context: str) -> Optional[str]:
    """Convenience function for debug screenshots"""
    return await screenshot_manager.capture_debug(page, context)