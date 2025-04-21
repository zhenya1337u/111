import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Dict, Optional

import disnake
from disnake.ext import commands
from dotenv import load_dotenv

# Добавление корневой директории проекта в sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.utils.config_manager import load_config
from bot.utils.logger import setup_logger
from bot.utils.db import establish_db_connection, close_db_connection
from bot.utils.language import LanguageManager

# Загрузка переменных окружения
load_dotenv()

# Получение конфигурации
config = load_config()

# Настройка логирования
setup_logger()
logger = logging.getLogger("bot")

class UniversalBot(commands.InteractionBot):
    def __init__(self, *args, **kwargs):
        # Определение интентов для бота
        intents = disnake.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.presences = True
        
        # Определение тестовых серверов
        test_guilds = config.get("bot", {}).get("test_guilds", [])
        
        # Инициализация бота
        super().__init__(
            intents=intents,
            test_guilds=test_guilds,
            sync_commands=True,
            reload=True,
            *args, **kwargs
        )
        
        # Дополнительные атрибуты
        self.start_time = datetime.utcnow()
        self.config = config
        self.db = None
        self.language_manager = LanguageManager(self)
        self.module_states: Dict[int, Dict[str, bool]] = {}  # guild_id -> {module_name: enabled}
        
        # Статус загрузки
        self.is_ready = False
        
    async def start_database(self):
        """Инициализация подключения к базе данных"""
        logger.info("Инициализация подключения к базе данных...")
        self.db = await establish_db_connection(self.config.get("database", {}).get("uri", ""))
        logger.info("Подключение к базе данных установлено")
    
    async def load_extensions(self):
        """Загрузка всех расширений (модулей) бота"""
        logger.info("Загрузка модулей бота...")
        
        # Список категорий модулей
        module_categories = [
            "cogs.moderation",
            "cogs.utility",
            "cogs.fun",
            "cogs.music",
            "cogs.ai",
            "cogs.admin",
            "cogs.logging",
            "cogs.verification",
        ]
        
        # Загрузка модулей
        for category in module_categories:
            try:
                self.load_extensions_from_dir(f"bot/{category}")
                logger.info(f"Модули из категории {category} загружены")
            except Exception as e:
                logger.error(f"Ошибка при загрузке модулей из категории {category}: {e}")
    
    def load_extensions_from_dir(self, directory):
        """Загрузка всех расширений из указанной директории"""
        if not os.path.exists(directory):
            logger.warning(f"Директория {directory} не найдена")
            return
        
        for filename in os.listdir(directory):
            if filename.endswith(".py") and not filename.startswith("_"):
                module_path = f"{directory.replace('/', '.')}.{filename[:-3]}"
                try:
                    self.load_extension(module_path)
                    logger.info(f"Модуль {module_path} загружен")
                except Exception as e:
                    logger.error(f"Ошибка при загрузке модуля {module_path}: {e}")
    
    async def load_module_states(self):
        """Загрузка состояний модулей из базы данных"""
        logger.info("Загрузка состояний модулей...")
        if not self.db:
            logger.warning("База данных не инициализирована, загрузка состояний модулей невозможна")
            return
        
        # Здесь будет код для загрузки состояний модулей из базы данных
        # Это будет реализовано позже
        
    async def on_ready(self):
        """Событие, срабатывающее при готовности бота к работе"""
        if self.is_ready:
            logger.info("Повторное подключение")
            return
        
        self.is_ready = True
        logger.info(f"Бот {self.user.name} (ID: {self.user.id}) запущен и готов к работе")
        
        # Установка статуса
        activity_type_str = config.get("bot", {}).get("activity", {}).get("type", "watching").lower()
        activity_name = config.get("bot", {}).get("activity", {}).get("name", "Disnake Bot | /help")
        
        activity_types = {
            "playing": disnake.ActivityType.playing,
            "listening": disnake.ActivityType.listening,
            "watching": disnake.ActivityType.watching,
            "competing": disnake.ActivityType.competing,
            "streaming": disnake.ActivityType.streaming
        }
        
        activity_type = activity_types.get(activity_type_str, disnake.ActivityType.listening)
        activity = disnake.Activity(type=activity_type, name=activity_name)
        
        await self.change_presence(status=disnake.Status.online, activity=activity)
        
        # Запуск инициализационных задач
        await self.start_database()
        await self.load_module_states()
        
        logger.info(f"Статистика: {len(self.guilds)} серверов, {len(self.users)} пользователей")
    
    async def on_guild_join(self, guild):
        """Событие, срабатывающее при присоединении бота к серверу"""
        logger.info(f"Бот присоединился к серверу: {guild.name} (ID: {guild.id})")
        
        # Здесь будет код для добавления сервера в базу данных
        # Это будет реализовано позже
    
    async def on_guild_remove(self, guild):
        """Событие, срабатывающее при удалении бота с сервера"""
        logger.info(f"Бот удален с сервера: {guild.name} (ID: {guild.id})")
        
        # Здесь будет код для обновления статуса сервера в базе данных
        # Это будет реализовано позже
    
    async def get_guild_language(self, guild_id: int) -> str:
        """Получение языка сервера"""
        # Пока что возвращаем язык по умолчанию
        # В будущем будет проверка в базе данных
        return config.get("bot", {}).get("default_language", "ru")
    
    async def close(self):
        """Закрытие соединений и очистка ресурсов при завершении работы бота"""
        logger.info("Закрытие бота...")
        
        # Закрытие соединения с базой данных
        if self.db:
            await close_db_connection(self.db)
            logger.info("Соединение с базой данных закрыто")
        
        await super().close()
        logger.info("Бот остановлен")

async def run_bot():
    """Запуск бота"""
    bot = UniversalBot()
    
    # Загрузка модулей
    await bot.load_extensions()
    
    # Получение токена
    token = os.getenv("DISCORD_TOKEN") or config.get("bot", {}).get("token", "")
    if not token:
        logger.error("Токен Discord не найден. Убедитесь, что он указан в переменных окружения или в config.yaml")
        return
    
    try:
        await bot.start(token)
    except disnake.LoginFailure:
        logger.error("Неверный токен Discord. Пожалуйста, проверьте токен и попробуйте снова.")
    except Exception as e:
        logger.error(f"Произошла ошибка при запуске бота: {e}")
    finally:
        if not bot.is_closed():
            await bot.close()

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Бот остановлен вручную")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")