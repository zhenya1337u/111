import disnake
from disnake.ext import commands
import logging
import platform
import os
import psutil
from datetime import datetime

from bot.utils.logger import get_logger_for_cog

logger = get_logger_for_cog("admin")

class BaseCommands(commands.Cog):
    """Базовые административные команды"""
    
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
    
    @commands.slash_command(name="ping", description="Проверка задержки бота")
    async def ping(self, inter: disnake.ApplicationCommandInteraction):
        """Проверка задержки бота"""
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Измерение задержки API
        start_time = datetime.now()
        await inter.response.defer(ephemeral=True)
        api_latency = (datetime.now() - start_time).total_seconds() * 1000
        
        # Создание эмбеда
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("commands.ping.title", guild_language),
            description=self.bot.language_manager.get_text(
                "commands.ping.description", 
                guild_language, 
                ping=round(self.bot.latency * 1000),
                api_latency=round(api_latency)
            ),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
        )
        
        embed.set_footer(text=f"Discord API | {self.bot.user.name}")
        embed.timestamp = datetime.utcnow()
        
        await inter.followup.send(embed=embed, ephemeral=True)
    
    @commands.slash_command(name="stats", description="Показать статистику бота")
    async def stats(self, inter: disnake.ApplicationCommandInteraction):
        """Показать статистику бота"""
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Расчет времени работы
        uptime = datetime.utcnow() - self.bot.start_time
        days, remainder = divmod(int(uptime.total_seconds()), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s" if days else f"{hours}h {minutes}m {seconds}s"
        
        # Получение информации о системе
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # В МБ
        
        # Создание эмбеда
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("commands.stats.title", guild_language),
            description=self.bot.language_manager.get_text("commands.stats.description", guild_language),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
        )
        
        # Добавление полей
        embed.add_field(
            name=self.bot.language_manager.get_text("commands.stats.uptime", guild_language),
            value=uptime_str,
            inline=True
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("commands.stats.servers", guild_language),
            value=str(len(self.bot.guilds)),
            inline=True
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("commands.stats.users", guild_language),
            value=str(len(self.bot.users)),
            inline=True
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("commands.stats.memory", guild_language),
            value=f"{memory_usage:.2f} MB",
            inline=True
        )
        
        embed.add_field(
            name="Python",
            value=platform.python_version(),
            inline=True
        )
        
        embed.add_field(
            name="Disnake",
            value=disnake.__version__,
            inline=True
        )
        
        # Добавление футера
        embed.set_footer(text=f"{self.bot.user.name} | ID: {self.bot.user.id}")
        embed.timestamp = datetime.utcnow()
        
        await inter.response.send_message(embed=embed)

    @commands.slash_command(name="help", description="Показать список команд")
    async def help(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        command: str = commands.Param(None, description="Название команды для подробной информации")
    ):
        """Показать список команд"""
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        if command:
            # Поиск конкретной команды
            slash_cmd = self.bot.get_slash_command(command)
            
            if not slash_cmd:
                no_command_text = self.bot.language_manager.get_text(
                    "commands.help.command_not_found", 
                    guild_language,
                    command=command
                )
                return await inter.response.send_message(no_command_text, ephemeral=True)
            
            # Создание эмбеда для конкретной команды
            embed = disnake.Embed(
                title=self.bot.language_manager.get_text(
                    "commands.help.command_details", 
                    guild_language,
                    command=slash_cmd.name
                ),
                description=slash_cmd.description or "Нет описания",
                color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
            )
            
            # Добавление информации о подкомандах, если есть
            if hasattr(slash_cmd, "children") and slash_cmd.children:
                subcommands = "\n".join([f"`/{slash_cmd.name} {sub_name}` - {sub_cmd.description}" 
                                     for sub_name, sub_cmd in slash_cmd.children.items()])
                
                embed.add_field(
                    name="Подкоманды",
                    value=subcommands,
                    inline=False
                )
            
            # Добавление футера
            embed.set_footer(text=f"{self.bot.user.name} | /help")
            embed.timestamp = datetime.utcnow()
            
            await inter.response.send_message(embed=embed)
            
        else:
            # Создание эмбеда для списка всех команд
            embed = disnake.Embed(
                title=self.bot.language_manager.get_text("commands.help.title", guild_language),
                description=self.bot.language_manager.get_text("commands.help.description", guild_language),
                color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
            )
            
            # Категоризация команд
            categories = {}
            
            for cmd in self.bot.slash_commands:
                cog_name = cmd.cog_name or "Без категории"
                
                if cog_name not in categories:
                    categories[cog_name] = []
                
                categories[cog_name].append(cmd)
            
            # Добавление полей для каждой категории
            for category, cmds in sorted(categories.items()):
                if not cmds:
                    continue
                
                commands_text = "\n".join([f"`/{cmd.name}` - {cmd.description}" for cmd in cmds])
                
                embed.add_field(
                    name=f"{category}",
                    value=commands_text or self.bot.language_manager.get_text("commands.help.no_commands", guild_language),
                    inline=False
                )
            
            # Добавление футера
            embed.set_footer(text=f"{self.bot.user.name} | /help [command]")
            embed.timestamp = datetime.utcnow()
            
            await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="module", description="Управление модулями бота")
    @commands.default_member_permissions(administrator=True)
    async def module(self, inter: disnake.ApplicationCommandInteraction):
        """Группа команд для управления модулями бота"""
        pass
    
    @module.sub_command(name="list", description="Показать список всех модулей")
    async def module_list(self, inter: disnake.ApplicationCommandInteraction):
        """Показать список всех модулей"""
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Получение состояний модулей для сервера
        if inter.guild.id in self.bot.module_states:
            module_states = self.bot.module_states[inter.guild.id]
        else:
            # Если состояния нет, используем дефолтные настройки
            module_states = {}
            
            for module_name, module_config in self.bot.config.get("modules", {}).items():
                module_states[module_name] = module_config.get("enabled", False)
        
        # Создание эмбеда
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("commands.module.title", guild_language),
            description=self.bot.language_manager.get_text("commands.module.list", guild_language),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
        )
        
        # Добавление полей для каждого модуля
        for module_name, is_enabled in sorted(module_states.items()):
            status = "✅" if is_enabled else "❌"
            
            embed.add_field(
                name=f"{module_name.capitalize()}",
                value=self.bot.language_manager.get_text(
                    "commands.module.status", 
                    guild_language,
                    module=module_name,
                    status=status
                ),
                inline=True
            )
        
        # Добавление инструкции
        embed.add_field(
            name="",
            value=f"Используйте `/module enable` или `/module disable` для управления модулями",
            inline=False
        )
        
        # Добавление футера
        embed.set_footer(text=f"{self.bot.user.name} | /module")
        embed.timestamp = datetime.utcnow()
        
        await inter.response.send_message(embed=embed)
    
    @module.sub_command(name="enable", description="Включить модуль")
    async def module_enable(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        module: str = commands.Param(description="Название модуля для включения")
    ):
        """Включить модуль"""
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Проверка, существует ли модуль
        if module not in self.bot.config.get("modules", {}):
            not_found_text = self.bot.language_manager.get_text(
                "commands.module.not_found", 
                guild_language,
                module=module
            )
            return await inter.response.send_message(not_found_text, ephemeral=True)
        
        # Инициализация состояний модулей для сервера, если их еще нет
        if inter.guild.id not in self.bot.module_states:
            self.bot.module_states[inter.guild.id] = {}
        
        # Включение модуля
        self.bot.module_states[inter.guild.id][module] = True
        
        # Обновление состояния модуля в базе данных
        if self.bot.db:
            try:
                # Получение текущих состояний из базы данных
                result = await self.bot.db.fetchval(
                    "SELECT module_config FROM guilds WHERE id = $1",
                    inter.guild.id
                )
                
                if result is None:
                    # Если записи о сервере нет, создаем ее
                    await self.bot.db.execute(
                        """
                        INSERT INTO guilds (id, name, module_config)
                        VALUES ($1, $2, $3)
                        """,
                        inter.guild.id, inter.guild.name, {module: True}
                    )
                else:
                    # Если запись есть, обновляем конфигурацию
                    module_config = result or {}
                    module_config[module] = True
                    
                    await self.bot.db.execute(
                        """
                        UPDATE guilds
                        SET module_config = $1
                        WHERE id = $2
                        """,
                        module_config, inter.guild.id
                    )
            except Exception as e:
                logger.error(f"Ошибка при обновлении состояния модуля в базе данных: {e}")
        
        # Отправка сообщения об успешном включении
        enabled_text = self.bot.language_manager.get_text(
            "commands.module.enabled", 
            guild_language,
            module=module
        )
        await inter.response.send_message(enabled_text)
    
    @module.sub_command(name="disable", description="Отключить модуль")
    async def module_disable(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        module: str = commands.Param(description="Название модуля для отключения")
    ):
        """Отключить модуль"""
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Проверка, существует ли модуль
        if module not in self.bot.config.get("modules", {}):
            not_found_text = self.bot.language_manager.get_text(
                "commands.module.not_found", 
                guild_language,
                module=module
            )
            return await inter.response.send_message(not_found_text, ephemeral=True)
        
        # Инициализация состояний модулей для сервера, если их еще нет
        if inter.guild.id not in self.bot.module_states:
            self.bot.module_states[inter.guild.id] = {}
        
        # Отключение модуля
        self.bot.module_states[inter.guild.id][module] = False
        
        # Обновление состояния модуля в базе данных
        if self.bot.db:
            try:
                # Получение текущих состояний из базы данных
                result = await self.bot.db.fetchval(
                    "SELECT module_config FROM guilds WHERE id = $1",
                    inter.guild.id
                )
                
                if result is None:
                    # Если записи о сервере нет, создаем ее
                    await self.bot.db.execute(
                        """
                        INSERT INTO guilds (id, name, module_config)
                        VALUES ($1, $2, $3)
                        """,
                        inter.guild.id, inter.guild.name, {module: False}
                    )
                else:
                    # Если запись есть, обновляем конфигурацию
                    module_config = result or {}
                    module_config[module] = False
                    
                    await self.bot.db.execute(
                        """
                        UPDATE guilds
                        SET module_config = $1
                        WHERE id = $2
                        """,
                        module_config, inter.guild.id
                    )
            except Exception as e:
                logger.error(f"Ошибка при обновлении состояния модуля в базе данных: {e}")
        
        # Отправка сообщения об успешном отключении
        disabled_text = self.bot.language_manager.get_text(
            "commands.module.disabled", 
            guild_language,
            module=module
        )
        await inter.response.send_message(disabled_text)
    
    @commands.slash_command(name="language", description="Управление языком бота")
    async def language(self, inter: disnake.ApplicationCommandInteraction):
        """Группа команд для управления языком бота"""
        pass
    
    @language.sub_command(name="get", description="Узнать текущий язык")
    async def language_get(self, inter: disnake.ApplicationCommandInteraction):
        """Узнать текущий язык"""
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Получение названия языка
        language_names = {
            "ru": "Русский",
            "en": "English",
            "de": "Deutsch"
        }
        
        language_name = language_names.get(guild_language, guild_language)
        
        # Создание эмбеда
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("commands.language.title", guild_language),
            description=self.bot.language_manager.get_text(
                "commands.language.description", 
                guild_language,
                language=language_name
            ),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
        )
        
        # Добавление доступных языков
        available_languages = ", ".join([f"{code} ({name})" for code, name in language_names.items()])
        
        embed.add_field(
            name="Available Languages / Доступные языки",
            value=available_languages,
            inline=False
        )
        
        # Добавление инструкции
        embed.add_field(
            name="",
            value="Use `/language set <language>` to change the language\nИспользуйте `/language set <язык>` для изменения языка",
            inline=False
        )
        
        # Добавление футера
        embed.set_footer(text=f"{self.bot.user.name} | /language")
        embed.timestamp = datetime.utcnow()
        
        await inter.response.send_message(embed=embed)
    
    @language.sub_command(name="set", description="Установить язык бота")
    async def language_set(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        language: str = commands.Param(description="Код языка (ru, en, de)")
    ):
        """Установить язык бота"""
        # Проверка, существует ли язык
        available_languages = self.bot.language_manager.get_available_languages()
        
        if language not in available_languages:
            # Используем английский для сообщения об ошибке
            invalid_text = self.bot.language_manager.get_text(
                "commands.language.invalid", 
                "en",
                languages=", ".join(available_languages.keys())
            )
            return await inter.response.send_message(invalid_text, ephemeral=True)
        
        # Установка языка для сервера
        await self.bot.language_manager.set_guild_language(inter.guild.id, language)
        
        # Обновление языка в базе данных
        if self.bot.db:
            try:
                result = await self.bot.db.fetchval(
                    "SELECT id FROM guilds WHERE id = $1",
                    inter.guild.id
                )
                
                if result is None:
                    # Если записи о сервере нет, создаем ее
                    await self.bot.db.execute(
                        """
                        INSERT INTO guilds (id, name, language)
                        VALUES ($1, $2, $3)
                        """,
                        inter.guild.id, inter.guild.name, language
                    )
                else:
                    # Если запись есть, обновляем язык
                    await self.bot.db.execute(
                        """
                        UPDATE guilds
                        SET language = $1
                        WHERE id = $2
                        """,
                        language, inter.guild.id
                    )
            except Exception as e:
                logger.error(f"Ошибка при обновлении языка в базе данных: {e}")
        
        # Отправка сообщения об успешной установке языка
        set_text = self.bot.language_manager.get_text(
            "commands.language.set", 
            language,
            language=available_languages[language]
        )
        await inter.response.send_message(set_text)

# Setup function for the cog
def setup(bot):
    bot.add_cog(BaseCommands(bot))