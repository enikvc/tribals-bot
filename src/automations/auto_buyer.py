"""
Auto Buyer - FAST VERSION - No human-like delays for maximum speed
"""
import asyncio
import random
from typing import Optional, Dict, List

from ..core.base_automation import BaseAutomation
from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class AutoBuyerFast(BaseAutomation):
    """Automates premium resource purchasing at maximum speed"""
    
    @property
    def name(self) -> str:
        return "auto_buyer"
        
    @property
    def url_pattern(self) -> str:
        return "screen=market&mode=exchange"
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.resources = ['wood', 'stone', 'iron']
        # Disable human behavior for this script
        self.use_human_behavior = False
        
    async def run_automation(self):
        """Main automation loop - FAST MODE"""
        while self.running and self.is_within_active_hours():
            try:
                # Check if paused
                if hasattr(self, 'paused') and self.paused:
                    logger.debug(f"{self.name} is paused, waiting...")
                    await asyncio.sleep(1)
                    continue
                    
                # Check premium points
                pp = await self.get_premium_points()
                if pp < self.script_config['min_pp']:
                    logger.warning(f"⚠️ PP {pp} < {self.script_config['min_pp']}, stopping")
                    break
                    
                # Check and buy resources FAST
                bought_something = await self.check_and_buy_resources_fast()
                
                if bought_something:
                    # Minimal wait after purchase
                    await asyncio.sleep(0.5)  # 500ms fixed delay
                else:
                    # Quick check interval
                    await asyncio.sleep(1)  # 1 second if nothing to buy
                    
            except Exception as e:
                logger.error(f"❌ Error in buy loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Short error recovery
                
    async def get_premium_points(self) -> int:
        """Get current premium points - FAST"""
        return await self.get_number_from_element_fast('#premium_points')
        
    async def get_stock(self, resource: str) -> int:
        """Get stock for a resource - FAST"""
        return await self.get_number_from_element_fast(f'#premium_exchange_stock_{resource}')
        
    async def get_rate(self, resource: str) -> int:
        """Get exchange rate for a resource - FAST"""
        selector = f'#premium_exchange_rate_{resource}'
        text = await self.wait_and_get_text_fast(selector)
        if text:
            import re
            match = re.search(r'(\d+):(\d+)', text)
            if match:
                return int(match.group(1))
        return float('inf')
        
    async def check_and_buy_resources_fast(self) -> bool:
        """Check all resources and buy the best option - FAST"""
        options = []
        
        # Check all resources in parallel for speed
        tasks = []
        for resource in self.resources:
            tasks.append(self.check_resource_fast(resource))
            
        results = await asyncio.gather(*tasks)
        
        for result in results:
            if result:
                options.append(result)
                
        if not options:
            logger.debug("ℹ️ No resources available for purchase")
            return False
            
        # Sort by amount (highest first)
        options.sort(key=lambda x: x['amount'], reverse=True)
        best = options[0]
        
        self.attempts += 1
        logger.info(f"🔄 #{self.attempts} Buying {best['amount']} {best['resource']} @ {best['rate']}")
        
        # Execute purchase FAST
        return await self.execute_purchase_fast(best['resource'], best['amount'])
        
    async def check_resource_fast(self, resource: str) -> Optional[Dict]:
        """Check a single resource - FAST"""
        try:
            stock = await self.get_stock(resource)
            if stock < self.script_config['min_stock']:
                return None
                
            rate = await self.get_rate(resource)
            
            # Calculate amount to buy
            if stock >= rate:
                amount = (stock // rate) * rate
            else:
                amount = stock
                logger.info(f"ℹ️ {resource}: stock<rate, using remainder {amount}")
                
            if amount > 0:
                return {
                    'resource': resource,
                    'amount': amount,
                    'rate': rate
                }
        except:
            return None
            
    async def execute_purchase_fast(self, resource: str, amount: int) -> bool:
        """Execute a purchase - FAST MODE"""
        try:
            # Clear all inputs first
            await self.page.evaluate("""
                document.querySelectorAll('input.premium-exchange-input[data-type="buy"]')
                    .forEach(input => input.value = '');
            """)
            
            # Fill amount directly
            input_selector = f'input.premium-exchange-input[data-resource="{resource}"][data-type="buy"]'
            await self.page.fill(input_selector, str(amount))
            
            # Click calculate button immediately
            await self.page.click('input.btn-premium-exchange-buy')
            
            # Quick wait for dialog
            await asyncio.sleep(0.2)
            
            # Check for warnings
            warning = await self.page.query_selector('#premium_exchange td.warn')
            if warning:
                logger.warning("⚠️ Trade warning detected")
                await self.page.click('.evt-cancel-btn.btn-confirm-no')
                return False
                
            # Get offered amount
            offered_text = await self.wait_and_get_text_fast(
                '#premium_exchange table.vis tr.row_a td:nth-child(2)'
            )
            
            if offered_text:
                import re
                match = re.search(r'(\d+)', offered_text)
                if match:
                    offered = int(match.group(1))
                    
                    if offered >= amount:
                        logger.info(f"✅ Good trade: {offered} offered")
                        await self.page.click('.evt-confirm-btn.btn-confirm-yes')
                        return True
                    else:
                        logger.warning(f"❌ Bad trade: only {offered} offered")
                        await self.page.click('.evt-cancel-btn.btn-confirm-no')
                        
        except Exception as e:
            logger.error(f"❌ Purchase failed: {e}", exc_info=True)
            
        return False
        
    # Override parent methods to remove human delays
    async def human_delay(self, min_ms: int, max_ms: int):
        """No human delay in fast mode"""
        pass
        
    async def click_with_delay(self, selector: str, min_delay: int = 0, max_delay: int = 0) -> bool:
        """Click without delay"""
        try:
            await self.page.click(selector, timeout=5000)
            return True
        except:
            return False
            
    async def wait_and_get_text_fast(self, selector: str, timeout: int = 3000) -> Optional[str]:
        """Get text without reading simulation"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=timeout)
            if element:
                return await element.text_content()
        except:
            pass
        return None
        
    async def get_number_from_element_fast(self, selector: str, default: int = 0) -> int:
        """Extract number fast"""
        text = await self.wait_and_get_text_fast(selector)
        if text:
            import re
            match = re.search(r'\d+', text)
            if match:
                return int(match.group())
        return default
        
    async def simulate_page_scan(self):
        """No page scanning in fast mode"""
        pass
        
    async def perform_random_actions(self):
        """No random actions in fast mode"""
        pass


# If you want to use this instead of the regular AutoBuyer, 
# rename the class to AutoBuyer:
class AutoBuyer(AutoBuyerFast):
    """Alias for the fast version"""
    pass