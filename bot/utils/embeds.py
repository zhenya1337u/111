#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utility functions for creating Discord embeds with consistent styling and localization
"""

import disnake
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from bot.config import load_config
from bot.utils.localization import get_text

def create_embed(
    title: str,
    description: str = "",
    color: Optional[Union[int, disnake.Color]] = None,
    fields: Optional[List[Dict[str, str]]] = None,
    footer: bool = True,
    footer_text: Optional[str] = None,
    footer_icon: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    image_url: Optional[str] = None,
    author_name: Optional[str] = None,
    author_icon: Optional[str] = None,
    author_url: Optional[str] = None,
    timestamp: bool = True,
    url: Optional[str] = None
) -> disnake.Embed:
    """
    Create a consistent Discord embed with configurable options
    
    Args:
        title: Embed title
        description: Embed description
        color: Embed color (overrides default from config)
        fields: List of dicts with 'name', 'value', 'inline' keys
        footer: Whether to add footer
        footer_text: Custom footer text (overrides default)
        footer_icon: Custom footer icon URL (overrides default)
        thumbnail_url: URL for thumbnail image
        image_url: URL for main image
        author_name: Name for author field
        author_icon: URL for author icon
        author_url: URL for author name link
        timestamp: Whether to add timestamp
        url: URL for the title
        
    Returns:
        Discord Embed object
    """
    config = load_config()
    embed_config = config.get("embed", {})
    
    # Set color from config if not provided
    if color is None:
        color = embed_config.get("color", 0x3498db)
    
    # Create the embed
    embed = disnake.Embed(
        title=title,
        description=description,
        color=color,
        url=url
    )
    
    # Add fields if provided
    if fields:
        for field in fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", False)
            )
    
    # Add footer
    if footer:
        embed_footer_text = footer_text or embed_config.get("footer_text", "Multipurpose Discord Bot")
        embed_footer_icon = footer_icon or embed_config.get("footer_icon", "")
        
        if embed_footer_icon:
            embed.set_footer(text=embed_footer_text, icon_url=embed_footer_icon)
        else:
            embed.set_footer(text=embed_footer_text)
    
    # Add thumbnail
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    elif embed_config.get("thumbnail"):
        embed.set_thumbnail(url=embed_config.get("thumbnail"))
    
    # Add image
    if image_url:
        embed.set_image(url=image_url)
    
    # Add author
    if author_name:
        embed.set_author(
            name=author_name,
            url=author_url,
            icon_url=author_icon
        )
    
    # Add timestamp
    if timestamp:
        embed.timestamp = datetime.utcnow()
    
    return embed

def error_embed(
    title: str,
    description: str,
    locale: str = "en"
) -> disnake.Embed:
    """
    Create an error embed with red color
    
    Args:
        title: Error title
        description: Error description
        locale: Locale for translation
        
    Returns:
        Discord Embed object
    """
    # Translate title and description if keys are provided
    title = get_text(title, locale) if title.startswith("error.") else title
    description = get_text(description, locale) if description.startswith("error.") else description
    
    return create_embed(
        title=title,
        description=description,
        color=0xe74c3c  # Red color
    )

def success_embed(
    title: str,
    description: str,
    locale: str = "en"
) -> disnake.Embed:
    """
    Create a success embed with green color
    
    Args:
        title: Success title
        description: Success description
        locale: Locale for translation
        
    Returns:
        Discord Embed object
    """
    # Translate title and description if keys are provided
    title = get_text(title, locale) if title.startswith("success.") else title
    description = get_text(description, locale) if description.startswith("success.") else description
    
    return create_embed(
        title=title,
        description=description,
        color=0x2ecc71  # Green color
    )

def info_embed(
    title: str,
    description: str,
    locale: str = "en"
) -> disnake.Embed:
    """
    Create an info embed with blue color
    
    Args:
        title: Info title
        description: Info description
        locale: Locale for translation
        
    Returns:
        Discord Embed object
    """
    # Translate title and description if keys are provided
    title = get_text(title, locale) if title.startswith("info.") else title
    description = get_text(description, locale) if description.startswith("info.") else description
    
    return create_embed(
        title=title,
        description=description,
        color=0x3498db  # Blue color
    )

def warning_embed(
    title: str,
    description: str,
    locale: str = "en"
) -> disnake.Embed:
    """
    Create a warning embed with yellow color
    
    Args:
        title: Warning title
        description: Warning description
        locale: Locale for translation
        
    Returns:
        Discord Embed object
    """
    # Translate title and description if keys are provided
    title = get_text(title, locale) if title.startswith("warning.") else title
    description = get_text(description, locale) if description.startswith("warning.") else description
    
    return create_embed(
        title=title,
        description=description,
        color=0xf39c12  # Yellow color
    )

def create_localized_embed(
    title_key: str,
    description_key: str,
    locale: str,
    **kwargs
) -> disnake.Embed:
    """
    Create an embed with localized title and description
    
    Args:
        title_key: Localization key for title
        description_key: Localization key for description
        locale: Locale code (e.g., 'en', 'ru', 'de')
        **kwargs: Additional arguments for create_embed
        
    Returns:
        Discord Embed object with localized content
    """
    title = get_text(title_key, locale)
    description = get_text(description_key, locale)
    
    # Handle fields localization if provided
    fields = kwargs.pop("fields", None)
    if fields:
        localized_fields = []
        for field in fields:
            name_key = field.get("name_key")
            value_key = field.get("value_key")
            
            localized_field = {
                "name": get_text(name_key, locale) if name_key else field.get("name", ""),
                "value": get_text(value_key, locale) if value_key else field.get("value", ""),
                "inline": field.get("inline", False)
            }
            localized_fields.append(localized_field)
        
        kwargs["fields"] = localized_fields
    
    return create_embed(title=title, description=description, **kwargs)

def paginate_embeds(
    items: List[Any],
    title: str,
    description: str,
    items_per_page: int = 10,
    color: Optional[Union[int, disnake.Color]] = None,
    formatter=lambda item: str(item),
    locale: str = "en"
) -> List[disnake.Embed]:
    """
    Create a list of embeds for pagination
    
    Args:
        items: List of items to paginate
        title: Base title for embeds
        description: Base description for embeds
        items_per_page: Number of items per page
        color: Embed color
        formatter: Function to format each item
        locale: Locale for translation
        
    Returns:
        List of Discord Embed objects
    """
    # Translate title and description if keys are provided
    title = get_text(title, locale) if title.startswith("title.") else title
    description = get_text(description, locale) if description.startswith("desc.") else description
    
    # Calculate number of pages
    pages = []
    page_count = (len(items) + items_per_page - 1) // items_per_page
    
    for page in range(page_count):
        # Get items for this page
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(items))
        page_items = items[start_idx:end_idx]
        
        # Format items
        formatted_items = "\n".join([formatter(item) for item in page_items])
        
        # Create embed
        page_embed = create_embed(
            title=f"{title} - {get_text('common.page', locale)} {page+1}/{page_count}",
            description=f"{description}\n\n{formatted_items}",
            color=color
        )
        
        # Add page number in footer
        footer_text = page_embed.footer.text
        page_embed.set_footer(
            text=f"{footer_text} • {get_text('common.page', locale)} {page+1}/{page_count}",
            icon_url=page_embed.footer.icon_url
        )
        
        pages.append(page_embed)
    
    # If no items, create a single page with a message
    if not pages:
        empty_embed = create_embed(
            title=title,
            description=f"{description}\n\n{get_text('common.no_items', locale)}",
            color=color
        )
        pages.append(empty_embed)
    
    return pages
