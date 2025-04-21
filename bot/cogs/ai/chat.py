import disnake
from disnake.ext import commands
import aiohttp
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional

from bot.utils.logger import get_logger_for_cog

logger = get_logger_for_cog("ai")

class AI(commands.Cog):
    """Команды для работы с AI-сервисами"""
    
    def __init__(self, bot):
        self.bot = bot
        self.api_key = None
        self.model = None
        self.max_tokens = 256
        self.temperature = 0.7
        self.session = None
        self.chat_histories = {}  # user_id -> [messages]
        
        # Максимальная длина истории для каждого пользователя
        self.max_history_length = 10
        
        # URL для запросов к OpenAI API
        self.openai_url = "https://api.openai.com/v1/chat/completions"
        
        # URL для запросов к Grok API (формат может отличаться)
        self.grok_url = "https://api.grok.ai/v1/chat/completions"
    
    async def cog_load(self):
        """Вызывается при загрузке cog"""
        # Создание HTTP сессии
        self.session = aiohttp.ClientSession()
        
        # Получение настроек из конфигурации
        ai_config = self.bot.config.get("modules", {}).get("ai", {})
        self.api_key = ai_config.get("api_key", "")
        self.model = ai_config.get("model", "gpt-3.5-turbo")
        self.max_tokens = ai_config.get("max_tokens", 256)
        self.temperature = ai_config.get("temperature", 0.7)
        
        logger.info(f"AI модуль инициализирован (модель: {self.model})")
    
    async def cog_unload(self):
        """Вызывается при выгрузке cog"""
        if self.session:
            await self.session.close()
    
    @commands.slash_command(name="ask", description="Задать вопрос искусственному интеллекту")
    async def ask(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        question: str = commands.Param(description="Ваш вопрос или запрос к AI"),
        reset_context: bool = commands.Param(False, description="Сбросить историю разговора")
    ):
        """Задать вопрос искусственному интеллекту"""
        # Проверка API ключа
        if not self.api_key:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text(
                "ai.ask.api_key_missing", 
                guild_language
            )
            return await inter.response.send_message(error_text, ephemeral=True)
        
        # Отложенный ответ, так как запрос может занять время
        await inter.response.defer()
        
        # Сброс истории, если запрошено
        if reset_context:
            self.chat_histories.pop(inter.author.id, None)
            logger.info(f"История разговора сброшена для пользователя {inter.author.id}")
        
        # Получение или создание истории разговора
        if inter.author.id not in self.chat_histories:
            self.chat_histories[inter.author.id] = []
        
        # Добавление вопроса пользователя в историю
        self.chat_histories[inter.author.id].append({
            "role": "user",
            "content": question
        })
        
        # Обрезка истории до максимальной длины
        if len(self.chat_histories[inter.author.id]) > self.max_history_length:
            self.chat_histories[inter.author.id] = self.chat_histories[inter.author.id][-self.max_history_length:]
        
        # Получение ответа от AI
        try:
            response = await self._get_ai_response(self.chat_histories[inter.author.id])
            
            if not response:
                guild_language = await self.bot.get_guild_language(inter.guild.id)
                error_text = self.bot.language_manager.get_text(
                    "ai.ask.error", 
                    guild_language,
                    error="Получен пустой ответ от API"
                )
                return await inter.followup.send(error_text)
            
            # Добавление ответа в историю
            self.chat_histories[inter.author.id].append({
                "role": "assistant",
                "content": response
            })
            
            # Создание эмбеда с ответом
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            
            embed = disnake.Embed(
                title=self.bot.language_manager.get_text("ai.ask.title", guild_language),
                description=response[:4000],  # Ограничение длины ответа для эмбеда
                color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
            )
            
            embed.set_footer(
                text=f"Model: {self.model} | {self.bot.language_manager.get_text('ai.ask.context_length', guild_language, length=len(self.chat_histories[inter.author.id]) // 2)}"
            )
            
            embed.timestamp = datetime.utcnow()
            
            # Создание кнопок для управления контекстом
            class AIControls(disnake.ui.View):
                def __init__(self, cog, user_id):
                    super().__init__(timeout=60)
                    self.cog = cog
                    self.user_id = user_id
                
                @disnake.ui.button(label="Сбросить контекст", style=disnake.ButtonStyle.danger, emoji="🔄")
                async def reset_context(self, button: disnake.ui.Button, button_inter: disnake.MessageInteraction):
                    if button_inter.author.id != self.user_id:
                        guild_language = await self.cog.bot.get_guild_language(button_inter.guild.id)
                        not_for_you_text = self.cog.bot.language_manager.get_text("ai.ask.not_for_you", guild_language)
                        return await button_inter.response.send_message(not_for_you_text, ephemeral=True)
                    
                    # Сброс истории
                    self.cog.chat_histories.pop(self.user_id, None)
                    
                    guild_language = await self.cog.bot.get_guild_language(button_inter.guild.id)
                    reset_text = self.cog.bot.language_manager.get_text("ai.ask.context_reset", guild_language)
                    await button_inter.response.send_message(reset_text, ephemeral=True)
                    
                    # Отключение кнопок
                    for item in self.children:
                        item.disabled = True
                    
                    await button_inter.message.edit(view=self)
            
            # Отправка ответа
            await inter.followup.send(embed=embed, view=AIControls(self, inter.author.id))
            
        except Exception as e:
            logger.error(f"Ошибка при получении ответа от AI: {e}")
            
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text(
                "ai.ask.error", 
                guild_language,
                error=str(e)
            )
            await inter.followup.send(error_text)
    
    async def _get_ai_response(self, messages):
        """
        Получение ответа от AI API
        
        Args:
            messages (list): Список сообщений в формате [{"role": "user", "content": "..."}, ...]
        
        Returns:
            str: Ответ от AI или None в случае ошибки
        """
        try:
            # Определение, какой API использовать
            if self.model.lower().startswith("gpt") or self.model.lower() == "gpt-3.5-turbo":
                # Использование OpenAI API
                return await self._get_openai_response(messages)
            elif self.model.lower() == "grok-1":
                # Использование Grok API
                return await self._get_grok_response(messages)
            else:
                logger.error(f"Неизвестная модель AI: {self.model}")
                return None
        except Exception as e:
            logger.error(f"Ошибка при получении ответа от AI: {e}")
            return None
    
    async def _get_openai_response(self, messages):
        """
        Получение ответа от OpenAI API
        
        Args:
            messages (list): Список сообщений в формате [{"role": "user", "content": "..."}, ...]
        
        Returns:
            str: Ответ от OpenAI или None в случае ошибки
        """
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        try:
            async with self.session.post(self.openai_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    error_data = await response.text()
                    logger.error(f"Ошибка OpenAI API: {response.status} - {error_data}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к OpenAI API: {e}")
            return None
    
    async def _get_grok_response(self, messages):
        """
        Получение ответа от Grok API
        
        Args:
            messages (list): Список сообщений в формате [{"role": "user", "content": "..."}, ...]
        
        Returns:
            str: Ответ от Grok или None в случае ошибки
        """
        # Примечание: Формат запроса к Grok API может отличаться от OpenAI,
        # код ниже является примерным и должен быть адаптирован под реальный API
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
        
        try:
            async with self.session.post(self.grok_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    # Адаптируйте этот код под реальный формат ответа Grok API
                    return data["choices"][0]["message"]["content"].strip()
                else:
                    error_data = await response.text()
                    logger.error(f"Ошибка Grok API: {response.status} - {error_data}")
                    return None
        except Exception as e:
            logger.error(f"Ошибка при запросе к Grok API: {e}")
            return None

# Setup function for the cog
def setup(bot):
    bot.add_cog(AI(bot))