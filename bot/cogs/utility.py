#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Utility commands for Discord bot.
Includes user info, server info, weather, reminder, and other utility functions.
"""

import disnake
from disnake.ext import commands, tasks
import asyncio
import datetime
import time
import pytz
import re
import random
import logging
from typing import Optional
from sqlalchemy.future import select

from bot.utils.embed_creator import create_embed
from bot.utils.localization import _
from bot.utils.db_manager import get_session, get_guild_language
from bot.utils.api_wrapper import get_api
from bot.models import Guild, Member, CommandUsage

class Utility(commands.Cog):
    """Utility commands for server and user information"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.utility')
        self.reminders = []
        self.reminder_task.start()
    
    def cog_unload(self):
        self.reminder_task.cancel()
    
    @tasks.loop(seconds=30)
    async def reminder_task(self):
        """Check for reminders that are due"""
        now = datetime.datetime.utcnow().timestamp()
        due_reminders = [r for r in self.reminders if r['due_time'] <= now]
        
        for reminder in due_reminders:
            self.reminders.remove(reminder)
            
            try:
                # Get the user
                user = await self.bot.fetch_user(reminder['user_id'])
                if not user:
                    continue
                
                # Create embed
                embed = create_embed(
                    title=_("Reminder", reminder['language']),
                    description=_("You asked me to remind you about:", reminder['language']),
                    color=disnake.Color.blue()
                )
                embed.add_field(
                    name=_("Message", reminder['language']),
                    value=reminder['message'],
                    inline=False
                )
                embed.add_field(
                    name=_("Set", reminder['language']),
                    value=f"<t:{int(reminder['set_time'])}:R>",
                    inline=True
                )
                
                # Try to send DM
                try:
                    await user.send(embed=embed)
                except Exception:
                    # If DM fails, try to send to the original channel
                    if reminder.get('channel_id'):
                        channel = self.bot.get_channel(reminder['channel_id'])
                        if channel:
                            await channel.send(
                                content=user.mention,
                                embed=embed
                            )
            except Exception as e:
                self.logger.error(f"Error sending reminder: {e}")
    
    @reminder_task.before_loop
    async def before_reminder_task(self):
        await self.bot.wait_until_ready()
    
    @commands.slash_command(name="ping")
    async def ping(self, interaction: disnake.ApplicationCommandInteraction):
        """Check the bot's latency"""
        start_time = time.time()
        await interaction.response.defer()
        end_time = time.time()
        
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Calculate latencies
        api_latency = (end_time - start_time) * 1000
        websocket_latency = self.bot.latency * 1000
        
        embed = create_embed(
            title=_("Pong! 🏓", lang),
            color=disnake.Color.green()
        )
        embed.add_field(
            name=_("API Latency", lang),
            value=f"{api_latency:.2f} ms",
            inline=True
        )
        embed.add_field(
            name=_("WebSocket Latency", lang),
            value=f"{websocket_latency:.2f} ms",
            inline=True
        )
        
        await interaction.edit_original_message(embed=embed)
    
    @commands.slash_command(name="userinfo")
    @commands.guild_only()
    async def userinfo(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.User = None
    ):
        """
        Display information about a user
        
        Parameters
        ----------
        user: The user to get info for (defaults to you)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Default to command user if not specified
        if not user:
            user = interaction.author
        
        # Get member object if user is in the server
        member = interaction.guild.get_member(user.id)
        
        # Create base embed
        embed = create_embed(
            title=_("User Information", lang),
            color=user.accent_color or disnake.Color.blue()
        )
        
        # Add user fields
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(
            name=_("Username", lang),
            value=str(user),
            inline=True
        )
        embed.add_field(
            name=_("User ID", lang),
            value=user.id,
            inline=True
        )
        embed.add_field(
            name=_("Account Created", lang),
            value=f"<t:{int(user.created_at.timestamp())}:F>\n<t:{int(user.created_at.timestamp())}:R>",
            inline=False
        )
        
        # Add member-specific fields if available
        if member:
            # Roles (excluding @everyone)
            roles = [role.mention for role in reversed(member.roles) if role.name != "@everyone"]
            roles_str = ", ".join(roles) if roles else _("None", lang)
            
            # Add member fields
            embed.add_field(
                name=_("Nickname", lang),
                value=member.nick or _("None", lang),
                inline=True
            )
            embed.add_field(
                name=_("Joined Server", lang),
                value=f"<t:{int(member.joined_at.timestamp())}:F>\n<t:{int(member.joined_at.timestamp())}:R>",
                inline=False
            )
            embed.add_field(
                name=_("Roles", lang) + f" [{len(roles)}]",
                value=roles_str if len(roles_str) <= 1024 else roles_str[:1020] + "...",
                inline=False
            )
        
        # Footer
        embed.set_footer(text=_("Requested by: {user}", lang).format(user=str(interaction.author)))
        
        # Send response
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "userinfo")
    
    @commands.slash_command(name="serverinfo")
    @commands.guild_only()
    async def serverinfo(self, interaction: disnake.ApplicationCommandInteraction):
        """Display information about the server"""
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        guild = interaction.guild
        
        # Count channels by type
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Count members by status
        total_members = guild.member_count
        bot_count = sum(1 for member in guild.members if member.bot)
        human_count = total_members - bot_count
        
        # Create embed
        embed = create_embed(
            title=_("Server Information", lang),
            description=guild.description,
            color=disnake.Color.blue()
        )
        
        # Add server icon
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # General information
        embed.add_field(
            name=_("Server Name", lang),
            value=guild.name,
            inline=True
        )
        embed.add_field(
            name=_("Server ID", lang),
            value=guild.id,
            inline=True
        )
        embed.add_field(
            name=_("Owner", lang),
            value=f"{guild.owner.mention} ({guild.owner})",
            inline=True
        )
        embed.add_field(
            name=_("Created On", lang),
            value=f"<t:{int(guild.created_at.timestamp())}:F>\n<t:{int(guild.created_at.timestamp())}:R>",
            inline=False
        )
        
        # Server stats
        embed.add_field(
            name=_("Members", lang),
            value=_("{total} total\n{humans} humans\n{bots} bots", lang).format(
                total=total_members,
                humans=human_count,
                bots=bot_count
            ),
            inline=True
        )
        embed.add_field(
            name=_("Channels", lang),
            value=_("{text} text\n{voice} voice\n{categories} categories", lang).format(
                text=text_channels,
                voice=voice_channels,
                categories=categories
            ),
            inline=True
        )
        embed.add_field(
            name=_("Emoji Count", lang),
            value=len(guild.emojis),
            inline=True
        )
        
        # Server features
        if guild.features:
            feature_list = "\n".join(f"• {feature.replace('_', ' ').title()}" for feature in guild.features)
            embed.add_field(
                name=_("Server Features", lang),
                value=feature_list[:1024],
                inline=False
            )
        
        # Server boost info
        boost_level = _("Level {level}", lang).format(level=guild.premium_tier)
        boost_count = guild.premium_subscription_count
        embed.add_field(
            name=_("Boost Status", lang),
            value=_("Level {level} with {count} boosts", lang).format(
                level=guild.premium_tier,
                count=boost_count
            ),
            inline=False
        )
        
        # Footer
        embed.set_footer(text=_("Requested by: {user}", lang).format(user=str(interaction.author)))
        
        # Send response
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "serverinfo")
    
    @commands.slash_command(name="avatar")
    async def avatar(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        user: disnake.User = None
    ):
        """
        Display a user's avatar
        
        Parameters
        ----------
        user: The user to get the avatar for (defaults to you)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Default to command user if not specified
        if not user:
            user = interaction.author
        
        # Create embed
        embed = create_embed(
            title=_("Avatar for {user}", lang).format(user=str(user)),
            color=user.accent_color or disnake.Color.blue()
        )
        
        # Add avatar
        embed.set_image(url=user.display_avatar.url)
        
        # Add links for different formats
        formats = []
        for fmt in ['png', 'jpg', 'webp']:
            formats.append(f"[{fmt.upper()}]({user.display_avatar.with_format(fmt).url})")
        if user.display_avatar.is_animated():
            formats.append(f"[GIF]({user.display_avatar.with_format('gif').url})")
        
        embed.add_field(
            name=_("Links", lang),
            value=" | ".join(formats),
            inline=False
        )
        
        # Send response
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "avatar")
    
    @commands.slash_command(name="weather")
    async def weather(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        location: str,
        units: str = commands.Param(
            default="metric",
            choices=["metric", "imperial"]
        )
    ):
        """
        Get current weather information for a location
        
        Parameters
        ----------
        location: City name or coordinates
        units: Unit system (metric: °C, km/h or imperial: °F, mph)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer response due to API call
        await interaction.response.defer()
        
        try:
            # Get weather API
            weather_api = get_api('openweathermap')
            
            # Get weather data
            weather_data = await weather_api.get_current_weather(location, units, lang[:2])
            
            # Prepare unit symbols based on chosen units
            if units == "metric":
                temp_symbol = "°C"
                speed_symbol = "m/s"
            else:
                temp_symbol = "°F"
                speed_symbol = "mph"
            
            # Create embed
            embed = create_embed(
                title=_("Weather for {location}", lang).format(location=weather_data['name']),
                description=_("Current conditions and temperature", lang),
                color=disnake.Color.blue()
            )
            
            # Main weather info
            weather = weather_data['weather'][0]
            temp = weather_data['main']['temp']
            feels_like = weather_data['main']['feels_like']
            
            # Add weather icon
            icon_code = weather['icon']
            embed.set_thumbnail(url=f"https://openweathermap.org/img/wn/{icon_code}@2x.png")
            
            # Add general weather fields
            embed.add_field(
                name=_("Conditions", lang),
                value=weather['description'].title(),
                inline=True
            )
            embed.add_field(
                name=_("Temperature", lang),
                value=f"{temp:.1f}{temp_symbol}",
                inline=True
            )
            embed.add_field(
                name=_("Feels Like", lang),
                value=f"{feels_like:.1f}{temp_symbol}",
                inline=True
            )
            
            # Add details
            embed.add_field(
                name=_("Humidity", lang),
                value=f"{weather_data['main']['humidity']}%",
                inline=True
            )
            embed.add_field(
                name=_("Wind", lang),
                value=f"{weather_data['wind']['speed']} {speed_symbol}",
                inline=True
            )
            if 'rain' in weather_data:
                embed.add_field(
                    name=_("Rain (1h)", lang),
                    value=f"{weather_data['rain'].get('1h', 0)} mm",
                    inline=True
                )
            
            # Add location and time data
            embed.add_field(
                name=_("Location", lang),
                value=f"{weather_data['name']}, {weather_data['sys']['country']}",
                inline=True
            )
            embed.add_field(
                name=_("Coordinates", lang),
                value=f"Lat: {weather_data['coord']['lat']}, Lon: {weather_data['coord']['lon']}",
                inline=True
            )
            
            # Add sunrise/sunset
            sunrise = datetime.datetime.utcfromtimestamp(weather_data['sys']['sunrise'])
            sunset = datetime.datetime.utcfromtimestamp(weather_data['sys']['sunset'])
            embed.add_field(
                name=_("Sunrise/Sunset", lang),
                value=_("Sunrise: <t:{sunrise}:t>\nSunset: <t:{sunset}:t>", lang).format(
                    sunrise=int(sunrise.timestamp()),
                    sunset=int(sunset.timestamp())
                ),
                inline=False
            )
            
            # Footer
            embed.set_footer(text=_("Data from OpenWeatherMap • Updated", lang))
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error fetching weather: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not fetch weather information. Please check the location and try again.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "weather")
    
    @commands.slash_command(name="forecast")
    async def forecast(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        location: str,
        units: str = commands.Param(
            default="metric",
            choices=["metric", "imperial"]
        )
    ):
        """
        Get a 5-day weather forecast for a location
        
        Parameters
        ----------
        location: City name or coordinates
        units: Unit system (metric: °C, km/h or imperial: °F, mph)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer response due to API call
        await interaction.response.defer()
        
        try:
            # Get weather API
            weather_api = get_api('openweathermap')
            
            # Get forecast data
            forecast_data = await weather_api.get_forecast(location, units, lang[:2])
            
            # Prepare unit symbols based on chosen units
            if units == "metric":
                temp_symbol = "°C"
                speed_symbol = "m/s"
            else:
                temp_symbol = "°F"
                speed_symbol = "mph"
            
            # Create embed
            embed = create_embed(
                title=_("5-Day Forecast for {location}", lang).format(location=forecast_data['city']['name']),
                description=_("Weather forecast for the next 5 days", lang),
                color=disnake.Color.blue()
            )
            
            # Group forecast by day
            forecasts_by_day = {}
            for item in forecast_data['list']:
                dt = datetime.datetime.utcfromtimestamp(item['dt'])
                day_key = dt.strftime("%Y-%m-%d")
                
                if day_key not in forecasts_by_day:
                    forecasts_by_day[day_key] = []
                
                forecasts_by_day[day_key].append(item)
            
            # Create summary for each day
            for day, forecasts in list(forecasts_by_day.items())[:5]:  # Limit to 5 days
                dt = datetime.datetime.strptime(day, "%Y-%m-%d")
                day_name = dt.strftime("%A")
                
                # Calculate average temperature and collect weather descriptions
                temps = [f['main']['temp'] for f in forecasts]
                avg_temp = sum(temps) / len(temps)
                min_temp = min(f['main']['temp_min'] for f in forecasts)
                max_temp = max(f['main']['temp_max'] for f in forecasts)
                descriptions = [f['weather'][0]['description'] for f in forecasts]
                main_desc = max(set(descriptions), key=descriptions.count)
                
                # Get appropriate icon (mid-day if available, otherwise first)
                mid_day = next((f for f in forecasts if datetime.datetime.utcfromtimestamp(f['dt']).hour in (12, 13, 14)), forecasts[0])
                
                # Add field for the day
                embed.add_field(
                    name=f"{day_name} ({day})",
                    value=_(
                        "**{main_desc}**\n"
                        "Avg: {avg_temp}{symbol}\n"
                        "Min: {min_temp}{symbol}\n"
                        "Max: {max_temp}{symbol}",
                        lang
                    ).format(
                        main_desc=main_desc.title(),
                        avg_temp=f"{avg_temp:.1f}",
                        min_temp=f"{min_temp:.1f}",
                        max_temp=f"{max_temp:.1f}",
                        symbol=temp_symbol
                    ),
                    inline=True
                )
            
            # Footer
            embed.set_footer(text=_("Data from OpenWeatherMap • Updated", lang))
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error fetching forecast: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not fetch forecast information. Please check the location and try again.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "forecast")
    
    @commands.slash_command(name="remind")
    async def remind(
        self, 
        interaction: disnake.ApplicationCommandInteraction,
        time: str,
        message: str
    ):
        """
        Set a reminder
        
        Parameters
        ----------
        time: When to remind you (e.g. 10m, 1h, 2d)
        message: What to remind you about
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Parse the time string
        time_regex = re.compile(r"(\d+)([smhdw])")
        match = time_regex.match(time.lower())
        
        if not match:
            embed = create_embed(
                title=_("Error", lang),
                description=_("Invalid time format. Please use a format like 10m, 1h, 2d, etc.", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        amount, unit = match.groups()
        amount = int(amount)
        
        # Calculate the due time
        now = datetime.datetime.utcnow()
        due_time = now
        
        if unit == 's':
            due_time += datetime.timedelta(seconds=amount)
            time_str = _("{amount} seconds", lang).format(amount=amount)
        elif unit == 'm':
            due_time += datetime.timedelta(minutes=amount)
            time_str = _("{amount} minutes", lang).format(amount=amount)
        elif unit == 'h':
            due_time += datetime.timedelta(hours=amount)
            time_str = _("{amount} hours", lang).format(amount=amount)
        elif unit == 'd':
            due_time += datetime.timedelta(days=amount)
            time_str = _("{amount} days", lang).format(amount=amount)
        elif unit == 'w':
            due_time += datetime.timedelta(weeks=amount)
            time_str = _("{amount} weeks", lang).format(amount=amount)
        
        # Add the reminder to the list
        reminder = {
            'user_id': interaction.author.id,
            'channel_id': interaction.channel.id if interaction.guild else None,
            'guild_id': interaction.guild.id if interaction.guild else None,
            'message': message,
            'set_time': now.timestamp(),
            'due_time': due_time.timestamp(),
            'language': lang
        }
        
        self.reminders.append(reminder)
        
        # Create response
        embed = create_embed(
            title=_("Reminder Set", lang),
            description=_("I'll remind you in {time}", lang).format(time=time_str),
            color=disnake.Color.green()
        )
        embed.add_field(
            name=_("Message", lang),
            value=message,
            inline=False
        )
        embed.add_field(
            name=_("Due Time", lang),
            value=f"<t:{int(due_time.timestamp())}:F>",
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "remind")
    
    @commands.slash_command(name="poll")
    @commands.guild_only()
    async def poll(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        question: str,
        options: str,
        multiple_choice: bool = False
    ):
        """
        Create a poll for users to vote on
        
        Parameters
        ----------
        question: The poll question
        options: Options separated by | (e.g. "Option 1 | Option 2 | Option 3")
        multiple_choice: Allow multiple votes per user
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Split options
        option_list = [opt.strip() for opt in options.split('|') if opt.strip()]
        
        # Check if we have at least two options
        if len(option_list) < 2:
            embed = create_embed(
                title=_("Error", lang),
                description=_("You need to provide at least two options separated by |", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check if we have too many options (limit to 10)
        if len(option_list) > 10:
            embed = create_embed(
                title=_("Error", lang),
                description=_("You can only have up to 10 options", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Create the poll embed
        embed = create_embed(
            title=_("📊 Poll: {question}", lang).format(question=question),
            description=_("Vote by reacting with the corresponding number!", lang),
            color=disnake.Color.blue()
        )
        
        # Add options to the embed
        emoji_numbers = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        for i, option in enumerate(option_list):
            embed.add_field(
                name=f"{emoji_numbers[i]} {option}",
                value="\u200b",  # Zero-width space
                inline=False
            )
        
        # Add poll info
        poll_type = _("Multiple Choice", lang) if multiple_choice else _("Single Choice", lang)
        embed.add_field(
            name=_("Poll Type", lang),
            value=poll_type,
            inline=True
        )
        embed.add_field(
            name=_("Created By", lang),
            value=interaction.author.mention,
            inline=True
        )
        
        # Send the poll
        await interaction.response.send_message(embed=embed)
        
        # Get the sent message to add reactions
        message = await interaction.original_message()
        
        # Add reactions
        for i in range(len(option_list)):
            await message.add_reaction(emoji_numbers[i])
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "poll")
    
    @commands.slash_command(name="random")
    async def random(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        choice: str = commands.Param(
            choices=["number", "coin", "dice", "card", "8ball"]
        ),
        min_value: int = None,
        max_value: int = None,
        question: str = None
    ):
        """
        Generate a random result
        
        Parameters
        ----------
        choice: Type of random generation
        min_value: Minimum value for number generation (required for 'number')
        max_value: Maximum value for number generation (required for 'number')
        question: Question to ask the Magic 8-Ball (required for '8ball')
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        if choice == "number":
            # Check if min and max values are provided
            if min_value is None or max_value is None:
                embed = create_embed(
                    title=_("Error", lang),
                    description=_("You must provide minimum and maximum values for a random number", lang),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # Generate random number
            result = random.randint(min_value, max_value)
            
            embed = create_embed(
                title=_("Random Number", lang),
                description=_("Between {min} and {max}", lang).format(min=min_value, max=max_value),
                color=disnake.Color.blue()
            )
            embed.add_field(
                name=_("Result", lang),
                value=str(result),
                inline=False
            )
        
        elif choice == "coin":
            # Flip a coin
            result = random.choice([_("Heads", lang), _("Tails", lang)])
            
            embed = create_embed(
                title=_("Coin Flip", lang),
                description=_("Flipping a coin...", lang),
                color=disnake.Color.gold()
            )
            embed.add_field(
                name=_("Result", lang),
                value=result,
                inline=False
            )
            
            # Add coin emoji based on result
            if result == _("Heads", lang):
                embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/322/coin_1fa99.png")
            else:
                embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/322/coin_1fa99.png")
        
        elif choice == "dice":
            # Roll a die
            result = random.randint(1, 6)
            
            embed = create_embed(
                title=_("Dice Roll", lang),
                description=_("Rolling a 6-sided die...", lang),
                color=disnake.Color.blurple()
            )
            embed.add_field(
                name=_("Result", lang),
                value=str(result),
                inline=False
            )
            
            # Add dice emoji
            dice_emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
            embed.description += f" {dice_emojis[result-1]}"
        
        elif choice == "card":
            # Draw a card
            suits = [_("Hearts", lang), _("Diamonds", lang), _("Clubs", lang), _("Spades", lang)]
            values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", _("Jack", lang), _("Queen", lang), _("King", lang), _("Ace", lang)]
            
            suit = random.choice(suits)
            value = random.choice(values)
            
            embed = create_embed(
                title=_("Card Draw", lang),
                description=_("Drawing a card from the deck...", lang),
                color=disnake.Color.dark_red() if suit in [_("Hearts", lang), _("Diamonds", lang)] else disnake.Color.dark_gray()
            )
            embed.add_field(
                name=_("Result", lang),
                value=_("{value} of {suit}", lang).format(value=value, suit=suit),
                inline=False
            )
        
        elif choice == "8ball":
            # Check if question is provided
            if not question:
                embed = create_embed(
                    title=_("Error", lang),
                    description=_("You must ask a question for the Magic 8-Ball", lang),
                    color=disnake.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            # 8-Ball responses
            responses = [
                # Positive answers
                _("It is certain.", lang),
                _("It is decidedly so.", lang),
                _("Without a doubt.", lang),
                _("Yes - definitely.", lang),
                _("You may rely on it.", lang),
                _("As I see it, yes.", lang),
                _("Most likely.", lang),
                _("Outlook good.", lang),
                _("Yes.", lang),
                _("Signs point to yes.", lang),
                
                # Neutral answers
                _("Reply hazy, try again.", lang),
                _("Ask again later.", lang),
                _("Better not tell you now.", lang),
                _("Cannot predict now.", lang),
                _("Concentrate and ask again.", lang),
                
                # Negative answers
                _("Don't count on it.", lang),
                _("My reply is no.", lang),
                _("My sources say no.", lang),
                _("Outlook not so good.", lang),
                _("Very doubtful.", lang)
            ]
            
            result = random.choice(responses)
            
            embed = create_embed(
                title=_("Magic 8-Ball", lang),
                description=f"**{question}**",
                color=disnake.Color.dark_purple()
            )
            embed.add_field(
                name=_("Answer", lang),
                value=result,
                inline=False
            )
            embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/120/twitter/322/pool-8-ball_1f3b1.png")
        
        # Send response
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, f"random_{choice}")
    
    @commands.slash_command(name="setlanguage")
    async def setlanguage(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        language: str = commands.Param(
            choices=["en", "ru", "de"]
        ),
        scope: str = commands.Param(
            default="user",
            choices=["user", "server"]
        )
    ):
        """
        Set your preferred language or the server's language
        
        Parameters
        ----------
        language: Language code (en, ru, de)
        scope: Whether to set for yourself or the server (if you have permission)
        """
        # Check if user has permission to set server language
        if scope == "server" and not interaction.guild:
            await interaction.response.send_message(
                "Server language can only be set in a server.",
                ephemeral=True
            )
            return
        
        if scope == "server" and not interaction.author.guild_permissions.manage_guild:
            await interaction.response.send_message(
                "You need the Manage Server permission to set the server language.",
                ephemeral=True
            )
            return
        
        # Get current language for response
        current_lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Set language based on scope
        try:
            if scope == "server":
                from bot.utils.db_manager import set_guild_language
                success = await set_guild_language(interaction.guild.id, language)
                
                if success:
                    embed = create_embed(
                        title=_("Language Set", current_lang),
                        description=_("The server language has been set to {language}.", current_lang).format(
                            language=language.upper()
                        ),
                        color=disnake.Color.green()
                    )
                    await interaction.response.send_message(embed=embed)
                else:
                    embed = create_embed(
                        title=_("Error", current_lang),
                        description=_("There was an error setting the server language.", current_lang),
                        color=disnake.Color.red()
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                from bot.utils.db_manager import set_member_language
                
                # For user scope, set language for user in this guild if in a guild
                if interaction.guild:
                    success = await set_member_language(interaction.author.id, interaction.guild.id, language)
                    
                    if success:
                        embed = create_embed(
                            title=_("Language Set", current_lang),
                            description=_("Your language in this server has been set to {language}.", current_lang).format(
                                language=language.upper()
                            ),
                            color=disnake.Color.green()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                    else:
                        embed = create_embed(
                            title=_("Error", current_lang),
                            description=_("There was an error setting your language.", current_lang),
                            color=disnake.Color.red()
                        )
                        await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    # In DMs, just acknowledge the preference
                    embed = create_embed(
                        title=_("Language Set", current_lang),
                        description=_("Your preferred language has been set to {language}.", current_lang).format(
                            language=language.upper()
                        ),
                        color=disnake.Color.green()
                    )
                    await interaction.response.send_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error setting language: {e}")
            embed = create_embed(
                title=_("Error", current_lang),
                description=_("There was an error setting the language.", current_lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
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
    """Setup function for the utility cog"""
    bot.add_cog(Utility(bot))
