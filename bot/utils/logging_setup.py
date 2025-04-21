"""
Logging setup module for the Discord bot.
"""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

def setup_logging():
    """
    Set up logging configuration for the Discord bot.
    
    Creates two handlers:
    - Console handler: INFO level, colored output
    - File handler: DEBUG level, rotating files
    """
    # Create logs directory if it doesn't exist
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Configure the discord_bot logger
    logger = logging.getLogger('discord_bot')
    logger.setLevel(logging.DEBUG)
    
    # Configure disnake logger
    disnake_logger = logging.getLogger('disnake')
    disnake_logger.setLevel(logging.WARNING)
    
    # Create formatters
    console_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    file_format = '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    
    console_formatter = logging.Formatter(console_format)
    file_formatter = logging.Formatter(file_format)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Create file handler
    file_handler = RotatingFileHandler(
        logs_dir / "discord_bot.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Create error file handler
    error_file_handler = RotatingFileHandler(
        logs_dir / "discord_bot_error.log",
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    error_file_handler.setLevel(logging.ERROR)
    error_file_handler.setFormatter(file_formatter)
    
    # Add handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_file_handler)
    
    # Prevent log propagation to avoid duplicate logging
    logger.propagate = False
    
    return logger
