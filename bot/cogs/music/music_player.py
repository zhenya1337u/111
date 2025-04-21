import asyncio
import disnake
from disnake.ext import commands
import logging
import wavelink
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union, Any, Tuple
import re
import random

from bot.utils.logger import get_logger_for_cog

logger = get_logger_for_cog("music")

# Регулярные выражения для распознавания URL
SPOTIFY_REGEX = re.compile(r"https?://open.spotify.com/(?P<type>album|playlist|track)/(?P<id>[a-zA-Z0-9]+)")
YOUTUBE_REGEX = re.compile(r"^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$")
YOUTUBE_PLAYLIST_REGEX = re.compile(r"^(https?://)?(www\.)?youtube\.com/playlist\?list=.+$")

class MusicPlayer(wavelink.Player):
    """Расширенный класс плеера для управления музыкой"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queue = wavelink.Queue()
        self.waiting = False
        self.current = None
        self.bound_channel = None
        self.last_activity = datetime.utcnow()
        self.autoplay = False
        self.loop = False
        self.skip_votes = set()

class Music(commands.Cog):
    """Команды для воспроизведения музыки"""
    
    def __init__(self, bot):
        self.bot = bot
        self.players = {}  # guild_id -> MusicPlayer
        self.spotify_client_id = None
        self.spotify_client_secret = None
        self.youtube_api_key = None
        self.default_volume = 50
        
        # Запуск задачи инициализации
        asyncio.create_task(self.initialize())
    
    async def initialize(self):
        """Инициализация музыкального модуля"""
        # Ожидание готовности бота
        await self.bot.wait_until_ready()
        
        # Получение API ключей
        music_config = self.bot.config.get("modules", {}).get("music", {})
        
        self.default_volume = music_config.get("default_volume", 50)
        self.youtube_api_key = music_config.get("youtube_api_key", "")
        
        spotify_config = music_config.get("spotify", {})
        self.spotify_client_id = spotify_config.get("client_id", "")
        self.spotify_client_secret = spotify_config.get("client_secret", "")
        
        # Инициализация Wavelink
        nodes = [
            wavelink.Node(
                uri="http://localhost:2333",  # Адрес Lavalink сервера
                password="youshallnotpass",   # Пароль Lavalink сервера
                secure=False
            )
        ]
        
        # Подключение к узлам Lavalink
        try:
            await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)
            logger.info("Музыкальный модуль успешно инициализирован и подключен к Lavalink")
        except Exception as e:
            logger.error(f"Ошибка при инициализации музыкального модуля: {e}")
        
        # Запуск проверки неактивных плееров
        self.bot.loop.create_task(self.check_inactive_players())
    
    async def check_inactive_players(self):
        """Проверка и отключение неактивных плееров"""
        await self.bot.wait_until_ready()
        
        while not self.bot.is_closed():
            try:
                timeout_minutes = self.bot.config.get("modules", {}).get("music", {}).get("timeout_minutes", 5)
                timeout = timedelta(minutes=timeout_minutes)
                
                for guild_id, player in list(self.players.items()):
                    # Проверка активности плеера
                    if (
                        not player.is_playing() and 
                        not player.waiting and 
                        not player.queue and
                        datetime.utcnow() - player.last_activity > timeout
                    ):
                        try:
                            # Отключение от голосового канала
                            guild = self.bot.get_guild(guild_id)
                            if guild:
                                await player.disconnect()
                            
                            # Удаление плеера
                            del self.players[guild_id]
                            
                            logger.info(f"Отключен неактивный музыкальный плеер на сервере {guild_id}")
                        except Exception as e:
                            logger.error(f"Ошибка при отключении неактивного плеера на сервере {guild_id}: {e}")
            
            except Exception as e:
                logger.error(f"Ошибка при проверке неактивных плееров: {e}")
            
            # Проверка каждую минуту
            await asyncio.sleep(60)
    
    # ===== Обработчики событий Wavelink =====
    
    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, node: wavelink.Node):
        """Вызывается, когда узел Lavalink готов"""
        logger.info(f"Узел Wavelink {node.identifier} готов к работе")
    
    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        """Вызывается, когда начинается воспроизведение трека"""
        player = payload.player
        
        if not isinstance(player, MusicPlayer):
            return
        
        # Обновление текущего трека
        player.current = payload.track
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Очистка голосования за пропуск
        player.skip_votes.clear()
        
        # Отправка информации о текущем треке
        if player.bound_channel:
            try:
                # Определение языка сервера
                guild_language = await self.bot.get_guild_language(player.guild.id)
                
                # Создание эмбеда
                embed = disnake.Embed(
                    title=self.bot.language_manager.get_text("music.play.now_playing", guild_language),
                    description=f"**{payload.track.title}**",
                    color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('default', 0x3498db))
                )
                
                embed.add_field(
                    name=self.bot.language_manager.get_text("music.play.duration", guild_language),
                    value=self._format_duration(payload.track.length),
                    inline=True
                )
                
                embed.add_field(
                    name=self.bot.language_manager.get_text("music.play.author", guild_language),
                    value=payload.track.author,
                    inline=True
                )
                
                if payload.track.uri:
                    embed.add_field(
                        name=self.bot.language_manager.get_text("music.play.source", guild_language),
                        value=f"[{self.bot.language_manager.get_text('music.play.link', guild_language)}]({payload.track.uri})",
                        inline=True
                    )
                
                # Добавление обложки трека, если доступна
                if hasattr(payload.track, 'artwork') and payload.track.artwork:
                    embed.set_thumbnail(url=payload.track.artwork)
                
                # Добавление информации о запросившем пользователе
                if hasattr(payload.track, 'requested_by') and payload.track.requested_by:
                    embed.set_footer(
                        text=self.bot.language_manager.get_text(
                            "music.play.requested_by", 
                            guild_language,
                            user=str(payload.track.requested_by)
                        ),
                        icon_url=payload.track.requested_by.display_avatar.url
                    )
                
                # Отправка сообщения
                await player.bound_channel.send(embed=embed)
            
            except Exception as e:
                logger.error(f"Ошибка при отправке информации о текущем треке: {e}")
    
    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        """Вызывается, когда заканчивается воспроизведение трека"""
        player = payload.player
        
        if not isinstance(player, MusicPlayer):
            return
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Проверка, если трек должен повторяться
        if player.loop and payload.track and payload.reason == "FINISHED":
            # Добавление текущего трека обратно в очередь
            await player.queue.put_wait(payload.track)
            return
        
        # Проверка, если нужно включить автоматическое воспроизведение
        if (
            player.autoplay and 
            not player.queue and 
            payload.reason == "FINISHED" and 
            payload.track and 
            hasattr(payload.track, 'uri') and 
            payload.track.uri
        ):
            try:
                # Добавление похожего трека в очередь
                suggested = await self._get_related_track(payload.track)
                
                if suggested:
                    # Установка атрибута requested_by
                    if hasattr(payload.track, 'requested_by') and payload.track.requested_by:
                        suggested.requested_by = payload.track.requested_by
                    
                    await player.queue.put_wait(suggested)
                    
                    logger.info(f"Добавлен похожий трек в автоматическом режиме: {suggested.title}")
            
            except Exception as e:
                logger.error(f"Ошибка при получении похожего трека: {e}")
        
        # Если в очереди нет треков, сбрасываем текущий трек
        if not player.queue:
            player.current = None
    
    @commands.Cog.listener()
    async def on_wavelink_node_closed(self, node: wavelink.Node):
        """Вызывается, когда узел Lavalink закрывается"""
        logger.warning(f"Узел Wavelink {node.identifier} закрыт")
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Обработка изменений голосовых состояний"""
        if not member.guild:
            return
        
        if member.id == self.bot.user.id:
            # Бот был отключен от голосового канала
            if before.channel and not after.channel:
                guild_id = member.guild.id
                
                if guild_id in self.players:
                    player = self.players[guild_id]
                    
                    # Очистка очереди и остановка воспроизведения
                    player.queue.clear()
                    await player.stop()
                    player.current = None
                    
                    # Удаление плеера
                    del self.players[guild_id]
                    
                    logger.info(f"Плеер удален после отключения от голосового канала на сервере {guild_id}")
            
            return
        
        # Проверка, остался ли бот один в голосовом канале
        if (
            before.channel and 
            before.channel.guild.id in self.players and 
            len([m for m in before.channel.members if not m.bot]) == 0
        ):
            # Бот остался один в голосовом канале
            guild_id = before.channel.guild.id
            player = self.players[guild_id]
            
            # Приостановка воспроизведения
            if player.is_playing():
                await player.pause()
                player.waiting = True
                
                # Уведомление в текстовом канале, если он привязан
                if player.bound_channel:
                    try:
                        guild_language = await self.bot.get_guild_language(guild_id)
                        
                        empty_message = self.bot.language_manager.get_text(
                            "music.voice_empty", 
                            guild_language,
                            timeout=self.bot.config.get("modules", {}).get("music", {}).get("timeout_minutes", 5)
                        )
                        
                        await player.bound_channel.send(empty_message)
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления о пустом голосовом канале: {e}")
        
        # Проверка, если кто-то присоединился к голосовому каналу, где бот на паузе
        elif (
            after.channel and 
            after.channel.guild.id in self.players and 
            not member.bot
        ):
            guild_id = after.channel.guild.id
            player = self.players[guild_id]
            
            # Возобновление воспроизведения, если оно было приостановлено из-за пустого канала
            if player.is_paused() and player.waiting:
                await player.resume()
                player.waiting = False
                
                # Уведомление в текстовом канале, если он привязан
                if player.bound_channel:
                    try:
                        guild_language = await self.bot.get_guild_language(guild_id)
                        
                        resume_message = self.bot.language_manager.get_text(
                            "music.voice_resumed", 
                            guild_language
                        )
                        
                        await player.bound_channel.send(resume_message)
                    except Exception as e:
                        logger.error(f"Ошибка при отправке уведомления о возобновлении воспроизведения: {e}")
    
    # ===== Вспомогательные методы =====
    
    async def _get_player(self, inter: disnake.ApplicationCommandInteraction, create: bool = False) -> Optional[MusicPlayer]:
        """
        Получение или создание плеера для сервера
        
        Args:
            inter (disnake.ApplicationCommandInteraction): Объект взаимодействия
            create (bool): Создать плеер, если он не существует
        
        Returns:
            MusicPlayer: Плеер для сервера или None, если плеер не существует и create=False
        """
        guild_id = inter.guild.id
        
        if guild_id in self.players:
            return self.players[guild_id]
        
        if not create:
            return None
        
        # Создание нового плеера
        player = MusicPlayer(client=self.bot, guild_id=guild_id)
        player.bound_channel = inter.channel
        player.last_activity = datetime.utcnow()
        
        # Установка громкости по умолчанию
        await player.set_volume(self.default_volume)
        
        self.players[guild_id] = player
        return player
    
    async def _get_related_track(self, track):
        """
        Получение похожего трека для автоматического воспроизведения
        
        Args:
            track (wavelink.Playable): Текущий трек
        
        Returns:
            wavelink.Playable: Похожий трек или None, если не удалось найти
        """
        try:
            # Попытка найти похожий трек по YouTube
            if track.uri and YOUTUBE_REGEX.match(track.uri):
                # Поиск по автору и названию
                search_query = f"{track.author} music"
                
                search_results = await wavelink.Playable.search(search_query)
                
                if not search_results:
                    return None
                
                # Исключение текущего трека и выбор случайного из результатов
                filtered_results = [t for t in search_results if t.uri != track.uri]
                
                if filtered_results:
                    return random.choice(filtered_results)
            
            # Если не удалось найти по YouTube, поиск по названию и автору
            search_query = f"{track.author} - {track.title}"
            
            search_results = await wavelink.Playable.search(search_query)
            
            if search_results:
                return search_results[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при поиске похожего трека: {e}")
            return None
    
    def _format_duration(self, ms: int) -> str:
        """
        Форматирование продолжительности в формат ЧЧ:ММ:СС
        
        Args:
            ms (int): Продолжительность в миллисекундах
        
        Returns:
            str: Отформатированная продолжительность
        """
        seconds = ms // 1000
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    # ===== Команды для воспроизведения музыки =====
    
    @commands.slash_command(name="play", description="Воспроизвести музыку")
    async def play(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        query: str = commands.Param(description="Название трека, URL YouTube, Spotify, SoundCloud и т.д.")
    ):
        """Воспроизвести музыку"""
        # Проверка, находится ли пользователь в голосовом канале
        if not inter.author.voice:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_in_voice_text = self.bot.language_manager.get_text("music.play.not_in_voice", guild_language)
            return await inter.response.send_message(not_in_voice_text, ephemeral=True)
        
        # Отложенный ответ, так как поиск может занять время
        await inter.response.defer()
        
        # Получение или создание плеера
        player = await self._get_player(inter, create=True)
        
        # Подключение к голосовому каналу, если еще не подключен
        if not player.channel:
            try:
                await player.connect(inter.author.voice.channel)
                logger.info(f"Подключен к голосовому каналу {inter.author.voice.channel.id} на сервере {inter.guild.id}")
            except Exception as e:
                logger.error(f"Ошибка при подключении к голосовому каналу: {e}")
                
                guild_language = await self.bot.get_guild_language(inter.guild.id)
                error_text = self.bot.language_manager.get_text(
                    "music.play.error", 
                    guild_language,
                    error=str(e)
                )
                return await inter.followup.send(error_text)
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Обновление привязанного текстового канала
        player.bound_channel = inter.channel
        
        # Поиск и добавление треков в очередь
        try:
            # Проверка, является ли запрос URL
            if query.startswith(("http://", "https://")):
                # Проверка на Spotify URL
                spotify_match = SPOTIFY_REGEX.match(query)
                if spotify_match and (self.spotify_client_id and self.spotify_client_secret):
                    # Получение треков из Spotify
                    search_type = spotify_match.group("type")
                    spotify_id = spotify_match.group("id")
                    
                    # Логика для обработки Spotify URL будет добавлена позже
                    
                    guild_language = await self.bot.get_guild_language(inter.guild.id)
                    not_supported_text = self.bot.language_manager.get_text("music.play.spotify_not_supported", guild_language)
                    return await inter.followup.send(not_supported_text)
                
                # Проверка на YouTube плейлист
                elif YOUTUBE_PLAYLIST_REGEX.match(query):
                    # Получение треков из YouTube плейлиста
                    playlist = await wavelink.Playable.search(query)
                    
                    if not playlist:
                        guild_language = await self.bot.get_guild_language(inter.guild.id)
                        no_results_text = self.bot.language_manager.get_text(
                            "music.play.no_results", 
                            guild_language,
                            query=query
                        )
                        return await inter.followup.send(no_results_text)
                    
                    # Добавление треков в очередь
                    tracks_added = 0
                    
                    for track in playlist:
                        # Установка атрибута requested_by
                        track.requested_by = inter.author
                        
                        # Добавление трека в очередь
                        await player.queue.put_wait(track)
                        tracks_added += 1
                    
                    # Начало воспроизведения, если еще не играет
                    if not player.is_playing():
                        await player.play(await player.queue.get_wait())
                    
                    # Отправка сообщения об успешном добавлении плейлиста
                    guild_language = await self.bot.get_guild_language(inter.guild.id)
                    
                    embed = disnake.Embed(
                        title=self.bot.language_manager.get_text("music.playlist.title", guild_language),
                        description=self.bot.language_manager.get_text(
                            "music.playlist.description", 
                            guild_language,
                            name=query,
                            count=tracks_added
                        ),
                        color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
                    )
                    
                    return await inter.followup.send(embed=embed)
                
                else:
                    # Обычный URL (YouTube, SoundCloud и т.д.)
                    tracks = await wavelink.Playable.search(query)
                    
                    if not tracks:
                        guild_language = await self.bot.get_guild_language(inter.guild.id)
                        no_results_text = self.bot.language_manager.get_text(
                            "music.play.no_results", 
                            guild_language,
                            query=query
                        )
                        return await inter.followup.send(no_results_text)
                    
                    track = tracks[0]
            else:
                # Обычный поиск
                tracks = await wavelink.Playable.search(query)
                
                if not tracks:
                    guild_language = await self.bot.get_guild_language(inter.guild.id)
                    no_results_text = self.bot.language_manager.get_text(
                        "music.play.no_results", 
                        guild_language,
                        query=query
                    )
                    return await inter.followup.send(no_results_text)
                
                track = tracks[0]
            
            # Установка атрибута requested_by
            track.requested_by = inter.author
            
            # Добавление трека в очередь
            if player.is_playing():
                # Если уже играет, добавляем в очередь
                position = len(player.queue) + 1
                await player.queue.put_wait(track)
                
                # Отправка сообщения об успешном добавлении трека в очередь
                guild_language = await self.bot.get_guild_language(inter.guild.id)
                
                embed = disnake.Embed(
                    title=self.bot.language_manager.get_text("music.play.title", guild_language),
                    description=self.bot.language_manager.get_text(
                        "music.play.description", 
                        guild_language,
                        title=track.title
                    ),
                    color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
                )
                
                embed.add_field(
                    name=self.bot.language_manager.get_text("music.play.duration", guild_language),
                    value=self._format_duration(track.length),
                    inline=True
                )
                
                embed.add_field(
                    name=self.bot.language_manager.get_text("music.play.position", guild_language),
                    value=str(position),
                    inline=True
                )
                
                if track.uri:
                    embed.add_field(
                        name=self.bot.language_manager.get_text("music.play.source", guild_language),
                        value=f"[{self.bot.language_manager.get_text('music.play.link', guild_language)}]({track.uri})",
                        inline=True
                    )
                
                # Добавление обложки трека, если доступна
                if hasattr(track, 'artwork') and track.artwork:
                    embed.set_thumbnail(url=track.artwork)
                
                await inter.followup.send(embed=embed)
            else:
                # Если не играет, начинаем воспроизведение
                await player.play(track)
                
                # Сообщение о текущем треке отправится через обработчик события on_wavelink_track_start
                await inter.followup.send("▶️")
        
        except Exception as e:
            logger.error(f"Ошибка при добавлении трека: {e}")
            
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            error_text = self.bot.language_manager.get_text(
                "music.play.error", 
                guild_language,
                error=str(e)
            )
            await inter.followup.send(error_text)
    
    @commands.slash_command(name="skip", description="Пропустить текущий трек")
    async def skip(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        force: bool = commands.Param(False, description="Принудительно пропустить трек без голосования")
    ):
        """Пропустить текущий трек"""
        player = await self._get_player(inter)
        
        if not player or not player.is_playing():
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_playing_text = self.bot.language_manager.get_text("music.skip.no_tracks", guild_language)
            return await inter.response.send_message(not_playing_text, ephemeral=True)
        
        # Проверка, находится ли пользователь в голосовом канале с ботом
        if not inter.author.voice or inter.author.voice.channel != player.channel:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_in_voice_text = self.bot.language_manager.get_text("music.play.not_in_voice", guild_language)
            return await inter.response.send_message(not_in_voice_text, ephemeral=True)
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Получение прав пользователя
        is_dj = (
            inter.author.guild_permissions.manage_channels or 
            inter.author.guild_permissions.administrator
        )
        
        # Проверка, является ли пользователь запросившим трек
        is_requester = (
            hasattr(player.current, 'requested_by') and 
            player.current.requested_by and 
            player.current.requested_by.id == inter.author.id
        )
        
        # Проверка, нужно ли голосование
        if is_dj or is_requester or force:
            # Пропуск трека без голосования
            current_track = player.current
            
            await player.skip()
            
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            
            embed = disnake.Embed(
                title=self.bot.language_manager.get_text("music.skip.title", guild_language),
                description=self.bot.language_manager.get_text(
                    "music.skip.description", 
                    guild_language,
                    title=current_track.title if current_track else "Unknown"
                ),
                color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
            )
            
            return await inter.response.send_message(embed=embed)
        
        # Голосование за пропуск
        required_votes = len([m for m in player.channel.members if not m.bot]) // 2 + 1
        
        # Добавление голоса
        player.skip_votes.add(inter.author.id)
        
        # Проверка, достаточно ли голосов
        if len(player.skip_votes) >= required_votes:
            # Пропуск трека
            current_track = player.current
            
            await player.skip()
            
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            
            embed = disnake.Embed(
                title=self.bot.language_manager.get_text("music.skip.title", guild_language),
                description=self.bot.language_manager.get_text(
                    "music.skip.description", 
                    guild_language,
                    title=current_track.title if current_track else "Unknown"
                ),
                color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
            )
            
            return await inter.response.send_message(embed=embed)
        else:
            # Недостаточно голосов
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            
            embed = disnake.Embed(
                title=self.bot.language_manager.get_text("music.skip.vote_title", guild_language),
                description=self.bot.language_manager.get_text(
                    "music.skip.vote", 
                    guild_language,
                    votes=len(player.skip_votes),
                    required=required_votes
                ),
                color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
            )
            
            return await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="queue", description="Показать очередь воспроизведения")
    async def queue(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        page: int = commands.Param(1, description="Номер страницы", ge=1)
    ):
        """Показать очередь воспроизведения"""
        player = await self._get_player(inter)
        
        if not player:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_playing_text = self.bot.language_manager.get_text("music.queue.empty", guild_language)
            return await inter.response.send_message(not_playing_text, ephemeral=True)
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Получение языка сервера
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        # Создание эмбеда для очереди
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("music.queue.title", guild_language),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('info', 0x7289da))
        )
        
        # Добавление информации о текущем треке
        if player.current:
            embed.add_field(
                name=self.bot.language_manager.get_text(
                    "music.queue.now_playing", 
                    guild_language,
                    title=player.current.title,
                    duration=self._format_duration(player.current.length)
                ),
                value=f"**{player.current.author}**",
                inline=False
            )
        
        # Проверка, есть ли треки в очереди
        if not player.queue:
            embed.description = self.bot.language_manager.get_text("music.queue.empty", guild_language)
            return await inter.response.send_message(embed=embed)
        
        # Пагинация очереди
        items_per_page = 10
        pages = (len(player.queue) + items_per_page - 1) // items_per_page
        
        if page > pages:
            page = pages
        
        start = (page - 1) * items_per_page
        end = min(start + items_per_page, len(player.queue))
        
        # Формирование списка треков
        queue_list = []
        for i, track in enumerate(list(player.queue)[start:end], start=start+1):
            requester = f" ({track.requested_by})" if hasattr(track, 'requested_by') and track.requested_by else ""
            queue_list.append(f"**{i}.** {track.title} - {track.author} [{self._format_duration(track.length)}]{requester}")
        
        # Добавление списка треков в эмбед
        embed.description = "\n".join(queue_list)
        
        # Добавление информации о количестве треков и страницах
        embed.set_footer(text=self.bot.language_manager.get_text(
            "music.queue.page", 
            guild_language,
            page=page,
            total_pages=pages
        ))
        
        embed.add_field(
            name=self.bot.language_manager.get_text("music.queue.description", guild_language),
            value=self.bot.language_manager.get_text(
                "music.queue.total", 
                guild_language,
                count=len(player.queue)
            ),
            inline=False
        )
        
        await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="stop", description="Остановить воспроизведение и очистить очередь")
    async def stop(self, inter: disnake.ApplicationCommandInteraction):
        """Остановить воспроизведение и очистить очередь"""
        player = await self._get_player(inter)
        
        if not player or not player.is_playing():
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_playing_text = self.bot.language_manager.get_text("music.stop.not_playing", guild_language)
            return await inter.response.send_message(not_playing_text, ephemeral=True)
        
        # Проверка, находится ли пользователь в голосовом канале с ботом
        if not inter.author.voice or inter.author.voice.channel != player.channel:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_in_voice_text = self.bot.language_manager.get_text("music.play.not_in_voice", guild_language)
            return await inter.response.send_message(not_in_voice_text, ephemeral=True)
        
        # Очистка очереди и остановка воспроизведения
        player.queue.clear()
        await player.stop()
        player.current = None
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Отправка сообщения об успешной остановке
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("music.stop.title", guild_language),
            description=self.bot.language_manager.get_text("music.stop.description", guild_language),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
        )
        
        await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="volume", description="Установить громкость воспроизведения")
    async def volume(
        self, 
        inter: disnake.ApplicationCommandInteraction,
        volume: int = commands.Param(description="Громкость (0-100)", ge=0, le=100)
    ):
        """Установить громкость воспроизведения"""
        player = await self._get_player(inter)
        
        if not player:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_playing_text = self.bot.language_manager.get_text("music.volume.not_playing", guild_language)
            return await inter.response.send_message(not_playing_text, ephemeral=True)
        
        # Проверка, находится ли пользователь в голосовом канале с ботом
        if not inter.author.voice or inter.author.voice.channel != player.channel:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_in_voice_text = self.bot.language_manager.get_text("music.play.not_in_voice", guild_language)
            return await inter.response.send_message(not_in_voice_text, ephemeral=True)
        
        # Установка громкости
        await player.set_volume(volume)
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Отправка сообщения об успешной установке громкости
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("music.volume.title", guild_language),
            description=self.bot.language_manager.get_text(
                "music.volume.description", 
                guild_language,
                volume=volume
            ),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
        )
        
        await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="pause", description="Приостановить воспроизведение")
    async def pause(self, inter: disnake.ApplicationCommandInteraction):
        """Приостановить воспроизведение"""
        player = await self._get_player(inter)
        
        if not player or not player.is_playing():
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_playing_text = self.bot.language_manager.get_text("music.pause.not_playing", guild_language)
            return await inter.response.send_message(not_playing_text, ephemeral=True)
        
        # Проверка, находится ли пользователь в голосовом канале с ботом
        if not inter.author.voice or inter.author.voice.channel != player.channel:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_in_voice_text = self.bot.language_manager.get_text("music.play.not_in_voice", guild_language)
            return await inter.response.send_message(not_in_voice_text, ephemeral=True)
        
        # Проверка, что воспроизведение не приостановлено
        if player.is_paused():
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            already_paused_text = self.bot.language_manager.get_text("music.pause.already_paused", guild_language)
            return await inter.response.send_message(already_paused_text, ephemeral=True)
        
        # Приостановка воспроизведения
        await player.pause()
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Отправка сообщения об успешной приостановке
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("music.pause.title", guild_language),
            description=self.bot.language_manager.get_text("music.pause.description", guild_language),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
        )
        
        await inter.response.send_message(embed=embed)
    
    @commands.slash_command(name="resume", description="Возобновить воспроизведение")
    async def resume(self, inter: disnake.ApplicationCommandInteraction):
        """Возобновить воспроизведение"""
        player = await self._get_player(inter)
        
        if not player or not player.current:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_playing_text = self.bot.language_manager.get_text("music.resume.not_playing", guild_language)
            return await inter.response.send_message(not_playing_text, ephemeral=True)
        
        # Проверка, находится ли пользователь в голосовом канале с ботом
        if not inter.author.voice or inter.author.voice.channel != player.channel:
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_in_voice_text = self.bot.language_manager.get_text("music.play.not_in_voice", guild_language)
            return await inter.response.send_message(not_in_voice_text, ephemeral=True)
        
        # Проверка, что воспроизведение приостановлено
        if not player.is_paused():
            guild_language = await self.bot.get_guild_language(inter.guild.id)
            not_paused_text = self.bot.language_manager.get_text("music.resume.not_paused", guild_language)
            return await inter.response.send_message(not_paused_text, ephemeral=True)
        
        # Возобновление воспроизведения
        await player.resume()
        
        # Сброс флага waiting (если он был установлен из-за пустого голосового канала)
        player.waiting = False
        
        # Обновление времени активности
        player.last_activity = datetime.utcnow()
        
        # Отправка сообщения об успешном возобновлении
        guild_language = await self.bot.get_guild_language(inter.guild.id)
        
        embed = disnake.Embed(
            title=self.bot.language_manager.get_text("music.resume.title", guild_language),
            description=self.bot.language_manager.get_text("music.resume.description", guild_language),
            color=disnake.Color(self.bot.config.get('embed', {}).get('colors', {}).get('success', 0x2ecc71))
        )
        
        await inter.response.send_message(embed=embed)

# Setup function for the cog
def setup(bot):
    bot.add_cog(Music(bot))