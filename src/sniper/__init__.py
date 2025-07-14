"""
Tribals Sniper Service Integration

High-performance Rust-based sniper service for microsecond-accurate attack timing.
"""

from .client import SniperClient
from .manager import SniperManager

__all__ = ['SniperClient', 'SniperManager']