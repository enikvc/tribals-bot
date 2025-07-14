"""
Scheduler - Updated with sleep mode that closes browser during inactive hours
"""
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from ..automations.auto_buyer import AutoBuyer
from ..automations.auto_farmer import AutoFarmer
from ..automations.auto_scavenger import AutoScavenger
from ..sniper.manager import SniperManager
from ..utils.logger import setup_logger
from ..utils.discord_webhook import DiscordNotifier
from ..utils.helpers import time_until_hour

logger = setup_logger(__name__)


class Scheduler:
    """Manages all automation scripts with sleep mode"""
    
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
        
        # Initialize sniper service
        self.sniper_manager = SniperManager(config, browser_manager)
        
        self.running = False
        self.emergency_stopped = False
        self.paused = False
        self.in_sleep_mode = False
        
    async def start(self):
        """Start the scheduler"""
        self.running = True
        self.emergency_stopped = False
        self.paused = False
        logger.info("📅 Scheduler started")
        
        # Initialize sniper service asynchronously (non-blocking)
        asyncio.create_task(self._initialize_sniper_async())
        
        # Check if we should start in sleep mode
        if not self.is_within_active_hours():
            await self.enter_sleep_mode()
        else:
            # Add a small delay to ensure captcha detector is fully initialized
            logger.info("⏳ Waiting for captcha detector initialization...")
            await asyncio.sleep(3)
            
            # Start enabled automations
            await self.start_enabled_automations()
        
        # Monitor active hours
        asyncio.create_task(self.monitor_active_hours())
    
    async def _initialize_sniper_async(self):
        """Initialize sniper service asynchronously without blocking startup"""
        try:
            logger.info("🎯 Initializing sniper service in background...")
            if await self.sniper_manager.initialize():
                logger.info("🎯 Sniper service ready for attack scheduling")
            else:
                logger.warning("⚠️ Sniper service failed to initialize - attacks won't be available")
        except Exception as e:
            logger.error(f"❌ Error initializing sniper service: {e}")
        
    async def stop(self):
        """Stop all automations"""
        self.running = False
        logger.info("📅 Stopping scheduler...")
        
        # Exit sleep mode if active
        if self.in_sleep_mode:
            await self.exit_sleep_mode()
        
        # Stop all automations
        for name, automation in self.automations.items():
            if automation.running:
                await automation.stop()
                
        # Stop sniper service
        await self.sniper_manager.shutdown()
                
        logger.info("📅 Scheduler stopped")
        
    async def enter_sleep_mode(self):
        """Enter sleep mode - close browser completely"""
        if self.in_sleep_mode:
            return
            
        logger.info("😴 Entering sleep mode - closing browser...")
        self.in_sleep_mode = True
        
        try:
            # Stop all running automations first
            await self.stop_all_automations()
            
            # Give automations time to clean up
            await asyncio.sleep(2)
            
            # Close the browser completely
            if self.browser_manager:
                await self.browser_manager.close_browser_for_sleep()
            
            # Calculate wake time
            start_hour = self.config['active_hours']['start']
            sleep_duration = time_until_hour(start_hour)
            wake_time = datetime.now() + timedelta(seconds=sleep_duration)
            
            logger.info(f"💤 Browser closed. Sleeping until {wake_time.strftime('%H:%M:%S')}")
            
            # Send Discord notification
            await self.discord.send_alert(
                "😴 Bot Sleeping",
                f"Bot entered sleep mode. Will wake at {wake_time.strftime('%H:%M:%S')}\n"
                f"Sleep duration: {sleep_duration // 3600}h {(sleep_duration % 3600) // 60}m"
            )
            
        except Exception as e:
            logger.error(f"❌ Error entering sleep mode: {e}", exc_info=True)
            self.in_sleep_mode = False
            
    async def exit_sleep_mode(self):
        """Exit sleep mode - restart browser and automations"""
        if not self.in_sleep_mode:
            return
            
        logger.info("🌅 Exiting sleep mode - restarting browser...")
        
        try:
            # Send wake notification
            await self.discord.send_success(
                "☀️ Bot Waking Up", 
                "Bot is waking from sleep mode. Reinitializing browser..."
            )
            
            # Reinitialize browser
            await self.browser_manager.reinitialize_after_sleep()
            
            # Wait for browser to be ready
            await asyncio.sleep(5)
            
            # Start enabled automations
            await self.start_enabled_automations()
            
            self.in_sleep_mode = False
            logger.info("✅ Successfully exited sleep mode")
            
            # Send ready notification
            await self.discord.send_success(
                "✅ Bot Active",
                "Bot is now active and automations are running"
            )
            
        except Exception as e:
            logger.error(f"❌ Error exiting sleep mode: {e}", exc_info=True)
            await self.discord.send_error("Failed to exit sleep mode", str(e))
            # Keep in sleep mode if we can't restart
            self.in_sleep_mode = True
        
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
        """Start all enabled automations with delay between each"""
        if self.emergency_stopped or self.paused or self.in_sleep_mode:
            return
            
        started_count = 0
        for name, automation in self.automations.items():
            script_config = self.config['scripts'].get(name, {})
            if script_config.get('enabled', False) and not automation.running:
                if self.is_within_active_hours():
                    logger.info(f"🚀 Starting {name}")
                    asyncio.create_task(automation.start())
                    started_count += 1
                    
                    # Add 2.5 second delay between automation starts
                    if started_count > 0:
                        logger.info(f"⏳ Waiting 2.5s before starting next automation...")
                        await asyncio.sleep(2.5)
                else:
                    logger.info(f"⏰ {name} enabled but outside active hours")
                    
    async def monitor_active_hours(self):
        """Monitor and enforce active hours with sleep mode"""
        last_active = self.is_within_active_hours()
        
        while self.running:
            try:
                current_active = self.is_within_active_hours()
                
                if current_active != last_active:
                    if current_active:
                        # Wake up
                        logger.info("🌅 Active hours started")
                        await self.exit_sleep_mode()
                    else:
                        # Go to sleep
                        logger.info("🌙 Active hours ended")
                        await self.enter_sleep_mode()
                        
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