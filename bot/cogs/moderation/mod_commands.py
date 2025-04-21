import logging
import disnake
from disnake.ext import commands
from datetime import datetime, timedelta
import asyncio
from typing import Optional
import re

from bot.utils.logger import get_logger_for_cog

logger = get_logger_for_cog("moderation")

class ModerationCommands(commands.Cog):
    """Команды модерации"""
    
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
        self.active_lockdowns = {}  # guild_id -> channel_id -> original_permissions

    # ===== Вспомогательные методы =====

    async def _check_mod_permissions(self, inter):
        """Проверка прав на использование модераторских команд"""
        # Проверка, является ли пользователь владельцем или администратором
        if inter.author.guild_permissions.administrator or inter.author.id in self.bot.config.get('bot', {}).get('owner_ids', []):
            return True
        
        # Проверка наличия роли модератора
        if not self.bot.db:
            logger.warning("База данных не инициализирована, проверка прав модератора невозможна")
            return False
        
        mod_roles = await self.bot.db.fetch(
            "SELECT role_id FROM mod_roles WHERE guild_id = $1",
            inter.guild.id
        )
        
        mod_role_ids = [r['role_id'] for r in mod_roles]
        user_role_ids = [role.id for role in inter.author.roles]
        
        return any(role_id in mod_role_ids for role_id in user_role_ids)

    async def _get_embed(self, inter, title_key, description_key, **kwargs):
        """Создание эмбеда с локализованным текстом"""
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        title = self.bot.language_manager.get_text(title_key, guild_language, **kwargs)
        description = self.bot.language_manager.get_text(description_key, guild_language, **kwargs)
        
        embed = disnake.Embed(
            title=title,
            description=description,
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('default', 0x3498db))
        )
        
        # Добавление временной метки
        if self.bot.config.get('embed', {}).get('timestamp', True):
            embed.timestamp = datetime.utcnow()
        
        # Добавление футера
        footer_text = self.bot.config.get('embed', {}).get('footer', {}).get('text', '')
        footer_icon = self.bot.config.get('embed', {}).get('footer', {}).get('icon_url', '')
        
        if footer_text:
            embed.set_footer(text=footer_text, icon_url=footer_icon if footer_icon else None)
        
        return embed

    async def _add_reason_field(self, embed, reason, guild_language):
        """Добавление поля с причиной в эмбед"""
        if reason:
            reason_text = self.bot.language_manager.get_text("moderation.ban.reason", guild_language, reason=reason)
        else:
            reason_text = self.bot.language_manager.get_text("moderation.ban.no_reason", guild_language)
        
        embed.add_field(name="", value=reason_text, inline=False)
        return embed
    
    async def _parse_time(self, time_str):
        """Парсинг строки времени в таймдельту"""
        if not time_str:
            return None
        
        time_regex = re.compile(r'(\d+)([smhdw])')
        matches = time_regex.findall(time_str.lower())
        
        if not matches:
            return None
        
        delta = timedelta()
        for amount, unit in matches:
            amount = int(amount)
            if unit == 's':
                delta += timedelta(seconds=amount)
            elif unit == 'm':
                delta += timedelta(minutes=amount)
            elif unit == 'h':
                delta += timedelta(hours=amount)
            elif unit == 'd':
                delta += timedelta(days=amount)
            elif unit == 'w':
                delta += timedelta(weeks=amount)
        
        return delta

    async def _format_duration(self, guild_language, duration):
        """Форматирование продолжительности для отображения"""
        if not duration:
            return self.bot.language_manager.get_text("moderation.ban.permanent", guild_language)
        
        seconds = duration.total_seconds()
        
        if seconds < 60:
            return f"{int(seconds)} сек."
        elif seconds < 3600:
            return f"{int(seconds / 60)} мин."
        elif seconds < 86400:
            return f"{int(seconds / 3600)} ч."
        elif seconds < 604800:
            return f"{int(seconds / 86400)} дн."
        else:
            return f"{int(seconds / 604800)} нед."

    # ===== Команды модерации =====

    @commands.slash_command(name="ban", description="Забанить пользователя на сервере")
    async def ban(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.User,
        reason: Optional[str] = None,
        delete_message_days: int = commands.Param(0, ge=0, le=7, description="Количество дней для удаления сообщений"),
        duration: Optional[str] = commands.Param(None, description="Продолжительность бана (1d, 7d, 1w и т.д.)")
    ):
        """Забанить пользователя на сервере"""
        # Проверка прав
        if not await self._check_mod_permissions(inter):
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            no_perm_text = self.bot.language_manager.get_text("moderation.ban.no_permission", guild_language)
            return await inter.response.send_message(no_perm_text, ephemeral=True)
        
        # Проверка, не пытается ли пользователь забанить себя
        if user.id == inter.author.id:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            self_ban_text = self.bot.language_manager.get_text("moderation.ban.self_ban", guild_language)
            return await inter.response.send_message(self_ban_text, ephemeral=True)
        
        # Проверка прав бота
        if not inter.guild.me.guild_permissions.ban_members:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            cannot_ban_text = self.bot.language_manager.get_text("moderation.ban.cannot_ban", guild_language)
            return await inter.response.send_message(cannot_ban_text, ephemeral=True)
        
        # Проверка иерархии ролей
        if (
            hasattr(user, "roles") and 
            user.top_role.position >= inter.guild.me.top_role.position and
            inter.guild.owner_id != user.id
        ):
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            cannot_ban_text = self.bot.language_manager.get_text("moderation.ban.cannot_ban", guild_language)
            return await inter.response.send_message(cannot_ban_text, ephemeral=True)
        
        # Парсинг продолжительности бана
        duration_delta = await self._parse_time(duration)
        expires_at = datetime.utcnow() + duration_delta if duration_delta else None
        
        # Преобразование продолжительности для отображения
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        duration_str = await self._format_duration(guild_language, duration_delta)
        
        # Создание эмбеда с информацией о бане
        embed = await self._get_embed(
            inter,
            "moderation.ban.title",
            "moderation.ban.description",
            user=str(user)
        )
        
        # Добавление поля с причиной
        await self._add_reason_field(embed, reason, guild_language)
        
        # Добавление поля с продолжительностью
        if duration:
            duration_text = self.bot.language_manager.get_text(
                "moderation.ban.duration", 
                guild_language, 
                duration=duration_str
            )
            embed.add_field(name="", value=duration_text, inline=False)
        
        # Отправка сообщения пользователю перед баном
        try:
            if reason:
                dm_text = self.bot.language_manager.get_text(
                    "moderation.ban.dm_message", 
                    guild_language, 
                    guild=inter.guild.name, 
                    reason=reason
                )
            else:
                dm_text = self.bot.language_manager.get_text(
                    "moderation.ban.dm_message", 
                    guild_language, 
                    guild=inter.guild.name, 
                    reason=self.bot.language_manager.get_text("moderation.ban.no_reason", guild_language)
                )
            
            try:
                await user.send(dm_text)
            except disnake.HTTPException:
                # Пользователь может иметь закрытые личные сообщения
                pass
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о бане пользователю {user.id}: {e}")
        
        # Бан пользователя
        try:
            await inter.guild.ban(
                user,
                reason=f"{inter.author} - {reason}" if reason else f"{inter.author}",
                delete_message_days=delete_message_days
            )
            
            # Ответ на команду
            await inter.response.send_message(embed=embed)
            
            # Логирование бана
            await self.log_ban(inter.guild, user, inter.author, reason, duration_str)
            
            # Добавление записи в базу данных
            # Здесь должен быть код для добавления записи о бане в базу данных
            
            # Если бан временный, запускаем таймер для снятия бана
            if duration_delta:
                asyncio.create_task(self.unban_timer(inter.guild.id, user.id, expires_at))
            
        except disnake.HTTPException as e:
            logger.error(f"Ошибка при бане пользователя {user.id}: {e}")
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text("commands.common.error", guild_language)
            await inter.response.send_message(error_text, ephemeral=True)
    
    async def unban_timer(self, guild_id, user_id, expires_at):
        """Таймер для снятия временного бана"""
        now = datetime.utcnow()
        if expires_at > now:
            wait_seconds = (expires_at - now).total_seconds()
            await asyncio.sleep(wait_seconds)
        
        guild = self.bot.get_guild(guild_id)
        if not guild:
            logger.error(f"Не удалось найти сервер {guild_id} для снятия бана")
            return
        
        try:
            # Проверка, забанен ли пользователь
            try:
                ban_entry = await guild.fetch_ban(disnake.Object(user_id))
            except disnake.NotFound:
                # Пользователь не забанен
                return
            
            # Снятие бана
            await guild.unban(disnake.Object(user_id), reason="Истек срок временного бана")
            
            # Логирование снятия бана
            guild_language = await self.bot.get_guild_language(guild.id)
            await self.log_unban(
                guild, 
                ban_entry.user, 
                self.bot.user, 
                self.bot.language_manager.get_text("moderation.unban.expired", guild_language)
            )
            
            # Обновление записи в базе данных
            # Здесь должен быть код для обновления записи о бане в базе данных
            
        except Exception as e:
            logger.error(f"Ошибка при снятии временного бана с пользователя {user_id} на сервере {guild_id}: {e}")

    @commands.slash_command(name="unban", description="Разбанить пользователя на сервере")
    async def unban(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        user_id: str = commands.Param(description="ID пользователя для разбана"),
        reason: Optional[str] = None
    ):
        """Разбанить пользователя на сервере"""
        # Проверка прав
        if not await self._check_mod_permissions(inter):
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            no_perm_text = self.bot.language_manager.get_text("moderation.unban.no_permission", guild_language)
            return await inter.response.send_message(no_perm_text, ephemeral=True)
        
        # Проверка прав бота
        if not inter.guild.me.guild_permissions.ban_members:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            cannot_unban_text = self.bot.language_manager.get_text("moderation.unban.cannot_unban", guild_language)
            return await inter.response.send_message(cannot_unban_text, ephemeral=True)
        
        try:
            # Проверка валидности ID
            user_id = int(user_id)
        except ValueError:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text("commands.common.error", guild_language)
            return await inter.response.send_message(error_text, ephemeral=True)
        
        # Проверка, забанен ли пользователь
        try:
            ban_entry = await inter.guild.fetch_ban(disnake.Object(user_id))
        except disnake.NotFound:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_banned_text = self.bot.language_manager.get_text("moderation.unban.not_banned", guild_language)
            return await inter.response.send_message(not_banned_text, ephemeral=True)
        
        # Разбан пользователя
        try:
            await inter.guild.unban(
                ban_entry.user,
                reason=f"{inter.author} - {reason}" if reason else f"{inter.author}"
            )
            
            # Создание эмбеда с информацией о разбане
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            embed = await self._get_embed(
                inter,
                "moderation.unban.title",
                "moderation.unban.description",
                user=str(ban_entry.user)
            )
            
            # Добавление поля с причиной
            await self._add_reason_field(embed, reason, guild_language)
            
            # Ответ на команду
            await inter.response.send_message(embed=embed)
            
            # Логирование разбана
            await self.log_unban(inter.guild, ban_entry.user, inter.author, reason)
            
            # Обновление записи в базе данных
            # Здесь должен быть код для обновления записи о бане в базе данных
            
        except disnake.HTTPException as e:
            logger.error(f"Ошибка при разбане пользователя {user_id}: {e}")
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text("commands.common.error", guild_language)
            await inter.response.send_message(error_text, ephemeral=True)

    @commands.slash_command(name="kick", description="Выгнать пользователя с сервера")
    async def kick(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        reason: Optional[str] = None
    ):
        """Выгнать пользователя с сервера"""
        # Проверка прав
        if not await self._check_mod_permissions(inter):
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            no_perm_text = self.bot.language_manager.get_text("moderation.kick.no_permission", guild_language)
            return await inter.response.send_message(no_perm_text, ephemeral=True)
        
        # Проверка, не пытается ли пользователь кикнуть себя
        if user.id == inter.author.id:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            self_kick_text = self.bot.language_manager.get_text("moderation.kick.self_kick", guild_language)
            return await inter.response.send_message(self_kick_text, ephemeral=True)
        
        # Проверка прав бота
        if not inter.guild.me.guild_permissions.kick_members:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            cannot_kick_text = self.bot.language_manager.get_text("moderation.kick.cannot_kick", guild_language)
            return await inter.response.send_message(cannot_kick_text, ephemeral=True)
        
        # Проверка иерархии ролей
        if (
            user.top_role.position >= inter.guild.me.top_role.position and
            inter.guild.owner_id != user.id
        ):
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            cannot_kick_text = self.bot.language_manager.get_text("moderation.kick.cannot_kick", guild_language)
            return await inter.response.send_message(cannot_kick_text, ephemeral=True)
        
        # Создание эмбеда с информацией о кике
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        embed = await self._get_embed(
            inter,
            "moderation.kick.title",
            "moderation.kick.description",
            user=str(user)
        )
        
        # Добавление поля с причиной
        await self._add_reason_field(embed, reason, guild_language)
        
        # Отправка сообщения пользователю перед киком
        try:
            if reason:
                dm_text = self.bot.language_manager.get_text(
                    "moderation.kick.dm_message", 
                    guild_language, 
                    guild=inter.guild.name, 
                    reason=reason
                )
            else:
                dm_text = self.bot.language_manager.get_text(
                    "moderation.kick.dm_message", 
                    guild_language, 
                    guild=inter.guild.name, 
                    reason=self.bot.language_manager.get_text("moderation.kick.no_reason", guild_language)
                )
            
            try:
                await user.send(dm_text)
            except disnake.HTTPException:
                # Пользователь может иметь закрытые личные сообщения
                pass
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения о кике пользователю {user.id}: {e}")
        
        # Кик пользователя
        try:
            await inter.guild.kick(
                user,
                reason=f"{inter.author} - {reason}" if reason else f"{inter.author}"
            )
            
            # Ответ на команду
            await inter.response.send_message(embed=embed)
            
            # Логирование кика
            # Здесь должен быть код для логирования кика
            
            # Добавление записи в базу данных
            # Здесь должен быть код для добавления записи о кике в базу данных
            
        except disnake.HTTPException as e:
            logger.error(f"Ошибка при кике пользователя {user.id}: {e}")
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text("commands.common.error", guild_language)
            await inter.response.send_message(error_text, ephemeral=True)

    @commands.slash_command(name="clear", description="Удалить сообщения из канала")
    async def clear(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        amount: int = commands.Param(description="Количество сообщений для удаления", ge=1, le=100),
        user: Optional[disnake.Member] = commands.Param(None, description="Удалять сообщения только от этого пользователя")
    ):
        """Удалить сообщения из канала"""
        # Проверка прав
        if not await self._check_mod_permissions(inter):
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            no_perm_text = self.bot.language_manager.get_text("moderation.clear.no_permission", guild_language)
            return await inter.response.send_message(no_perm_text, ephemeral=True)
        
        # Проверка прав бота
        if not inter.guild.me.guild_permissions.manage_messages:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text("commands.common.error", guild_language)
            return await inter.response.send_message(error_text, ephemeral=True)
        
        # Для уведомления пользователя о том, что команда выполняется
        await inter.response.defer()
        
        try:
            # Получение сообщений
            if user:
                # Если указан пользователь, получаем больше сообщений, чтобы отфильтровать только его
                messages = []
                async for message in inter.channel.history(limit=min(amount * 5, 500)):
                    if message.author.id == user.id:
                        messages.append(message)
                        if len(messages) >= amount:
                            break
            else:
                # Иначе просто получаем указанное количество сообщений
                messages = await inter.channel.history(limit=amount).flatten()
            
            # Проверка, есть ли сообщения
            if not messages:
                guild_language = await self.bot.get_guild_language(inter.guild.id)
                error_text = self.bot.language_manager.get_text("commands.common.error", guild_language)
                return await inter.followup.send(error_text, ephemeral=True)
            
            # Удаление сообщений
            deleted = await inter.channel.purge(limit=amount, check=lambda m: user is None or m.author.id == user.id)
            
            # Создание эмбеда с информацией об удаленных сообщениях
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            embed = await self._get_embed(
                inter,
                "moderation.clear.title",
                "moderation.clear.description",
                count=len(deleted)
            )
            
            # Ответ на команду
            await inter.followup.send(embed=embed, ephemeral=True)
            
        except disnake.HTTPException as e:
            logger.error(f"Ошибка при удалении сообщений: {e}")
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text(
                "moderation.clear.error", 
                guild_language, 
                error=str(e)
            )
            await inter.followup.send(error_text, ephemeral=True)

    # ===== Методы для логирования модераторских действий =====
    
    async def log_ban(self, guild, user, moderator, reason=None, duration=None):
        """Логирование бана в канал модерации"""
        if not guild or not user or not moderator:
            return
        
        guild_language = await self.bot.get_guild_language(guild.id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("logging.member_ban.title", guild_language),
            description=self.bot.language_manager.get_text("logging.member_ban.description", guild_language, user=str(user)),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('error', 0xe74c3c))
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("logging.member_ban.moderator", guild_language),
            value=str(moderator),
            inline=False
        )
        
        if reason:
            embed.add_field(
                name=self.bot.language_manager.get_text("logging.member_ban.reason", guild_language, reason=""),
                value=reason,
                inline=False
            )
        
        if duration:
            duration_text = self.bot.language_manager.get_text("moderation.ban.duration", guild_language, duration=duration)
            embed.add_field(name="", value=duration_text, inline=False)
        
        embed.timestamp = datetime.utcnow()
        
        # Получение канала для логирования
        log_channel_name = self.bot.config.get("modules", {}).get("moderation", {}).get("log_channel_name", "mod-logs")
        log_channel = next((channel for channel in guild.text_channels if channel.name == log_channel_name), None)
        
        if log_channel and log_channel.permissions_for(guild.me).send_messages:
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Ошибка при логировании бана в канал {log_channel.name}: {e}")
    
    async def log_unban(self, guild, user, moderator, reason=None):
        """Логирование разбана в канал модерации"""
        if not guild or not user or not moderator:
            return
        
        guild_language = await self.bot.get_guild_language(guild.id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("logging.member_unban.title", guild_language),
            description=self.bot.language_manager.get_text("logging.member_unban.description", guild_language, user=str(user)),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
        )
        
        embed.add_field(
            name=self.bot.language_manager.get_text("logging.member_unban.moderator", guild_language),
            value=str(moderator),
            inline=False
        )
        
        if reason:
            embed.add_field(
                name=self.bot.language_manager.get_text("logging.member_unban.reason", guild_language, reason=""),
                value=reason,
                inline=False
            )
        
        embed.timestamp = datetime.utcnow()
        
        # Получение канала для логирования
        log_channel_name = self.bot.config.get("modules", {}).get("moderation", {}).get("log_channel_name", "mod-logs")
        log_channel = next((channel for channel in guild.text_channels if channel.name == log_channel_name), None)
        
        if log_channel and log_channel.permissions_for(guild.me).send_messages:
            try:
                await log_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"Ошибка при логировании разбана в канал {log_channel.name}: {e}")

# Setup function for the cog
def setup(bot):
    bot.add_cog(ModerationCommands(bot))