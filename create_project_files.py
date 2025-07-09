#!/usr/bin/env python3
"""
Create all project files for Tribals Bot Python
"""
import os
from pathlib import Path

# Create directory structure
directories = [
    "src",
    "src/core",
    "src/automations", 
    "src/captcha",
    "src/utils",
    "src/vendor",
    "logs",
    "vendor",
    "browser_data"
]

for dir_path in directories:
    Path(dir_path).mkdir(parents=True, exist_ok=True)

# File contents
files = {
    "requirements.txt": """playwright==1.40.0
pyyaml==6.0.1
python-dotenv==1.0.0
requests==2.31.0
aiofiles==23.2.1
schedule==1.2.0
coloredlogs==15.0.1
discord-webhook==1.3.0
""",

    ".env.example": """# Discord webhook for notifications
DISCORD_WEBHOOK=

# Tribals login credentials (optional - can login manually)
TRIBALS_USERNAME=
TRIBALS_PASSWORD=

# Server selection
TRIBALS_SERVER=it94
""",

    "config.yaml": """# Global Configuration
active_hours:
  start: 8  # 8:00 AM
  end: 3    # 3:00 AM (next day)

debug_mode: false
discord_webhook: ""

# Server Configuration
server:
  base_url: "https://it94.tribals.it"
  login_url: "https://www.tribals.it"
  
# Browser Configuration
browser:
  headless: false
  slow_mo: 0
  user_data_dir: "./browser_data"
  viewport:
    width: 1920
    height: 1080

# Automation Scripts Configuration
scripts:
  auto_buyer:
    enabled: false
    min_pp: 3000
    min_stock: 64
    post_buy_delay: 4800
    check_interval: 5000
    
  auto_farmer:
    enabled: false
    interval_seconds: 600
    plan_delay: 700
    icon_start_delay: 1000
    icon_click_interval: 300
    max_icons_per_run: 50
    
  auto_scavenger:
    enabled: false
    base_interval_seconds: 600
    interval_jitter_seconds: 60
    click_min_delay: 200
    click_max_delay: 800
    
# Captcha Configuration
captcha:
  max_retries: 3
  solver_timeout: 120
  detection_interval: 2000
  
# Logging Configuration
logging:
  level: INFO
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  file: "tribals_bot.log"
""",

    "src/__init__.py": '''"""
Tribals Bot Python Package
"""

__version__ = "1.0.0"
__author__ = "Tribals Bot Team"
''',

    "src/core/__init__.py": '''"""Core modules"""''',
    "src/automations/__init__.py": '''"""Automation modules"""''',
    "src/captcha/__init__.py": '''"""Captcha handling modules"""''',
    "src/utils/__init__.py": '''"""Utility modules"""''',
    "src/vendor/__init__.py": '''"""Vendor modules"""''',
}

# Create files
for file_path, content in files.items():
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Created {file_path}")

print("\n✅ All basic files created!")
print("\nNow you need to create the Python modules from the artifacts.")
print("The main modules to create are:")
print("- main.py")
print("- src/core/browser_manager.py")
print("- src/core/config_manager.py")
print("- src/core/scheduler.py")
print("- src/core/base_automation.py")
print("- src/automations/auto_buyer.py")
print("- src/automations/auto_farmer.py")
print("- src/automations/auto_scavenger.py")
print("- src/captcha/detector.py")
print("- src/captcha/solver.py")
print("- src/utils/logger.py")
print("- src/utils/helpers.py")
print("- src/utils/discord_webhook.py")
print("- src/vendor/download_scripts.py")