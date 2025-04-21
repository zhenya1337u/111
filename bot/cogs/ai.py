#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
AI integration commands for Discord bot.
Includes features for Grok AI for chat, image generation, and other AI services.
"""

import disnake
from disnake.ext import commands
import logging
import asyncio
import datetime
import json
import os
from typing import Optional
from sqlalchemy.future import select

from bot.utils.embed_creator import create_embed
from bot.utils.localization import _
from bot.utils.db_manager import get_session, get_guild_language
from bot.utils.api_wrapper import get_api
from bot.models import CommandUsage

class AI(commands.Cog):
    """AI commands for chat and image generation"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('bot.ai')
        self.grok_api = None
        self.user_conversations = {}
        
    async def cog_load(self):
        """Called when the cog is loaded"""
        try:
            self.grok_api = get_api('grok')
            self.logger.info("AI cog initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize Grok API: {e}")
    
    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.grok_api:
            await self.grok_api.close()
    
    @commands.slash_command(name="ask")
    async def ask(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        question: str,
        model: str = commands.Param(
            default="grok",
            choices=["grok"]  # Can add more models in the future
        )
    ):
        """
        Ask a question to an AI assistant
        
        Parameters
        ----------
        question: Your question for the AI
        model: Which AI model to use
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer response due to potential long processing time
        await interaction.response.defer()
        
        try:
            # Initialize Grok API if needed
            if not self.grok_api:
                self.grok_api = get_api('grok')
            
            # Check if this is a continuation of a conversation
            user_id = interaction.author.id
            guild_id = interaction.guild.id if interaction.guild else 0
            conversation_key = f"{user_id}_{guild_id}"
            system_message = None
            
            # If the user has a conversation, get the system message
            if conversation_key in self.user_conversations:
                system_message = self.user_conversations[conversation_key].get('system_message')
            else:
                # Create a new conversation with system message
                system_message = _(
                    "You are a helpful assistant called Grok. Your responses should be concise and helpful. "
                    "You are responding in a Discord server, so format your responses appropriately with Markdown.",
                    lang
                )
                self.user_conversations[conversation_key] = {
                    'system_message': system_message,
                    'last_used': datetime.datetime.utcnow()
                }
            
            # Ask Grok
            response = await self.grok_api.generate_response(question, system_message)
            
            # Update last used time
            if conversation_key in self.user_conversations:
                self.user_conversations[conversation_key]['last_used'] = datetime.datetime.utcnow()
            
            # Create embed
            embed = create_embed(
                title=_("AI Response", lang),
                description=response[:4096],  # Limit to Discord embed description max length
                color=disnake.Color.purple()
            )
            
            # Add question as field
            embed.add_field(
                name=_("Your Question", lang),
                value=question[:1024],  # Limit to Discord embed field max length
                inline=False
            )
            
            # Add footer with model info
            embed.set_footer(text=f"Model: {model.capitalize()}")
            
            # If response is too long, add a note
            if len(response) > 4096:
                embed.add_field(
                    name=_("Note", lang),
                    value=_("The response was too long and has been truncated.", lang),
                    inline=False
                )
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error with AI response: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not generate an AI response. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "ask")
    
    @commands.slash_command(name="summarize")
    @commands.guild_only()
    async def summarize(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        message_count: int = commands.Param(min_value=5, max_value=100, default=20)
    ):
        """
        Summarize recent messages in the channel
        
        Parameters
        ----------
        message_count: Number of messages to summarize (5-100)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id)
        
        # Defer response due to potentially long processing time
        await interaction.response.defer()
        
        try:
            # Initialize Grok API if needed
            if not self.grok_api:
                self.grok_api = get_api('grok')
            
            # Fetch messages
            messages = []
            async for message in interaction.channel.history(limit=message_count):
                # Skip bot messages and empty messages
                if message.author.bot or not message.content:
                    continue
                
                # Format message for inclusion
                messages.append({
                    'author': str(message.author),
                    'content': message.content,
                    'timestamp': message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                })
            
            # Reverse to chronological order
            messages.reverse()
            
            if not messages:
                embed = create_embed(
                    title=_("Error", lang),
                    description=_("No valid messages found to summarize.", lang),
                    color=disnake.Color.red()
                )
                await interaction.edit_original_message(embed=embed)
                return
            
            # Format messages for the prompt
            formatted_messages = "\n\n".join([
                f"[{msg['timestamp']}] {msg['author']}: {msg['content']}"
                for msg in messages
            ])
            
            # Create the prompt
            prompt = _(
                "Please provide a concise summary of the following conversation. "
                "Focus on the main topics and key points discussed:\n\n{messages}",
                lang
            ).format(messages=formatted_messages)
            
            # Create system message
            system_message = _(
                "You are a helpful assistant. Your task is to summarize the provided conversation. "
                "Be concise but comprehensive, capturing the main points and important details. "
                "Format your summary in bullet points for readability.",
                lang
            )
            
            # Generate summary
            summary = await self.grok_api.generate_response(prompt, system_message)
            
            # Create embed
            embed = create_embed(
                title=_("Conversation Summary", lang),
                description=summary[:4096],  # Limit to Discord embed description max length
                color=disnake.Color.purple()
            )
            
            # Add metadata
            embed.add_field(
                name=_("Messages Analyzed", lang),
                value=str(len(messages)),
                inline=True
            )
            embed.add_field(
                name=_("Timespan", lang),
                value=_("{start} to {end}", lang).format(
                    start=messages[0]['timestamp'] if messages else "N/A",
                    end=messages[-1]['timestamp'] if messages else "N/A"
                ),
                inline=True
            )
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error summarizing messages: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not generate a summary. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        await self.log_command(interaction.author.id, interaction.guild.id, "summarize")
    
    @commands.slash_command(name="translate")
    async def translate(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        text: str,
        target_language: str
    ):
        """
        Translate text to another language
        
        Parameters
        ----------
        text: Text to translate
        target_language: Language to translate to (e.g., Spanish, German, Russian)
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer response due to potential long processing time
        await interaction.response.defer()
        
        try:
            # Initialize Grok API if needed
            if not self.grok_api:
                self.grok_api = get_api('grok')
            
            # Create the prompt
            prompt = _(
                "Translate the following text to {language}:\n\n{text}",
                lang
            ).format(language=target_language, text=text)
            
            # Create system message
            system_message = _(
                "You are a translation assistant. Your task is to accurately translate the provided text "
                "to the requested language. Only provide the translated text as your response, "
                "without any additional comments or explanations.",
                lang
            )
            
            # Generate translation
            translation = await self.grok_api.generate_response(prompt, system_message)
            
            # Create embed
            embed = create_embed(
                title=_("Translation", lang),
                description=translation[:4096],  # Limit to Discord embed description max length
                color=disnake.Color.blue()
            )
            
            # Add original text
            embed.add_field(
                name=_("Original Text", lang),
                value=text[:1024],  # Limit to Discord embed field max length
                inline=False
            )
            
            # Add target language
            embed.add_field(
                name=_("Target Language", lang),
                value=target_language,
                inline=True
            )
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error translating text: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not translate the text. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "translate")
    
    @commands.slash_command(name="clearconversation")
    async def clearconversation(self, interaction: disnake.ApplicationCommandInteraction):
        """Clear your current AI conversation history"""
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Get conversation key
        user_id = interaction.author.id
        guild_id = interaction.guild.id if interaction.guild else 0
        conversation_key = f"{user_id}_{guild_id}"
        
        # Check if user has a conversation
        if conversation_key in self.user_conversations:
            # Remove the conversation
            del self.user_conversations[conversation_key]
            
            embed = create_embed(
                title=_("Conversation Cleared", lang),
                description=_("Your AI conversation history has been cleared.", lang),
                color=disnake.Color.green()
            )
        else:
            embed = create_embed(
                title=_("No Conversation", lang),
                description=_("You don't have an active conversation to clear.", lang),
                color=disnake.Color.orange()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "clearconversation")
    
    @commands.slash_command(name="explain")
    async def explain(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        concept: str,
        detail_level: str = commands.Param(
            default="medium",
            choices=["simple", "medium", "detailed"]
        )
    ):
        """
        Get an explanation of a concept
        
        Parameters
        ----------
        concept: The concept to explain
        detail_level: How detailed the explanation should be
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer response due to potential long processing time
        await interaction.response.defer()
        
        try:
            # Initialize Grok API if needed
            if not self.grok_api:
                self.grok_api = get_api('grok')
            
            # Map detail level to instructions
            detail_instructions = {
                "simple": _("Explain this in simple terms as if to a child.", lang),
                "medium": _("Provide a moderate explanation suitable for a general audience.", lang),
                "detailed": _("Give a detailed explanation with technical details where appropriate.", lang)
            }
            
            # Create the prompt
            prompt = _(
                "Explain the following concept: {concept}\n\n{detail_instruction}",
                lang
            ).format(
                concept=concept,
                detail_instruction=detail_instructions[detail_level]
            )
            
            # Create system message
            system_message = _(
                "You are an educational assistant. Your task is to explain concepts clearly "
                "and accurately at the requested level of detail. Use analogies and examples "
                "where appropriate to illustrate your points.",
                lang
            )
            
            # Generate explanation
            explanation = await self.grok_api.generate_response(prompt, system_message)
            
            # Create embed
            embed = create_embed(
                title=_("Explanation: {concept}", lang).format(concept=concept),
                description=explanation[:4096],  # Limit to Discord embed description max length
                color=disnake.Color.gold()
            )
            
            # Add detail level
            embed.add_field(
                name=_("Detail Level", lang),
                value=detail_level.capitalize(),
                inline=True
            )
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error generating explanation: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not generate an explanation. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "explain")
    
    @commands.slash_command(name="code")
    async def code(
        self,
        interaction: disnake.ApplicationCommandInteraction,
        prompt: str,
        language: str = commands.Param(
            default="python",
            choices=["python", "javascript", "html", "css", "java", "c++", "c#", "php", "sql", "bash"]
        )
    ):
        """
        Generate code based on a prompt
        
        Parameters
        ----------
        prompt: Description of what the code should do
        language: Programming language to generate
        """
        # Get language
        lang = await get_guild_language(interaction.guild.id if interaction.guild else None)
        
        # Defer response due to potential long processing time
        await interaction.response.defer()
        
        try:
            # Initialize Grok API if needed
            if not self.grok_api:
                self.grok_api = get_api('grok')
            
            # Create the prompt
            prompt_text = _(
                "Generate {language} code for the following task: {prompt}\n\n"
                "Please only provide the code with appropriate comments. "
                "Do not include explanations before or after the code.",
                lang
            ).format(language=language, prompt=prompt)
            
            # Create system message
            system_message = _(
                "You are a programming assistant. Your task is to generate clean, efficient, "
                "and well-documented code in the requested programming language. "
                "Include comments to explain complex parts. The code should be complete "
                "and ready to use.",
                lang
            )
            
            # Generate code
            code_result = await self.grok_api.generate_response(prompt_text, system_message)
            
            # Extract code block if present
            if "```" in code_result:
                # Try to extract code between code blocks
                code_parts = code_result.split("```")
                if len(code_parts) >= 3:
                    # Get the content of the first code block
                    code_block = code_parts[1]
                    # Remove language identifier if present
                    if code_block.startswith(language) or code_block.startswith(language.lower()):
                        code_block = code_block[len(language):].lstrip()
                    code_result = f"```{language}\n{code_block}\n```"
                else:
                    # If we can't parse it correctly, just format it
                    code_result = f"```{language}\n{code_result}\n```"
            else:
                # If no code block, add one
                code_result = f"```{language}\n{code_result}\n```"
            
            # Create embed
            embed = create_embed(
                title=_("Generated {language} Code", lang).format(language=language.capitalize()),
                description=code_result[:4096],  # Limit to Discord embed description max length
                color=disnake.Color.dark_green()
            )
            
            # Add prompt as field
            embed.add_field(
                name=_("Prompt", lang),
                value=prompt[:1024],  # Limit to Discord embed field max length
                inline=False
            )
            
            # Send response
            await interaction.edit_original_message(embed=embed)
        
        except Exception as e:
            self.logger.error(f"Error generating code: {e}")
            
            embed = create_embed(
                title=_("Error", lang),
                description=_("Could not generate code. Please try again later.", lang),
                color=disnake.Color.red()
            )
            await interaction.edit_original_message(embed=embed)
        
        # Log command usage
        if interaction.guild:
            await self.log_command(interaction.author.id, interaction.guild.id, "code")
    
    @tasks.loop(hours=1)
    async def cleanup_old_conversations(self):
        """Cleanup old conversations to free up memory"""
        try:
            current_time = datetime.datetime.utcnow()
            to_remove = []
            
            # Find conversations older than 1 hour
            for key, data in self.user_conversations.items():
                last_used = data.get('last_used', datetime.datetime.min)
                if (current_time - last_used).total_seconds() > 3600:  # 1 hour
                    to_remove.append(key)
            
            # Remove old conversations
            for key in to_remove:
                del self.user_conversations[key]
            
            if to_remove:
                self.logger.info(f"Cleaned up {len(to_remove)} old AI conversations")
        except Exception as e:
            self.logger.error(f"Error cleaning up conversations: {e}")
    
    @cleanup_old_conversations.before_loop
    async def before_cleanup(self):
        await self.bot.wait_until_ready()
    
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
    """Setup function for the AI cog"""
    cog = AI(bot)
    cog.cleanup_old_conversations.start()
    bot.add_cog(cog)
