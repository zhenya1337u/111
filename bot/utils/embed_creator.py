#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utility for creating standardized embeds for Discord messages.
"""

import disnake
import datetime

def create_embed(title=None, description=None, color=None, author=None, 
                thumbnail=None, image=None, fields=None, footer=None, 
                timestamp=True, url=None):
    """
    Create a standardized Discord embed.
    
    Args:
        title (str, optional): Title of the embed
        description (str, optional): Description of the embed
        color (disnake.Color, optional): Color of the embed. Default is blue.
        author (dict, optional): Author dict with 'name', 'url', and 'icon_url'
        thumbnail (str, optional): URL of thumbnail image
        image (str, optional): URL of large image
        fields (list, optional): List of field dicts with 'name', 'value', and 'inline'
        footer (dict, optional): Footer dict with 'text' and 'icon_url'
        timestamp (bool, optional): Whether to add current timestamp. Default is True.
        url (str, optional): URL for the title to link to
    
    Returns:
        disnake.Embed: The created embed
    """
    # Set default color if not provided
    if color is None:
        color = disnake.Color.blue()
    
    # Create the embed
    embed = disnake.Embed(
        title=title,
        description=description,
        color=color,
        url=url
    )
    
    # Add author if provided
    if author:
        name = author.get('name', '')
        url = author.get('url', None)
        icon_url = author.get('icon_url', None)
        embed.set_author(name=name, url=url, icon_url=icon_url)
    
    # Add thumbnail if provided
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    
    # Add image if provided
    if image:
        embed.set_image(url=image)
    
    # Add fields if provided
    if fields:
        for field in fields:
            name = field.get('name', '')
            value = field.get('value', '')
            inline = field.get('inline', False)
            embed.add_field(name=name, value=value, inline=inline)
    
    # Add footer if provided
    if footer:
        text = footer.get('text', '')
        icon_url = footer.get('icon_url', None)
        embed.set_footer(text=text, icon_url=icon_url)
    
    # Add timestamp if enabled
    if timestamp:
        embed.timestamp = datetime.datetime.utcnow()
    
    return embed

def create_success_embed(title, description, **kwargs):
    """Create a success embed with green color"""
    return create_embed(
        title=title,
        description=description,
        color=disnake.Color.green(),
        **kwargs
    )

def create_error_embed(title, description, **kwargs):
    """Create an error embed with red color"""
    return create_embed(
        title=title,
        description=description,
        color=disnake.Color.red(),
        **kwargs
    )

def create_warning_embed(title, description, **kwargs):
    """Create a warning embed with yellow/gold color"""
    return create_embed(
        title=title,
        description=description,
        color=disnake.Color.gold(),
        **kwargs
    )

def create_info_embed(title, description, **kwargs):
    """Create an info embed with blue color"""
    return create_embed(
        title=title,
        description=description,
        color=disnake.Color.blue(),
        **kwargs
    )

def create_loading_embed(title, description, **kwargs):
    """Create a loading embed with purple color"""
    return create_embed(
        title=title,
        description=description,
        color=disnake.Color.purple(),
        **kwargs
    )

def create_paginated_embed(title, pages, page_num, color=None, footer=None, timestamp=True):
    """
    Create a paginated embed.
    
    Args:
        title (str): Title of the embed
        pages (list): List of content strings for each page
        page_num (int): Current page number (0-indexed)
        color (disnake.Color, optional): Color of the embed
        footer (dict, optional): Footer dict with 'text' and 'icon_url'
        timestamp (bool, optional): Whether to add current timestamp
    
    Returns:
        disnake.Embed: The paginated embed
    """
    total_pages = len(pages)
    page_num = max(0, min(page_num, total_pages - 1))  # Ensure valid page number
    
    if not footer:
        footer = {'text': f'Page {page_num + 1}/{total_pages}'}
    else:
        footer['text'] = f"{footer['text']} • Page {page_num + 1}/{total_pages}"
    
    return create_embed(
        title=title,
        description=pages[page_num],
        color=color,
        footer=footer,
        timestamp=timestamp
    )
