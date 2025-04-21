from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Make this file a proper module for models
# The db object will be injected from main.py

class UserModel:
    """Base for all user models"""
    
    @classmethod
    def setup_model(cls, db):
        """Configure the model with SQLAlchemy instance"""
        
        class Guild(db.Model):
            """Model for guild (server) settings"""
            __tablename__ = 'guilds'
            
            id = db.Column(db.BigInteger, primary_key=True)  # Discord Guild ID
            name = db.Column(db.String(100), nullable=False)
            prefix = db.Column(db.String(10), default='!')
            language = db.Column(db.String(10), default='en')
            log_channel_id = db.Column(db.BigInteger, nullable=True)
            welcome_channel_id = db.Column(db.BigInteger, nullable=True)
            welcome_message = db.Column(db.Text, nullable=True)
            mute_role_id = db.Column(db.BigInteger, nullable=True)
            verification_enabled = db.Column(db.Boolean, default=False)
            verification_channel_id = db.Column(db.BigInteger, nullable=True)
            verification_role_id = db.Column(db.BigInteger, nullable=True)
            anti_raid_enabled = db.Column(db.Boolean, default=False)
            anti_raid_threshold = db.Column(db.Integer, default=10)
            auto_mod_enabled = db.Column(db.Boolean, default=False)
            caps_filter_enabled = db.Column(db.Boolean, default=False)
            caps_filter_threshold = db.Column(db.Float, default=0.7)
            module_config = db.Column(db.JSON, default={})
            joined_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        class Member(db.Model):
            """Model for guild member data"""
            __tablename__ = 'members'
            
            id = db.Column(db.BigInteger, primary_key=True)  # Discord User ID
            guild_id = db.Column(db.BigInteger, db.ForeignKey('guilds.id'), primary_key=True)
            username = db.Column(db.String(100), nullable=False)
            nickname = db.Column(db.String(100), nullable=True)
            joined_at = db.Column(db.DateTime, default=datetime.utcnow)
            last_active = db.Column(db.DateTime, nullable=True)
            experience = db.Column(db.Integer, default=0)
            level = db.Column(db.Integer, default=0)
            language = db.Column(db.String(10), nullable=True)
            is_verified = db.Column(db.Boolean, default=False)
        
        class ModRole(db.Model):
            """Model for moderator roles"""
            __tablename__ = 'mod_roles'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, db.ForeignKey('guilds.id'))
            role_id = db.Column(db.BigInteger, nullable=False)
            role_name = db.Column(db.String(100), nullable=False)
        
        class AutoRole(db.Model):
            """Model for auto-assigned roles"""
            __tablename__ = 'auto_roles'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, db.ForeignKey('guilds.id'))
            role_id = db.Column(db.BigInteger, nullable=False)
            role_name = db.Column(db.String(100), nullable=False)
        
        class CustomCommand(db.Model):
            """Model for custom commands"""
            __tablename__ = 'custom_commands'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, db.ForeignKey('guilds.id'))
            name = db.Column(db.String(50), nullable=False)
            response = db.Column(db.Text, nullable=False)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            created_by = db.Column(db.BigInteger, nullable=False)  # Discord User ID
        
        class Warning(db.Model):
            """Model for user warnings"""
            __tablename__ = 'warnings'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, db.ForeignKey('guilds.id'))
            user_id = db.Column(db.BigInteger, db.ForeignKey('members.id'))
            moderator_id = db.Column(db.BigInteger, nullable=False)  # Discord User ID
            reason = db.Column(db.Text, nullable=True)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        class Mute(db.Model):
            """Model for user mutes"""
            __tablename__ = 'mutes'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, db.ForeignKey('guilds.id'))
            user_id = db.Column(db.BigInteger, db.ForeignKey('members.id'))
            moderator_id = db.Column(db.BigInteger, nullable=False)  # Discord User ID
            reason = db.Column(db.Text, nullable=True)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            expires_at = db.Column(db.DateTime, nullable=True)
            is_active = db.Column(db.Boolean, default=True)
        
        class Ban(db.Model):
            """Model for user bans"""
            __tablename__ = 'bans'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, db.ForeignKey('guilds.id'))
            user_id = db.Column(db.BigInteger, db.ForeignKey('members.id'))
            moderator_id = db.Column(db.BigInteger, nullable=False)  # Discord User ID
            reason = db.Column(db.Text, nullable=True)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            expires_at = db.Column(db.DateTime, nullable=True)
            is_active = db.Column(db.Boolean, default=True)
        
        class Verification(db.Model):
            """Model for verification sessions"""
            __tablename__ = 'verifications'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, nullable=False)
            user_id = db.Column(db.BigInteger, nullable=False)
            verification_code = db.Column(db.String(20), nullable=False)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            expires_at = db.Column(db.DateTime, nullable=False)
            completed = db.Column(db.Boolean, default=False)
        
        class RaidProtection(db.Model):
            """Model for raid protection events"""
            __tablename__ = 'raid_protection'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, nullable=False)
            triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
            triggered_by = db.Column(db.String(100), nullable=True)  # Description of what triggered it
            action_taken = db.Column(db.String(50), nullable=False)  # lockdown, notify, etc.
            resolved_at = db.Column(db.DateTime, nullable=True)
            resolved_by = db.Column(db.BigInteger, nullable=True)  # Discord User ID
        
        class GuildStats(db.Model):
            """Model for guild statistics"""
            __tablename__ = 'guild_stats'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, nullable=False)
            date = db.Column(db.DateTime, default=datetime.utcnow)
            member_count = db.Column(db.Integer, default=0)
            message_count = db.Column(db.Integer, default=0)
            command_count = db.Column(db.Integer, default=0)
            join_count = db.Column(db.Integer, default=0)
            leave_count = db.Column(db.Integer, default=0)
        
        class ReactionRole(db.Model):
            """Model for reaction roles"""
            __tablename__ = 'reaction_roles'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, nullable=False)
            channel_id = db.Column(db.BigInteger, nullable=False)
            message_id = db.Column(db.BigInteger, nullable=False)
            emoji = db.Column(db.String(100), nullable=False)
            role_id = db.Column(db.BigInteger, nullable=False)
        
        class MusicSession(db.Model):
            """Model for music playback sessions"""
            __tablename__ = 'music_sessions'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, nullable=False)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            ended_at = db.Column(db.DateTime, nullable=True)
            songs_played = db.Column(db.Integer, default=0)
        
        class CommandUsage(db.Model):
            """Model for command usage statistics"""
            __tablename__ = 'command_usage'
            
            id = db.Column(db.Integer, primary_key=True)
            guild_id = db.Column(db.BigInteger, nullable=False)
            user_id = db.Column(db.BigInteger, nullable=False)
            command_name = db.Column(db.String(50), nullable=False)
            used_at = db.Column(db.DateTime, default=datetime.utcnow)
        
        class WebUser(db.Model):
            """Model for web panel users"""
            __tablename__ = 'web_users'
            
            id = db.Column(db.BigInteger, primary_key=True)  # Discord User ID
            username = db.Column(db.String(100), nullable=False)
            email = db.Column(db.String(100), nullable=True)
            password_hash = db.Column(db.String(256), nullable=True)
            is_admin = db.Column(db.Boolean, default=False)
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            last_login = db.Column(db.DateTime, nullable=True)
        
        class WebSession(db.Model):
            """Model for web panel sessions"""
            __tablename__ = 'web_sessions'
            
            id = db.Column(db.String(64), primary_key=True)
            user_id = db.Column(db.BigInteger, db.ForeignKey('web_users.id'))
            created_at = db.Column(db.DateTime, default=datetime.utcnow)
            expires_at = db.Column(db.DateTime, nullable=False)
            ip_address = db.Column(db.String(50), nullable=True)
            user_agent = db.Column(db.String(200), nullable=True)
        
        class BackupLog(db.Model):
            """Model for database backup logs"""
            __tablename__ = 'backup_logs'
            
            id = db.Column(db.Integer, primary_key=True)
            backup_time = db.Column(db.DateTime, default=datetime.utcnow)
            filename = db.Column(db.String(100), nullable=False)
            size_bytes = db.Column(db.BigInteger, nullable=False)
            status = db.Column(db.String(20), nullable=False)  # success, failed
            destination = db.Column(db.String(100), nullable=True)  # local, google_drive, etc.
    
        # Return all models
        return {
            'Guild': Guild,
            'Member': Member,
            'ModRole': ModRole,
            'AutoRole': AutoRole,
            'CustomCommand': CustomCommand,
            'Warning': Warning,
            'Mute': Mute,
            'Ban': Ban,
            'Verification': Verification,
            'RaidProtection': RaidProtection,
            'GuildStats': GuildStats,
            'ReactionRole': ReactionRole,
            'MusicSession': MusicSession, 
            'CommandUsage': CommandUsage,
            'WebUser': WebUser,
            'WebSession': WebSession,
            'BackupLog': BackupLog
        }