"""Utility modules"""
from .logger import setup_logger
from .helpers import *
from .discord_webhook import DiscordNotifier
from .anti_detection import (
    AntiDetectionManager,
    HumanBehavior, 
    BrowserFingerprint, 
    SessionBehavior
)
# NetworkBehavior removed - we use authentic headers instead