#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Music commands for Discord bot.
Includes features for playing music from YouTube, SoundCloud, and Spotify.
"""

import disnake
from disnake.ext import commands
import asyncio
import datetime
import logging
import re
import random
from typing import Optional
from sqlalchemy.future import select
import wavelink
from wavelink.ext import spotify

from bot.utils.embed_creator import create_embed
from bot.utils.localization import _
from bot.utils.db_manager import get_session, get_guild_language
from bot.models import CommandUsage, MusicSession

class Music(commands.Cog):
    """Music commands for playing audio in voice channels"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.music')
        self.wavelink = None
        # Active music sessions
        self.sessions = {}
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        try:
            # Initialize wavelink nodes for music playback
            await self.setup_wavelink()
            self.logger.info("Music cog initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Wavelink: {e}")
    
    async def setup_wavelink(self):
        """Set up the Wavelink connection"""
        # Get configuration
        lavalink_host = self.bot.config.get("music", {}).get("lavalink_host", "127.0.0.1")
        lavalink_port = self.bot.config.get("music", {}).get("lavalink_port", 2333)
        lavalink_pass = self.bot.config.get("music", {}).get("lavalink_password", "youshallnotpass")
        spotify_client = self.bot.config.get("api_keys", {}).get("spotify_client_id", "")
        spotify_secret = self.bot.config.get("api_keys", {}).get("spotify_client_secret", "")
        
        # Initialize Wavelink client
        await wavelink.NodePool.create_node(
            bot=self.bot,
            host=lavalink_host,
            port=lavalink_port,
            password=lavalink_pass,
            spotify_client=spotify_client,
            spotify_secret=spotify_secret
        )
    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Event fired when a wavelink node is ready"""
        self.logger.info(f"Wavelink node '{node.identifier}' is ready!")
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, player: wavelink.Player, track: wavelink.Track, reason):
        """Event fired when a track ends"""
        guild_id = player.guild.id
        
        # Skip to the next track if available
        if guild_id in self.sessions and not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)
            
            # Update now playing message if available
            if 'now_playing_message' in self.sessions[guild_id]:
                try:
                    lang = await get_guild_language(guild_id)
                    embed = self.create_now_playing_embed(next_track, lang)
                    await self.sessions[guild_id]['now_playing_message'].edit(embed=embed)
                    self.sessions[guild_id]['current_track'] = next_track
                except Exception as e:
                    self.logger.error(f"Failed to update now playing message: {e}")
            
            # Update track count in database
            await self.increment_songs_played(guild_id)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Event fired when a voice state changes"""
        if member.id != self.bot.user.id:
            return
        
        # Bot disconnected from voice
        if before.channel and not after.channel:
            guild_id = before.channel.guild.id
            
            # Clean up music session when bot leaves voice
            if guild_id in self.sessions:
                # Mark session as ended in database
                await self.end_music_session(guild_id)
                
                # Clean up session data
                if 'now_playing_message' in self.sessions[guild_id]:
                    try:
                        await self.sessions[guild_id]['now_playing_message'].delete()
                    except:
                        pass
                
                del self.sessions[guild_id]
                self.logger.info(f"Music session ended in guild {guild_id}")
    
    async def ensure_voice(self, interaction: disnake.ApplicationCommandInteraction):
        """
        Ensure the bot and user are in a voice channel.
        
        Args:
            interaction: The command interaction
        
        Returns:
            player: The wavelink player or None if error
            error_embed: Error embed or None if no error
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Check if user is in a voice channel
        if not interaction.author.voice or not interaction.author.voice.channel:
            embed = create_embed(
                title=_("Error", lang),
                description=_("You must be in a voice channel to use this command.", lang),
                color=disnake.Color.red()
            )
            return None, embed
        
        # Get or create the wavelink player
        player = wavelink.NodePool.get_node().get_player(interaction.guild)
        
        if not player:
            # Create a new player and connect to the voice channel
            player = await interaction.author.voice.channel.connect(cls=wavelink.Player)
            
            # Create a new session
            self.sessions[interaction.guild.id] = {
                'channel_id': interaction.channel.id,
                'voice_channel_id': interaction.author.voice.channel.id
            }
            
            # Create music session in database
            await self.start_music_session(interaction.guild.id)
        elif not player.is_connected():
            # Reconnect if not connected
            await interaction.author.voice.channel.connect(cls=wavelink.Player)
        elif player.channel.id != interaction.author.voice.channel.id:
            # Check if user is in the same voice channel
            embed = create_embed(
                title=_("Error", lang),
                description=_("You must be in the same voice channel as the bot to use this command.", lang),
                color=disnake.Color.red()
            )
            return None, embed
        
        return player, None
    
    @commands.slash_command(name="play")
    @commands.guild_only()
    async def play(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        query: str
    ):
        """
        Play music from YouTube, Spotify, or SoundCloud
        
        Parameters
        ----------
        query: Song name or URL to play
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Defer the response due to potential API calls
        await interaction.response.defer()
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.edit_original_message(embed=error_embed)
            return
        
        # Search for the track
        try:
            # Check if query is a URL
            if re.match(r'https?://', query):
                # Handle Spotify links
                if 'spotify.com' in query:
                    if 'track' in query:
                        # Single Spotify track
                        decoded = await spotify.SpotifyTrack.search(query=query, return_first=True)
                        tracks = [decoded]
                    elif 'playlist' in query or 'album' in query:
                        # Spotify playlist or album
                        async for partial in spotify.SpotifyTrack.iterator(query=query):
                            if player.queue.is_empty and not player.is_playing():
                                # Play first track immediately
                                await player.play(partial)
                                self.sessions[interaction.guild.id]['current_track'] = partial
                                
                                # Create now playing message
                                embed = self.create_now_playing_embed(partial, lang)
                                now_playing_message = await interaction.edit_original_message(embed=embed)
                                self.sessions[interaction.guild.id]['now_playing_message'] = now_playing_message
                            else:
                                # Add the rest to queue
                                player.queue.put(partial)
                        
                        # Create response embed for playlist
                        embed = create_embed(
                            title=_("Playlist Added", lang),
                            description=_("Added Spotify playlist to the queue", lang),
                            color=disnake.Color.green()
                        )
                        
                        if 'now_playing_message' not in self.sessions[interaction.guild.id]:
                            await interaction.edit_original_message(embed=embed)
                        else:
                            await interaction.followup.send(embed=embed, ephemeral=True)
                        
                        # Log command usage
                        await self.log_command(interaction.author.id, interaction.guild.id, "play_spotify_playlist")
                        return
                    else:
                        raise ValueError("Unsupported Spotify URL")
                else:
                    # YouTube, SoundCloud, or other URL
                    tracks = await wavelink.NodePool.get_node().get_tracks(cls=wavelink.Track, query=query)
                    if not tracks:
                        raise ValueError("No tracks found")
            else:
                # Search query on YouTube
                tracks = await wavelink.YouTubeTrack.search(query)
                if not tracks:
                    raise ValueError("No tracks found")
        
        except Exception as e:
            self.logger.error(f"Error searching for track: {e}")
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not find tracks for your query. Please try a different search or URL.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
            return
        
        # Handle the track(s)
        if isinstance(tracks, list) and len(tracks) > 0:
            track = tracks[0]  # Take the first result
            
            if player.is_playing() or not player.queue.is_empty:
                # Add to queue if already playing
                player.queue.put(track)
                
                embed = create_embed(
                    title=_("Added to Queue", lang),
                    description=_("**{title}** has been added to the queue", lang).format(title=track.title),
                    color=disnake.Color.green()
                )
                embed.add_field(
                    name=_("Duration", lang),
                    value=self.format_duration(track.duration),
                    inline=True
                )
                embed.add_field(
                    name=_("Position", lang),
                    value=str(player.queue.count),
                    inline=True
                )
                if hasattr(track, 'thumbnail') and track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
                
                await interaction.edit_original_message(embed=embed)
            else:
                # Play immediately if not playing
                await player.play(track)
                self.sessions[interaction.guild.id]['current_track'] = track
                
                # Create now playing embed
                embed = self.create_now_playing_embed(track, lang)
                now_playing_message = await interaction.edit_original_message(embed=embed)
                self.sessions[interaction.guild.id]['now_playing_message'] = now_playing_message
        else:
            # No tracks found
            embed = create_embed(
                title=_("Error", lang),
                description=_("No tracks found for your query.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
            return
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "play")
    
    @commands.slash_command(name="skip")
    @commands.guild_only()
    async def skip(self, interaction: disnake.ApplicationCommandInteraction):
        """Skip the current song"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Check if anything is playing
        if not player.is_playing():
            embed = create_embed(
                title=_("Error", lang),
                description=_("Nothing is currently playing.", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get the current track before skipping
        current_track = self.sessions[interaction.guild.id].get('current_track')
        
        if player.queue.is_empty:
            # Nothing to skip to, stop playback
            await player.stop()
            
            embed = create_embed(
                title=_("Skipped", lang),
                description=_("Skipped the current song. No more songs in queue.", lang),
                color=disnake.Color.blue()
            )
            
            # Delete now playing message if it exists
            if 'now_playing_message' in self.sessions[interaction.guild.id]:
                try:
                    await self.sessions[interaction.guild.id]['now_playing_message'].delete()
                    self.sessions[interaction.guild.id].pop('now_playing_message')
                except:
                    pass
        else:
            # Skip to next track
            next_track = player.queue.get()
            await player.play(next_track)
            self.sessions[interaction.guild.id]['current_track'] = next_track
            
            embed = create_embed(
                title=_("Skipped", lang),
                description=_("Skipped **{title}**", lang).format(
                    title=current_track.title if current_track else "Current song"
                ),
                color=disnake.Color.blue()
            )
            
            # Update now playing message if it exists
            if 'now_playing_message' in self.sessions[interaction.guild.id]:
                try:
                    new_embed = self.create_now_playing_embed(next_track, lang)
                    await self.sessions[interaction.guild.id]['now_playing_message'].edit(embed=new_embed)
                except Exception as e:
                    self.logger.error(f"Failed to update now playing message: {e}")
        
        await interaction.response.send_message(embed=embed)
        
        # Increment songs played counter
        await self.increment_songs_played(interaction.guild.id)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "skip")
    
    @commands.slash_command(name="queue")
    @commands.guild_only()
    async def queue(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        page: int = 1
    ):
        """
        Show the current music queue
        
        Parameters
        ----------
        page: Page number to view
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Check if anything is playing
        if not player.is_playing() and player.queue.is_empty:
            embed = create_embed(
                title=_("Queue", lang),
                description=_("The queue is empty.", lang),
                color=disnake.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Calculate pages
        items_per_page = 10
        queue_list = list(player.queue)
        total_pages = max(1, (len(queue_list) + items_per_page - 1) // items_per_page)
        
        # Validate page number
        page = max(1, min(page, total_pages))
        
        # Create embed
        embed = create_embed(
            title=_("Music Queue", lang),
            color=disnake.Color.blue()
        )
        
        # Add currently playing track
        current_track = self.sessions[interaction.guild.id].get('current_track')
        if current_track:
            embed.add_field(
                name=_("Now Playing", lang),
                value=f"**{current_track.title}** ({self.format_duration(current_track.duration)})",
                inline=False
            )
        
        # Add queue tracks for this page
        if queue_list:
            start_idx = (page - 1) * items_per_page
            end_idx = min(start_idx + items_per_page, len(queue_list))
            
            queue_text = ""
            for i, track in enumerate(queue_list[start_idx:end_idx], start=start_idx + 1):
                queue_text += f"**{i}.** {track.title} ({self.format_duration(track.duration)})\n"
            
            embed.add_field(
                name=_("Upcoming Songs", lang),
                value=queue_text or _("No upcoming songs in queue.", lang),
                inline=False
            )
        else:
            embed.add_field(
                name=_("Upcoming Songs", lang),
                value=_("No upcoming songs in queue.", lang),
                inline=False
            )
        
        # Add queue stats
        total_duration = sum(track.duration for track in queue_list)
        if current_track:
            total_duration += current_track.duration
        
        embed.add_field(
            name=_("Queue Info", lang),
            value=_(
                "**{count}** songs in queue | Total duration: **{duration}**",
                lang
            ).format(
                count=len(queue_list) + (1 if current_track else 0),
                duration=self.format_duration(total_duration)
            ),
            inline=False
        )
        
        # Add pagination info
        if total_pages > 1:
            embed.set_footer(text=_("Page {current}/{total}", lang).format(current=page, total=total_pages))
        
        # Create pagination buttons if needed
        components = None
        if total_pages > 1:
            components = disnake.ui.ActionRow()
            
            # Previous page button
            prev_button = disnake.ui.Button(
                style=disnake.ButtonStyle.primary,
                label=_("Previous", lang),
                emoji="⬅️",
                custom_id=f"queue_prev_{page}",
                disabled=(page == 1)
            )
            components.append_item(prev_button)
            
            # Next page button
            next_button = disnake.ui.Button(
                style=disnake.ButtonStyle.primary,
                label=_("Next", lang),
                emoji="➡️",
                custom_id=f"queue_next_{page}",
                disabled=(page == total_pages)
            )
            components.append_item(next_button)
        
        # Send response with pagination
        await interaction.response.send_message(embed=embed, components=components)
        
        # Handle pagination interactions
        if components:
            try:
                button_interaction = await self.bot.wait_for(
                    "button_click",
                    check=lambda i: (
                        i.user.id == interaction.user.id and
                        i.message.id == (await interaction.original_message()).id and
                        i.component.custom_id.startswith(("queue_prev_", "queue_next_"))
                    ),
                    timeout=60.0
                )
                
                # Determine new page
                if button_interaction.component.custom_id.startswith("queue_prev_"):
                    new_page = page - 1
                else:
                    new_page = page + 1
                
                # Recursively call queue command with new page
                await button_interaction.response.defer()
                await self.queue(button_interaction, new_page)
                
            except asyncio.TimeoutError:
                # Disable buttons after timeout
                for component in components.children:
                    component.disabled = True
                
                try:
                    await interaction.edit_original_message(components=components)
                except:
                    pass
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "queue")
    
    @commands.slash_command(name="pause")
    @commands.guild_only()
    async def pause(self, interaction: disnake.ApplicationCommandInteraction):
        """Pause the current song"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Check if anything is playing
        if not player.is_playing():
            embed = create_embed(
                title=_("Error", lang),
                description=_("Nothing is currently playing.", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if already paused
        if player.is_paused():
            embed = create_embed(
                title=_("Already Paused", lang),
                description=_("The player is already paused. Use `/resume` to continue playback.", lang),
                color=disnake.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Pause playback
        await player.pause()
        
        embed = create_embed(
            title=_("Paused", lang),
            description=_("Playback has been paused. Use `/resume` to continue.", lang),
            color=disnake.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "pause")
    
    @commands.slash_command(name="resume")
    @commands.guild_only()
    async def resume(self, interaction: disnake.ApplicationCommandInteraction):
        """Resume the current song"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Check if anything is playing
        if not player.is_playing():
            embed = create_embed(
                title=_("Error", lang),
                description=_("Nothing is currently playing.", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if already playing
        if not player.is_paused():
            embed = create_embed(
                title=_("Already Playing", lang),
                description=_("The player is already playing.", lang),
                color=disnake.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Resume playback
        await player.resume()
        
        embed = create_embed(
            title=_("Resumed", lang),
            description=_("Playback has been resumed.", lang),
            color=disnake.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "resume")
    
    @commands.slash_command(name="stop")
    @commands.guild_only()
    async def stop(self, interaction: disnake.ApplicationCommandInteraction):
        """Stop playing and clear the queue"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Check if anything is playing
        if not player.is_playing() and player.queue.is_empty:
            embed = create_embed(
                title=_("Error", lang),
                description=_("Nothing is currently playing.", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Clear queue and stop
        player.queue.clear()
        await player.stop()
        
        # Delete now playing message if it exists
        if interaction.guild.id in self.sessions and 'now_playing_message' in self.sessions[interaction.guild.id]:
            try:
                await self.sessions[interaction.guild.id]['now_playing_message'].delete()
                self.sessions[interaction.guild.id].pop('now_playing_message')
            except:
                pass
        
        embed = create_embed(
            title=_("Stopped", lang),
            description=_("Playback has been stopped and the queue has been cleared.", lang),
            color=disnake.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "stop")
    
    @commands.slash_command(name="volume")
    @commands.guild_only()
    async def volume(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        level: int = commands.Param(min_value=0, max_value=150)
    ):
        """
        Set the volume level
        
        Parameters
        ----------
        level: Volume level (0-150)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Set volume
        await player.set_volume(level)
        
        embed = create_embed(
            title=_("Volume Set", lang),
            description=_("Volume set to **{level}%**", lang).format(level=level),
            color=disnake.Color.blue()
        )
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "volume")
    
    @commands.slash_command(name="nowplaying")
    @commands.guild_only()
    async def nowplaying(self, interaction: disnake.ApplicationCommandInteraction):
        """Show what's currently playing"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Check if anything is playing
        if not player.is_playing():
            embed = create_embed(
                title=_("Now Playing", lang),
                description=_("Nothing is currently playing.", lang),
                color=disnake.Color.blue()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Get current track
        current_track = self.sessions[interaction.guild.id].get('current_track')
        if not current_track:
            current_track = player.track
            self.sessions[interaction.guild.id]['current_track'] = current_track
        
        # Create now playing embed
        embed = self.create_now_playing_embed(current_track, lang)
        
        # Send response
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "nowplaying")
    
    @commands.slash_command(name="shuffle")
    @commands.guild_only()
    async def shuffle(self, interaction: disnake.ApplicationCommandInteraction):
        """Shuffle the music queue"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # Check if there's anything in the queue
        if player.queue.is_empty:
            embed = create_embed(
                title=_("Error", lang),
                description=_("The queue is empty. Add some songs first.", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Shuffle the queue
        player.queue.shuffle()
        
        embed = create_embed(
            title=_("Queue Shuffled", lang),
            description=_("The music queue has been shuffled.", lang),
            color=disnake.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "shuffle")
    
    @commands.slash_command(name="disconnect")
    @commands.guild_only()
    async def disconnect(self, interaction: disnake.ApplicationCommandInteraction):
        """Disconnect the bot from voice channel"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Ensure bot and user are in voice
        player, error_embed = await self.ensure_voice(interaction)
        if error_embed:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return
        
        # End music session in database
        await self.end_music_session(interaction.guild.id)
        
        # Clear queue and disconnect
        if player:
            player.queue.clear()
            await player.stop()
            await player.disconnect()
        
        # Delete now playing message if it exists
        if interaction.guild.id in self.sessions and 'now_playing_message' in self.sessions[interaction.guild.id]:
            try:
                await self.sessions[interaction.guild.id]['now_playing_message'].delete()
            except:
                pass
        
        # Clean up session data
        if interaction.guild.id in self.sessions:
            del self.sessions[interaction.guild.id]
        
        embed = create_embed(
            title=_("Disconnected", lang),
            description=_("Disconnected from voice channel.", lang),
            color=disnake.Color.red()
        )
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "disconnect")
    
    def create_now_playing_embed(self, track, lang):
        """Create an embed for the now playing track"""
        embed = create_embed(
            title=_("Now Playing", lang),
            description=f"**{track.title}**",
            color=disnake.Color.blue()
        )
        
        # Add track info
        embed.add_field(
            name=_("Duration", lang),
            value=self.format_duration(track.duration),
            inline=True
        )
        if hasattr(track, 'author'):
            embed.add_field(
                name=_("Author", lang),
                value=track.author,
                inline=True
            )
        
        # Add source info
        source = "YouTube"
        if isinstance(track, spotify.SpotifyTrack):
            source = "Spotify"
        elif hasattr(track, 'uri') and 'soundcloud.com' in track.uri:
            source = "SoundCloud"
        
        embed.add_field(
            name=_("Source", lang),
            value=source,
            inline=True
        )
        
        # Add URL if available
        if hasattr(track, 'uri') and track.uri:
            embed.add_field(
                name=_("Link", lang),
                value=f"[{_('Click here', lang)}]({track.uri})",
                inline=True
            )
        
        # Add thumbnail if available
        if hasattr(track, 'thumbnail') and track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)
        
        return embed
    
    def format_duration(self, milliseconds):
        """Format milliseconds into a readable duration"""
        seconds = milliseconds // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    async def start_music_session(self, guild_id):
        """Record the start of a music session in the database"""
        try:
            async with get_session() as session:
                music_session = MusicSession(
                    guild_id=guild_id,
                    created_at=datetime.datetime.utcnow(),
                    songs_played=0
                )
                session.add(music_session)
                await session.commit()
                
                # Store session ID
                if guild_id in self.sessions:
                    self.sessions[guild_id]['db_session_id'] = music_session.id
                
                self.logger.info(f"Started music session {music_session.id} for guild {guild_id}")
        except Exception as e:
            self.logger.error(f"Error creating music session: {e}")
    
    async def end_music_session(self, guild_id):
        """Record the end of a music session in the database"""
        try:
            # Get session ID from memory
            session_id = None
            if guild_id in self.sessions and 'db_session_id' in self.sessions[guild_id]:
                session_id = self.sessions[guild_id]['db_session_id']
            
            if not session_id:
                return
            
            async with get_session() as session:
                # Get the music session
                query = select(MusicSession).where(MusicSession.id == session_id)
                result = await session.execute(query)
                music_session = result.scalar_one_or_none()
                
                if music_session:
                    music_session.ended_at = datetime.datetime.utcnow()
                    await session.commit()
                    self.logger.info(f"Ended music session {session_id} for guild {guild_id}")
        except Exception as e:
            self.logger.error(f"Error ending music session: {e}")
    
    async def increment_songs_played(self, guild_id):
        """Increment the songs played counter for the current session"""
        try:
            # Get session ID from memory
            session_id = None
            if guild_id in self.sessions and 'db_session_id' in self.sessions[guild_id]:
                session_id = self.sessions[guild_id]['db_session_id']
            
            if not session_id:
                return
            
            async with get_session() as session:
                # Get the music session
                query = select(MusicSession).where(MusicSession.id == session_id)
                result = await session.execute(query)
                music_session = result.scalar_one_or_none()
                
                if music_session:
                    music_session.songs_played += 1
                    await session.commit()
        except Exception as e:
            self.logger.error(f"Error incrementing songs played: {e}")
    
    async def log_command(self, user_id, guild_id, command_name):
        """Log command usage to the database"""
        try:
            async with get_session() as session:
                command_usage = CommandUsage(
                    guild_id=guild_id,
                    user_id=user_id,
                    command_name=command_name
                )
                session.add(command_usage)
                await session.commit()
        except Exception as e:
            self.logger.error(f"Error logging command usage: {e}")

def setup(bot):
    """Setup function for the music cog"""
    bot.add_cog(Music(bot))
