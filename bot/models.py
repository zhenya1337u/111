#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Database models for the Discord bot using SQLAlchemy ORM.
"""

import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, BigInteger, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class Guild(Base):
    """Model for guild (server) settings"""
    __tablename__ = 'guilds'
    
    id = Column(BigInteger, primary_key=True)  # Discord Guild ID
    name = Column(String(100), nullable=False)
    prefix = Column(String(10), default='!')
    language = Column(String(10), default='en')
    log_channel_id = Column(BigInteger, nullable=True)
    welcome_channel_id = Column(BigInteger, nullable=True)
    welcome_message = Column(Text, nullable=True)
    mute_role_id = Column(BigInteger, nullable=True)
    verification_enabled = Column(Boolean, default=False)
    verification_channel_id = Column(BigInteger, nullable=True)
    verification_role_id = Column(BigInteger, nullable=True)
    anti_raid_enabled = Column(Boolean, default=False)
    anti_raid_threshold = Column(Integer, default=10)
    auto_mod_enabled = Column(Boolean, default=False)
    caps_filter_enabled = Column(Boolean, default=False)
    caps_filter_threshold = Column(Float, default=0.7)
    module_config = Column(JSON, default={})
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    members = relationship("Member", back_populates="guild", cascade="all, delete-orphan")
    mod_roles = relationship("ModRole", back_populates="guild", cascade="all, delete-orphan")
    auto_roles = relationship("AutoRole", back_populates="guild", cascade="all, delete-orphan")
    custom_commands = relationship("CustomCommand", back_populates="guild", cascade="all, delete-orphan")
    warnings = relationship("Warning", back_populates="guild", cascade="all, delete-orphan")
    mutes = relationship("Mute", back_populates="guild", cascade="all, delete-orphan")
    bans = relationship("Ban", back_populates="guild", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Guild(id={self.id}, name='{self.name}')>"

class Member(Base):
    """Model for guild member data"""
    __tablename__ = 'members'
    
    id = Column(BigInteger, primary_key=True)  # Discord User ID
    guild_id = Column(BigInteger, ForeignKey('guilds.id'), primary_key=True)
    username = Column(String(100), nullable=False)
    nickname = Column(String(100), nullable=True)
    joined_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_active = Column(DateTime, nullable=True)
    experience = Column(Integer, default=0)
    level = Column(Integer, default=0)
    language = Column(String(10), nullable=True)
    is_verified = Column(Boolean, default=False)
    
    # Relationships
    guild = relationship("Guild", back_populates="members")
    warnings = relationship("Warning", back_populates="member", cascade="all, delete-orphan")
    mutes = relationship("Mute", back_populates="member", cascade="all, delete-orphan")
    bans = relationship("Ban", back_populates="member", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Member(id={self.id}, guild_id={self.guild_id}, username='{self.username}')>"

class ModRole(Base):
    """Model for moderator roles"""
    __tablename__ = 'mod_roles'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'))
    role_id = Column(BigInteger, nullable=False)
    role_name = Column(String(100), nullable=False)
    
    # Relationships
    guild = relationship("Guild", back_populates="mod_roles")
    
    def __repr__(self):
        return f"<ModRole(guild_id={self.guild_id}, role_id={self.role_id}, role_name='{self.role_name}')>"

class AutoRole(Base):
    """Model for auto-assigned roles"""
    __tablename__ = 'auto_roles'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'))
    role_id = Column(BigInteger, nullable=False)
    role_name = Column(String(100), nullable=False)
    
    # Relationships
    guild = relationship("Guild", back_populates="auto_roles")
    
    def __repr__(self):
        return f"<AutoRole(guild_id={self.guild_id}, role_id={self.role_id}, role_name='{self.role_name}')>"

class CustomCommand(Base):
    """Model for custom commands"""
    __tablename__ = 'custom_commands'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'))
    name = Column(String(50), nullable=False)
    response = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    created_by = Column(BigInteger, nullable=False)  # Discord User ID
    
    # Relationships
    guild = relationship("Guild", back_populates="custom_commands")
    
    def __repr__(self):
        return f"<CustomCommand(guild_id={self.guild_id}, name='{self.name}')>"

class Warning(Base):
    """Model for user warnings"""
    __tablename__ = 'warnings'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'))
    user_id = Column(BigInteger, ForeignKey('members.id'))
    moderator_id = Column(BigInteger, nullable=False)  # Discord User ID
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    guild = relationship("Guild", back_populates="warnings")
    member = relationship("Member", back_populates="warnings")
    
    def __repr__(self):
        return f"<Warning(guild_id={self.guild_id}, user_id={self.user_id}, reason='{self.reason}')>"

class Mute(Base):
    """Model for user mutes"""
    __tablename__ = 'mutes'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'))
    user_id = Column(BigInteger, ForeignKey('members.id'))
    moderator_id = Column(BigInteger, nullable=False)  # Discord User ID
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    guild = relationship("Guild", back_populates="mutes")
    member = relationship("Member", back_populates="mutes")
    
    def __repr__(self):
        return f"<Mute(guild_id={self.guild_id}, user_id={self.user_id}, expires_at={self.expires_at})>"

class Ban(Base):
    """Model for user bans"""
    __tablename__ = 'bans'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'))
    user_id = Column(BigInteger, ForeignKey('members.id'))
    moderator_id = Column(BigInteger, nullable=False)  # Discord User ID
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    guild = relationship("Guild", back_populates="bans")
    member = relationship("Member", back_populates="bans")
    
    def __repr__(self):
        return f"<Ban(guild_id={self.guild_id}, user_id={self.user_id}, reason='{self.reason}')>"

class Verification(Base):
    """Model for verification sessions"""
    __tablename__ = 'verifications'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    verification_code = Column(String(20), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    completed = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<Verification(guild_id={self.guild_id}, user_id={self.user_id}, completed={self.completed})>"

class RaidProtection(Base):
    """Model for raid protection events"""
    __tablename__ = 'raid_protection'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    triggered_at = Column(DateTime, default=datetime.datetime.utcnow)
    triggered_by = Column(String(100), nullable=True)  # Description of what triggered it
    action_taken = Column(String(50), nullable=False)  # lockdown, notify, etc.
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(BigInteger, nullable=True)  # Discord User ID
    
    def __repr__(self):
        return f"<RaidProtection(guild_id={self.guild_id}, triggered_at={self.triggered_at}, action='{self.action_taken}')>"

class GuildStats(Base):
    """Model for guild statistics"""
    __tablename__ = 'guild_stats'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    member_count = Column(Integer, default=0)
    message_count = Column(Integer, default=0)
    command_count = Column(Integer, default=0)
    join_count = Column(Integer, default=0)
    leave_count = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<GuildStats(guild_id={self.guild_id}, date={self.date})>"

class ReactionRole(Base):
    """Model for reaction roles"""
    __tablename__ = 'reaction_roles'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    channel_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    emoji = Column(String(100), nullable=False)
    role_id = Column(BigInteger, nullable=False)
    
    def __repr__(self):
        return f"<ReactionRole(guild_id={self.guild_id}, message_id={self.message_id}, role_id={self.role_id})>"

class MusicSession(Base):
    """Model for music playback sessions"""
    __tablename__ = 'music_sessions'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    songs_played = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<MusicSession(guild_id={self.guild_id}, created_at={self.created_at})>"

class CommandUsage(Base):
    """Model for command usage statistics"""
    __tablename__ = 'command_usage'
    
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, nullable=False)
    user_id = Column(BigInteger, nullable=False)
    command_name = Column(String(50), nullable=False)
    used_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    def __repr__(self):
        return f"<CommandUsage(guild_id={self.guild_id}, command='{self.command_name}')>"

class WebUser(Base):
    """Model for web panel users"""
    __tablename__ = 'web_users'
    
    id = Column(BigInteger, primary_key=True)  # Discord User ID
    username = Column(String(100), nullable=False)
    email = Column(String(100), nullable=True)
    password_hash = Column(String(256), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<WebUser(id={self.id}, username='{self.username}')>"

class WebSession(Base):
    """Model for web panel sessions"""
    __tablename__ = 'web_sessions'
    
    id = Column(String(64), primary_key=True)
    user_id = Column(BigInteger, ForeignKey('web_users.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(200), nullable=True)
    
    def __repr__(self):
        return f"<WebSession(user_id={self.user_id}, created_at={self.created_at})>"

class BackupLog(Base):
    """Model for database backup logs"""
    __tablename__ = 'backup_logs'
    
    id = Column(Integer, primary_key=True)
    backup_time = Column(DateTime, default=datetime.datetime.utcnow)
    filename = Column(String(100), nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    status = Column(String(20), nullable=False)  # success, failed
    destination = Column(String(100), nullable=True)  # local, google_drive, etc.
    
    def __repr__(self):
        return f"<BackupLog(backup_time={self.backup_time}, status='{self.status}')>"
