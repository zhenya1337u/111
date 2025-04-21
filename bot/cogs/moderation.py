#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Moderation commands for Discord bot.
Includes features for warning, kicking, banning, muting users and more.
"""

import disnake
from disnake.ext import commands, tasks
import asyncio
import datetime
from typing import Optional
import logging
from sqlalchemy.future import select
from sqlalchemy import update, delete

from bot.utils.embed_creator import create_embed
from bot.utils.localization import _
from bot.utils.db_manager import get_session
from bot.models import Guild, Member, Warning, Mute, Ban

class Moderation(commands.Cog):
    """Moderation commands for server management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.moderation')
        self.mute_check.start()
        self.ban_check.start()
    
    def cog_unload(self):
        self.mute_check.cancel()
        self.ban_check.cancel()
    
    @tasks.loop(minutes=1)
    async def mute_check(self):
        """Check for expired mutes and unmute users"""
        try:
            async with get_session() as session:
                # Get all active mutes that have expired
                now = datetime.datetime.utcnow()
                query = select(Mute).where(
                    Mute.is_active == True,
                    Mute.expires_at <= now
                )
                result = await session.execute(query)
                expired_mutes = result.scalars().all()
                
                for mute in expired_mutes:
                    # Get guild and update mute status
                    guild = self.bot.get_guild(mute.guild_id)
                    if not guild:
                        continue
                    
                    # Update mute in database
                    stmt = update(Mute).where(Mute.id == mute.id).values(is_active=False)
                    await session.execute(stmt)
                    await session.commit()
                    
                    # Try to unmute the user
                    try:
                        # Get mute role
                        guild_query = select(Guild).where(Guild.id == mute.guild_id)
                        guild_result = await session.execute(guild_query)
                        guild_data = guild_result.scalars().first()
                        
                        if not guild_data or not guild_data.mute_role_id:
                            continue
                        
                        mute_role = guild.get_role(guild_data.mute_role_id)
                        if not mute_role:
                            continue
                        
                        # Get member and remove role
                        member = guild.get_member(mute.user_id)
                        if member:
                            await member.remove_roles(mute_role, reason="Mute expired")
                            self.logger.info(f"Automatically unmuted user {member.name}#{member.discriminator} in {guild.name}")
                            
                            # Log to mod channel if configured
                            if guild_data.log_channel_id:
                                log_channel = guild.get_channel(guild_data.log_channel_id)
                                if log_channel:
                                    embed = create_embed(
                                        title=_("Mute Expired", guild_data.language),
                                        description=_("User has been automatically unmuted", guild_data.language),
                                        color=disnake.Color.green()
                                    )
                                    embed.add_field(
                                        name=_("User", guild_data.language),
                                        value=f"{member.mention} ({member.name}#{member.discriminator})"
                                    )
                                    embed.set_footer(text=f"User ID: {member.id}")
                                    embed.timestamp = now
                                    await log_channel.send(embed=embed)
                    except Exception as e:
                        self.logger.error(f"Error unmuting user {mute.user_id} in guild {mute.guild_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error in mute check task: {e}")
    
    @mute_check.before_loop
    async def before_mute_check(self):
        await self.bot.wait_until_ready()
    
    @tasks.loop(minutes=5)
    async def ban_check(self):
        """Check for expired bans and unban users"""
        try:
            async with get_session() as session:
                # Get all active bans that have expired
                now = datetime.datetime.utcnow()
                query = select(Ban).where(
                    Ban.is_active == True,
                    Ban.expires_at <= now
                )
                result = await session.execute(query)
                expired_bans = result.scalars().all()
                
                for ban in expired_bans:
                    # Get guild and update ban status
                    guild = self.bot.get_guild(ban.guild_id)
                    if not guild:
                        continue
                    
                    # Update ban in database
                    stmt = update(Ban).where(Ban.id == ban.id).values(is_active=False)
                    await session.execute(stmt)
                    await session.commit()
                    
                    # Try to unban the user
                    try:
                        # Get user and unban
                        user = await self.bot.fetch_user(ban.user_id)
                        if user:
                            await guild.unban(user, reason="Temporary ban expired")
                            self.logger.info(f"Automatically unbanned user {user.name}#{user.discriminator} from {guild.name}")
                            
                            # Log to mod channel if configured
                            guild_query = select(Guild).where(Guild.id == ban.guild_id)
                            guild_result = await session.execute(guild_query)
                            guild_data = guild_result.scalars().first()
                            
                            if guild_data and guild_data.log_channel_id:
                                log_channel = guild.get_channel(guild_data.log_channel_id)
                                if log_channel:
                                    embed = create_embed(
                                        title=_("Ban Expired", guild_data.language),
                                        description=_("User has been automatically unbanned", guild_data.language),
                                        color=disnake.Color.green()
                                    )
                                    embed.add_field(
                                        name=_("User", guild_data.language),
                                        value=f"{user.mention} ({user.name}#{user.discriminator})"
                                    )
                                    embed.set_footer(text=f"User ID: {user.id}")
                                    embed.timestamp = now
                                    await log_channel.send(embed=embed)
                    except Exception as e:
                        self.logger.error(f"Error unbanning user {ban.user_id} from guild {ban.guild_id}: {e}")
        except Exception as e:
            self.logger.error(f"Error in ban check task: {e}")
    
    @ban_check.before_loop
    async def before_ban_check(self):
        await self.bot.wait_until_ready()
        
    @commands.slash_command(name="warn")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def warn(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.User,
        reason: str = "No reason provided"
    ):
        """
        Warn a user for breaking rules
        
        Parameters
        ----------
        user: The user to warn
        reason: Reason for the warning
        """
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Check if member exists in database
            member_query = select(Member).where(
                Member.id == user.id,
                Member.guild_id == interaction.guild.id
            )
            member_result = await session.execute(member_query)
            member_data = member_result.scalars().first()
            
            if not member_data:
                # Create member data if it doesn't exist
                member_data = Member(
                    id=user.id,
                    guild_id=interaction.guild.id,
                    username=f"{user.name}#{user.discriminator}"
                )
                session.add(member_data)
                await session.commit()
            
            # Create warning
            warning = Warning(
                guild_id=interaction.guild.id,
                user_id=user.id,
                moderator_id=interaction.author.id,
                reason=reason
            )
            session.add(warning)
            await session.commit()
            
            # Count total warnings
            count_query = select(Warning).where(
                Warning.user_id == user.id,
                Warning.guild_id == interaction.guild.id
            )
            count_result = await session.execute(count_query)
            warnings = count_result.scalars().all()
            warning_count = len(warnings)
            
            # Create response embed
            embed = create_embed(
                title=_("User Warned", guild_data.language),
                description=_("A warning has been issued", guild_data.language),
                color=disnake.Color.orange()
            )
            embed.add_field(
                name=_("User", guild_data.language),
                value=f"{user.mention} ({user.name}#{user.discriminator})",
                inline=False
            )
            embed.add_field(
                name=_("Reason", guild_data.language),
                value=reason,
                inline=False
            )
            embed.add_field(
                name=_("Total Warnings", guild_data.language),
                value=str(warning_count),
                inline=False
            )
            embed.add_field(
                name=_("Moderator", guild_data.language),
                value=f"{interaction.author.mention}",
                inline=False
            )
            embed.set_footer(text=f"Warning ID: {warning.id}")
            embed.timestamp = datetime.datetime.utcnow()
            
            # Send response
            await interaction.response.send_message(embed=embed)
            
            # Try to DM the user
            try:
                user_embed = create_embed(
                    title=_("Warning Received", guild_data.language),
                    description=_("You have received a warning in {guild}", guild_data.language).format(
                        guild=interaction.guild.name
                    ),
                    color=disnake.Color.orange()
                )
                user_embed.add_field(
                    name=_("Reason", guild_data.language),
                    value=reason,
                    inline=False
                )
                user_embed.add_field(
                    name=_("Total Warnings", guild_data.language),
                    value=str(warning_count),
                    inline=False
                )
                user_embed.set_footer(text=f"Warning ID: {warning.id}")
                user_embed.timestamp = datetime.datetime.utcnow()
                
                await user.send(embed=user_embed)
            except Exception:
                # User might have DMs disabled
                pass
            
            # Log warning to mod channel if configured
            if guild_data.log_channel_id:
                log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                if log_channel:
                    await log_channel.send(embed=embed)
    
    @commands.slash_command(name="warnings")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def warnings(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.User
    ):
        """
        View warnings for a user
        
        Parameters
        ----------
        user: The user to check warnings for
        """
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Get warnings
            warnings_query = select(Warning).where(
                Warning.user_id == user.id,
                Warning.guild_id == interaction.guild.id
            ).order_by(Warning.created_at.desc())
            warnings_result = await session.execute(warnings_query)
            warnings = warnings_result.scalars().all()
            
            # Create response embed
            embed = create_embed(
                title=_("User Warnings", guild_data.language),
                description=_("Warnings for {user}", guild_data.language).format(
                    user=f"{user.name}#{user.discriminator}"
                ),
                color=disnake.Color.orange()
            )
            
            if not warnings:
                embed.description = _("This user has no warnings.", guild_data.language)
            else:
                for i, warning in enumerate(warnings[:10], 1):  # Show up to 10 warnings
                    moderator = interaction.guild.get_member(warning.moderator_id) or await self.bot.fetch_user(warning.moderator_id)
                    moderator_name = f"{moderator.name}#{moderator.discriminator}" if moderator else f"Unknown ({warning.moderator_id})"
                    
                    embed.add_field(
                        name=f"{_('Warning', guild_data.language)} #{i} (ID: {warning.id})",
                        value=_(
                            "**Reason:** {reason}\n**Date:** {date}\n**Moderator:** {moderator}",
                            guild_data.language
                        ).format(
                            reason=warning.reason,
                            date=warning.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                            moderator=moderator_name
                        ),
                        inline=False
                    )
                
                if len(warnings) > 10:
                    embed.set_footer(text=_("Showing 10 of {count} warnings", guild_data.language).format(count=len(warnings)))
            
            embed.timestamp = datetime.datetime.utcnow()
            
            # Send response
            await interaction.response.send_message(embed=embed)
    
    @commands.slash_command(name="clearwarnings")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def clearwarnings(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.User,
        warning_id: Optional[int] = None
    ):
        """
        Clear warnings for a user
        
        Parameters
        ----------
        user: The user to clear warnings for
        warning_id: Optional specific warning ID to remove (all warnings if not specified)
        """
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Delete warnings
            if warning_id:
                # Delete specific warning
                stmt = delete(Warning).where(
                    Warning.id == warning_id,
                    Warning.user_id == user.id,
                    Warning.guild_id == interaction.guild.id
                )
                result = await session.execute(stmt)
                await session.commit()
                
                if result.rowcount == 0:
                    embed = create_embed(
                        title=_("Error", guild_data.language),
                        description=_("Warning with ID {id} not found for this user.", guild_data.language).format(id=warning_id),
                        color=disnake.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
                
                embed = create_embed(
                    title=_("Warning Cleared", guild_data.language),
                    description=_("Removed warning #{id} from {user}", guild_data.language).format(
                        id=warning_id,
                        user=f"{user.mention} ({user.name}#{user.discriminator})"
                    ),
                    color=disnake.Color.green()
                )
            else:
                # Delete all warnings
                stmt = delete(Warning).where(
                    Warning.user_id == user.id,
                    Warning.guild_id == interaction.guild.id
                )
                result = await session.execute(stmt)
                await session.commit()
                
                embed = create_embed(
                    title=_("Warnings Cleared", guild_data.language),
                    description=_("Removed all warnings from {user}", guild_data.language).format(
                        user=f"{user.mention} ({user.name}#{user.discriminator})"
                    ),
                    color=disnake.Color.green()
                )
                embed.set_footer(text=_("{count} warnings were removed", guild_data.language).format(count=result.rowcount))
            
            embed.timestamp = datetime.datetime.utcnow()
            
            # Send response
            await interaction.response.send_message(embed=embed)
            
            # Log to mod channel if configured
            if guild_data.log_channel_id:
                log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                if log_channel:
                    log_embed = create_embed(
                        title=_("Warnings Cleared", guild_data.language),
                        description=_("Warnings have been cleared by a moderator", guild_data.language),
                        color=disnake.Color.green()
                    )
                    log_embed.add_field(
                        name=_("User", guild_data.language),
                        value=f"{user.mention} ({user.name}#{user.discriminator})",
                        inline=False
                    )
                    log_embed.add_field(
                        name=_("Moderator", guild_data.language),
                        value=f"{interaction.author.mention}",
                        inline=False
                    )
                    if warning_id:
                        log_embed.add_field(
                            name=_("Warning ID", guild_data.language),
                            value=str(warning_id),
                            inline=False
                        )
                    log_embed.timestamp = datetime.datetime.utcnow()
                    await log_channel.send(embed=log_embed)
    
    @commands.slash_command(name="kick")
    @commands.guild_only()
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        member: disnake.Member,
        reason: str = "No reason provided"
    ):
        """
        Kick a member from the server
        
        Parameters
        ----------
        member: The member to kick
        reason: Reason for the kick
        """
        # Check if user can be kicked
        if member.top_role >= interaction.author.top_role and interaction.author.id != interaction.guild.owner_id:
            embed = create_embed(
                title=_("Error", "en"),
                description=_("You cannot kick someone with a higher or equal role.", "en"),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if member.top_role >= interaction.guild.me.top_role:
            embed = create_embed(
                title=_("Error", "en"),
                description=_("I cannot kick someone with a higher role than me.", "en"),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Create response embed
            embed = create_embed(
                title=_("User Kicked", guild_data.language),
                description=_("A user has been kicked from the server", guild_data.language),
                color=disnake.Color.red()
            )
            embed.add_field(
                name=_("User", guild_data.language),
                value=f"{member.mention} ({member.name}#{member.discriminator})",
                inline=False
            )
            embed.add_field(
                name=_("Reason", guild_data.language),
                value=reason,
                inline=False
            )
            embed.add_field(
                name=_("Moderator", guild_data.language),
                value=f"{interaction.author.mention}",
                inline=False
            )
            embed.set_footer(text=f"User ID: {member.id}")
            embed.timestamp = datetime.datetime.utcnow()
            
            # Try to DM the user
            try:
                user_embed = create_embed(
                    title=_("You've Been Kicked", guild_data.language),
                    description=_("You have been kicked from {guild}", guild_data.language).format(
                        guild=interaction.guild.name
                    ),
                    color=disnake.Color.red()
                )
                user_embed.add_field(
                    name=_("Reason", guild_data.language),
                    value=reason,
                    inline=False
                )
                user_embed.timestamp = datetime.datetime.utcnow()
                
                await member.send(embed=user_embed)
            except Exception:
                # User might have DMs disabled
                pass
            
            # Kick the user
            await member.kick(reason=f"{interaction.author}: {reason}")
            
            # Send response
            await interaction.response.send_message(embed=embed)
            
            # Log kick to mod channel if configured
            if guild_data.log_channel_id:
                log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                if log_channel:
                    await log_channel.send(embed=embed)
    
    @commands.slash_command(name="ban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.User,
        reason: str = "No reason provided",
        delete_days: int = commands.Param(0, choices=[0, 1, 2, 3, 4, 5, 6, 7]),
        duration: str = None
    ):
        """
        Ban a user from the server
        
        Parameters
        ----------
        user: The user to ban
        reason: Reason for the ban
        delete_days: Number of days of messages to delete (0-7)
        duration: Optional duration of the ban (e.g. 1d, 7d, 1w, 1m)
        """
        member = interaction.guild.get_member(user.id)
        
        # Check if user can be banned
        if member:
            if member.top_role >= interaction.author.top_role and interaction.author.id != interaction.guild.owner_id:
                embed = create_embed(
                    title=_("Error", "en"),
                    description=_("You cannot ban someone with a higher or equal role.", "en"),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if member.top_role >= interaction.guild.me.top_role:
                embed = create_embed(
                    title=_("Error", "en"),
                    description=_("I cannot ban someone with a higher role than me.", "en"),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Parse duration
        expires_at = None
        if duration:
            try:
                amount = int(duration[:-1])
                unit = duration[-1].lower()
                
                if unit == 'd':
                    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=amount)
                elif unit == 'h':
                    expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=amount)
                elif unit == 'w':
                    expires_at = datetime.datetime.utcnow() + datetime.timedelta(weeks=amount)
                elif unit == 'm':
                    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=amount * 30)
                else:
                    embed = create_embed(
                        title=_("Error", "en"),
                        description=_("Invalid duration format. Use format like 1d, 7d, 1w, 1m.", "en"),
                        color=disnake.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return
            except ValueError:
                embed = create_embed(
                    title=_("Error", "en"),
                    description=_("Invalid duration format. Use format like 1d, 7d, 1w, 1m.", "en"),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Check if member exists in database
            member_query = select(Member).where(
                Member.id == user.id,
                Member.guild_id == interaction.guild.id
            )
            member_result = await session.execute(member_query)
            member_data = member_result.scalars().first()
            
            if not member_data:
                # Create member data if it doesn't exist
                member_data = Member(
                    id=user.id,
                    guild_id=interaction.guild.id,
                    username=f"{user.name}#{user.discriminator}"
                )
                session.add(member_data)
                await session.commit()
            
            # Create ban record
            ban_record = Ban(
                guild_id=interaction.guild.id,
                user_id=user.id,
                moderator_id=interaction.author.id,
                reason=reason,
                expires_at=expires_at,
                is_active=True
            )
            session.add(ban_record)
            await session.commit()
            
            # Create response embed
            embed = create_embed(
                title=_("User Banned", guild_data.language),
                description=_("A user has been banned from the server", guild_data.language),
                color=disnake.Color.dark_red()
            )
            embed.add_field(
                name=_("User", guild_data.language),
                value=f"{user.mention} ({user.name}#{user.discriminator})",
                inline=False
            )
            embed.add_field(
                name=_("Reason", guild_data.language),
                value=reason,
                inline=False
            )
            if expires_at:
                embed.add_field(
                    name=_("Duration", guild_data.language),
                    value=_("Until {date}", guild_data.language).format(
                        date=expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                    ),
                    inline=False
                )
            embed.add_field(
                name=_("Moderator", guild_data.language),
                value=f"{interaction.author.mention}",
                inline=False
            )
            embed.set_footer(text=f"User ID: {user.id}")
            embed.timestamp = datetime.datetime.utcnow()
            
            # Try to DM the user
            try:
                user_embed = create_embed(
                    title=_("You've Been Banned", guild_data.language),
                    description=_("You have been banned from {guild}", guild_data.language).format(
                        guild=interaction.guild.name
                    ),
                    color=disnake.Color.dark_red()
                )
                user_embed.add_field(
                    name=_("Reason", guild_data.language),
                    value=reason,
                    inline=False
                )
                if expires_at:
                    user_embed.add_field(
                        name=_("Duration", guild_data.language),
                        value=_("Until {date}", guild_data.language).format(
                            date=expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                        ),
                        inline=False
                    )
                user_embed.timestamp = datetime.datetime.utcnow()
                
                await user.send(embed=user_embed)
            except Exception:
                # User might have DMs disabled
                pass
            
            # Ban the user
            await interaction.guild.ban(
                user,
                reason=f"{interaction.author}: {reason}",
                delete_message_days=delete_days
            )
            
            # Send response
            await interaction.response.send_message(embed=embed)
            
            # Log ban to mod channel if configured
            if guild_data.log_channel_id:
                log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                if log_channel:
                    await log_channel.send(embed=embed)
    
    @commands.slash_command(name="unban")
    @commands.guild_only()
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        user_id: str,
        reason: str = "No reason provided"
    ):
        """
        Unban a user from the server
        
        Parameters
        ----------
        user_id: The ID of the user to unban
        reason: Reason for the unban
        """
        try:
            user_id = int(user_id)
        except ValueError:
            embed = create_embed(
                title=_("Error", "en"),
                description=_("Invalid user ID. Please provide a valid ID.", "en"),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Update ban records
            ban_query = select(Ban).where(
                Ban.user_id == user_id,
                Ban.guild_id == interaction.guild.id,
                Ban.is_active == True
            )
            ban_result = await session.execute(ban_query)
            ban_record = ban_result.scalars().first()
            
            if ban_record:
                ban_record.is_active = False
                await session.commit()
            
        # Try to unban the user
        try:
            user = await self.bot.fetch_user(user_id)
            await interaction.guild.unban(user, reason=f"{interaction.author}: {reason}")
            
            # Create response embed
            embed = create_embed(
                title=_("User Unbanned", guild_data.language),
                description=_("A user has been unbanned from the server", guild_data.language),
                color=disnake.Color.green()
            )
            embed.add_field(
                name=_("User", guild_data.language),
                value=f"{user.mention} ({user.name}#{user.discriminator})",
                inline=False
            )
            embed.add_field(
                name=_("Reason", guild_data.language),
                value=reason,
                inline=False
            )
            embed.add_field(
                name=_("Moderator", guild_data.language),
                value=f"{interaction.author.mention}",
                inline=False
            )
            embed.set_footer(text=f"User ID: {user.id}")
            embed.timestamp = datetime.datetime.utcnow()
            
            # Send response
            await interaction.response.send_message(embed=embed)
            
            # Log unban to mod channel if configured
            if guild_data.log_channel_id:
                log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                if log_channel:
                    await log_channel.send(embed=embed)
                    
        except disnake.NotFound:
            embed = create_embed(
                title=_("Error", guild_data.language),
                description=_("User not found. Please check the ID.", guild_data.language),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except disnake.Forbidden:
            embed = create_embed(
                title=_("Error", guild_data.language),
                description=_("I don't have permission to unban users.", guild_data.language),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error unbanning user {user_id}: {e}")
            embed = create_embed(
                title=_("Error", guild_data.language),
                description=_("An error occurred while unbanning the user.", guild_data.language),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(name="mute")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def mute(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        member: disnake.Member,
        duration: str,
        reason: str = "No reason provided"
    ):
        """
        Mute a member in the server
        
        Parameters
        ----------
        member: The member to mute
        duration: Duration of the mute (e.g. 10m, 1h, 1d, 1w)
        reason: Reason for the mute
        """
        # Check if user can be muted
        if member.top_role >= interaction.author.top_role and interaction.author.id != interaction.guild.owner_id:
            embed = create_embed(
                title=_("Error", "en"),
                description=_("You cannot mute someone with a higher or equal role.", "en"),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if member.top_role >= interaction.guild.me.top_role:
            embed = create_embed(
                title=_("Error", "en"),
                description=_("I cannot mute someone with a higher role than me.", "en"),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Parse duration
        try:
            time_unit = duration[-1].lower()
            time_val = int(duration[:-1])
            
            if time_unit == 's':
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(seconds=time_val)
                duration_text = f"{time_val} seconds"
            elif time_unit == 'm':
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=time_val)
                duration_text = f"{time_val} minutes"
            elif time_unit == 'h':
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(hours=time_val)
                duration_text = f"{time_val} hours"
            elif time_unit == 'd':
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=time_val)
                duration_text = f"{time_val} days"
            elif time_unit == 'w':
                expires_at = datetime.datetime.utcnow() + datetime.timedelta(weeks=time_val)
                duration_text = f"{time_val} weeks"
            else:
                embed = create_embed(
                    title=_("Error", "en"),
                    description=_("Invalid duration format. Use format like 30s, 10m, 1h, 1d, 1w.", "en"),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        except (ValueError, IndexError):
            embed = create_embed(
                title=_("Error", "en"),
                description=_("Invalid duration format. Use format like 30s, 10m, 1h, 1d, 1w.", "en"),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get guild data and mute role
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Check mute role
            mute_role = None
            if guild_data.mute_role_id:
                mute_role = interaction.guild.get_role(guild_data.mute_role_id)
            
            # Create mute role if it doesn't exist
            if not mute_role:
                # Try to create the mute role
                await interaction.response.defer()
                try:
                    mute_role = await interaction.guild.create_role(
                        name="Muted",
                        reason="Created mute role for moderation"
                    )
                    
                    # Set permissions for all channels
                    for channel in interaction.guild.channels:
                        try:
                            if isinstance(channel, disnake.TextChannel):
                                await channel.set_permissions(
                                    mute_role,
                                    send_messages=False,
                                    add_reactions=False
                                )
                            elif isinstance(channel, disnake.VoiceChannel):
                                await channel.set_permissions(
                                    mute_role,
                                    speak=False
                                )
                        except Exception as e:
                            self.logger.error(f"Error setting permissions for channel {channel.name}: {e}")
                    
                    # Update the mute role ID in database
                    guild_data.mute_role_id = mute_role.id
                    await session.commit()
                    
                except Exception as e:
                    self.logger.error(f"Error creating mute role: {e}")
                    embed = create_embed(
                        title=_("Error", guild_data.language),
                        description=_("Could not create mute role. Please make sure I have the necessary permissions.", guild_data.language),
                        color=disnake.Color.red()
                    )
                    await interaction.edit_original_message(embed=embed)
                    return
            
            # Check if member exists in database
            member_query = select(Member).where(
                Member.id == member.id,
                Member.guild_id == interaction.guild.id
            )
            member_result = await session.execute(member_query)
            member_data = member_result.scalars().first()
            
            if not member_data:
                # Create member data if it doesn't exist
                member_data = Member(
                    id=member.id,
                    guild_id=interaction.guild.id,
                    username=f"{member.name}#{member.discriminator}"
                )
                session.add(member_data)
                await session.commit()
            
            # Create mute record
            mute_record = Mute(
                guild_id=interaction.guild.id,
                user_id=member.id,
                moderator_id=interaction.author.id,
                reason=reason,
                expires_at=expires_at,
                is_active=True
            )
            session.add(mute_record)
            await session.commit()
            
            # Mute the member
            try:
                await member.add_roles(mute_role, reason=f"{interaction.author}: {reason}")
                
                # Create response embed
                embed = create_embed(
                    title=_("User Muted", guild_data.language),
                    description=_("A user has been muted in the server", guild_data.language),
                    color=disnake.Color.orange()
                )
                embed.add_field(
                    name=_("User", guild_data.language),
                    value=f"{member.mention} ({member.name}#{member.discriminator})",
                    inline=False
                )
                embed.add_field(
                    name=_("Duration", guild_data.language),
                    value=duration_text,
                    inline=False
                )
                embed.add_field(
                    name=_("Expires", guild_data.language),
                    value=expires_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                    inline=False
                )
                embed.add_field(
                    name=_("Reason", guild_data.language),
                    value=reason,
                    inline=False
                )
                embed.add_field(
                    name=_("Moderator", guild_data.language),
                    value=f"{interaction.author.mention}",
                    inline=False
                )
                embed.set_footer(text=f"User ID: {member.id} | Mute ID: {mute_record.id}")
                embed.timestamp = datetime.datetime.utcnow()
                
                # Try to DM the user
                try:
                    user_embed = create_embed(
                        title=_("You've Been Muted", guild_data.language),
                        description=_("You have been muted in {guild}", guild_data.language).format(
                            guild=interaction.guild.name
                        ),
                        color=disnake.Color.orange()
                    )
                    user_embed.add_field(
                        name=_("Duration", guild_data.language),
                        value=duration_text,
                        inline=False
                    )
                    user_embed.add_field(
                        name=_("Expires", guild_data.language),
                        value=expires_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                        inline=False
                    )
                    user_embed.add_field(
                        name=_("Reason", guild_data.language),
                        value=reason,
                        inline=False
                    )
                    user_embed.timestamp = datetime.datetime.utcnow()
                    
                    await member.send(embed=user_embed)
                except Exception:
                    # User might have DMs disabled
                    pass
                
                # Send or edit response
                if interaction.response.is_done():
                    await interaction.edit_original_message(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed)
                
                # Log mute to mod channel if configured
                if guild_data.log_channel_id:
                    log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                    if log_channel:
                        await log_channel.send(embed=embed)
                        
            except Exception as e:
                self.logger.error(f"Error muting user {member.id}: {e}")
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("An error occurred while muting the user.", guild_data.language),
                    color=disnake.Color.red()
                )
                # Send or edit response
                if interaction.response.is_done():
                    await interaction.edit_original_message(embed=embed)
                else:
                    await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(name="unmute")
    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unmute(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        member: disnake.Member,
        reason: str = "No reason provided"
    ):
        """
        Unmute a member in the server
        
        Parameters
        ----------
        member: The member to unmute
        reason: Reason for the unmute
        """
        # Get guild data and mute role
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Check mute role
            if not guild_data.mute_role_id:
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("Mute role not configured. Please set up the mute role first.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            mute_role = interaction.guild.get_role(guild_data.mute_role_id)
            if not mute_role:
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("Mute role not found. It may have been deleted.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Check if member is muted
            if mute_role not in member.roles:
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("This user is not muted.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Update mute records
            mute_query = select(Mute).where(
                Mute.user_id == member.id,
                Mute.guild_id == interaction.guild.id,
                Mute.is_active == True
            )
            mute_result = await session.execute(mute_query)
            mute_records = mute_result.scalars().all()
            
            for mute in mute_records:
                mute.is_active = False
            await session.commit()
            
            # Unmute the member
            try:
                await member.remove_roles(mute_role, reason=f"{interaction.author}: {reason}")
                
                # Create response embed
                embed = create_embed(
                    title=_("User Unmuted", guild_data.language),
                    description=_("A user has been unmuted in the server", guild_data.language),
                    color=disnake.Color.green()
                )
                embed.add_field(
                    name=_("User", guild_data.language),
                    value=f"{member.mention} ({member.name}#{member.discriminator})",
                    inline=False
                )
                embed.add_field(
                    name=_("Reason", guild_data.language),
                    value=reason,
                    inline=False
                )
                embed.add_field(
                    name=_("Moderator", guild_data.language),
                    value=f"{interaction.author.mention}",
                    inline=False
                )
                embed.set_footer(text=f"User ID: {member.id}")
                embed.timestamp = datetime.datetime.utcnow()
                
                # Try to DM the user
                try:
                    user_embed = create_embed(
                        title=_("You've Been Unmuted", guild_data.language),
                        description=_("You have been unmuted in {guild}", guild_data.language).format(
                            guild=interaction.guild.name
                        ),
                        color=disnake.Color.green()
                    )
                    user_embed.add_field(
                        name=_("Reason", guild_data.language),
                        value=reason,
                        inline=False
                    )
                    user_embed.timestamp = datetime.datetime.utcnow()
                    
                    await member.send(embed=user_embed)
                except Exception:
                    # User might have DMs disabled
                    pass
                
                # Send response
                await interaction.response.send_message(embed=embed)
                
                # Log unmute to mod channel if configured
                if guild_data.log_channel_id:
                    log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                    if log_channel:
                        await log_channel.send(embed=embed)
                        
            except Exception as e:
                self.logger.error(f"Error unmuting user {member.id}: {e}")
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("An error occurred while unmuting the user.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(name="purge")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        amount: int = commands.Param(min_value=1, max_value=100),
        user: disnake.User = None
    ):
        """
        Delete multiple messages from a channel
        
        Parameters
        ----------
        amount: Number of messages to delete (1-100)
        user: Optional - only delete messages from this user
        """
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Defer the response
            await interaction.response.defer(ephemeral=True)
            
            # Delete messages
            try:
                if user:
                    # Delete only messages from specific user
                    def check(msg):
                        return msg.author.id == user.id
                    
                    deleted = await interaction.channel.purge(limit=amount, check=check)
                    count = len(deleted)
                    
                    embed = create_embed(
                        title=_("Messages Purged", guild_data.language),
                        description=_(
                            "Deleted {count} messages from {user} in {channel}",
                            guild_data.language
                        ).format(
                            count=count,
                            user=f"{user.mention} ({user.name}#{user.discriminator})",
                            channel=interaction.channel.mention
                        ),
                        color=disnake.Color.blue()
                    )
                else:
                    # Delete any messages
                    deleted = await interaction.channel.purge(limit=amount)
                    count = len(deleted)
                    
                    embed = create_embed(
                        title=_("Messages Purged", guild_data.language),
                        description=_(
                            "Deleted {count} messages in {channel}",
                            guild_data.language
                        ).format(
                            count=count,
                            channel=interaction.channel.mention
                        ),
                        color=disnake.Color.blue()
                    )
                
                embed.add_field(
                    name=_("Moderator", guild_data.language),
                    value=f"{interaction.author.mention}",
                    inline=False
                )
                embed.timestamp = datetime.datetime.utcnow()
                
                await interaction.edit_original_message(embed=embed)
                
                # Log purge to mod channel if configured
                if guild_data.log_channel_id:
                    log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                    if log_channel and log_channel.id != interaction.channel.id:  # Don't log to the same channel
                        await log_channel.send(embed=embed)
                        
            except Exception as e:
                self.logger.error(f"Error purging messages: {e}")
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("An error occurred while purging messages.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.edit_original_message(embed=embed)
    
    @commands.slash_command(name="slowmode")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def slowmode(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        seconds: int = commands.Param(min_value=0, max_value=21600),
        channel: disnake.TextChannel = None
    ):
        """
        Set slowmode for a channel
        
        Parameters
        ----------
        seconds: Cooldown between messages (0-21600, 0 to disable)
        channel: Channel to set slowmode for (current channel if not specified)
        """
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Set the channel to the current channel if not specified
            if not channel:
                channel = interaction.channel
            
            # Set slowmode
            try:
                await channel.edit(slowmode_delay=seconds)
                
                if seconds == 0:
                    embed = create_embed(
                        title=_("Slowmode Disabled", guild_data.language),
                        description=_(
                            "Slowmode has been disabled in {channel}",
                            guild_data.language
                        ).format(
                            channel=channel.mention
                        ),
                        color=disnake.Color.green()
                    )
                else:
                    # Format duration for display
                    if seconds < 60:
                        duration = _("{seconds} seconds", guild_data.language).format(seconds=seconds)
                    elif seconds < 3600:
                        minutes = seconds // 60
                        duration = _("{minutes} minutes", guild_data.language).format(minutes=minutes)
                    else:
                        hours = seconds // 3600
                        duration = _("{hours} hours", guild_data.language).format(hours=hours)
                    
                    embed = create_embed(
                        title=_("Slowmode Enabled", guild_data.language),
                        description=_(
                            "Slowmode of {duration} has been set in {channel}",
                            guild_data.language
                        ).format(
                            duration=duration,
                            channel=channel.mention
                        ),
                        color=disnake.Color.orange()
                    )
                
                embed.add_field(
                    name=_("Moderator", guild_data.language),
                    value=f"{interaction.author.mention}",
                    inline=False
                )
                embed.timestamp = datetime.datetime.utcnow()
                
                await interaction.response.send_message(embed=embed)
                
                # Log slowmode change to mod channel if configured
                if guild_data.log_channel_id:
                    log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                    if log_channel and log_channel.id != channel.id:  # Don't log to the same channel
                        await log_channel.send(embed=embed)
                        
            except Exception as e:
                self.logger.error(f"Error setting slowmode: {e}")
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("An error occurred while setting slowmode.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(name="lock")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = None,
        reason: str = "No reason provided"
    ):
        """
        Lock a channel to prevent new messages
        
        Parameters
        ----------
        channel: Channel to lock (current channel if not specified)
        reason: Reason for locking the channel
        """
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Set the channel to the current channel if not specified
            if not channel:
                channel = interaction.channel
            
            # Lock the channel
            try:
                # Update permission overwrites to prevent @everyone from sending messages
                await channel.set_permissions(
                    interaction.guild.default_role,
                    send_messages=False,
                    reason=f"{interaction.author}: {reason}"
                )
                
                embed = create_embed(
                    title=_("Channel Locked", guild_data.language),
                    description=_(
                        "{channel} has been locked",
                        guild_data.language
                    ).format(
                        channel=channel.mention
                    ),
                    color=disnake.Color.red()
                )
                embed.add_field(
                    name=_("Reason", guild_data.language),
                    value=reason,
                    inline=False
                )
                embed.add_field(
                    name=_("Moderator", guild_data.language),
                    value=f"{interaction.author.mention}",
                    inline=False
                )
                embed.timestamp = datetime.datetime.utcnow()
                
                await interaction.response.send_message(embed=embed)
                
                # Also send the embed to the locked channel if it's different
                if channel.id != interaction.channel.id:
                    await channel.send(embed=embed)
                
                # Log lock to mod channel if configured
                if guild_data.log_channel_id:
                    log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                    if log_channel and log_channel.id != channel.id:  # Don't log to the same channel
                        await log_channel.send(embed=embed)
                        
            except Exception as e:
                self.logger.error(f"Error locking channel: {e}")
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("An error occurred while locking the channel.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @commands.slash_command(name="unlock")
    @commands.guild_only()
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = None,
        reason: str = "No reason provided"
    ):
        """
        Unlock a channel to allow new messages
        
        Parameters
        ----------
        channel: Channel to unlock (current channel if not specified)
        reason: Reason for unlocking the channel
        """
        # Get guild data
        async with get_session() as session:
            guild_query = select(Guild).where(Guild.id == interaction.guild.id)
            guild_result = await session.execute(guild_query)
            guild_data = guild_result.scalars().first()
            
            if not guild_data:
                # Create guild data if it doesn't exist
                guild_data = Guild(
                    id=interaction.guild.id,
                    name=interaction.guild.name,
                    language="en"  # Default language
                )
                session.add(guild_data)
                await session.commit()
            
            # Set the channel to the current channel if not specified
            if not channel:
                channel = interaction.channel
            
            # Unlock the channel
            try:
                # Update permission overwrites to allow @everyone to send messages
                await channel.set_permissions(
                    interaction.guild.default_role,
                    send_messages=None,  # Reset to default
                    reason=f"{interaction.author}: {reason}"
                )
                
                embed = create_embed(
                    title=_("Channel Unlocked", guild_data.language),
                    description=_(
                        "{channel} has been unlocked",
                        guild_data.language
                    ).format(
                        channel=channel.mention
                    ),
                    color=disnake.Color.green()
                )
                embed.add_field(
                    name=_("Reason", guild_data.language),
                    value=reason,
                    inline=False
                )
                embed.add_field(
                    name=_("Moderator", guild_data.language),
                    value=f"{interaction.author.mention}",
                    inline=False
                )
                embed.timestamp = datetime.datetime.utcnow()
                
                await interaction.response.send_message(embed=embed)
                
                # Also send the embed to the unlocked channel if it's different
                if channel.id != interaction.channel.id:
                    await channel.send(embed=embed)
                
                # Log unlock to mod channel if configured
                if guild_data.log_channel_id:
                    log_channel = interaction.guild.get_channel(guild_data.log_channel_id)
                    if log_channel and log_channel.id != channel.id:  # Don't log to the same channel
                        await log_channel.send(embed=embed)
                        
            except Exception as e:
                self.logger.error(f"Error unlocking channel: {e}")
                embed = create_embed(
                    title=_("Error", guild_data.language),
                    description=_("An error occurred while unlocking the channel.", guild_data.language),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)

def setup(bot):
    """Setup function for the moderation cog"""
    bot.add_cog(Moderation(bot))
