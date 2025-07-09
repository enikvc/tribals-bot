"""
Scheduler - Manages automation lifecycle
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from ..automations.auto_buyer import AutoBuyer
from ..automations.auto_farmer import AutoFarmer
from ..automations.auto_scavenger import AutoScavenger
from ..utils.logger import setup_logger
from ..utils.discord_webhook import DiscordNotifier

logger = setup_logger(__name__)


class Scheduler:
    """Manages all automation scripts"""
    
    def __init__(self, config: Dict[str, Any], browser_manager):
        self.config = config
        self.browser_manager = browser_manager
        self.browser_manager.scheduler = self  # Add reference for captcha handling
        self.discord = DiscordNotifier(config.get('discord_webhook'))
        
        # Initialize automations
        self.automations = {
            'auto_buyer': AutoBuyer(config, browser_manager),
            'auto_farmer': AutoFarmer(config, browser_manager),
            'auto_scavenger': AutoScavenger(config, browser_manager)
        }
        
        self.running = False
        self.emergency_stopped = False
        self.paused = False
        
    async def start(self):
        """Start the scheduler"""
        self.running = True
        self.emergency_stopped = False
        self.paused = False
        logger.info("📅 Scheduler started")
        
        # Add a small delay to ensure captcha detector is fully initialized
        logger.info("⏳ Waiting for captcha detector initialization...")
        await asyncio.sleep(3)
        
        # Start enabled automations
        await self.start_enabled_automations()
        
        # Monitor active hours
        asyncio.create_task(self.monitor_active_hours())
        
    async def stop(self):
        """Stop all automations"""
        self.running = False
        logger.info("📅 Stopping scheduler...")
        
        # Stop all automations
        for name, automation in self.automations.items():
            if automation.running:
                await automation.stop()
                
        logger.info("📅 Scheduler stopped")
        
    async def pause_all_automations(self, reason: str):
        """Pause all automations without stopping them (keeps pages open)"""
        logger.warning(f"⏸️ PAUSING ALL AUTOMATIONS: {reason}")
        self.paused = True
        
        # Set paused flag on all automations
        for name, automation in self.automations.items():
            if automation.running:
                automation.paused = True
                logger.info(f"⏸️ Paused {name}")
                
        # Send Discord notification
        await self.discord.send_alert(
            "⏸️ Automations Paused",
            f"All automations paused: {reason}"
        )
        
    async def emergency_stop(self, reason: str):
        """Emergency stop all automations"""
        logger.error(f"🚨 EMERGENCY STOP: {reason}")
        self.emergency_stopped = True
        
        # Stop all automations immediately
        tasks = []
        for name, automation in self.automations.items():
            if automation.running:
                tasks.append(automation.stop())
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
        # Send Discord notification
        await self.discord.send_alert(
            "🚨 Emergency Stop",
            f"All automations stopped: {reason}"
        )
        
    async def resume_after_captcha(self):
        """Resume automations after captcha is solved"""
        if self.paused:
            logger.info("▶️ Resuming paused automations after captcha")
            self.paused = False
            
            # Resume all paused automations
            for name, automation in self.automations.items():
                if automation.running and hasattr(automation, 'paused'):
                    automation.paused = False
                    logger.info(f"▶️ Resumed {name}")
                    
            # Send Discord notification
            await self.discord.send_success(
                "✅ Automations Resumed",
                "Captcha/bot protection solved, automations resumed"
            )
            
        elif self.emergency_stopped:
            logger.info("🔄 Restarting automations after emergency stop")
            self.emergency_stopped = False
            
            # Restart enabled automations
            await self.start_enabled_automations()
            
            # Send Discord notification
            await self.discord.send_success(
                "✅ Automations Restarted",
                "Captcha/bot protection solved, automations restarted"
            )
        
    async def start_enabled_automations(self):
        """Start all enabled automations"""
        if self.emergency_stopped or self.paused:
            return
            
        for name, automation in self.automations.items():
            script_config = self.config['scripts'].get(name, {})
            if script_config.get('enabled', False) and not automation.running:
                if self.is_within_active_hours():
                    logger.info(f"🚀 Starting {name}")
                    asyncio.create_task(automation.start())
                else:
                    logger.info(f"⏰ {name} enabled but outside active hours")
                    
    async def monitor_active_hours(self):
        """Monitor and enforce active hours"""
        last_active = self.is_within_active_hours()
        
        while self.running:
            try:
                current_active = self.is_within_active_hours()
                
                if current_active != last_active:
                    if current_active:
                        logger.info("🌅 Active hours started")
                        await self.start_enabled_automations()
                    else:
                        logger.info("🌙 Active hours ended")
                        await self.stop_all_automations()
                        
                    last_active = current_active
                    
                # Check every minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in active hours monitor: {e}", exc_info=True)
                await asyncio.sleep(60)
                
    async def stop_all_automations(self):
        """Stop all running automations"""
        tasks = []
        for name, automation in self.automations.items():
            if automation.running:
                tasks.append(automation.stop())
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    def is_within_active_hours(self) -> bool:
        """Check if current time is within active hours"""
        now = datetime.now()
        current_hour = now.hour
        
        start_hour = self.config['active_hours']['start']
        end_hour = self.config['active_hours']['end']
        
        if start_hour < end_hour:
            return start_hour <= current_hour < end_hour
        else:
            # Crosses midnight
            return current_hour >= start_hour or current_hour < end_hour