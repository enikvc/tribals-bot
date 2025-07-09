"""
Configuration Manager
"""
import os
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

from ..utils.logger import setup_logger

logger = setup_logger(__name__)


class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = Path(config_path)
        self.config = {}
        
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        self.load_config()
        
    def load_config(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            logger.error(f"Configuration file not found: {self.config_path}")
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
                
            # Override with environment variables
            self._apply_env_overrides()
            
            logger.info("✅ Configuration loaded successfully")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}", exc_info=True)
            raise
            
    def _apply_env_overrides(self):
        """Apply environment variable overrides"""
        # Discord webhook
        discord_webhook = os.getenv('DISCORD_WEBHOOK')
        if discord_webhook:
            self.config['discord_webhook'] = discord_webhook
            
        # Server
        server = os.getenv('TRIBALS_SERVER')
        if server:
            self.config['server']['base_url'] = f"https://{server}.tribals.it"
            
    def save_config(self):
        """Save configuration back to file"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, sort_keys=False)
                
            logger.info("✅ Configuration saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}", exc_info=True)
            raise
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
                
        return value
        
    def set(self, key: str, value: Any):
        """Set configuration value by key (supports dot notation)"""
        keys = key.split('.')
        config = self.config
        
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
            
        config[keys[-1]] = value
        
    def update_script_config(self, script_name: str, updates: Dict[str, Any]):
        """Update script-specific configuration"""
        if 'scripts' not in self.config:
            self.config['scripts'] = {}
            
        if script_name not in self.config['scripts']:
            self.config['scripts'][script_name] = {}
            
        self.config['scripts'][script_name].update(updates)
        self.save_config()