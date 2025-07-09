"""
Auto Scavenger - Fixed to handle massScavenge popup dialog
"""
import asyncio
import random
import os
from typing import Optional

from ..core.base_automation import BaseAutomation
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AutoScavenger(BaseAutomation):
    """Automates scavenging expeditions"""
    
    @property
    def name(self) -> str:
        return "auto_scavenger"
        
    @property
    def url_pattern(self) -> str:
        return "screen=place&mode=scavenge_mass"
        
    async def run_automation(self):
        """Main automation loop"""
        consecutive_failures = 0
        max_consecutive_failures = 3
        
        while self.running and self.is_within_active_hours():
            try:
                # Check if paused
                if hasattr(self, 'paused') and self.paused:
                    logger.debug(f"{self.name} is paused, waiting...")
                    await asyncio.sleep(1)
                    continue
                    
                # Run scavenging cycle
                success = await self.run_scavenge_cycle()
                
                if success:
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_consecutive_failures:
                        logger.error(f"❌ {max_consecutive_failures} consecutive failures, stopping")
                        self.running = False
                        break
                    logger.warning(f"⚠️ Scavenge failed ({consecutive_failures}/{max_consecutive_failures})")
                
                # Calculate next interval with jitter
                base_interval = self.script_config['base_interval_seconds']
                jitter = random.random() * self.script_config['interval_jitter_seconds']
                total_interval = base_interval + jitter
                
                logger.info(f"⏳ Waiting {total_interval:.1f}s until next scavenge")
                await asyncio.sleep(total_interval)
                
            except Exception as e:
                logger.error(f"❌ Error in scavenge cycle: {e}", exc_info=True)
                consecutive_failures += 1
                await asyncio.sleep(30)
                
    async def run_scavenge_cycle(self) -> bool:
        """Execute one scavenging cycle"""
        logger.info("🔍 Starting scavenge cycle")
        
        try:
            # Load massScavenge.js
            if not await self.load_mass_scavenge_script():
                return False
            
            # Wait for script to initialize
            await self.human_delay(2000, 4000)
            
            # Verify script loaded
            script_loaded = await self.page.evaluate("""
                () => typeof readyToSend !== 'undefined' && typeof sendGroup !== 'undefined'
            """)
            
            if not script_loaded:
                logger.error("❌ Mass scavenge script did not load properly")
                return False
            
            # Execute click sequence
            return await self.execute_click_sequence()
            
        except Exception as e:
            logger.error(f"❌ Error in scavenge cycle: {e}", exc_info=True)
            # Take screenshot for debugging
            await self.page.screenshot(path=f"scavenge_error_{self.attempts}.png")
            return False
        
    async def load_mass_scavenge_script(self) -> bool:
        """Load the massScavenge.js script with error handling"""
        script_path = os.path.join('vendor', 'massScavenge.js')
        
        if not os.path.exists(script_path):
            logger.error("❌ massScavenge.js not found in vendor/")
            return False
            
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            script_content = None
            
            for encoding in encodings:
                try:
                    with open(script_path, 'r', encoding=encoding) as f:
                        script_content = f.read()
                    logger.debug(f"✅ Loaded massScavenge.js with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
                    
            if not script_content:
                logger.error("❌ Could not read massScavenge.js with any encoding")
                return False
            
            # Remove javascript: prefix if present
            if script_content.strip().startswith('javascript:'):
                script_content = script_content.strip()[11:]
            
            # Inject script into page
            await self.page.evaluate(script_content)
            logger.debug("✅ Loaded massScavenge.js")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load massScavenge.js: {e}", exc_info=True)
            return False
        
    async def execute_click_sequence(self) -> bool:
        """Execute the scavenging click sequence with better dialog handling"""
        try:
            # Wait for and handle the initial dialog
            scavenge_dialog = await self.page.wait_for_selector('#massScavengeSophie', timeout=5000)
            if not scavenge_dialog:
                logger.error("❌ Mass scavenge dialog did not appear")
                return False
                
            logger.info("✅ Mass scavenge dialog found")
            
            # Make sure dialog is visible and centered
            await self.page.evaluate("""
                const dialog = document.querySelector('#massScavengeSophie');
                if (dialog) {
                    // Ensure it's visible
                    dialog.style.display = 'block';
                    dialog.style.visibility = 'visible';
                    dialog.style.opacity = '1';
                    dialog.style.zIndex = '9999';
                    
                    // Move to center of viewport
                    dialog.style.position = 'fixed';
                    dialog.style.left = '50%';
                    dialog.style.top = '50%';
                    dialog.style.transform = 'translate(-50%, -50%)';
                    
                    // Focus the dialog
                    dialog.focus();
                }
            """)
            
            # First click - readyToSend()
            first_delay = random.randint(
                self.script_config['click_min_delay'],
                self.script_config['click_max_delay']
            )
            
            await asyncio.sleep(first_delay / 1000)
            
            # Click using JavaScript for reliability
            ready_result = await self.page.evaluate("""
                () => {
                    // Try multiple selectors
                    const selectors = [
                        'input.btnSophie[onclick="readyToSend()"]',
                        'input[onclick="readyToSend()"]',
                        '#sendMass',
                        'input[value*="Calcola"]',  // Italian
                        'input[value*="Calculate"]',  // English
                        '#massScavengeSophie input.btnSophie'
                    ];
                    
                    for (const selector of selectors) {
                        const button = document.querySelector(selector);
                        if (button) {
                            button.click();
                            return { success: true, selector: selector };
                        }
                    }
                    
                    // Debug info
                    const buttons = document.querySelectorAll('input[type="button"]');
                    return { 
                        success: false, 
                        error: 'No button found',
                        buttonCount: buttons.length,
                        buttons: Array.from(buttons).slice(0, 5).map(b => ({
                            value: b.value,
                            onclick: b.getAttribute('onclick'),
                            className: b.className
                        }))
                    };
                }
            """)
            
            if not ready_result['success']:
                logger.error(f"❌ readyToSend() button not found: {ready_result}")
                return False
                
            logger.info(f"✅ Clicked readyToSend() with selector: {ready_result['selector']}")
            
            # Wait for calculation to complete and new dialog to appear
            await asyncio.sleep(5)
            
            # Look for the final dialog
            final_dialog = await self.page.query_selector('#massScavengeFinal')
            if not final_dialog:
                logger.warning("⚠️ Final scavenge dialog did not appear")
                
                # Check if there was an error or no troops
                error_msg = await self.page.evaluate("""
                    () => {
                        const errors = document.querySelectorAll('.error, .error_box, .warn');
                        for (const error of errors) {
                            if (error.textContent && error.textContent.trim()) {
                                return error.textContent.trim();
                            }
                        }
                        return null;
                    }
                """)
                
                if error_msg:
                    logger.warning(f"⚠️ Scavenge error: {error_msg}")
                    
                return False
                
            logger.info("✅ Final scavenge dialog appeared")
            
            # Make sure final dialog is visible
            await self.page.evaluate("""
                const dialog = document.querySelector('#massScavengeFinal');
                if (dialog) {
                    dialog.style.display = 'block';
                    dialog.style.visibility = 'visible';
                    dialog.style.opacity = '1';
                    dialog.style.zIndex = '10000';
                    dialog.style.position = 'fixed';
                    dialog.style.left = '50%';
                    dialog.style.top = '50%';
                    dialog.style.transform = 'translate(-50%, -50%)';
                }
            """)
            
            # Second click - sendGroup()
            second_delay = random.randint(300, 1000)
            await asyncio.sleep(second_delay / 1000)
            
            # Click the first send group button
            send_result = await self.page.evaluate("""
                () => {
                    // Try multiple selectors for send button
                    const selectors = [
                        'input[onclick="sendGroup(0,false)"]',
                        'input[onclick^="sendGroup"][onclick*="false"]',
                        '#sendMass',
                        'input.btnSophie[value*="Lanseaza"]',  // Romanian
                        'input.btnSophie[value*="Launch"]',  // English
                        'input.btnSophie[value*="Lancia"]',  // Italian
                        '#massScavengeFinal input[onclick^="sendGroup"]'
                    ];
                    
                    for (const selector of selectors) {
                        const button = document.querySelector(selector);
                        if (button && !button.disabled) {
                            button.click();
                            return { success: true, selector: selector };
                        }
                    }
                    
                    // Debug info
                    const sendButtons = document.querySelectorAll('input[onclick*="sendGroup"]');
                    return { 
                        success: false, 
                        error: 'No send button found',
                        buttonCount: sendButtons.length,
                        buttons: Array.from(sendButtons).map(b => ({
                            value: b.value,
                            onclick: b.getAttribute('onclick'),
                            disabled: b.disabled
                        }))
                    };
                }
            """)
            
            if send_result['success']:
                logger.info(f"✅ Clicked sendGroup() with selector: {send_result['selector']}")
                logger.info(f"✅ Total click time: {first_delay + second_delay}ms")
                logger.info("✅ Scavenge expedition sent")
                
                # Wait for UI update
                await asyncio.sleep(2)
                
                # Check for success message
                success_msg = await self.page.evaluate("""
                    () => {
                        const msg = document.querySelector('.success_msg, .autoHideBox.success');
                        return msg ? msg.textContent : null;
                    }
                """)
                
                if success_msg:
                    logger.info(f"✅ Success confirmed: {success_msg}")
                    
                # Clean up dialogs
                await self.page.evaluate("""
                    () => {
                        const dialogs = ['#massScavengeSophie', '#massScavengeFinal'];
                        dialogs.forEach(selector => {
                            const dialog = document.querySelector(selector);
                            if (dialog) dialog.remove();
                        });
                    }
                """)
                    
                return True
            else:
                logger.error(f"❌ sendGroup() failed: {send_result}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error in click sequence: {e}", exc_info=True)
            return False