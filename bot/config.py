#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Configuration loader and manager for the Discord bot.
"""

import os
import yaml
import logging

def load_config(config_path=None):
    """
    Load configuration from YAML file or environment variables
    
    Args:
        config_path (str, optional): Path to config file. Defaults to '../config.yaml'.
    
    Returns:
        dict: Configuration dictionary
    """
    logger = logging.getLogger('bot')
    
    if config_path is None:
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
    
    # Default configuration
    default_config = {
        "discord": {
            "token": os.environ.get("DISCORD_TOKEN", ""),
            "prefix": "!",
            "owners": [],
            "status_text": "/help | {guild_count} servers",
            "embed_color": 0x3498db,
        },
        "database": {
            "host": os.environ.get("PGHOST", "localhost"),
            "port": os.environ.get("PGPORT", 5432),
            "user": os.environ.get("PGUSER", "postgres"),
            "password": os.environ.get("PGPASSWORD", ""),
            "database": os.environ.get("PGDATABASE", "discord_bot"),
            "url": os.environ.get("DATABASE_URL", "")
        },
        "web": {
            "host": "0.0.0.0",
            "port": 5000,
            "secret_key": os.environ.get("WEB_SECRET_KEY", ""),
            "debug": False
        },
        "modules": {
            "moderation": True,
            "utility": True,
            "entertainment": True,
            "music": True,
            "ai": True,
            "verification": True,
            "statistics": True
        },
        "api_keys": {
            "openweathermap": os.environ.get("OPENWEATHERMAP_API_KEY", ""),
            "youtube": os.environ.get("YOUTUBE_API_KEY", ""),
            "reddit": os.environ.get("REDDIT_API_KEY", ""),
            "grok": os.environ.get("GROK_API_KEY", "")
        },
        "localization": {
            "default": "en",
            "available": ["en", "ru", "de"]
        },
        "security": {
            "rate_limit": {
                "enabled": True,
                "commands_per_minute": 10
            },
            "anti_raid": {
                "enabled": True,
                "joins_per_minute": 10,
                "action": "temporary_lockdown"  # temporary_lockdown, notify_mods, kick_new_accounts
            },
            "caps_filter": {
                "enabled": True,
                "threshold": 0.7  # Percentage of uppercase characters to trigger
            },
            "verification": {
                "enabled": True,
                "captcha_type": "image",  # image, text, reaction
                "timeout": 300  # Seconds to complete verification
            }
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "bot.log",
            "discord_channel": 0  # Channel ID for logging, 0 to disable
        }
    }
    
    # Load configuration from file
    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as file:
                file_config = yaml.safe_load(file)
                
                # Recursively update default config with file config
                def update_dict(d, u):
                    for k, v in u.items():
                        if isinstance(v, dict) and k in d:
                            d[k] = update_dict(d.get(k, {}), v)
                        else:
                            d[k] = v
                    return d
                
                config = update_dict(default_config, file_config)
                logger.info(f"Loaded configuration from {config_path}")
        else:
            logger.warning(f"Config file {config_path} not found. Using default configuration.")
            config = default_config
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        config = default_config
    
    # Validate critical configuration
    if not config['discord']['token'] and 'DISCORD_TOKEN' not in os.environ:
        logger.warning("Discord token not found in config or environment variables")
    
    return config

def save_config(config, config_path=None):
    """
    Save configuration to YAML file
    
    Args:
        config (dict): Configuration dictionary
        config_path (str, optional): Path to config file. Defaults to '../config.yaml'.
    
    Returns:
        bool: Success status
    """
    logger = logging.getLogger('bot')
    
    if config_path is None:
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'config.yaml'))
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        # Don't save sensitive information to file
        safe_config = config.copy()
        if 'discord' in safe_config and 'token' in safe_config['discord']:
            safe_config['discord']['token'] = ''
        if 'database' in safe_config:
            if 'password' in safe_config['database']:
                safe_config['database']['password'] = ''
            if 'url' in safe_config['database']:
                safe_config['database']['url'] = ''
        if 'web' in safe_config and 'secret_key' in safe_config['web']:
            safe_config['web']['secret_key'] = ''
        
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(safe_config, file, default_flow_style=False, allow_unicode=True, sort_keys=False)
        
        logger.info(f"Saved configuration to {config_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        return False

def get_guild_config(bot, guild_id):
    """
    Get configuration for a specific guild
    
    Args:
        bot: Bot instance
        guild_id (int): Guild ID
    
    Returns:
        dict: Guild configuration
    """
    # This would typically retrieve from database, but for now we'll return a default
    return {
        "prefix": bot.config.get("discord", {}).get("prefix", "!"),
        "modules": bot.config.get("modules", {}),
        "language": bot.config.get("localization", {}).get("default", "en"),
        "log_channel": None,
        "mod_roles": [],
        "welcome_channel": None,
        "welcome_message": "Welcome to the server, {user}!",
        "auto_roles": [],
        "mute_role": None
    }

def update_guild_config(bot, guild_id, key, value):
    """
    Update configuration for a specific guild
    
    Args:
        bot: Bot instance
        guild_id (int): Guild ID
        key (str): Configuration key
        value: Configuration value
    
    Returns:
        bool: Success status
    """
    # This would typically update the database
    return True
