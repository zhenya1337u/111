import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Dict, Any

def setup_logger(log_level: str = "INFO") -> None:
    """
    Настройка логирования
    
    Args:
        log_level (str): Уровень логирования. По умолчанию 'INFO'.
    """
    # Преобразование строкового уровня логирования в константу
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Недопустимый уровень логирования: {log_level}")
    
    # Создание директории для логов, если она не существует
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Формат логов
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Обработчик для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    
    # Обработчик для вывода в файл
    current_date = datetime.now().strftime("%Y-%m-%d")
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, f"bot_{current_date}.log"),
        maxBytes=10 * 1024 * 1024,  # 10 МБ
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(log_format)
    
    # Настройка корневого логгера
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Очистка обработчиков, если они уже существуют
    if root_logger.handlers:
        root_logger.handlers.clear()
    
    # Добавление обработчиков
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Настройка логгера для бота
    bot_logger = logging.getLogger("bot")
    bot_logger.setLevel(numeric_level)
    
    # Отключение логирования для некоторых модулей
    logging.getLogger("disnake").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    bot_logger.info("Логирование настроено")

def get_logger_for_cog(cog_name: str) -> logging.Logger:
    """
    Получение логгера для конкретного модуля (cog)
    
    Args:
        cog_name (str): Имя модуля
    
    Returns:
        logging.Logger: Настроенный логгер
    """
    return logging.getLogger(f"bot.cogs.{cog_name}")

class LoggingManager:
    """Класс для управления логированием событий на серверах"""
    
    def __init__(self, bot):
        """
        Инициализация менеджера логирования
        
        Args:
            bot: Экземпляр бота
        """
        self.bot = bot
        self.logger = logging.getLogger("bot.logging_manager")
        self.guild_configs: Dict[int, Dict[str, Any]] = {}  # guild_id -> logging_config
    
    async def load_guild_configs(self):
        """Загрузка конфигураций логирования для всех серверов"""
        # Здесь будет логика загрузки конфигураций из базы данных
        # Пока используем дефолтные настройки из общей конфигурации
        for guild in self.bot.guilds:
            self.guild_configs[guild.id] = self.bot.config.get("modules", {}).get("logging", {})
        
        self.logger.info(f"Конфигурации логирования загружены для {len(self.guild_configs)} серверов")
    
    async def get_log_channel(self, guild_id: int):
        """
        Получение канала для логирования на конкретном сервере
        
        Args:
            guild_id (int): ID сервера
        
        Returns:
            disnake.TextChannel: Канал для логирования
        """
        if guild_id not in self.guild_configs:
            return None
        
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return None
        
        log_channel_name = self.guild_configs[guild_id].get("log_channel_name", "bot-logs")
        
        # Поиск канала по имени
        log_channel = next((channel for channel in guild.text_channels if channel.name == log_channel_name), None)
        
        return log_channel
    
    async def is_event_enabled(self, guild_id: int, event_name: str) -> bool:
        """
        Проверка, включено ли логирование конкретного события на сервере
        
        Args:
            guild_id (int): ID сервера
            event_name (str): Имя события
        
        Returns:
            bool: True, если логирование события включено
        """
        if guild_id not in self.guild_configs:
            return False
        
        # Проверка, включено ли логирование вообще
        if not self.guild_configs[guild_id].get("enabled", False):
            return False
        
        # Проверка, включено ли логирование конкретного события
        events = self.guild_configs[guild_id].get("events", {})
        return events.get(event_name, False)
    
    async def log_event(self, guild_id: int, event_name: str, embed, content: str = None):
        """
        Логирование события на сервере
        
        Args:
            guild_id (int): ID сервера
            event_name (str): Имя события
            embed: Embed для отправки в канал логирования
            content (str, optional): Текстовое содержимое сообщения
        
        Returns:
            bool: True, если логирование прошло успешно
        """
        # Проверка, включено ли логирование события
        if not await self.is_event_enabled(guild_id, event_name):
            return False
        
        # Получение канала для логирования
        log_channel = await self.get_log_channel(guild_id)
        if not log_channel:
            return False
        
        # Отправка сообщения в канал логирования
        try:
            await log_channel.send(content=content, embed=embed)
            return True
        except Exception as e:
            self.logger.error(f"Ошибка при логировании события {event_name} на сервере {guild_id}: {e}")
            return False