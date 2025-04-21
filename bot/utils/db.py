import logging
import asyncpg
import json
from typing import Optional, Dict, Any, List, Union

# Настройка логирования
logger = logging.getLogger("bot.db")


async def establish_db_connection(uri: str):
    """
    Установка соединения с базой данных

    Args:
        uri (str): URI для подключения к PostgreSQL

    Returns:
        asyncpg.Pool: Пул соединений с базой данных
    """
    try:
        # Создание пула соединений
        pool = await asyncpg.create_pool(
            uri, min_size=5, max_size=20, command_timeout=60
        )

        # Настройка расширения hstore
        async with pool.acquire() as connection:
            await connection.execute("CREATE EXTENSION IF NOT EXISTS hstore")

        # Настройка конвертации JSON
        await setup_json_conversion(pool)

        logger.info("Соединение с базой данных установлено")
        return pool
    except Exception as e:
        logger.error(f"Ошибка при подключении к базе данных: {e}", exc_info=True)
        raise


async def close_db_connection(pool):
    """
    Закрытие соединения с базой данных

    Args:
        pool (asyncpg.Pool): Пул соединений с базой данных
    """
    if pool:
        await pool.close()
        logger.info("Соединение с базой данных закрыто")


async def setup_json_conversion(pool):
    """
    Настройка конвертации JSON для PostgreSQL

    Args:
        pool (asyncpg.Pool): Пул соединений с базой данных
    """

    async def _encode_jsonb(value):
        return json.dumps(value)

    async def _decode_jsonb(value):
        if value is None:
            return None
        return json.loads(value)

    # Получаем соединение из пула
    async with pool.acquire() as connection:
        # Регистрация типов JSON
        await connection.set_type_codec(
            "jsonb", encoder=_encode_jsonb, decoder=_decode_jsonb, schema="pg_catalog"
        )
        await connection.set_type_codec(
            "json", encoder=_encode_jsonb, decoder=_decode_jsonb, schema="pg_catalog"
        )


async def execute_query(pool, query: str, *args):
    """
    Выполнение запроса к базе данных

    Args:
        pool (asyncpg.Pool): Пул соединений с базой данных
        query (str): SQL-запрос
        *args: Аргументы для SQL-запроса

    Returns:
        str: Результат выполнения запроса
    """
    try:
        async with pool.acquire() as connection:
            return await connection.execute(query, *args)
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса {query}: {e}")
        raise


async def fetch(pool, query: str, *args):
    """
    Получение данных из базы данных

    Args:
        pool (asyncpg.Pool): Пул соединений с базой данных
        query (str): SQL-запрос
        *args: Аргументы для SQL-запроса

    Returns:
        List[Record]: Результат выполнения запроса
    """
    try:
        async with pool.acquire() as connection:
            return await connection.fetch(query, *args)
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса {query}: {e}")
        raise


async def fetchrow(pool, query: str, *args):
    """
    Получение одной строки из базы данных

    Args:
        pool (asyncpg.Pool): Пул соединений с базой данных
        query (str): SQL-запрос
        *args: Аргументы для SQL-запроса

    Returns:
        Record: Результат выполнения запроса
    """
    try:
        async with pool.acquire() as connection:
            return await connection.fetchrow(query, *args)
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса {query}: {e}")
        raise


async def fetchval(pool, query: str, *args):
    """
    Получение одного значения из базы данных

    Args:
        pool (asyncpg.Pool): Пул соединений с базой данных
        query (str): SQL-запрос
        *args: Аргументы для SQL-запроса

    Returns:
        Any: Результат выполнения запроса
    """
    try:
        async with pool.acquire() as connection:
            return await connection.fetchval(query, *args)
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса {query}: {e}")
        raise


