#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Database manager for the Discord bot.
Handles database connections, sessions, and operations.
"""

import os
import logging
import asyncio
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

from bot.models import Base, Guild, Member, ModRole, AutoRole

# Set up logging
logger = logging.getLogger('bot.db_manager')

# Database engine and session factory
engine = None
AsyncSessionFactory = None

async def init_db():
    """
    Initialize the database connection and create tables if they don't exist.
    
    Returns:
        bool: True if successful, False otherwise
    """
    global engine, AsyncSessionFactory
    
    try:
        # Get database URL from environment or config
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            # Construct from individual parameters
            db_host = os.environ.get('PGHOST', 'localhost')
            db_port = os.environ.get('PGPORT', '5432')
            db_name = os.environ.get('PGDATABASE', 'discord_bot')
            db_user = os.environ.get('PGUSER', 'postgres')
            db_pass = os.environ.get('PGPASSWORD', '')
            
            database_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        
        # If URL doesn't start with postgresql+asyncpg://, convert it
        if not database_url.startswith('postgresql+asyncpg://'):
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql+asyncpg://', 1)
            elif database_url.startswith('postgresql://'):
                database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        
        # Create engine and session factory
        engine = create_async_engine(
            database_url,
            pool_pre_ping=True,
            pool_recycle=300,  # Recycle connections after 5 minutes
            echo=False  # Set to True for debugging
        )
        
        AsyncSessionFactory = sessionmaker(
            engine,
            expire_on_commit=False,
            class_=AsyncSession
        )
        
        # Create tables (if they don't exist)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database initialized successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

async def close_db():
    """Close database connections"""
    global engine
    
    if engine:
        await engine.dispose()
        logger.info("Database connections closed")

@asynccontextmanager
async def get_session():
    """
    Get a database session.
    
    Yields:
        AsyncSession: Database session
    """
    global AsyncSessionFactory
    
    if not AsyncSessionFactory:
        await init_db()
    
    session = AsyncSessionFactory()
    try:
        yield session
    finally:
        await session.close()

async def setup_guild(guild_id, guild_name=None):
    """
    Set up a guild in the database.
    
    Args:
        guild_id (int): Discord guild ID
        guild_name (str, optional): Guild name. If None, will be retrieved from the database.
    
    Returns:
        Guild: Guild database object
    """
    try:
        async with get_session() as session:
            # Check if guild exists
            query = select(Guild).where(Guild.id == guild_id)
            result = await session.execute(query)
            guild = result.scalar_one_or_none()
            
            if guild:
                # Update name if provided
                if guild_name and guild.name != guild_name:
                    guild.name = guild_name
                    await session.commit()
                return guild
            
            # Create new guild
            guild = Guild(
                id=guild_id,
                name=guild_name or f"Guild {guild_id}",
                prefix="!",
                language="en"
            )
            session.add(guild)
            await session.commit()
            
            logger.info(f"Created new guild in database: {guild_id}")
            return guild
    
    except Exception as e:
        logger.error(f"Error setting up guild {guild_id}: {e}")
        return None

async def get_guild_language(guild_id):
    """
    Get the preferred language for a guild.
    
    Args:
        guild_id (int): Discord guild ID
    
    Returns:
        str: Language code (e.g., 'en', 'ru', 'de')
    """
    try:
        async with get_session() as session:
            query = select(Guild.language).where(Guild.id == guild_id)
            result = await session.execute(query)
            language = result.scalar_one_or_none()
            
            return language or 'en'
    except Exception as e:
        logger.error(f"Error getting guild language for {guild_id}: {e}")
        return 'en'

async def get_member_language(user_id, guild_id):
    """
    Get the preferred language for a member.
    
    Args:
        user_id (int): Discord user ID
        guild_id (int): Discord guild ID
    
    Returns:
        str: Language code (e.g., 'en', 'ru', 'de')
    """
    try:
        async with get_session() as session:
            # Check if member has a language preference
            query = select(Member.language).where(
                Member.id == user_id,
                Member.guild_id == guild_id
            )
            result = await session.execute(query)
            member_language = result.scalar_one_or_none()
            
            if member_language:
                return member_language
            
            # Fall back to guild language
            return await get_guild_language(guild_id)
    except Exception as e:
        logger.error(f"Error getting member language for {user_id} in {guild_id}: {e}")
        return 'en'

async def set_guild_language(guild_id, language):
    """
    Set the preferred language for a guild.
    
    Args:
        guild_id (int): Discord guild ID
        language (str): Language code
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with get_session() as session:
            # Get or create guild
            query = select(Guild).where(Guild.id == guild_id)
            result = await session.execute(query)
            guild = result.scalar_one_or_none()
            
            if not guild:
                guild = Guild(
                    id=guild_id,
                    name=f"Guild {guild_id}",
                    language=language
                )
                session.add(guild)
            else:
                guild.language = language
            
            await session.commit()
            logger.info(f"Set language for guild {guild_id} to {language}")
            return True
    
    except Exception as e:
        logger.error(f"Error setting guild language for {guild_id}: {e}")
        return False

async def set_member_language(user_id, guild_id, language):
    """
    Set the preferred language for a member.
    
    Args:
        user_id (int): Discord user ID
        guild_id (int): Discord guild ID
        language (str): Language code
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with get_session() as session:
            # Check if member exists
            query = select(Member).where(
                Member.id == user_id,
                Member.guild_id == guild_id
            )
            result = await session.execute(query)
            member = result.scalar_one_or_none()
            
            if not member:
                member = Member(
                    id=user_id,
                    guild_id=guild_id,
                    username=f"User {user_id}",
                    language=language
                )
                session.add(member)
            else:
                member.language = language
            
            await session.commit()
            logger.info(f"Set language for member {user_id} in guild {guild_id} to {language}")
            return True
    
    except Exception as e:
        logger.error(f"Error setting member language for {user_id} in {guild_id}: {e}")
        return False

async def get_guild_module_states(guild_id):
    """
    Get the module states for a guild.
    
    Args:
        guild_id (int): Discord guild ID
    
    Returns:
        dict: Module states
    """
    try:
        async with get_session() as session:
            query = select(Guild.module_config).where(Guild.id == guild_id)
            result = await session.execute(query)
            module_config = result.scalar_one_or_none()
            
            if not module_config:
                # Default module configuration
                return {
                    "moderation": True,
                    "utility": True,
                    "entertainment": True,
                    "music": True,
                    "ai": True,
                    "verification": False,
                    "statistics": True,
                    "auto_mod": False
                }
            
            return module_config
    
    except Exception as e:
        logger.error(f"Error getting module states for guild {guild_id}: {e}")
        return {
            "moderation": True,
            "utility": True,
            "entertainment": True,
            "music": True,
            "ai": True,
            "verification": False,
            "statistics": True,
            "auto_mod": False
        }

async def set_guild_module_state(guild_id, module_name, state):
    """
    Set the state of a module for a guild.
    
    Args:
        guild_id (int): Discord guild ID
        module_name (str): Module name
        state (bool): Module state
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        async with get_session() as session:
            # Get guild
            query = select(Guild).where(Guild.id == guild_id)
            result = await session.execute(query)
            guild = result.scalar_one_or_none()
            
            if not guild:
                return False
            
            # Initialize module_config if it doesn't exist
            if not guild.module_config:
                guild.module_config = {}
            
            # Update module state
            guild.module_config[module_name] = state
            await session.commit()
            
            logger.info(f"Set module {module_name} to {state} for guild {guild_id}")
            return True
    
    except Exception as e:
        logger.error(f"Error setting module state for guild {guild_id}: {e}")
        return False
