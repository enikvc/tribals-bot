"""
Auto Sniper - Example automation using the sniper service for precise attacks
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
import random

from ..core.base_automation import BaseAutomation
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AutoSniper(BaseAutomation):
    """Automated sniper using the high-precision Rust service"""
    
    @property
    def name(self) -> str:
        return "auto_sniper"
        
    @property
    def url_pattern(self) -> str:
        return "screen=overview"  # Can work from any screen
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Sniper configuration
        self.sniper_config = self.script_config
        self.check_interval = self.sniper_config.get('check_interval_seconds', 300)  # 5 minutes
        self.auto_snipe_range = self.sniper_config.get('auto_snipe_range', 50)  # Maximum coordinates difference
        self.min_units_threshold = self.sniper_config.get('min_units_threshold', 100)  # Minimum units to launch
        self.timing_offset_ms = self.sniper_config.get('timing_offset_ms', -500)  # Launch 500ms before landing
        
        # Target tracking
        self.known_targets: Dict[int, Dict[str, Any]] = {}
        self.scheduled_attacks: List[str] = []  # Track our attack IDs
        
    async def run_automation(self):
        """Main sniper automation loop"""
        while self.running and self.is_within_active_hours():
            try:
                # Check if paused
                if hasattr(self, 'paused') and self.paused:
                    logger.debug(f"{self.name} is paused, waiting...")
                    await asyncio.sleep(1)
                    continue
                    
                # Monitor for sniping opportunities
                await self.scan_for_targets()
                
                # Check on scheduled attacks
                await self.monitor_scheduled_attacks()
                
                # Increment run count
                self.run_count += 1
                self.last_run_time = datetime.now()
                logger.debug(f"✅ {self.name} completed scan #{self.run_count}")
                
                # Wait before next scan
                await asyncio.sleep(self.check_interval)
                    
            except Exception as e:
                logger.error(f"❌ Error in sniper loop: {e}", exc_info=True)
                self.error_count += 1
                await asyncio.sleep(30)  # Error recovery delay
                
    async def scan_for_targets(self):
        """Scan for incoming attacks that can be sniped"""
        try:
            # Navigate to incoming attacks view
            await self.navigate_to_url("screen=overview_villages&mode=incomings")
            await asyncio.sleep(2)
            
            # Extract incoming attacks data
            incoming_attacks = await self.extract_incoming_attacks()
            
            for attack in incoming_attacks:
                await self.evaluate_snipe_opportunity(attack)
                
        except Exception as e:
            logger.error(f"Error scanning for targets: {e}", exc_info=True)
            
    async def extract_incoming_attacks(self) -> List[Dict[str, Any]]:
        """Extract incoming attacks from the page"""
        try:
            # Extract attack data using JavaScript
            attacks_data = await self.page.evaluate("""
                () => {
                    const attacks = [];
                    const rows = document.querySelectorAll('#incomings_table tr');
                    
                    for (const row of rows) {
                        try {
                            const attackElement = row.querySelector('a[href*="screen=info_command"]');
                            if (!attackElement) continue;
                            
                            const sourceElement = row.querySelector('a[href*="screen=info_village"]');
                            const targetElement = row.querySelectorAll('a[href*="screen=info_village"]')[1];
                            const timeElement = row.querySelector('.timer, [data-endtime]');
                            
                            if (sourceElement && targetElement && timeElement) {
                                // Extract village IDs from hrefs
                                const sourceMatch = sourceElement.href.match(/id=(\\d+)/);
                                const targetMatch = targetElement.href.match(/id=(\\d+)/);
                                
                                // Extract arrival time
                                let arrivalTime = null;
                                if (timeElement.dataset.endtime) {
                                    arrivalTime = parseInt(timeElement.dataset.endtime) * 1000;
                                } else {
                                    // Parse timer format like "1:23:45"
                                    const timerText = timeElement.textContent.trim();
                                    const parts = timerText.split(':').map(p => parseInt(p));
                                    if (parts.length >= 3) {
                                        const totalSeconds = parts[0] * 3600 + parts[1] * 60 + parts[2];
                                        arrivalTime = Date.now() + (totalSeconds * 1000);
                                    }
                                }
                                
                                if (sourceMatch && targetMatch && arrivalTime) {
                                    attacks.push({
                                        source_village_id: parseInt(sourceMatch[1]),
                                        target_village_id: parseInt(targetMatch[1]),
                                        arrival_time: arrivalTime,
                                        attack_element: attackElement.href
                                    });
                                }
                            }
                        } catch (e) {
                            console.warn('Error parsing attack row:', e);
                        }
                    }
                    
                    return attacks;
                }
            """)
            
            logger.debug(f"Found {len(attacks_data)} incoming attacks")
            return attacks_data
            
        except Exception as e:
            logger.error(f"Error extracting attacks: {e}")
            return []
            
    async def evaluate_snipe_opportunity(self, attack: Dict[str, Any]):
        """Evaluate if an incoming attack can be sniped"""
        try:
            target_village_id = attack['target_village_id']
            arrival_time = attack['arrival_time']
            
            # Check if this is a new attack or updated timing
            attack_key = f"{attack['source_village_id']}_{target_village_id}_{arrival_time}"
            if attack_key in self.known_targets:
                return  # Already processed this attack
                
            # Calculate when to launch snipe (with timing offset)
            arrival_datetime = datetime.fromtimestamp(arrival_time / 1000, tz=timezone.utc)
            snipe_time = arrival_datetime + timedelta(milliseconds=self.timing_offset_ms)
            
            # Check if we have enough time to prepare (at least 1 minute)
            time_until_snipe = (snipe_time - datetime.now(timezone.utc)).total_seconds()
            if time_until_snipe < 60:
                logger.debug(f"Attack on {target_village_id} too soon to snipe ({time_until_snipe:.1f}s)")
                return
                
            # Find our closest village to the target
            snipe_source = await self.find_best_snipe_source(target_village_id)
            if not snipe_source:
                logger.debug(f"No suitable village found to snipe attack on {target_village_id}")
                return
                
            # Get available units for sniping
            snipe_units = await self.get_snipe_units(snipe_source['village_id'])
            if not snipe_units:
                logger.debug(f"No units available for sniping from village {snipe_source['village_id']}")
                return
                
            # Schedule the snipe attack
            await self.schedule_snipe_attack(
                source_village_id=snipe_source['village_id'],
                target_village_id=target_village_id,
                units=snipe_units,
                execute_at=snipe_time,
                original_attack=attack
            )
            
            # Remember this target
            self.known_targets[attack_key] = {
                'target_village_id': target_village_id,
                'arrival_time': arrival_time,
                'snipe_scheduled': True,
                'snipe_time': snipe_time
            }
            
        except Exception as e:
            logger.error(f"Error evaluating snipe opportunity: {e}", exc_info=True)
            
    async def find_best_snipe_source(self, target_village_id: int) -> Optional[Dict[str, Any]]:
        """Find the best village to launch snipe from"""
        try:
            # This would typically involve:
            # 1. Getting all our villages
            # 2. Calculating distances to target
            # 3. Checking available units
            # 4. Selecting the closest with sufficient units
            
            # For now, return a mock source - this would be implemented based on game data extraction
            # You would extract this from the game's village list
            current_village = await self.get_current_village_id()
            if current_village:
                return {
                    'village_id': current_village,
                    'distance': 10,  # Mock distance
                    'coordinates': '500|500'  # Mock coordinates
                }
                
        except Exception as e:
            logger.error(f"Error finding snipe source: {e}")
            
        return None
        
    async def get_current_village_id(self) -> Optional[int]:
        """Get the current village ID"""
        try:
            village_id = await self.page.evaluate("""
                () => {
                    if (window.game_data && window.game_data.village) {
                        return window.game_data.village.id;
                    }
                    
                    const villageElement = document.querySelector('#village_switch_link');
                    if (villageElement) {
                        const match = villageElement.href.match(/village=(\\d+)/);
                        if (match) return parseInt(match[1]);
                    }
                    
                    return null;
                }
            """)
            
            return village_id
            
        except Exception as e:
            logger.debug(f"Could not get village ID: {e}")
            return None
            
    async def get_snipe_units(self, village_id: int) -> Optional[Dict[str, int]]:
        """Get available units for sniping from a village"""
        try:
            # Navigate to place (command) screen for the village
            await self.navigate_to_url(f"village={village_id}&screen=place")
            await asyncio.sleep(2)
            
            # Extract available units
            units = await self.page.evaluate("""
                () => {
                    const units = {};
                    const unitInputs = document.querySelectorAll('input[name^="units["]');
                    
                    for (const input of unitInputs) {
                        const unitType = input.name.match(/units\\[(\\w+)\\]/);
                        if (unitType) {
                            const maxElement = input.parentElement.querySelector('[data-all-count]');
                            const available = maxElement ? parseInt(maxElement.dataset.allCount) : 0;
                            
                            if (available > 0) {
                                units[unitType[1]] = available;
                            }
                        }
                    }
                    
                    return units;
                }
            """)
            
            # Filter for suitable snipe units (typically light cavalry for speed)
            snipe_units = {}
            
            # Prioritize light cavalry, then heavy cavalry, then other fast units
            unit_priority = ['light', 'heavy', 'spy', 'archer']
            
            for unit_type in unit_priority:
                if unit_type in units and units[unit_type] >= self.min_units_threshold:
                    snipe_units[unit_type] = min(units[unit_type], 500)  # Don't send too many
                    break
                    
            return snipe_units if snipe_units else None
            
        except Exception as e:
            logger.error(f"Error getting snipe units: {e}")
            return None
            
    async def schedule_snipe_attack(
        self,
        source_village_id: int,
        target_village_id: int,
        units: Dict[str, int],
        execute_at: datetime,
        original_attack: Dict[str, Any]
    ):
        """Schedule a snipe attack using the sniper service"""
        try:
            # Get sniper manager from scheduler
            sniper_manager = self.browser_manager.scheduler.sniper_manager
            
            # Schedule the attack with high priority
            attack_id = await sniper_manager.schedule_attack(
                target_village_id=target_village_id,
                source_village_id=source_village_id,
                attack_type="attack",
                units=units,
                execute_at=execute_at,
                priority=200  # High priority for snipes
            )
            
            if attack_id:
                self.scheduled_attacks.append(attack_id)
                logger.info(f"🎯 Scheduled snipe attack {attack_id}: "
                          f"{source_village_id} -> {target_village_id} "
                          f"at {execute_at.strftime('%H:%M:%S.%f')[:-3]} "
                          f"with {units}")
            else:
                logger.error(f"Failed to schedule snipe attack")
                
        except Exception as e:
            logger.error(f"Error scheduling snipe attack: {e}", exc_info=True)
            
    async def monitor_scheduled_attacks(self):
        """Monitor our scheduled attacks and remove completed ones"""
        try:
            if not self.scheduled_attacks:
                return
                
            sniper_manager = self.browser_manager.scheduler.sniper_manager
            
            # Check status of each attack
            completed_attacks = []
            for attack_id in self.scheduled_attacks:
                try:
                    if sniper_manager.client:
                        status = await sniper_manager.client.get_attack_status(attack_id)
                        if status and status.get('status') in ['completed', 'failed']:
                            completed_attacks.append(attack_id)
                            logger.info(f"🏁 Attack {attack_id} {status.get('status')}")
                except Exception as e:
                    logger.debug(f"Error checking attack {attack_id}: {e}")
                    
            # Remove completed attacks from tracking
            for attack_id in completed_attacks:
                self.scheduled_attacks.remove(attack_id)
                
        except Exception as e:
            logger.error(f"Error monitoring attacks: {e}")
            
    async def cancel_all_scheduled_attacks(self):
        """Cancel all our scheduled attacks"""
        if not self.scheduled_attacks:
            return
            
        logger.info(f"Cancelling {len(self.scheduled_attacks)} scheduled snipe attacks")
        
        sniper_manager = self.browser_manager.scheduler.sniper_manager
        
        for attack_id in self.scheduled_attacks.copy():
            try:
                if sniper_manager.client:
                    await sniper_manager.client.cancel_attack(attack_id)
                self.scheduled_attacks.remove(attack_id)
            except Exception as e:
                logger.error(f"Error cancelling attack {attack_id}: {e}")
                
    async def stop(self):
        """Stop the automation and cancel scheduled attacks"""
        await self.cancel_all_scheduled_attacks()
        await super().stop()