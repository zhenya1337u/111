import json
import os
import logging
from typing import Dict, Any, Optional

# Настройка логирования
logger = logging.getLogger("bot.language")

class LanguageManager:
    """Класс для управления локализацией"""
    
    def __init__(self, bot):
        """
        Инициализация менеджера локализации
        
        Args:
            bot: Экземпляр бота
        """
        self.bot = bot
        self.logger = logging.getLogger("bot.language_manager")
        self.languages = {}
        self.user_languages = {}  # user_id -> language
        self.guild_languages = {}  # guild_id -> language
        
        # Загрузка языковых файлов
        self.load_languages()
    
    def load_languages(self):
        """Загрузка всех языковых файлов"""
        lang_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lang")
        
        # Проверка наличия директории
        if not os.path.exists(lang_dir):
            self.logger.error(f"Директория с языковыми файлами не найдена: {lang_dir}")
            return
        
        # Поиск и загрузка языковых файлов
        for filename in os.listdir(lang_dir):
            if filename.endswith(".json"):
                language_code = filename[:-5]  # Удаление расширения .json
                try:
                    with open(os.path.join(lang_dir, filename), 'r', encoding='utf-8') as file:
                        self.languages[language_code] = json.load(file)
                    self.logger.info(f"Загружен языковой файл: {language_code}")
                except Exception as e:
                    self.logger.error(f"Ошибка при загрузке языкового файла {filename}: {e}")
        
        # Проверка наличия языка по умолчанию
        default_language = self.bot.config.get("bot", {}).get("default_language", "ru")
        if default_language not in self.languages:
            self.logger.error(f"Язык по умолчанию {default_language} не найден!")
    
    async def load_user_languages(self):
        """Загрузка пользовательских языковых настроек из базы данных"""
        # Это будет реализовано позже, когда появится подключение к базе данных
        pass
    
    async def load_guild_languages(self):
        """Загрузка языковых настроек серверов из базы данных"""
        # Это будет реализовано позже, когда появится подключение к базе данных
        pass
    
    def get_text(self, key: str, language: str = None, **kwargs) -> str:
        """
        Получение локализованного текста по ключу
        
        Args:
            key (str): Ключ в формате "раздел.подраздел.параметр"
            language (str, optional): Код языка. По умолчанию используется язык по умолчанию.
            **kwargs: Параметры для форматирования текста
        
        Returns:
            str: Локализованный текст
        """
        if language is None:
            language = self.bot.config.get("bot", {}).get("default_language", "ru")
        
        if language not in self.languages:
            self.logger.warning(f"Язык {language} не найден, используется язык по умолчанию")
            language = self.bot.config.get("bot", {}).get("default_language", "ru")
        
        # Разбиение ключа на части
        parts = key.split('.')
        
        # Поиск текста по ключу
        current = self.languages[language]
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                self.logger.warning(f"Ключ {key} не найден в языке {language}")
                # Если ключ не найден в выбранном языке, пробуем язык по умолчанию
                if language != self.bot.config.get("bot", {}).get("default_language", "ru"):
                    return self.get_text(key, self.bot.config.get("bot", {}).get("default_language", "ru"), **kwargs)
                return f"Missing text: {key}"
        
        # Форматирование текста
        if isinstance(current, str):
            try:
                return current.format(**kwargs)
            except KeyError as e:
                self.logger.error(f"Ошибка при форматировании текста {key}: отсутствует параметр {e}")
                return current
            except Exception as e:
                self.logger.error(f"Ошибка при форматировании текста {key}: {e}")
                return current
        else:
            self.logger.error(f"Ключ {key} не является строкой")
            return f"Invalid text type: {key}"
    
    async def set_user_language(self, user_id: int, language: str) -> bool:
        """
        Установка языка для пользователя
        
        Args:
            user_id (int): ID пользователя
            language (str): Код языка
        
        Returns:
            bool: True, если язык установлен успешно
        """
        if language not in self.languages:
            self.logger.warning(f"Попытка установить несуществующий язык {language} для пользователя {user_id}")
            return False
        
        self.user_languages[user_id] = language
        
        # Сохранение в базу данных будет реализовано позже
        
        return True
    
    async def set_guild_language(self, guild_id: int, language: str) -> bool:
        """
        Установка языка для сервера
        
        Args:
            guild_id (int): ID сервера
            language (str): Код языка
        
        Returns:
            bool: True, если язык установлен успешно
        """
        if language not in self.languages:
            self.logger.warning(f"Попытка установить несуществующий язык {language} для сервера {guild_id}")
            return False
        
        self.guild_languages[guild_id] = language
        
        # Сохранение в базу данных будет реализовано позже
        
        return True
    
    async def get_user_language(self, user_id: int) -> str:
        """
        Получение языка пользователя
        
        Args:
            user_id (int): ID пользователя
        
        Returns:
            str: Код языка пользователя
        """
        # Проверка в кэше
        if user_id in self.user_languages:
            return self.user_languages[user_id]
        
        # Получение из базы данных будет реализовано позже
        
        # Возвращаем язык по умолчанию
        return self.bot.config.get("bot", {}).get("default_language", "ru")
    
    async def get_guild_language(self, guild_id: int) -> str:
        """
        Получение языка сервера
        
        Args:
            guild_id (int): ID сервера
        
        Returns:
            str: Код языка сервера
        """
        # Проверка в кэше
        if guild_id in self.guild_languages:
            return self.guild_languages[guild_id]
        
        # Получение из базы данных будет реализовано позже
        
        # Возвращаем язык по умолчанию
        return self.bot.config.get("bot", {}).get("default_language", "ru")
    
    def get_available_languages(self) -> Dict[str, str]:
        """
        Получение списка доступных языков
        
        Returns:
            dict: Словарь {код языка: название языка}
        """
        language_names = {
            "ru": "Русский",
            "en": "English",
            "de": "Deutsch"
        }
        
        return {lang: language_names.get(lang, lang) for lang in self.languages.keys()}