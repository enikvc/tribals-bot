"""
Discord Webhook Integration
"""
import aiohttp
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from .logger import setup_logger

logger = setup_logger(__name__)


class DiscordNotifier:
    """Sends notifications to Discord"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url
        
    async def send_notification(self, content: str, embeds: Optional[List[Dict]] = None):
        """Send a notification to Discord"""
        if not self.webhook_url:
            return
            
        payload = {
            "content": content,
            "username": "Tribals Bot",
            "embeds": embeds or []
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as response:
                    if response.status == 204:
                        logger.debug("Discord notification sent")
                    else:
                        logger.error(f"Discord webhook failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send Discord notification: {e}")
            
    async def send_alert(self, title: str, description: str):
        """Send an alert embed"""
        embed = {
            "title": title,
            "description": description,
            "color": 0xFF0000,  # Red
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.send_notification("", [embed])
        
    async def send_success(self, title: str, description: str):
        """Send a success embed"""
        embed = {
            "title": title,
            "description": description,
            "color": 0x00FF00,  # Green
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.send_notification("", [embed])
        
    async def send_error(self, title: str, error: str):
        """Send an error embed"""
        embed = {
            "title": f"❌ {title}",
            "description": f"```{error}```",
            "color": 0xFF0000,  # Red
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.send_notification("@everyone Bot error!", [embed])