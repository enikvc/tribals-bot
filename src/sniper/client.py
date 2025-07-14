"""
Python client for communicating with the Rust sniper service
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import aiohttp
from uuid import UUID

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class SniperClient:
    """Client for communicating with the Rust sniper service"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 9001):
        self.host = host
        self.port = port
        self.base_url = f"http://{host}:{port}"
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        await self.connect()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
        
    async def connect(self):
        """Initialize HTTP session"""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=5)
            self.session = aiohttp.ClientSession(timeout=timeout)
            
    async def disconnect(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()
            
    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to sniper service"""
        if not self.session or self.session.closed:
            await self.connect()
            
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with self.session.request(method, url, **kwargs) as response:
                if response.content_type == 'application/json':
                    return await response.json()
                else:
                    text = await response.text()
                    if response.status >= 400:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status,
                            message=text
                        )
                    return {"response": text}
                    
        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            raise
            
    async def health_check(self) -> bool:
        """Check if sniper service is running"""
        try:
            response = await self._request("GET", "/health")
            return "Sniper Service" in str(response)
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False
            
    async def get_status(self) -> Dict[str, Any]:
        """Get sniper service status"""
        return await self._request("GET", "/status")
        
    async def update_session(self, session_data: Dict[str, Any]) -> bool:
        """Update session data in sniper service"""
        try:
            await self._request("POST", "/session", json=session_data)
            logger.info("📋 Updated sniper service session data")
            return True
        except Exception as e:
            logger.error(f"Failed to update session: {e}")
            return False
            
    async def schedule_attack(
        self,
        target_village_id: int,
        source_village_id: int,
        attack_type: str,
        units: Dict[str, int],
        execute_at: datetime,
        priority: int = 100
    ) -> Optional[str]:
        """
        Schedule an attack
        
        Args:
            target_village_id: Target village ID
            source_village_id: Source village ID  
            attack_type: 'attack', 'support', or 'spy'
            units: Dictionary of unit types and counts
            execute_at: When to execute the attack (UTC)
            priority: Attack priority (0-255, higher = more priority)
            
        Returns:
            Attack ID if successful, None if failed
        """
        # Ensure execute_at is timezone-aware
        if execute_at.tzinfo is None:
            execute_at = execute_at.replace(tzinfo=timezone.utc)
            
        request_data = {
            "target_village_id": target_village_id,
            "source_village_id": source_village_id,
            "attack_type": attack_type.lower(),
            "units": units,
            "execute_at": execute_at.isoformat(),
            "priority": priority
        }
        
        try:
            response = await self._request("POST", "/attack/schedule", json=request_data)
            attack_id = response.get("attack_id")
            
            logger.info(f"🎯 Scheduled {attack_type} attack {attack_id}: {source_village_id} -> {target_village_id} at {execute_at}")
            return attack_id
            
        except Exception as e:
            logger.error(f"Failed to schedule attack: {e}")
            return None
            
    async def get_attack_status(self, attack_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a specific attack"""
        try:
            return await self._request("GET", f"/attack/{attack_id}")
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                return None
            raise
            
    async def cancel_attack(self, attack_id: str) -> bool:
        """Cancel a scheduled attack"""
        try:
            await self._request("DELETE", f"/attack/{attack_id}")
            logger.info(f"❌ Cancelled attack {attack_id}")
            return True
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                logger.warning(f"Attack {attack_id} not found for cancellation")
                return False
            raise
        except Exception as e:
            logger.error(f"Failed to cancel attack {attack_id}: {e}")
            return False
            
    async def list_attacks(self) -> List[Dict[str, Any]]:
        """List all attacks (active and completed)"""
        try:
            logger.info(f"📋 Requesting attacks from {self.base_url}/attacks")
            result = await self._request("GET", "/attacks")
            logger.info(f"📋 Rust service returned {len(result) if isinstance(result, list) else 'non-list'} attacks: {result[:2] if isinstance(result, list) and len(result) > 0 else result}")
            
            # Handle different response formats
            if isinstance(result, dict) and "attacks" in result:
                return result["attacks"]
            elif isinstance(result, list):
                return result
            else:
                logger.warning(f"⚠️ Unexpected response format: {result}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to list attacks: {e}")
            return []
            
    async def wait_for_service(self, timeout: int = 30) -> bool:
        """Wait for sniper service to be ready"""
        for i in range(timeout):
            if await self.health_check():
                logger.info("✅ Sniper service is ready")
                return True
            await asyncio.sleep(1)
            
        logger.error("❌ Sniper service failed to start within timeout")
        return False


class AttackBuilder:
    """Helper class for building attack requests"""
    
    def __init__(self, sniper_client: SniperClient):
        self.client = sniper_client
        self.reset()
        
    def reset(self):
        """Reset builder to default values"""
        self._target_village_id: Optional[int] = None
        self._source_village_id: Optional[int] = None
        self._attack_type: str = "attack"
        self._units: Dict[str, int] = {}
        self._execute_at: Optional[datetime] = None
        self._priority: int = 100
        return self
        
    def target(self, village_id: int):
        """Set target village ID"""
        self._target_village_id = village_id
        return self
        
    def source(self, village_id: int):
        """Set source village ID"""
        self._source_village_id = village_id
        return self
        
    def attack_type(self, attack_type: str):
        """Set attack type: 'attack', 'support', or 'spy'"""
        self._attack_type = attack_type.lower()
        return self
        
    def units(self, **units):
        """Set units to send (e.g., units(spear=100, sword=50))"""
        self._units.update(units)
        return self
        
    def add_units(self, unit_type: str, count: int):
        """Add units of specific type"""
        self._units[unit_type] = self._units.get(unit_type, 0) + count
        return self
        
    def execute_at(self, when: datetime):
        """Set execution time"""
        self._execute_at = when
        return self
        
    def priority(self, priority: int):
        """Set attack priority (0-255)"""
        self._priority = max(0, min(255, priority))
        return self
        
    async def schedule(self) -> Optional[str]:
        """Schedule the attack"""
        if not self._target_village_id or not self._source_village_id:
            raise ValueError("Target and source village IDs are required")
        if not self._execute_at:
            raise ValueError("Execution time is required")
        if not self._units:
            raise ValueError("At least one unit type is required")
            
        return await self.client.schedule_attack(
            target_village_id=self._target_village_id,
            source_village_id=self._source_village_id,
            attack_type=self._attack_type,
            units=self._units,
            execute_at=self._execute_at,
            priority=self._priority
        )