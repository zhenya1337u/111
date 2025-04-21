"""
Database management module for the Discord bot.
Handles database connections and operations.
"""

import os
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, Float
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import JSONB
import asyncio

logger = logging.getLogger('discord_bot')

# Create declarative base for SQLAlchemy models
Base = declarative_base()

# Engine and session factory variables (initialized in initialize_db)
engine = None
SessionFactory = None


class Guild(Base):
    """Guild database model."""
    __tablename__ = 'guilds'
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    prefix = Column(String(10), default="!")
    language = Column(String(5), default="en")
    owner_id = Column(BigInteger, nullable=False)
    joined_at = Column(DateTime, server_default=func.now())
    settings = Column(JSONB, default={})


class User(Base):
    """User database model."""
    __tablename__ = 'users'
    
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    discriminator = Column(String(10), nullable=True)
    bot = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    preferences = Column(JSONB, default={})


class GuildMember(Base):
    """Guild Member database model."""
    __tablename__ = 'guild_members'
    
    guild_id = Column(BigInteger, ForeignKey('guilds.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True)
    nickname = Column(String(255), nullable=True)
    joined_at = Column(DateTime, nullable=True)
    roles = Column(JSONB, default=[])
    settings = Column(JSONB, default={})


class ModLog(Base):
    """Moderation log database model."""
    __tablename__ = 'mod_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    moderator_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    action = Column(String(50), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)
    active = Column(Boolean, default=True)
    metadata = Column(JSONB, default={})


class ModuleSettings(Base):
    """Module settings database model."""
    __tablename__ = 'module_settings'
    
    guild_id = Column(BigInteger, ForeignKey('guilds.id', ondelete='CASCADE'), primary_key=True)
    module_name = Column(String(100), primary_key=True)
    enabled = Column(Boolean, default=True)
    settings = Column(JSONB, default={})


class Stats(Base):
    """Server statistics database model."""
    __tablename__ = 'stats'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id', ondelete='CASCADE'), nullable=False)
    timestamp = Column(DateTime, server_default=func.now())
    member_count = Column(Integer, default=0)
    online_count = Column(Integer, default=0)
    message_count = Column(Integer, default=0)
    command_count = Column(Integer, default=0)
    metadata = Column(JSONB, default={})


class MusicPlaylist(Base):
    """Music playlist database model."""
    __tablename__ = 'music_playlists'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(BigInteger, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    name = Column(String(100), nullable=False)
    songs = Column(JSONB, default=[])
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class RaidProtection(Base):
    """Raid protection database model."""
    __tablename__ = 'raid_protection'
    
    guild_id = Column(BigInteger, ForeignKey('guilds.id', ondelete='CASCADE'), primary_key=True)
    enabled = Column(Boolean, default=False)
    min_account_age = Column(Integer, default=86400)  # Seconds
    join_rate_limit = Column(Integer, default=10)     # Members per minute
    auto_action = Column(String(50), default="none")  # none, captcha, kick, ban
    log_channel_id = Column(BigInteger, nullable=True)
    settings = Column(JSONB, default={})


class Verification(Base):
    """Verification database model."""
    __tablename__ = 'verification'
    
    guild_id = Column(BigInteger, ForeignKey('guilds.id', ondelete='CASCADE'), primary_key=True)
    enabled = Column(Boolean, default=False)
    role_id = Column(BigInteger, nullable=True)
    method = Column(String(50), default="captcha")  # captcha, reaction, etc.
    settings = Column(JSONB, default={})


async def initialize_db(database_url: str) -> None:
    """
    Initialize the database connection.
    
    Args:
        database_url: Database connection URL.
    """
    global engine, SessionFactory
    
    try:
        engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
            pool_recycle=300,
        )
        
        SessionFactory = async_sessionmaker(
            engine,
            expire_on_commit=False,
            class_=AsyncSession
        )
        
        # Create all tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
        logger.info("Database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def get_session() -> AsyncSession:
    """
    Get a database session.
    
    Returns:
        An AsyncSession instance.
    """
    if SessionFactory is None:
        raise RuntimeError("Database not initialized. Call initialize_db first.")
    
    return SessionFactory()


async def execute_sql(sql: str, params: Dict = None) -> Any:
    """
    Execute raw SQL query.
    
    Args:
        sql: SQL query.
        params: SQL parameters.
        
    Returns:
        Query result.
    """
    session = await get_session()
    try:
        result = await session.execute(sql, params or {})
        await session.commit()
        return result
    except Exception as e:
        await session.rollback()
        logger.error(f"SQL error: {e}")
        raise
    finally:
        await session.close()