class DatabaseManager:
    """Класс для управления базой данных"""

    def __init__(self, bot):
        """
        Инициализация менеджера базы данных

        Args:
            bot: Экземпляр бота
        """
        self.bot = bot
        self.pool = bot.db
        self.logger = logging.getLogger("bot.db_manager")

    async def get_guild(self, guild_id: int):
        """
        Получение информации о сервере из базы данных

        Args:
            guild_id (int): ID сервера

        Returns:
            dict: Информация о сервере
        """
        query = """
            SELECT * FROM guilds
            WHERE id = $1
        """

        try:
            row = await fetchrow(self.pool, query, guild_id)
            return dict(row) if row else None
        except Exception as e:
            self.logger.error(
                f"Ошибка при получении информации о сервере {guild_id}: {e}"
            )
            return None

    async def create_guild(self, guild_id: int, guild_name: str):
        """
        Создание записи о сервере в базе данных

        Args:
            guild_id (int): ID сервера
            guild_name (str): Название сервера

        Returns:
            bool: True, если запись создана успешно
        """
        query = """
            INSERT INTO guilds (id, name, prefix, language)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (id) DO UPDATE
            SET name = $2
            RETURNING id
        """

        prefix = self.bot.config.get("bot", {}).get("prefix", "!")
        language = self.bot.config.get("bot", {}).get("default_language", "ru")

        try:
            result = await fetchval(
                self.pool, query, guild_id, guild_name, prefix, language
            )
            return result is not None
        except Exception as e:
            self.logger.error(f"Ошибка при создании записи о сервере {guild_id}: {e}")
            return False

    async def update_guild(self, guild_id: int, **kwargs):
        """
        Обновление информации о сервере в базе данных

        Args:
            guild_id (int): ID сервера
            **kwargs: Параметры для обновления

        Returns:
            bool: True, если запись обновлена успешно
        """
        # Формирование запроса на основе переданных параметров
        set_parts = []
        args = [guild_id]

        for i, (key, value) in enumerate(kwargs.items(), start=2):
            set_parts.append(f"{key} = ${i}")
            args.append(value)

        if not set_parts:
            return False

        query = f"""
            UPDATE guilds
            SET {', '.join(set_parts)}
            WHERE id = $1
            RETURNING id
        """

        try:
            result = await fetchval(self.pool, query, *args)
            return result is not None
        except Exception as e:
            self.logger.error(
                f"Ошибка при обновлении информации о сервере {guild_id}: {e}"
            )
            return False

    async def add_warning(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        reason: Optional[str] = None,
    ):
        """
        Добавление предупреждения пользователю

        Args:
            guild_id (int): ID сервера
            user_id (int): ID пользователя
            moderator_id (int): ID модератора
            reason (str, optional): Причина предупреждения

        Returns:
            int: ID предупреждения или None в случае ошибки
        """
        query = """
            INSERT INTO warnings (guild_id, user_id, moderator_id, reason)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """

        try:
            result = await fetchval(
                self.pool, query, guild_id, user_id, moderator_id, reason
            )
            return result
        except Exception as e:
            self.logger.error(
                f"Ошибка при добавлении предупреждения пользователю {user_id} на сервере {guild_id}: {e}"
            )
            return None

    async def remove_warning(self, warning_id: int):
        """
        Удаление предупреждения

        Args:
            warning_id (int): ID предупреждения

        Returns:
            bool: True, если предупреждение удалено успешно
        """
        query = """
            DELETE FROM warnings
            WHERE id = $1
            RETURNING id
        """

        try:
            result = await fetchval(self.pool, query, warning_id)
            return result is not None
        except Exception as e:
            self.logger.error(f"Ошибка при удалении предупреждения {warning_id}: {e}")
            return False

    async def get_warnings(self, guild_id: int, user_id: int):
        """
        Получение списка предупреждений пользователя

        Args:
            guild_id (int): ID сервера
            user_id (int): ID пользователя

        Returns:
            List[dict]: Список предупреждений
        """
        query = """
            SELECT * FROM warnings
            WHERE guild_id = $1 AND user_id = $2
            ORDER BY created_at DESC
        """

        try:
            rows = await fetch(self.pool, query, guild_id, user_id)
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(
                f"Ошибка при получении предупреждений пользователя {user_id} на сервере {guild_id}: {e}"
            )
            return []

    async def add_mute(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        reason: Optional[str] = None,
        expires_at=None,
    ):
        """
        Добавление мута пользователю

        Args:
            guild_id (int): ID сервера
            user_id (int): ID пользователя
            moderator_id (int): ID модератора
            reason (str, optional): Причина мута
            expires_at (datetime, optional): Время окончания мута

        Returns:
            int: ID мута или None в случае ошибки
        """
        query = """
            INSERT INTO mutes (guild_id, user_id, moderator_id, reason, expires_at, is_active)
            VALUES ($1, $2, $3, $4, $5, TRUE)
            RETURNING id
        """

        try:
            result = await fetchval(
                self.pool, query, guild_id, user_id, moderator_id, reason, expires_at
            )
            return result
        except Exception as e:
            self.logger.error(
                f"Ошибка при добавлении мута пользователю {user_id} на сервере {guild_id}: {e}"
            )
            return None

    async def remove_mute(self, mute_id: int):
        """
        Удаление мута

        Args:
            mute_id (int): ID мута

        Returns:
            bool: True, если мут удален успешно
        """
        query = """
            UPDATE mutes
            SET is_active = FALSE
            WHERE id = $1
            RETURNING id
        """

        try:
            result = await fetchval(self.pool, query, mute_id)
            return result is not None
        except Exception as e:
            self.logger.error(f"Ошибка при удалении мута {mute_id}: {e}")
            return False

    async def get_active_mute(self, guild_id: int, user_id: int):
        """
        Получение активного мута пользователя

        Args:
            guild_id (int): ID сервера
            user_id (int): ID пользователя

        Returns:
            dict: Информация о муте или None, если мут не найден
        """
        query = """
            SELECT * FROM mutes
            WHERE guild_id = $1 AND user_id = $2 AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """

        try:
            row = await fetchrow(self.pool, query, guild_id, user_id)
            return dict(row) if row else None
        except Exception as e:
            self.logger.error(
                f"Ошибка при получении активного мута пользователя {user_id} на сервере {guild_id}: {e}"
            )
            return None

    async def add_ban(
        self,
        guild_id: int,
        user_id: int,
        moderator_id: int,
        reason: Optional[str] = None,
        expires_at=None,
    ):
        """
        Добавление бана пользователю

        Args:
            guild_id (int): ID сервера
            user_id (int): ID пользователя
            moderator_id (int): ID модератора
            reason (str, optional): Причина бана
            expires_at (datetime, optional): Время окончания бана

        Returns:
            int: ID бана или None в случае ошибки
        """
        query = """
            INSERT INTO bans (guild_id, user_id, moderator_id, reason, expires_at, is_active)
            VALUES ($1, $2, $3, $4, $5, TRUE)
            RETURNING id
        """

        try:
            result = await fetchval(
                self.pool, query, guild_id, user_id, moderator_id, reason, expires_at
            )
            return result
        except Exception as e:
            self.logger.error(
                f"Ошибка при добавлении бана пользователю {user_id} на сервере {guild_id}: {e}"
            )
            return None

    async def remove_ban(self, ban_id: int):
        """
        Удаление бана

        Args:
            ban_id (int): ID бана

        Returns:
            bool: True, если бан удален успешно
        """
        query = """
            UPDATE bans
            SET is_active = FALSE
            WHERE id = $1
            RETURNING id
        """

        try:
            result = await fetchval(self.pool, query, ban_id)
            return result is not None
        except Exception as e:
            self.logger.error(f"Ошибка при удалении бана {ban_id}: {e}")
            return False

    async def get_active_ban(self, guild_id: int, user_id: int):
        """
        Получение активного бана пользователя

        Args:
            guild_id (int): ID сервера
            user_id (int): ID пользователя

        Returns:
            dict: Информация о бане или None, если бан не найден
        """
        query = """
            SELECT * FROM bans
            WHERE guild_id = $1 AND user_id = $2 AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """

        try:
            row = await fetchrow(self.pool, query, guild_id, user_id)
            return dict(row) if row else None
        except Exception as e:
            self.logger.error(
                f"Ошибка при получении активного бана пользователя {user_id} на сервере {guild_id}: {e}"
            )
            return None

    async def add_mod_role(self, guild_id: int, role_id: int, role_name: str):
        """
        Добавление роли модератора

        Args:
            guild_id (int): ID сервера
            role_id (int): ID роли
            role_name (str): Название роли

        Returns:
            int: ID записи или None в случае ошибки
        """
        query = """
            INSERT INTO mod_roles (guild_id, role_id, role_name)
            VALUES ($1, $2, $3)
            ON CONFLICT (guild_id, role_id) DO UPDATE
            SET role_name = $3
            RETURNING id
        """

        try:
            result = await fetchval(self.pool, query, guild_id, role_id, role_name)
            return result
        except Exception as e:
            self.logger.error(
                f"Ошибка при добавлении роли модератора {role_id} на сервере {guild_id}: {e}"
            )
            return None

    async def remove_mod_role(self, guild_id: int, role_id: int):
        """
        Удаление роли модератора

        Args:
            guild_id (int): ID сервера
            role_id (int): ID роли

        Returns:
            bool: True, если роль удалена успешно
        """
        query = """
            DELETE FROM mod_roles
            WHERE guild_id = $1 AND role_id = $2
            RETURNING id
        """

        try:
            result = await fetchval(self.pool, query, guild_id, role_id)
            return result is not None
        except Exception as e:
            self.logger.error(
                f"Ошибка при удалении роли модератора {role_id} на сервере {guild_id}: {e}"
            )
            return False

    async def get_mod_roles(self, guild_id: int):
        """
        Получение списка ролей модераторов

        Args:
            guild_id (int): ID сервера

        Returns:
            List[dict]: Список ролей модераторов
        """
        query = """
            SELECT * FROM mod_roles
            WHERE guild_id = $1
        """

        try:
            rows = await fetch(self.pool, query, guild_id)
            return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(
                f"Ошибка при получении ролей модераторов на сервере {guild_id}: {e}"
            )
            return []

    async def update_module_config(
        self, guild_id: int, module_name: str, config: Dict[str, Any]
    ):
        """
        Обновление конфигурации модуля

        Args:
            guild_id (int): ID сервера
            module_name (str): Название модуля
            config (dict): Конфигурация модуля

        Returns:
            bool: True, если конфигурация обновлена успешно
        """
        # Сначала получаем текущую конфигурацию модулей
        query_get = """
            SELECT module_config FROM guilds
            WHERE id = $1
        """

        try:
            current_config = await fetchval(self.pool, query_get, guild_id)

            if current_config is None:
                current_config = {}

            # Обновляем конфигурацию конкретного модуля
            if module_name not in current_config:
                current_config[module_name] = {}

            current_config[module_name].update(config)

            # Сохраняем обновленную конфигурацию
            query_update = """
                UPDATE guilds
                SET module_config = $1
                WHERE id = $2
                RETURNING id
            """

            result = await fetchval(self.pool, query_update, current_config, guild_id)
            return result is not None
        except Exception as e:
            self.logger.error(
                f"Ошибка при обновлении конфигурации модуля {module_name} на сервере {guild_id}: {e}"
            )
            return False

    async def get_module_config(self, guild_id: int, module_name: str):
        """
        Получение конфигурации модуля

        Args:
            guild_id (int): ID сервера
            module_name (str): Название модуля

        Returns:
            dict: Конфигурация модуля
        """
        query = """
            SELECT module_config FROM guilds
            WHERE id = $1
        """

        try:
            config = await fetchval(self.pool, query, guild_id)

            if config is None:
                return {}

            return config.get(module_name, {})
        except Exception as e:
            self.logger.error(
                f"Ошибка при получении конфигурации модуля {module_name} на сервере {guild_id}: {e}"
            )
            return {}
