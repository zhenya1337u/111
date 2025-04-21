"""
Utility helper functions for the Discord bot.
"""

import re
import random
import string
import disnake
import asyncio
import datetime
from typing import Union, Optional, Dict, List, Any


def create_embed(
    title: str,
    description: str,
    color: int = 0x3498db,
    fields: List[Dict[str, Any]] = None,
    author: Dict[str, Any] = None,
    footer: str = None,
    image_url: str = None,
    thumbnail_url: str = None,
    timestamp: bool = True,
) -> disnake.Embed:
    """
    Create a Discord embed with common properties.
    
    Args:
        title: Embed title.
        description: Embed description.
        color: Embed color (hex value).
        fields: List of field dictionaries, each with "name", "value", and optional "inline" keys.
        author: Dict with "name" and optional "icon_url" and "url" keys.
        footer: Footer text.
        image_url: URL for embed image.
        thumbnail_url: URL for embed thumbnail.
        timestamp: Whether to add the current timestamp.
        
    Returns:
        disnake.Embed: The created embed.
    """
    embed = disnake.Embed(
        title=title,
        description=description,
        color=color
    )
    
    # Add fields if provided
    if fields:
        for field in fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False)
            )
    
    # Add author if provided
    if author:
        embed.set_author(
            name=author["name"],
            icon_url=author.get("icon_url"),
            url=author.get("url")
        )
    
    # Add footer if provided
    if footer:
        embed.set_footer(text=footer)
    
    # Add image if provided
    if image_url:
        embed.set_image(url=image_url)
    
    # Add thumbnail if provided
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    
    # Add timestamp if requested
    if timestamp:
        embed.timestamp = datetime.datetime.utcnow()
    
    return embed


def generate_random_string(length: int = 10) -> str:
    """
    Generate a random string of letters and digits.
    
    Args:
        length: Length of the string.
        
    Returns:
        Random string.
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def format_time_delta(delta_seconds: Union[int, float]) -> str:
    """
    Format a time delta in seconds to a human-readable string.
    
    Args:
        delta_seconds: Time delta in seconds.
        
    Returns:
        Formatted string (e.g., "2 hours, 30 minutes").
    """
    if delta_seconds < 0:
        return "0 seconds"
    
    days, remainder = divmod(int(delta_seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds > 0 and not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    
    return ", ".join(parts) or "0 seconds"


def truncate_text(text: str, max_length: int = 1024, suffix: str = "...") -> str:
    """
    Truncate text to the specified maximum length.
    
    Args:
        text: Text to truncate.
        max_length: Maximum length.
        suffix: Suffix to add when truncating.
        
    Returns:
        Truncated text.
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def parse_time_string(time_string: str) -> Optional[int]:
    """
    Parse a time string (e.g., "1d", "2h", "30m", "15s") to seconds.
    
    Args:
        time_string: Time string to parse.
        
    Returns:
        Time in seconds, or None if invalid format.
    """
    if not time_string:
        return None
    
    # Regular expression to match time format (number + unit)
    match = re.match(r'^(\d+)([dhms])$', time_string.lower())
    if not match:
        return None
    
    value, unit = match.groups()
    value = int(value)
    
    if unit == 'd':
        return value * 86400
    elif unit == 'h':
        return value * 3600
    elif unit == 'm':
        return value * 60
    elif unit == 's':
        return value
    
    return None


def escape_markdown(text: str) -> str:
    """
    Escape markdown formatting characters in text.
    
    Args:
        text: Text to escape.
        
    Returns:
        Escaped text.
    """
    escape_chars = r'\*_~`|>'
    for char in escape_chars:
        text = text.replace(char, f'\\{char}')
    return text


async def wait_for_confirmation(
    bot: disnake.Client,
    message: disnake.Message,
    user_id: int,
    timeout: int = 30
) -> bool:
    """
    Wait for confirmation reaction from a specific user.
    
    Args:
        bot: Discord bot instance.
        message: Message to add reactions to.
        user_id: User ID to wait for reaction from.
        timeout: Timeout in seconds.
        
    Returns:
        True if confirmed, False otherwise.
    """
    await message.add_reaction("✅")
    await message.add_reaction("❌")
    
    def check(reaction, user):
        return (
            user.id == user_id and 
            reaction.message.id == message.id and 
            str(reaction.emoji) in ["✅", "❌"]
        )
    
    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=timeout, check=check)
        return str(reaction.emoji) == "✅"
    except asyncio.TimeoutError:
        return False
