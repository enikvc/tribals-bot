"""
Auto Farmer - Fixed to handle FarmGod popup dialog
"""
import asyncio
import os
from typing import List, Optional

from ..core.base_automation import BaseAutomation
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AutoFarmer(BaseAutomation):
    """Automates farming using farmgod.js"""
    
    @property
    def name(self) -> str:
        return "auto_farmer"
        
    @property
    def url_pattern(self) -> str:
        return "screen=am_farm"
        
    async def run_automation(self):
        """Main automation loop"""
        while self.running and self.is_within_active_hours():
            try:
                # Check if paused
                if hasattr(self, 'paused') and self.paused:
                    logger.debug(f"{self.name} is paused, waiting...")
                    await asyncio.sleep(1)
                    continue
                    
                # Run farming cycle
                success = await self.run_farming_cycle()
                
                if not success:
                    logger.warning("⚠️ Farming cycle failed, waiting 60s before retry")
                    await asyncio.sleep(60)
                    continue
                
                # Wait for next cycle
                interval = self.script_config['interval_seconds']
                logger.info(f"⏳ Waiting {interval}s until next farming cycle")
                await asyncio.sleep(interval)
                
            except Exception as e:
                logger.error(f"❌ Error in farming cycle: {e}", exc_info=True)
                await asyncio.sleep(30)
                
    async def run_farming_cycle(self) -> bool:
        """Execute one farming cycle"""
        logger.info("🌾 Starting farming cycle")
        
        try:
            # Load farmgod.js
            if not await self.load_farmgod_script():
                return False
            
            # Wait longer for script to initialize and UI to appear
            await asyncio.sleep(3)
            
            # The FarmGod UI can appear in different formats
            # Try multiple selectors for different dialog types
            dialog_selectors = [
                '#popup_box_FarmGod',  # Game's popup system
                'div#popup_box_FarmGod',
                '.popup_box#popup_box_FarmGod',
                '#massScavengeSophie',  # Original draggable dialog
                'div#massScavengeSophie',
                '.ui-widget-content#massScavengeSophie'
            ]
            
            farmgod_dialog = None
            for selector in dialog_selectors:
                farmgod_dialog = await self.page.query_selector(selector)
                if farmgod_dialog:
                    logger.info(f"✅ Found FarmGod dialog with selector: {selector}")
                    break
                    
            if not farmgod_dialog:
                # Wait a bit more for popup to appear
                await asyncio.sleep(2)
                # Try again with the most common selector
                farmgod_dialog = await self.page.query_selector('#popup_box_FarmGod')
                
            if not farmgod_dialog:
                logger.warning("⚠️ FarmGod dialog did not appear")
                # Debug: Check what's on the page
                page_info = await self.page.evaluate("""
                    () => {
                        const popup = document.querySelector('#popup_box_FarmGod');
                        const sophie = document.querySelector('#massScavengeSophie');
                        const popups = document.querySelectorAll('.popup_box');
                        return {
                            farmGodPopup: popup ? 'found' : 'not found',
                            sophieDialog: sophie ? 'found' : 'not found',
                            popupCount: popups.length,
                            popupIds: Array.from(popups).map(p => p.id),
                            farmGodExists: typeof window.FarmGod !== 'undefined'
                        };
                    }
                """)
                logger.debug(f"Page debug info: {page_info}")
                return False
                
            logger.info("✅ FarmGod dialog found")
            
            # No need to reposition the popup_box as it's already styled by the game
            # Just ensure it's visible
            await self.page.evaluate("""
                const dialog = document.querySelector('#popup_box_FarmGod');
                if (dialog) {
                    dialog.style.display = 'block';
                    dialog.style.visibility = 'visible';
                    dialog.style.opacity = '1';
                    
                    // Focus on the popup content
                    const content = dialog.querySelector('.popup_box_content');
                    if (content) content.focus();
                }
            """)
            
            # Wait a bit for positioning
            await asyncio.sleep(1)
            
            # Now try to find and click the "Plan farms" button
            # The button should have class="btn optionButton" and value="Plan farms"
            button_clicked = False
            
            # Method 1: Direct JavaScript click on the exact button
            js_click_result = await self.page.evaluate("""
                () => {
                    // Look for button in popup_box_FarmGod
                    const popup = document.querySelector('#popup_box_FarmGod');
                    if (!popup) {
                        // Try massScavengeSophie as fallback
                        const sophie = document.querySelector('#massScavengeSophie');
                        if (!sophie) return { success: false, error: 'No dialog found' };
                    }
                    
                    // Find the exact button: class="btn optionButton" value="Plan farms"
                    const button = document.querySelector('input.btn.optionButton[value="Plan farms"]');
                    if (button) {
                        button.click();
                        return { 
                            success: true, 
                            selector: 'input.btn.optionButton[value="Plan farms"]',
                            value: button.value
                        };
                    }
                    
                    // Try without exact value match (for different languages)
                    const optionButton = document.querySelector('input.btn.optionButton');
                    if (optionButton) {
                        optionButton.click();
                        return { 
                            success: true, 
                            selector: 'input.btn.optionButton',
                            value: optionButton.value
                        };
                    }
                    
                    // Try any button with optionButton class
                    const anyOption = document.querySelector('input.optionButton');
                    if (anyOption) {
                        anyOption.click();
                        return { 
                            success: true, 
                            selector: 'input.optionButton',
                            value: anyOption.value
                        };
                    }
                    
                    // Last resort: find any button in the options div
                    const optionsDiv = document.querySelector('.optionsContent');
                    if (optionsDiv) {
                        const anyButton = optionsDiv.querySelector('input[type="button"]');
                        if (anyButton) {
                            anyButton.click();
                            return { 
                                success: true, 
                                selector: 'last resort button',
                                value: anyButton.value
                            };
                        }
                    }
                    
                    // Debug info
                    const allButtons = document.querySelectorAll('input[type="button"]');
                    return { 
                        success: false, 
                        error: 'No button found',
                        totalButtons: allButtons.length,
                        buttons: Array.from(allButtons).map(b => ({
                            value: b.value,
                            className: b.className,
                            id: b.id
                        }))
                    };
                }
            """)
            
            if js_click_result['success']:
                button_clicked = True
                logger.info(f"✅ Clicked button: {js_click_result['value']} using {js_click_result['selector']}")
            else:
                logger.warning(f"⚠️ JS click failed: {js_click_result}")
                
                # Method 2: Playwright click as fallback
                button_selectors = [
                    'input.btn.optionButton[value="Plan farms"]',
                    '#popup_box_FarmGod input.btn.optionButton',
                    'input.btn.optionButton',
                    'input.optionButton',
                    '.optionsContent input[type="button"]'
                ]
                
                for selector in button_selectors:
                    try:
                        button = await self.page.wait_for_selector(selector, timeout=2000)
                        if button:
                            # Get button info before clicking
                            button_info = await button.evaluate("""
                                (el) => ({ value: el.value, className: el.className })
                            """)
                            
                            await button.click()
                            button_clicked = True
                            logger.info(f"✅ Clicked button via Playwright: {button_info['value']}")
                            break
                    except Exception as e:
                        logger.debug(f"Selector {selector} failed: {e}")
                        continue
                        
            if not button_clicked:
                logger.warning("⚠️ Could not click Plan farms button")
                
                # Final attempt: Take a screenshot and try to find any button
                await self.page.screenshot(path=f"farmgod_dialog_{self.attempts}.png")
                
                # Try one more time with a broader search
                final_attempt = await self.page.evaluate("""
                    () => {
                        // Find ANY button with optionButton class
                        const optionButtons = document.querySelectorAll('input.optionButton');
                        if (optionButtons.length > 0) {
                            // Click the last one (usually the action button)
                            const button = optionButtons[optionButtons.length - 1];
                            button.click();
                            return { 
                                success: true, 
                                value: button.value,
                                index: optionButtons.length - 1
                            };
                        }
                        
                        // Try clicking readyToSend function directly
                        if (typeof readyToSend === 'function') {
                            readyToSend();
                            return { success: true, method: 'direct function call' };
                        }
                        
                        return { success: false };
                    }
                """)
                
                if final_attempt['success']:
                    button_clicked = True
                    logger.info(f"✅ Final attempt succeeded: {final_attempt}")
                else:
                    return False
                
            # Wait for planning to complete
            await asyncio.sleep(5)
            
            # Close the popup dialog if it's still open
            await self.page.evaluate("""
                () => {
                    // Close popup_box_FarmGod
                    const popup = document.querySelector('#popup_box_FarmGod');
                    if (popup) {
                        const closeBtn = popup.querySelector('.popup_box_close');
                        if (closeBtn) {
                            closeBtn.click();
                        } else {
                            popup.remove();
                        }
                    }
                    
                    // Also remove massScavengeSophie if present
                    const sophie = document.querySelector('#massScavengeSophie');
                    if (sophie) sophie.remove();
                }
            """)
            
            # Wait for the results table to appear
            await asyncio.sleep(2)
            
            # Find and click farm icons
            icons = await self.find_farm_icons()
            
            if not icons:
                logger.warning("⚠️ No farm icons found - villages might be empty")
                return True  # Not necessarily a failure
                
            await self.click_farm_icons(icons)
            return True
            
        except Exception as e:
            logger.error(f"❌ Error in farming cycle: {e}", exc_info=True)
            # Take screenshot for debugging
            await self.page.screenshot(path=f"farmgod_error_{self.attempts}.png")
            return False
        
    async def load_farmgod_script(self) -> bool:
        """Load the farmgod.js script with better error handling"""
        script_path = os.path.join('vendor', 'farmgod.js')
        
        if not os.path.exists(script_path):
            logger.error("❌ farmgod.js not found in vendor/")
            return False
            
        try:
            # Try different encodings
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            script_content = None
            
            for encoding in encodings:
                try:
                    with open(script_path, 'r', encoding=encoding) as f:
                        script_content = f.read()
                    logger.debug(f"✅ Loaded farmgod.js with {encoding} encoding")
                    break
                except UnicodeDecodeError:
                    continue
                    
            if not script_content:
                logger.error("❌ Could not read farmgod.js with any encoding")
                return False
            
            # Inject script into page
            await self.page.evaluate(script_content)
            logger.debug("✅ Injected farmgod.js into page")
            
            # Verify script loaded
            script_loaded = await self.page.evaluate("""
                () => typeof window.FarmGod !== 'undefined'
            """)
            
            if not script_loaded:
                logger.error("❌ FarmGod script did not initialize properly")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to load farmgod.js: {e}", exc_info=True)
            return False
        
    async def find_farm_icons(self, max_attempts: int = 10) -> List:
        """Find farm icons with retry and multiple selectors"""
        selectors = [
            'div.farmGodContent a.farmGod_icon',
            'div.farmGodContent a[class*="farm_icon"]',
            '.farmGodContent a.farmGod_icon',
            'a.farmGod_icon[data-origin]',
            'a.farm_icon_a',
            'td a[class*="farm_icon"]'
        ]
        
        for attempt in range(max_attempts):
            for selector in selectors:
                icons = await self.page.query_selector_all(selector)
                
                if icons:
                    logger.info(f"✅ Found {len(icons)} farm icons with selector: {selector}")
                    return icons
                    
            logger.debug(f"Attempt {attempt + 1}/{max_attempts}: No icons yet")
            await asyncio.sleep(0.5)
            
        return []
        
    async def click_farm_icons(self, icons: List):
        """Click farm icons with rate limiting and error handling"""
        max_icons = self.script_config.get('max_icons_per_run', 50)
        icons_to_click = icons[:max_icons]
        
        click_interval = max(self.script_config['icon_click_interval'], 250) / 1000
        
        logger.info(f"🖱️ Clicking {len(icons_to_click)} icons with {click_interval:.2f}s interval")
        
        successful_clicks = 0
        failed_clicks = 0
        
        for i, icon in enumerate(icons_to_click):
            try:
                # Use JavaScript click for reliability
                clicked = await self.page.evaluate("""
                    (element) => {
                        if (element) {
                            element.click();
                            return true;
                        }
                        return false;
                    }
                """, icon)
                
                if clicked:
                    successful_clicks += 1
                    logger.debug(f"✅ Clicked farm icon #{i+1}")
                else:
                    logger.debug(f"⚠️ Icon #{i+1} could not be clicked")
                    failed_clicks += 1
                
                if i < len(icons_to_click) - 1:
                    await asyncio.sleep(click_interval)
                    
            except Exception as e:
                logger.warning(f"⚠️ Failed to click icon #{i+1}: {e}")
                failed_clicks += 1
                
        logger.info(f"✅ Farming cycle complete - {successful_clicks} successful, {failed_clicks} failed")