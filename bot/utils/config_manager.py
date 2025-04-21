import os
import yaml
import logging
from typing import Dict, Any, Optional

# Настройка логирования
logger = logging.getLogger("bot.config")

def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Загрузка конфигурации из YAML-файла или переменных окружения
    
    Args:
        config_path (str, optional): Путь к файлу конфигурации. По умолчанию 'bot/config/config.yaml'.
    
    Returns:
        dict: Словарь с конфигурацией
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.yaml")
    
    config = {}
    
    # Загрузка из файла
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file) or {}
        logger.info(f"Конфигурация загружена из {config_path}")
    except FileNotFoundError:
        logger.warning(f"Файл конфигурации {config_path} не найден")
    except yaml.YAMLError as e:
        logger.error(f"Ошибка при чтении YAML-файла {config_path}: {e}")
    
    # Переопределение из переменных окружения
    override_from_env(config)
    
    # Проверка и заполнение отсутствующих обязательных параметров
    validate_config(config)
    
    return config

def override_from_env(config: Dict[str, Any]) -> None:
    """
    Переопределение значений конфигурации из переменных окружения
    
    Args:
        config (dict): Словарь с конфигурацией для переопределения
    """
    # Токен бота
    if os.getenv("DISCORD_TOKEN"):
        if "bot" not in config:
            config["bot"] = {}
        config["bot"]["token"] = os.getenv("DISCORD_TOKEN")
    
    # URI базы данных
    if os.getenv("DATABASE_URL"):
        if "database" not in config:
            config["database"] = {}
        config["database"]["uri"] = os.getenv("DATABASE_URL")
    
    # URI Redis
    if os.getenv("REDIS_URL"):
        if "redis" not in config:
            config["redis"] = {}
        config["redis"]["uri"] = os.getenv("REDIS_URL")
    
    # Секретный ключ для веб-панели
    if os.getenv("SECRET_KEY"):
        if "web_panel" not in config:
            config["web_panel"] = {}
        config["web_panel"]["secret_key"] = os.getenv("SECRET_KEY")
    
    # ID владельцев бота
    if os.getenv("OWNER_IDS"):
        if "bot" not in config:
            config["bot"] = {}
        config["bot"]["owner_ids"] = [int(id.strip()) for id in os.getenv("OWNER_IDS").split(",") if id.strip()]
    
    # Тестовые серверы
    if os.getenv("TEST_GUILDS"):
        if "bot" not in config:
            config["bot"] = {}
        config["bot"]["test_guilds"] = [int(id.strip()) for id in os.getenv("TEST_GUILDS").split(",") if id.strip()]

def validate_config(config: Dict[str, Any]) -> None:
    """
    Проверка и заполнение отсутствующих обязательных параметров
    
    Args:
        config (dict): Словарь с конфигурацией для проверки
    """
    # Проверка основных разделов
    required_sections = ["bot", "database", "redis", "modules", "embed", "localization", "rate_limits", "security", "web_panel"]
    for section in required_sections:
        if section not in config:
            config[section] = {}
            logger.warning(f"Раздел {section} не найден в конфигурации, создан пустой раздел")
    
    # Проверка модулей
    required_modules = ["moderation", "verification", "anti_raid", "auto_mod", "logging", "music", "utility", "fun", "ai"]
    for module in required_modules:
        if module not in config["modules"]:
            config["modules"][module] = {"enabled": False}
            logger.warning(f"Модуль {module} не найден в конфигурации, создан со значением enabled=False")

def save_config(config: Dict[str, Any], config_path: Optional[str] = None) -> bool:
    """
    Сохранение конфигурации в YAML-файл
    
    Args:
        config (dict): Словарь с конфигурацией для сохранения
        config_path (str, optional): Путь к файлу конфигурации. По умолчанию 'bot/config/config.yaml'.
    
    Returns:
        bool: Успешность операции
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "config.yaml")
    
    try:
        with open(config_path, 'w', encoding='utf-8') as file:
            yaml.dump(config, file, default_flow_style=False, allow_unicode=True)
        logger.info(f"Конфигурация сохранена в {config_path}")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфигурации в {config_path}: {e}")
        return False

def update_dict(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
    """
    Рекурсивное обновление словаря
    
    Args:
        d (dict): Словарь для обновления
        u (dict): Словарь с обновлениями
    
    Returns:
        dict: Обновленный словарь
    """
    for k, v in u.items():
        if isinstance(v, dict) and k in d and isinstance(d[k], dict):
            d[k] = update_dict(d[k], v)
        else:
            d[k] = v
    return d

def get_guild_config(bot, guild_id: int) -> Dict[str, Any]:
    """
    Получение конфигурации для конкретного сервера
    
    Args:
        bot: Экземпляр бота
        guild_id (int): ID сервера
    
    Returns:
        dict: Конфигурация сервера
    """
    # Здесь будет логика получения конфигурации сервера из базы данных
    # Пока возвращаем дефолтную конфигурацию
    return bot.config

def update_guild_config(bot, guild_id: int, key: str, value: Any) -> bool:
    """
    Обновление конфигурации для конкретного сервера
    
    Args:
        bot: Экземпляр бота
        guild_id (int): ID сервера
        key (str): Ключ конфигурации в формате "раздел.подраздел.параметр"
        value: Значение для установки
    
    Returns:
        bool: Успешность операции
    """
    # Здесь будет логика обновления конфигурации сервера в базе данных
    # Пока просто возвращаем True
    return True