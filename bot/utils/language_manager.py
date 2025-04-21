"""
Менеджер языковых файлов для бота
"""
import os
import json
import logging
from typing import Dict, Optional, Any, List

class LanguageManager:
    """Класс для управления языковыми файлами бота"""
    
    def __init__(self, language_dir: str = "bot/languages", default_language: str = "ru"):
        """
        Инициализация менеджера языков
        
        Args:
            language_dir (str): Директория с языковыми файлами
            default_language (str): Язык по умолчанию
        """
        self.language_dir = language_dir
        self.default_language = default_language
        self.languages: Dict[str, Dict[str, Any]] = {}
        self.guild_languages: Dict[int, str] = {}
        
        # Создание директории с языковыми файлами, если она не существует
        os.makedirs(language_dir, exist_ok=True)
        
        # Загрузка языковых файлов
        self._load_languages()
    
    def _load_languages(self) -> None:
        """Загрузка всех доступных языковых файлов"""
        try:
            for filename in os.listdir(self.language_dir):
                if filename.endswith('.json'):
                    language_code = filename.split('.')[0]  # Extract language code from filename
                    file_path = os.path.join(self.language_dir, filename)
                    
                    with open(file_path, 'r', encoding='utf-8') as file:
                        self.languages[language_code] = json.load(file)
                        logging.info(f"Loaded language file: {filename}")
        except Exception as e:
            logging.error(f"Error loading language files: {e}")
            
            # Создаем базовые языковые файлы если их нет
            self._create_default_language_files()
    
    def _create_default_language_files(self) -> None:
        """Создание базовых языковых файлов если их нет"""
        # Русский язык (по умолчанию)
        ru_lang = {
            "bot": {
                "name": "Discord Админ Бот",
                "description": "Многофункциональный бот для управления Discord серверами"
            },
            "commands": {
                "ping": {
                    "title": "📡 Проверка подключения",
                    "description": "🤖 Пинг: **{ping}ms**\n📡 API задержка: **{api_latency}ms**"
                },
                "stats": {
                    "title": "📊 Статистика бота",
                    "description": "Актуальная информация о работе бота",
                    "uptime": "⏱️ Время работы",
                    "servers": "🌐 Серверов",
                    "users": "👥 Пользователей",
                    "memory": "💾 Использование памяти"
                },
                "help": {
                    "title": "📚 Список команд",
                    "description": "Вот список доступных команд:",
                    "command_details": "📝 Информация о команде: {command}",
                    "command_not_found": "❌ Команда `{command}` не найдена",
                    "no_commands": "Нет доступных команд"
                },
                "module": {
                    "title": "🧩 Управление модулями",
                    "list": "Список всех доступных модулей и их статус:",
                    "status": "Статус: {status}",
                    "not_found": "❌ Модуль `{module}` не найден",
                    "enabled": "✅ Модуль `{module}` включен",
                    "disabled": "❌ Модуль `{module}` отключен"
                },
                "language": {
                    "title": "🌐 Управление языком",
                    "description": "Текущий язык: **{language}**",
                    "invalid": "❌ Неверный язык. Доступные языки: {languages}",
                    "set": "✅ Язык изменен на **{language}**"
                }
            },
            "errors": {
                "missing_permissions": "❌ У вас нет необходимых прав для использования этой команды",
                "bot_missing_permissions": "❌ У бота недостаточно прав для выполнения этой команды",
                "command_error": "❌ Произошла ошибка при выполнении команды: {error}",
                "database_error": "❌ Ошибка при работе с базой данных: {error}"
            }
        }
        
        # Английский язык
        en_lang = {
            "bot": {
                "name": "Discord Admin Bot",
                "description": "Multifunctional bot for Discord server management"
            },
            "commands": {
                "ping": {
                    "title": "📡 Connection Check",
                    "description": "🤖 Ping: **{ping}ms**\n📡 API latency: **{api_latency}ms**"
                },
                "stats": {
                    "title": "📊 Bot Statistics",
                    "description": "Current information about the bot",
                    "uptime": "⏱️ Uptime",
                    "servers": "🌐 Servers",
                    "users": "👥 Users",
                    "memory": "💾 Memory Usage"
                },
                "help": {
                    "title": "📚 Command List",
                    "description": "Here's a list of available commands:",
                    "command_details": "📝 Command Information: {command}",
                    "command_not_found": "❌ Command `{command}` not found",
                    "no_commands": "No commands available"
                },
                "module": {
                    "title": "🧩 Module Management",
                    "list": "List of all available modules and their status:",
                    "status": "Status: {status}",
                    "not_found": "❌ Module `{module}` not found",
                    "enabled": "✅ Module `{module}` enabled",
                    "disabled": "❌ Module `{module}` disabled"
                },
                "language": {
                    "title": "🌐 Language Management",
                    "description": "Current language: **{language}**",
                    "invalid": "❌ Invalid language. Available languages: {languages}",
                    "set": "✅ Language changed to **{language}**"
                }
            },
            "errors": {
                "missing_permissions": "❌ You don't have the necessary permissions to use this command",
                "bot_missing_permissions": "❌ The bot doesn't have enough permissions to execute this command",
                "command_error": "❌ An error occurred while executing the command: {error}",
                "database_error": "❌ Database error: {error}"
            }
        }
        
        # Немецкий язык
        de_lang = {
            "bot": {
                "name": "Discord Admin Bot",
                "description": "Multifunktionaler Bot für die Discord-Serververwaltung"
            },
            "commands": {
                "ping": {
                    "title": "📡 Verbindungsprüfung",
                    "description": "🤖 Ping: **{ping}ms**\n📡 API-Latenz: **{api_latency}ms**"
                },
                "stats": {
                    "title": "📊 Bot-Statistiken",
                    "description": "Aktuelle Informationen über den Bot",
                    "uptime": "⏱️ Betriebszeit",
                    "servers": "🌐 Server",
                    "users": "👥 Benutzer",
                    "memory": "💾 Speichernutzung"
                },
                "help": {
                    "title": "📚 Befehlsliste",
                    "description": "Hier ist eine Liste der verfügbaren Befehle:",
                    "command_details": "📝 Befehlsinformationen: {command}",
                    "command_not_found": "❌ Befehl `{command}` nicht gefunden",
                    "no_commands": "Keine Befehle verfügbar"
                },
                "module": {
                    "title": "🧩 Modulverwaltung",
                    "list": "Liste aller verfügbaren Module und ihr Status:",
                    "status": "Status: {status}",
                    "not_found": "❌ Modul `{module}` nicht gefunden",
                    "enabled": "✅ Modul `{module}` aktiviert",
                    "disabled": "❌ Modul `{module}` deaktiviert"
                },
                "language": {
                    "title": "🌐 Sprachverwaltung",
                    "description": "Aktuelle Sprache: **{language}**",
                    "invalid": "❌ Ungültige Sprache. Verfügbare Sprachen: {languages}",
                    "set": "✅ Sprache auf **{language}** geändert"
                }
            },
            "errors": {
                "missing_permissions": "❌ Sie haben nicht die erforderlichen Berechtigungen, um diesen Befehl zu verwenden",
                "bot_missing_permissions": "❌ Der Bot hat nicht genügend Berechtigungen, um diesen Befehl auszuführen",
                "command_error": "❌ Bei der Ausführung des Befehls ist ein Fehler aufgetreten: {error}",
                "database_error": "❌ Datenbankfehler: {error}"
            }
        }
        
        # Сохранение языковых файлов
        self._save_language_file('ru', ru_lang)
        self._save_language_file('en', en_lang)
        self._save_language_file('de', de_lang)
        
        # Загрузка созданных файлов
        self.languages = {
            'ru': ru_lang,
            'en': en_lang,
            'de': de_lang
        }
    
    def _save_language_file(self, language_code: str, data: Dict[str, Any]) -> None:
        """
        Сохранение языкового файла
        
        Args:
            language_code (str): Код языка
            data (Dict[str, Any]): Данные для сохранения
        """
        try:
            os.makedirs(self.language_dir, exist_ok=True)
            file_path = os.path.join(self.language_dir, f"{language_code}.json")
            
            with open(file_path, 'w', encoding='utf-8') as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
                
            logging.info(f"Created language file: {language_code}.json")
        except Exception as e:
            logging.error(f"Error creating language file {language_code}.json: {e}")
    
    def get_text(self, key_path: str, language: str, **kwargs) -> str:
        """
        Получение текста по ключу
        
        Args:
            key_path (str): Путь к ключу (например, "commands.ping.title")
            language (str): Код языка
            **kwargs: Параметры для форматирования строки
        
        Returns:
            str: Текст на указанном языке
        """
        # Если язык недоступен, используем язык по умолчанию
        if language not in self.languages:
            language = self.default_language
        
        # Разбиваем путь на части
        keys = key_path.split('.')
        
        # Получаем текст из языкового файла
        try:
            text = self.languages[language]
            for key in keys:
                text = text[key]
            
            # Форматируем строку с переданными параметрами
            if kwargs:
                return text.format(**kwargs)
            
            return text
        except (KeyError, TypeError):
            # Если ключ не найден в указанном языке, пробуем найти в языке по умолчанию
            try:
                text = self.languages[self.default_language]
                for key in keys:
                    text = text[key]
                
                # Форматируем строку с переданными параметрами
                if kwargs:
                    return text.format(**kwargs)
                
                return text
            except (KeyError, TypeError):
                # Если ключ не найден и в языке по умолчанию, возвращаем сам ключ
                return key_path
    
    def get_available_languages(self) -> Dict[str, str]:
        """
        Получение списка доступных языков
        
        Returns:
            Dict[str, str]: Словарь с кодами и названиями языков
        """
        language_names = {
            "ru": "Русский",
            "en": "English",
            "de": "Deutsch"
        }
        
        # Фильтруем только доступные языки
        available = {code: name for code, name in language_names.items() if code in self.languages}
        
        return available
    
    async def set_guild_language(self, guild_id: int, language: str) -> bool:
        """
        Установка языка для сервера
        
        Args:
            guild_id (int): ID сервера
            language (str): Код языка
        
        Returns:
            bool: Успешность операции
        """
        if language not in self.languages:
            return False
        
        self.guild_languages[guild_id] = language
        return True
    
    async def get_guild_language(self, guild_id: int) -> str:
        """
        Получение языка сервера
        
        Args:
            guild_id (int): ID сервера
        
        Returns:
            str: Код языка
        """
        return self.guild_languages.get(guild_id, self.default_language)