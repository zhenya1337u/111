"""
Database models for the Discord bot.
These models define the schema for the PostgreSQL database.
"""
import datetime
from typing import List, Optional
import enum

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum, ForeignKey, 
    Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all models."""
    pass

class User(Base):
    """Model representing a Discord user."""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True)
    username = Column(String(32), nullable=False)
    discriminator = Column(String(4), nullable=True)  # Might be None with Discord's new username system
    avatar_url = Column(String(255), nullable=True)
    is_bot = Column(Boolean, default=False)
    language = Column(String(5), default="en")  # User's preferred language
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    warns = relationship("Warn", back_populates="user", cascade="all, delete-orphan")
    mod_logs_as_moderator = relationship("ModLog", back_populates="moderator", foreign_keys="ModLog.moderator_id")
    mod_logs_as_user = relationship("ModLog", back_populates="user", foreign_keys="ModLog.user_id")
    
    def __repr__(self):
        return f"<User id={self.id} username={self.username}>"

class GuildConfig(Base):
    """Configuration for a Discord guild/server."""
    __tablename__ = "guild_configs"
    
    guild_id = Column(BigInteger, primary_key=True)
    prefix = Column(String(10), default="!")
    language = Column(String(5), default="en")
    
    # Module settings
    moderation_enabled = Column(Boolean, default=True)
    fun_enabled = Column(Boolean, default=True)
    utility_enabled = Column(Boolean, default=True)
    music_enabled = Column(Boolean, default=True)
    ai_enabled = Column(Boolean, default=False)
    
    # Channel IDs for various logs
    log_channel_id = Column(BigInteger, nullable=True)
    mod_log_channel_id = Column(BigInteger, nullable=True)
    welcome_channel_id = Column(BigInteger, nullable=True)
    
    # Auto-moderation settings
    caps_filter_enabled = Column(Boolean, default=False)
    caps_threshold = Column(Integer, default=70)  # Percentage
    spam_filter_enabled = Column(Boolean, default=False)
    max_mentions = Column(Integer, default=5)
    
    # CAPTCHA verification
    verification_enabled = Column(Boolean, default=False)
    verification_role_id = Column(BigInteger, nullable=True)
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    raid_config = relationship("RaidConfig", uselist=False, back_populates="guild_config", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<GuildConfig guild_id={self.guild_id}>"

class ActionType(enum.Enum):
    """Types of moderation actions."""
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    TIMEOUT = "timeout"
    UNMUTE = "unmute"
    UNBAN = "unban"
    CLEAR = "clear"
    ANTIRAID = "antiraid"
    VERIFICATION = "verification"
    OTHER = "other"

class ModLog(Base):
    """Log of moderation actions."""
    __tablename__ = "mod_logs"
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    moderator_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    action_type = Column(Enum(ActionType), nullable=False)
    reason = Column(Text, nullable=True)
    duration = Column(Integer, nullable=True)  # Duration in seconds for temporary actions
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    moderator = relationship("User", back_populates="mod_logs_as_moderator", foreign_keys=[moderator_id])
    user = relationship("User", back_populates="mod_logs_as_user", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<ModLog id={self.id} action={self.action_type.value}>"

class Warn(Base):
    """Warning issued to a user."""
    __tablename__ = "warns"
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    moderator_id = Column(BigInteger, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="warns")
    
    # Composite index for guild_id and user_id
    __table_args__ = (
        UniqueConstraint("id", "guild_id", name="uix_warn_id_guild_id"),
    )
    
    def __repr__(self):
        return f"<Warn id={self.id} user_id={self.user_id}>"

class RaidConfig(Base):
    """Anti-raid configuration for a guild."""
    __tablename__ = "raid_configs"
    
    guild_id = Column(BigInteger, ForeignKey("guild_configs.guild_id"), primary_key=True)
    enabled = Column(Boolean, default=False)
    join_threshold = Column(Integer, default=10)  # Number of joins
    join_time_window = Column(Integer, default=10)  # Time window in seconds
    action = Column(String(20), default="verification")  # 'verification', 'kick', 'ban'
    alert_channel_id = Column(BigInteger, nullable=True)
    
    # Relationships
    guild_config = relationship("GuildConfig", back_populates="raid_config")
    
    def __repr__(self):
        return f"<RaidConfig guild_id={self.guild_id} enabled={self.enabled}>"

class MusicSession(Base):
    """Music player session data."""
    __tablename__ = "music_sessions"
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False, unique=True)
    text_channel_id = Column(BigInteger, nullable=True)
    voice_channel_id = Column(BigInteger, nullable=True)
    is_playing = Column(Boolean, default=False)
    volume = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<MusicSession guild_id={self.guild_id} is_playing={self.is_playing}>"

class Statistics(Base):
    """Bot usage statistics."""
    __tablename__ = "statistics"
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    command_name = Column(String(50), nullable=False)
    user_id = Column(BigInteger, nullable=False)
    success = Column(Boolean, default=True)
    execution_time = Column(Integer, nullable=True)  # in milliseconds
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Composite index for guild_id and command_name
    __table_args__ = (
        UniqueConstraint("id", "guild_id", "command_name", name="uix_stats_id_guild_command"),
    )
    
    def __repr__(self):
        return f"<Statistics command={self.command_name} guild_id={self.guild_id}>"
