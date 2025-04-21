#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Entertainment commands for Discord bot.
Includes features for memes, jokes, quotes, and other fun commands.
"""

import disnake
from disnake.ext import commands
import random
import logging
import asyncio
import datetime
from typing import Optional
from sqlalchemy.future import select

from bot.utils.embed_creator import create_embed
from bot.utils.localization import _
from bot.utils.db_manager import get_session, get_guild_language
from bot.utils.api_wrapper import get_api
from bot.models import CommandUsage

class Entertainment(commands.Cog):
    """Entertainment commands for fun and enjoyment"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.entertainment')
        self.reddit_api = None
    
    async def cog_load(self):
        """Called when the cog is loaded"""
        try:
            self.reddit_api = get_api('reddit')
        except Exception as e:
            self.logger.error(f"Failed to initialize Reddit API: {e}")
    
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.reddit_api:
            await self.reddit_api.close()
    
    @commands.slash_command(name="meme")
    async def meme(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        subreddit: str = "memes"
    ):
        """
        Get a random meme from Reddit
        
        Parameters
        ----------
        subreddit: Subreddit to get meme from (default: memes)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer the response due to API call
        await interaction.response.defer()
        
        try:
            # Initialize Reddit API if needed
            if not self.reddit_api:
                self.reddit_api = get_api('reddit')
            
            # Get a random meme
            # Use SFW content only in guild channels, can allow NSFW in DMs if 18+
            allow_nsfw = interaction.channel.is_nsfw() if hasattr(interaction.channel, 'is_nsfw') else False
            meme = await self.reddit_api.get_random_meme(subreddit, allow_nsfw)
            
            if not meme:
                embed = create_embed(
                    title=_("Error", lang),
                    description=_("Couldn't find any memes on r/{subreddit}. Try another subreddit.", lang).format(
                        subreddit=subreddit
                    ),
                    color=disnake.Color.red()
                )
                await interaction.edit_original_message(embed=embed)
                return
            
            # Create embed
            embed = create_embed(
                title=meme['title'],
                url=meme['permalink'],
                color=disnake.Color.random()
            )
            
            # Add image if it's not a video
            if not meme['is_video']:
                embed.set_image(url=meme['url'])
            else:
                embed.description = _("This is a video meme. [Click here to view it.]({url})", lang).format(
                    url=meme['url']
                )
            
            # Add footer
            embed.set_footer(
                text=_("Posted by u/{author} • 👍 {score}", lang).format(
                    author=meme['author'],
                    score=meme['score']
                )
            )
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error fetching meme: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not fetch meme. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "meme")
    
    @commands.slash_command(name="joke")
    async def joke(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        category: str = commands.Param(
            default="any",
            choices=["any", "programming", "misc", "dark", "pun", "spooky", "christmas"]
        )
    ):
        """
        Get a random joke
        
        Parameters
        ----------
        category: Joke category
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer the response due to API call
        await interaction.response.defer()
        
        try:
            # Fetch joke from JokeAPI
            session = await self.ensure_session()
            
            # Build URL with specified category and safe mode for SFW channels
            is_nsfw = interaction.channel.is_nsfw() if hasattr(interaction.channel, 'is_nsfw') else False
            base_url = "https://v2.jokeapi.dev/joke/"
            
            if category == "any":
                url = f"{base_url}Any"
            else:
                url = f"{base_url}{category.capitalize()}"
            
            # Add flags if needed (SFW/NSFW)
            if not is_nsfw:
                url += "?blacklistFlags=nsfw,religious,political,racist,sexist,explicit"
            
            # Get the joke
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"API returned status code {response.status}")
                
                data = await response.json()
                
                if data.get('error'):
                    raise Exception(data.get('message', 'Unknown error'))
                
                # Create embed based on joke type
                if data['type'] == 'single':
                    embed = create_embed(
                        title=_("Joke", lang),
                        description=data['joke'],
                        color=disnake.Color.gold()
                    )
                else:  # twopart
                    embed = create_embed(
                        title=data['setup'],
                        color=disnake.Color.gold()
                    )
                    
                    # For two-part jokes, add a button to reveal the punchline
                    components = disnake.ui.Button(
                        style=disnake.ButtonStyle.primary,
                        label=_("Reveal Punchline", lang),
                        custom_id="reveal_punchline"
                    )
                    
                    # Send initial response with button
                    await interaction.edit_original_message(embed=embed, components=components)
                    
                    # Wait for button press
                    try:
                        button_interaction = await self.bot.wait_for(
                            "button_click",
                            check=lambda i: i.component.custom_id == "reveal_punchline" and i.user.id == interaction.user.id,
                            timeout=60.0
                        )
                        
                        # Update embed with punchline
                        embed.description = data['delivery']
                        await button_interaction.response.edit_message(embed=embed, components=None)
                        
                        # No need to continue further for two-part jokes
                        await self.log_command(interaction.author.id, interaction.guild.id if interaction.guild else None, "joke")
                        return
                        
                    except asyncio.TimeoutError:
                        # User didn't click the button in time
                        embed.description = _("*Punchline not revealed*", lang)
                        await interaction.edit_original_message(embed=embed, components=None)
                        await self.log_command(interaction.author.id, interaction.guild.id if interaction.guild else None, "joke")
                        return
                
                # For single-part jokes, just send the embed
                await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error fetching joke: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not fetch joke. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "joke")
    
    async def ensure_session(self):
        """Ensure aiohttp ClientSession exists and return it"""
        if not hasattr(self, 'session') or self.session.closed:
            import aiohttp
            self.session = aiohttp.ClientSession()
        return self.session
    
    @commands.slash_command(name="quote")
    async def quote(self, interaction: disnake.ApplicationCommandInteraction):
        """Get an inspirational quote"""
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer the response due to API call
        await interaction.response.defer()
        
        try:
            # Fetch quote from quotable API
            session = await self.ensure_session()
            
            async with session.get("https://api.quotable.io/random") as response:
                if response.status != 200:
                    raise Exception(f"API returned status code {response.status}")
                
                data = await response.json()
                
                embed = create_embed(
                    title=_("Inspirational Quote", lang),
                    description=f"*{data['content']}*",
                    color=disnake.Color.blue()
                )
                embed.set_footer(text=f"— {data['author']}")
                
                await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error fetching quote: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not fetch quote. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "quote")
    
    @commands.slash_command(name="fact")
    async def fact(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        category: str = commands.Param(
            default="random",
            choices=["random", "animal", "science", "history", "tech"]
        )
    ):
        """
        Get a random fact
        
        Parameters
        ----------
        category: Fact category
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer the response due to API call
        await interaction.response.defer()
        
        # Collection of facts by category
        facts = {
            "animal": [
                "Octopuses have three hearts.",
                "A group of flamingos is called a flamboyance.",
                "Cows have best friends and get stressed when separated.",
                "Dolphins have names for each other.",
                "Koalas sleep up to 22 hours a day.",
                "Goats have rectangular pupils.",
                "A tiger's skin is striped, not just its fur.",
                "Elephants are the only mammals that can't jump.",
                "Otters hold hands while sleeping so they don't drift apart.",
                "A snail can sleep for three years at a time."
            ],
            "science": [
                "Bananas are berries, but strawberries aren't.",
                "About 8% of human DNA comes from viruses.",
                "Humans share 50% of their DNA with bananas.",
                "The speed of light is 299,792,458 meters per second.",
                "A teaspoonful of neutron star would weigh 6 billion tons.",
                "There are more possible iterations of a game of chess than atoms in the known universe.",
                "A day on Venus is longer than a year on Venus.",
                "Water can exist in three states at once (triple point).",
                "The human body contains enough fat to make 7 bars of soap.",
                "Stomach acid is strong enough to dissolve metal."
            ],
            "history": [
                "Cleopatra lived closer in time to the Moon landing than to the building of the Great Pyramid.",
                "Oxford University is older than the Aztec Empire.",
                "The first pyramids were built while woolly mammoths still roamed the Earth.",
                "Nintendo was founded in 1889 as a playing card company.",
                "Ancient Romans used crushed mouse brains as toothpaste.",
                "The shortest war in history was between Britain and Zanzibar in 1896, lasting only 38 minutes.",
                "Einstein was offered the presidency of Israel in 1952 but declined.",
                "Saudi Arabia imports camels from Australia.",
                "The ancient Greeks had an Olympic sport that involved racing in full armor.",
                "The world's oldest known living tree was already almost 1,000 years old when the pyramids were built."
            ],
            "tech": [
                "The first computer bug was an actual real-life moth.",
                "The first message sent over the internet was 'LOGIN', but the system crashed after 'LO'.",
                "The first computer programmer was a woman named Ada Lovelace.",
                "The entire internet weighs about 50 grams.",
                "There are more than 5,000 cryptocurrencies in existence.",
                "The first ever website is still online: http://info.cern.ch/.",
                "About 90% of all the data in the world was created in the last two years.",
                "On average, people read 10% slower from a screen than from paper.",
                "The 'MP3' file extension stands for 'MPEG Audio Layer 3'.",
                "QWERTY keyboard layout was designed to slow down typing to prevent typewriter jams."
            ]
        }
        
        try:
            if category == "random":
                # Pick a random category then a random fact
                chosen_category = random.choice(list(facts.keys()))
                fact = random.choice(facts[chosen_category])
                embed_title = _("Random Fact", lang)
            else:
                # Pick a random fact from the specified category
                fact = random.choice(facts[category])
                embed_title = _("{category} Fact", lang).format(category=category.capitalize())
            
            embed = create_embed(
                title=embed_title,
                description=fact,
                color=disnake.Color.green()
            )
            
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error fetching fact: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not fetch fact. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "fact")
    
    @commands.slash_command(name="emojify")
    async def emojify(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        text: str
    ):
        """
        Convert text to emoji
        
        Parameters
        ----------
        text: Text to convert to emoji
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Mapping letters to emojis
        emoji_map = {
            'a': '🇦', 'b': '🇧', 'c': '🇨', 'd': '🇩', 'e': '🇪', 'f': '🇫', 'g': '🇬',
            'h': '🇭', 'i': '🇮', 'j': '🇯', 'k': '🇰', 'l': '🇱', 'm': '🇲', 'n': '🇳',
            'o': '🇴', 'p': '🇵', 'q': '🇶', 'r': '🇷', 's': '🇸', 't': '🇹', 'u': '🇺',
            'v': '🇻', 'w': '🇼', 'x': '🇽', 'y': '🇾', 'z': '🇿', '0': '0️⃣', '1': '1️⃣',
            '2': '2️⃣', '3': '3️⃣', '4': '4️⃣', '5': '5️⃣', '6': '6️⃣', '7': '7️⃣',
            '8': '8️⃣', '9': '9️⃣', '?': '❓', '!': '❗', ' ': '   '
        }
        
        # Convert text to emojis with a space between each character
        emojified = ' '.join(emoji_map.get(c.lower(), c) for c in text)
        
        # Check if result is too long for Discord
        if len(emojified) > 2000:
            embed = create_embed(
                title=_("Error", lang),
                description=_("The emojified text is too long (max 2000 characters).", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        await interaction.response.send_message(emojified)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "emojify")
    
    @commands.slash_command(name="choose")
    async def choose(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        choices: str
    ):
        """
        Make a random choice from a list
        
        Parameters
        ----------
        choices: Options to choose from, separated by commas
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Split the choices
        options = [option.strip() for option in choices.split(',') if option.strip()]
        
        if len(options) < 2:
            embed = create_embed(
                title=_("Error", lang),
                description=_("Please provide at least two options separated by commas.", lang),
                color=disnake.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Make a choice
        choice = random.choice(options)
        
        embed = create_embed(
            title=_("I choose...", lang),
            description=f"🎯 **{choice}**",
            color=disnake.Color.purple()
        )
        
        # List all options
        options_text = "\n".join(f"• {option}" for option in options)
        embed.add_field(
            name=_("Options", lang),
            value=options_text[:1024],  # Limit to 1024 characters (Discord field limit)
            inline=False
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "choose")
    
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
    """Setup function for the entertainment cog"""
    bot.add_cog(Entertainment(bot))
