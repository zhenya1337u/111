#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Rate limiting utilities for the Discord bot.
Provides mechanism to rate limit commands and other operations.
"""

import time
import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger('bot.rate_limiter')

class RateLimiter:
    """Rate limiter for commands and other operations"""
    
    def __init__(self):
        """Initialize the rate limiter"""
        # Dict to store rate limit data, structure:
        # {
        #   'user_id': {
        #       'command_name': (last_used_time, use_count)
        #   }
        # }
        self.rate_limits = defaultdict(lambda: defaultdict(lambda: (0, 0)))
        self.global_rate_limits = defaultdict(lambda: (0, 0))
        self.guild_rate_limits = defaultdict(lambda: defaultdict(lambda: (0, 0)))
        
        # Cleanup task
        self.cleanup_task = None
    
    def start_cleanup_task(self, bot):
        """
        Start the cleanup task to remove expired rate limits.
        
        Args:
            bot: Discord bot instance
        """
        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(300)  # Run every 5 minutes
                    self._cleanup()
                except Exception as e:
                    logger.error(f"Error in rate limit cleanup task: {e}")
        
        self.cleanup_task = bot.loop.create_task(cleanup_loop())
    
    def _cleanup(self):
        """Remove expired rate limits (older than 1 hour)"""
        current_time = time.time()
        expired_time = current_time - 3600  # 1 hour ago
        
        # Clean user rate limits
        for user_id in list(self.rate_limits.keys()):
            for command in list(self.rate_limits[user_id].keys()):
                last_used, _ = self.rate_limits[user_id][command]
                if last_used < expired_time:
                    del self.rate_limits[user_id][command]
            
            # Remove user if they have no commands left
            if not self.rate_limits[user_id]:
                del self.rate_limits[user_id]
        
        # Clean global rate limits
        for command in list(self.global_rate_limits.keys()):
            last_used, _ = self.global_rate_limits[command]
            if last_used < expired_time:
                del self.global_rate_limits[command]
        
        # Clean guild rate limits
        for guild_id in list(self.guild_rate_limits.keys()):
            for command in list(self.guild_rate_limits[guild_id].keys()):
                last_used, _ = self.guild_rate_limits[guild_id][command]
                if last_used < expired_time:
                    del self.guild_rate_limits[guild_id][command]
            
            # Remove guild if they have no commands left
            if not self.guild_rate_limits[guild_id]:
                del self.guild_rate_limits[guild_id]
    
    def is_rate_limited(self, user_id, command_name, limit, per_seconds):
        """
        Check if a user is rate limited for a command.
        
        Args:
            user_id (int): User ID
            command_name (str): Command name
            limit (int): Maximum number of uses
            per_seconds (int): Time period in seconds
        
        Returns:
            tuple: (is_limited, wait_time, current_uses)
            - is_limited: Whether the user is rate limited
            - wait_time: Seconds to wait before command can be used again
            - current_uses: Number of times the command has been used in the period
        """
        current_time = time.time()
        last_used, use_count = self.rate_limits[user_id][command_name]
        
        # Reset count if we're in a new period
        if current_time - last_used > per_seconds:
            self.rate_limits[user_id][command_name] = (current_time, 1)
            return False, 0, 1
        
        # Check if over limit
        if use_count >= limit:
            wait_time = per_seconds - (current_time - last_used)
            return True, max(0, wait_time), use_count
        
        # Increment count
        self.rate_limits[user_id][command_name] = (last_used, use_count + 1)
        return False, 0, use_count + 1
    
    def is_global_rate_limited(self, command_name, limit, per_seconds):
        """
        Check if a command is globally rate limited.
        
        Args:
            command_name (str): Command name
            limit (int): Maximum number of uses
            per_seconds (int): Time period in seconds
        
        Returns:
            tuple: (is_limited, wait_time, current_uses)
        """
        current_time = time.time()
        last_used, use_count = self.global_rate_limits[command_name]
        
        # Reset count if we're in a new period
        if current_time - last_used > per_seconds:
            self.global_rate_limits[command_name] = (current_time, 1)
            return False, 0, 1
        
        # Check if over limit
        if use_count >= limit:
            wait_time = per_seconds - (current_time - last_used)
            return True, max(0, wait_time), use_count
        
        # Increment count
        self.global_rate_limits[command_name] = (last_used, use_count + 1)
        return False, 0, use_count + 1
    
    def is_guild_rate_limited(self, guild_id, command_name, limit, per_seconds):
        """
        Check if a command is rate limited in a guild.
        
        Args:
            guild_id (int): Guild ID
            command_name (str): Command name
            limit (int): Maximum number of uses
            per_seconds (int): Time period in seconds
        
        Returns:
            tuple: (is_limited, wait_time, current_uses)
        """
        current_time = time.time()
        last_used, use_count = self.guild_rate_limits[guild_id][command_name]
        
        # Reset count if we're in a new period
        if current_time - last_used > per_seconds:
            self.guild_rate_limits[guild_id][command_name] = (current_time, 1)
            return False, 0, 1
        
        # Check if over limit
        if use_count >= limit:
            wait_time = per_seconds - (current_time - last_used)
            return True, max(0, wait_time), use_count
        
        # Increment count
        self.guild_rate_limits[guild_id][command_name] = (last_used, use_count + 1)
        return False, 0, use_count + 1
    
    def add_guild_join(self, guild_id):
        """
        Record a guild join event for anti-raid detection.
        
        Args:
            guild_id (int): Guild ID
        
        Returns:
            int: Number of joins in the last minute
        """
        current_time = time.time()
        command_name = "_guild_join"  # Special command name for guild joins
        last_used, use_count = self.guild_rate_limits[guild_id][command_name]
        
        # Reset count if we're in a new period (1 minute)
        if current_time - last_used > 60:
            self.guild_rate_limits[guild_id][command_name] = (current_time, 1)
            return 1
        
        # Increment count
        new_count = use_count + 1
        self.guild_rate_limits[guild_id][command_name] = (last_used, new_count)
        return new_count
    
    def reset_rate_limit(self, user_id, command_name=None):
        """
        Reset rate limit for a user.
        
        Args:
            user_id (int): User ID
            command_name (str, optional): Command name. If None, reset all commands.
        """
        if command_name:
            if user_id in self.rate_limits and command_name in self.rate_limits[user_id]:
                del self.rate_limits[user_id][command_name]
        else:
            if user_id in self.rate_limits:
                del self.rate_limits[user_id]
    
    def reset_global_rate_limit(self, command_name=None):
        """
        Reset global rate limit.
        
        Args:
            command_name (str, optional): Command name. If None, reset all commands.
        """
        if command_name:
            if command_name in self.global_rate_limits:
                del self.global_rate_limits[command_name]
        else:
            self.global_rate_limits.clear()
    
    def reset_guild_rate_limit(self, guild_id, command_name=None):
        """
        Reset guild rate limit.
        
        Args:
            guild_id (int): Guild ID
            command_name (str, optional): Command name. If None, reset all commands.
        """
        if command_name:
            if guild_id in self.guild_rate_limits and command_name in self.guild_rate_limits[guild_id]:
                del self.guild_rate_limits[guild_id][command_name]
        else:
            if guild_id in self.guild_rate_limits:
                del self.guild_rate_limits[guild_id]

# Create a singleton instance
limiter = RateLimiter()

def get_rate_limiter():
    """Get the singleton rate limiter instance"""
    return limiter
