#!/usr/bin/env python3
"""
Fixed Setup script for Tribals Bot
"""
import os
import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Check Python version"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        sys.exit(1)
    print(f"✅ Python {sys.version.split()[0]} detected")


def upgrade_pip():
    """Upgrade pip to latest version"""
    print("📦 Upgrading pip...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    print("✅ Pip upgraded")


def install_requirements():
    """Install Python requirements"""
    print("📦 Installing Python requirements...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    print("✅ Python requirements installed")


def install_playwright():
    """Install Playwright browsers"""
    print("🌐 Installing Playwright browsers...")
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])
    print("✅ Playwright browsers installed")


def install_hcaptcha_challenger_alternative():
    """Install hcaptcha-challenger with alternative method"""
    print("🔧 Installing hcaptcha-challenger (alternative method)...")
    
    # First, install required dependencies
    deps = [
        "packaging>=23.0",
        "undetected-chromedriver>=3.5.0",
        "selenium>=4.0.0",
        "loguru>=0.6.0",
        "pyyaml>=6.0",
        "opencv-python>=4.0.0",
        "numpy>=1.20.0",
        "requests>=2.25.0"
    ]
    
    print("📦 Installing hcaptcha-challenger dependencies...")
    for dep in deps:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", dep])
        except:
            print(f"⚠️  Warning: Could not install {dep}")
    
    # Try to install hcaptcha-challenger
    try:
        # First try the specific release
        subprocess.check_call([
            sys.executable, "-m", "pip", "install",
            "hcaptcha-challenger==0.18.9"
        ])
        print("✅ hcaptcha-challenger installed successfully")
    except:
        print("⚠️  Could not install hcaptcha-challenger")
        print("   You can try manually later with:")
        print("   pip install hcaptcha-challenger")
        print("   or")
        print("   pip install git+https://github.com/QIN2DIM/hcaptcha-challenger.git@main")
        print("")
        print("   The bot will still work but without automatic captcha solving.")


def create_directories():
    """Create necessary directories"""
    dirs = ["logs", "vendor", "browser_data", "src/core", "src/automations", "src/captcha", "src/utils", "src/vendor"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True, parents=True)
    print("✅ Directories created")


def create_env_file():
    """Create .env file if it doesn't exist"""
    if not Path(".env").exists():
        if Path(".env.example").exists():
            Path(".env").write_text(Path(".env.example").read_text())
            print("✅ Created .env file from .env.example")
        else:
            # Create a basic .env file
            env_content = """# Discord webhook for notifications
DISCORD_WEBHOOK=

# Tribals login credentials (optional - can login manually)
TRIBALS_USERNAME=
TRIBALS_PASSWORD=

# Server selection
TRIBALS_SERVER=it94
"""
            Path(".env").write_text(env_content)
            print("✅ Created .env file with defaults")
    else:
        print("ℹ️ .env file already exists")


def create_alternative_solver():
    """Create alternative captcha solver that doesn't require hcaptcha-challenger"""
    alt_solver = '''"""
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
'''
    
    # Save fallback solver
    solver_path = Path("src/captcha/solver_fallback.py")
    solver_path.parent.mkdir(parents=True, exist_ok=True)
    solver_path.write_text(alt_solver)
    print("✅ Created fallback captcha solver")


def main():
    """Main setup function"""
    print("🚀 Setting up Tribals Bot Python...")
    print("-" * 50)
    
    check_python_version()
    upgrade_pip()
    install_requirements()
    install_playwright()
    install_hcaptcha_challenger_alternative()
    create_directories()
    create_env_file()
    create_alternative_solver()
    
    print("-" * 50)
    print("✅ Setup complete!")
    print("\nNext steps:")
    print("1. Edit .env file with your settings")
    print("2. Adjust config.yaml as needed")
    print("3. Copy Python module code from artifacts to appropriate files")
    print("4. Run: python main.py")
    print("\nNote: If captcha solving doesn't work automatically,")
    print("      you'll need to solve captchas manually when prompted.")


if __name__ == "__main__":
    main()