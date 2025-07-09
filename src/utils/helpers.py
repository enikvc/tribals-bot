"""
Helper Functions
"""
import re
import random
import asyncio
from typing import Optional, Union, List, Dict, Any
from datetime import datetime, timedelta


def extract_number(text: str, default: int = 0) -> int:
    """Extract first number from text"""
    if not text:
        return default
        
    match = re.search(r'\d+', text)
    if match:
        return int(match.group())
    return default


def extract_ratio(text: str) -> tuple:
    """Extract ratio like '3:1' from text"""
    match = re.search(r'(\d+):(\d+)', text)
    if match:
        return int(match.group(1)), int(match.group(2))
    return 0, 0


def human_delay_ms() -> int:
    """Generate human-like delay in milliseconds"""
    # Base delay 100-300ms with occasional longer delays
    if random.random() < 0.1:  # 10% chance of longer delay
        return random.randint(500, 1500)
    return random.randint(100, 300)


def calculate_next_run_time(base_seconds: int, jitter_seconds: int = 0) -> datetime:
    """Calculate next run time with optional jitter"""
    delay = base_seconds
    if jitter_seconds > 0:
        delay += random.uniform(0, jitter_seconds)
    return datetime.now() + timedelta(seconds=delay)


def format_duration(seconds: int) -> str:
    """Format duration in human-readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes}m {secs}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"


def is_within_time_range(start_hour: int, end_hour: int, current_time: Optional[datetime] = None) -> bool:
    """Check if current time is within specified hour range"""
    if current_time is None:
        current_time = datetime.now()
        
    current_hour = current_time.hour
    
    if start_hour < end_hour:
        # Same day range (e.g., 8 AM to 6 PM)
        return start_hour <= current_hour < end_hour
    else:
        # Crosses midnight (e.g., 8 PM to 3 AM)
        return current_hour >= start_hour or current_hour < end_hour


def time_until_hour(target_hour: int, current_time: Optional[datetime] = None) -> int:
    """Calculate seconds until target hour"""
    if current_time is None:
        current_time = datetime.now()
        
    # Create target time for today
    target = current_time.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    
    # If target has passed today, use tomorrow
    if target <= current_time:
        target += timedelta(days=1)
        
    return int((target - current_time).total_seconds())


def parse_tribals_url(url: str) -> Dict[str, Any]:
    """Parse Tribals URL to extract server, village, screen, etc."""
    result = {
        'server': None,
        'village': None,
        'screen': None,
        'mode': None
    }
    
    # Extract server
    server_match = re.search(r'https://([^.]+)\.tribals\.it', url)
    if server_match:
        result['server'] = server_match.group(1)
        
    # Extract parameters
    param_matches = re.findall(r'(\w+)=([^&]+)', url)
    for key, value in param_matches:
        if key in result:
            result[key] = value
            
    return result


def build_tribals_url(server: str, village: str = '300', screen: str = None, mode: str = None, **kwargs) -> str:
    """Build a Tribals URL with parameters"""
    base = f"https://{server}.tribals.it/game.php"
    params = [f"village={village}"]
    
    if screen:
        params.append(f"screen={screen}")
    if mode:
        params.append(f"mode={mode}")
        
    # Add any additional parameters
    for key, value in kwargs.items():
        params.append(f"{key}={value}")
        
    return f"{base}?{'&'.join(params)}"


class AsyncRetry:
    """Async retry decorator"""
    
    def __init__(self, max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
        self.max_attempts = max_attempts
        self.delay = delay
        self.backoff = backoff
        
    def __call__(self, func):
        async def wrapper(*args, **kwargs):
            last_exception = None
            delay = self.delay
            
            for attempt in range(self.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_attempts - 1:
                        await asyncio.sleep(delay)
                        delay *= self.backoff
                        
            raise last_exception
            
        return wrapper


# Resource type helpers
RESOURCE_TYPES = ['wood', 'stone', 'iron']


def parse_resources(wood: Union[str, int], stone: Union[str, int], iron: Union[str, int]) -> Dict[str, int]:
    """Parse resource values into dictionary"""
    return {
        'wood': int(wood) if isinstance(wood, str) else wood,
        'stone': int(stone) if isinstance(stone, str) else stone,
        'iron': int(iron) if isinstance(iron, str) else iron
    }


def format_resources(resources: Dict[str, int]) -> str:
    """Format resources for display"""
    return f"Wood: {resources['wood']:,} | Stone: {resources['stone']:,} | Iron: {resources['iron']:,}"