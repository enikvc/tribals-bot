"""
Logger Configuration
"""
import logging
import coloredlogs
import os
from datetime import datetime
from pathlib import Path


def setup_logger(name: str) -> logging.Logger:
    """Setup a logger with colored output and file logging"""
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Create logger
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.DEBUG)
    
    # Console handler with colors
    console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    coloredlogs.install(
        level='INFO',
        logger=logger,
        fmt=console_format,
        field_styles={
            'asctime': {'color': 'green'},
            'hostname': {'color': 'magenta'},
            'levelname': {'bold': True, 'color': 'blue'},
            'name': {'color': 'cyan'},
            'programname': {'color': 'cyan'}
        }
    )
    
    # File handler
    log_file = log_dir / f"tribals_bot_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_format)
    
    logger.addHandler(file_handler)
    
    return logger


# Emoji log helpers
class EmojiLogger:
    """Logger with emoji prefixes for better readability"""
    
    def __init__(self, logger):
        self.logger = logger
        
    def info(self, emoji: str, message: str):
        self.logger.info(f"{emoji} {message}")
        
    def warning(self, emoji: str, message: str):
        self.logger.warning(f"{emoji} {message}")
        
    def error(self, emoji: str, message: str, exc_info=False):
        self.logger.error(f"{emoji} {message}", exc_info=exc_info)
        
    def debug(self, emoji: str, message: str):
        self.logger.debug(f"{emoji} {message}")