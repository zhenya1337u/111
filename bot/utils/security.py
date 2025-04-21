#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Security utilities for the Discord bot
Includes rate limiting, permission checks, and anti-raid protection
"""

import time
import logging
import disnake
from typing import Dict, Any, Tuple, Optional, List, Union
from collections import defaultdict
import asyncio
import re
import hashlib
import os
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from bot.config import load_config

logger = logging.getLogger("bot.security")

# Rate limiting
_rate_limits = {
    "global": defaultdict(list),
    "user": defaultdict(list),
    "guild": defaultdict(list),
    "channel": defaultdict(list)
}

def check_rate_limit(limit_type: str, id: Union[int, str], limit: int, window: int) -> Tuple[bool, float]:
    """
    Check if a rate limit has been exceeded
    
    Args:
        limit_type: Type of rate limit ('global', 'user', 'guild', 'channel')
        id: Identifier for the entity being rate limited
        limit: Maximum number of actions in the time window
        window: Time window in seconds
        
    Returns:
        Tuple of (is_rate_limited, retry_after)
    """
    current_time = time.time()
    rate_limits = _rate_limits.get(limit_type, defaultdict(list))
    
    # Remove timestamps outside the window
    rate_limits[id] = [ts for ts in rate_limits[id] if current_time - ts < window]
    
    # Check if limit is exceeded
    if len(rate_limits[id]) >= limit:
        oldest = rate_limits[id][0]
        retry_after = window - (current_time - oldest)
        return True, retry_after
    
    # Add current timestamp
    rate_limits[id].append(current_time)
    return False, 0.0

def reset_rate_limits(limit_type: Optional[str] = None, id: Optional[Union[int, str]] = None) -> None:
    """
    Reset rate limits
    
    Args:
        limit_type: Type of rate limit to reset (None for all)
        id: Identifier to reset (None for all of the specified type)
    """
    if limit_type is None:
        # Reset all rate limits
        for type_key in _rate_limits:
            _rate_limits[type_key].clear()
    elif id is None:
        # Reset all rate limits of the specified type
        _rate_limits[limit_type].clear()
    else:
        # Reset rate limits for the specified type and ID
        if limit_type in _rate_limits:
            if id in _rate_limits[limit_type]:
                del _rate_limits[limit_type][id]

def check_command_rate_limit(interaction: disnake.ApplicationCommandInteraction) -> Tuple[bool, float, str]:
    """
    Check rate limits for a command interaction
    
    Args:
        interaction: Discord interaction
        
    Returns:
        Tuple of (is_rate_limited, retry_after, limit_type)
    """
    config = load_config()
    rate_limits = config.get("rate_limits", {})
    
    # Check global rate limit
    global_limit = rate_limits.get("global", 5)
    global_window = rate_limits.get("cooldown", 3)
    is_limited, retry_after = check_rate_limit("global", "global", global_limit, global_window)
    if is_limited:
        return True, retry_after, "global"
    
    # Check user rate limit
    user_limit = rate_limits.get("user", 2)
    user_window = rate_limits.get("cooldown", 3)
    is_limited, retry_after = check_rate_limit("user", interaction.author.id, user_limit, user_window)
    if is_limited:
        return True, retry_after, "user"
    
    # Check channel rate limit if in a guild
    if interaction.guild:
        channel_limit = rate_limits.get("channel", 3)
        channel_window = rate_limits.get("cooldown", 3)
        is_limited, retry_after = check_rate_limit("channel", interaction.channel.id, channel_limit, channel_window)
        if is_limited:
            return True, retry_after, "channel"
    
    return False, 0.0, ""

def has_required_permissions(member: disnake.Member, **perms) -> bool:
    """
    Check if a member has the required permissions
    
    Args:
        member: Discord member to check
        **perms: Permission keyword arguments
        
    Returns:
        True if member has all the required permissions, False otherwise
    """
    # Check if member is the guild owner
    if member.guild.owner_id == member.id:
        return True
    
    # Check permissions
    missing_perms = []
    for perm, value in perms.items():
        if not getattr(member.guild_permissions, perm) and value:
            missing_perms.append(perm)
    
    return len(missing_perms) == 0

def is_admin(member: disnake.Member) -> bool:
    """
    Check if a member is an admin
    
    Args:
        member: Discord member to check
        
    Returns:
        True if member is an admin, False otherwise
    """
    return has_required_permissions(member, administrator=True)

def is_moderator(member: disnake.Member) -> bool:
    """
    Check if a member is a moderator
    
    Args:
        member: Discord member to check
        
    Returns:
        True if member is a moderator, False otherwise
    """
    mod_perms = {
        "kick_members": True,
        "ban_members": True,
        "manage_messages": True,
        "mute_members": True
    }
    
    return has_required_permissions(member, **mod_perms)

def is_bot_owner(user_id: int) -> bool:
    """
    Check if a user is the bot owner
    
    Args:
        user_id: Discord user ID to check
        
    Returns:
        True if user is the bot owner, False otherwise
    """
    config = load_config()
    owner_ids = config.get("owner_ids", [])
    
    return user_id in owner_ids

def get_encryption_key(password: Optional[str] = None) -> bytes:
    """
    Generate an encryption key from a password or environment variable
    
    Args:
        password: Password to derive key from (None to use environment)
        
    Returns:
        Encryption key as bytes
    """
    # Use provided password or get from environment
    if password is None:
        password = os.getenv("BOT_ENCRYPTION_KEY", "default_secret_key")
    
    # Convert password to bytes
    password_bytes = password.encode('utf-8')
    
    # Generate a salt or use a stored one
    salt = os.getenv("BOT_ENCRYPTION_SALT", "").encode('utf-8')
    if not salt:
        salt = os.urandom(16)
        # In a real application, this salt should be stored securely
    
    # Use PBKDF2 to derive a key
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    return key

def encrypt_text(text: str, password: Optional[str] = None) -> str:
    """
    Encrypt text using Fernet symmetric encryption
    
    Args:
        text: Text to encrypt
        password: Password to derive key from (None to use environment)
        
    Returns:
        Encrypted text as base64 string
    """
    key = get_encryption_key(password)
    f = Fernet(key)
    encrypted = f.encrypt(text.encode('utf-8'))
    return encrypted.decode('utf-8')

def decrypt_text(encrypted_text: str, password: Optional[str] = None) -> str:
    """
    Decrypt text using Fernet symmetric encryption
    
    Args:
        encrypted_text: Encrypted text as base64 string
        password: Password to derive key from (None to use environment)
        
    Returns:
        Decrypted text
    """
    key = get_encryption_key(password)
    f = Fernet(key)
    decrypted = f.decrypt(encrypted_text.encode('utf-8'))
    return decrypted.decode('utf-8')

def check_caps(text: str, threshold: float = 0.7) -> bool:
    """
    Check if text has too many capital letters
    
    Args:
        text: Text to check
        threshold: Threshold for ratio of capital letters (0.0 to 1.0)
        
    Returns:
        True if text has too many capital letters, False otherwise
    """
    if not text or len(text) < 5:
        return False
    
    # Count uppercase letters
    uppercase_count = sum(1 for char in text if char.isupper())
    
    # Calculate ratio of uppercase to total
    uppercase_ratio = uppercase_count / len(text)
    
    return uppercase_ratio > threshold

def check_mention_spam(text: str, threshold: int = 5) -> bool:
    """
    Check if text has too many mentions
    
    Args:
        text: Text to check
        threshold: Maximum number of mentions allowed
        
    Returns:
        True if text has too many mentions, False otherwise
    """
    # Count mentions (user, role, and everyone/here)
    mention_count = len(re.findall(r'<@!?&?\d+>', text))
    mention_count += text.count('@everyone')
    mention_count += text.count('@here')
    
    return mention_count > threshold

def check_invite_links(text: str) -> bool:
    """
    Check if text contains Discord invite links
    
    Args:
        text: Text to check
        
    Returns:
        True if text contains invite links, False otherwise
    """
    invite_pattern = r'(discord\.gg|discordapp\.com\/invite|discord\.com\/invite)\/[a-zA-Z0-9]+'
    return bool(re.search(invite_pattern, text))

def generate_captcha() -> Tuple[str, str]:
    """
    Generate a simple text-based CAPTCHA
    
    Returns:
        Tuple of (challenge, answer)
    """
    # Simple math problem
    a = asyncio.get_event_loop().time() % 10 + 1
    b = asyncio.get_event_loop().time() % 10 + 1
    operation = ['addition', 'subtraction', 'multiplication'][int(asyncio.get_event_loop().time() % 3)]
    
    if operation == 'addition':
        challenge = f"What is {int(a)} + {int(b)}?"
        answer = str(int(a + b))
    elif operation == 'subtraction':
        if a < b:
            a, b = b, a  # Make sure result is positive
        challenge = f"What is {int(a)} - {int(b)}?"
        answer = str(int(a - b))
    else:  # multiplication
        challenge = f"What is {int(a)} × {int(b)}?"
        answer = str(int(a * b))
    
    return challenge, answer
