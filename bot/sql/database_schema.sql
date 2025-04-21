-- Схема базы данных для универсального Discord бота

-- Создание таблицы серверов
CREATE TABLE IF NOT EXISTS guilds (
    id BIGINT PRIMARY KEY,  -- Discord Guild ID
    name VARCHAR(100) NOT NULL,
    prefix VARCHAR(10) DEFAULT '!',
    language VARCHAR(10) DEFAULT 'ru',
    log_channel_id BIGINT,
    welcome_channel_id BIGINT,
    welcome_message TEXT,
    mute_role_id BIGINT,
    verification_enabled BOOLEAN DEFAULT FALSE,
    verification_channel_id BIGINT,
    verification_role_id BIGINT,
    anti_raid_enabled BOOLEAN DEFAULT FALSE,
    anti_raid_threshold INTEGER DEFAULT 10,
    auto_mod_enabled BOOLEAN DEFAULT FALSE,
    caps_filter_enabled BOOLEAN DEFAULT FALSE,
    caps_filter_threshold FLOAT DEFAULT 0.7,
    module_config JSONB DEFAULT '{}',
    joined_at TIMESTAMP DEFAULT NOW()
);

-- Создание таблицы участников серверов
CREATE TABLE IF NOT EXISTS members (
    id BIGINT,  -- Discord User ID
    guild_id BIGINT REFERENCES guilds(id),
    username VARCHAR(100) NOT NULL,
    nickname VARCHAR(100),
    joined_at TIMESTAMP DEFAULT NOW(),
    last_active TIMESTAMP,
    experience INTEGER DEFAULT 0,
    level INTEGER DEFAULT 0,
    language VARCHAR(10),
    is_verified BOOLEAN DEFAULT FALSE,
    PRIMARY KEY (id, guild_id)
);

-- Создание таблицы модераторских ролей
CREATE TABLE IF NOT EXISTS mod_roles (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    role_id BIGINT NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    UNIQUE (guild_id, role_id)
);

-- Создание таблицы авто-ролей
CREATE TABLE IF NOT EXISTS auto_roles (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    role_id BIGINT NOT NULL,
    role_name VARCHAR(100) NOT NULL,
    UNIQUE (guild_id, role_id)
);

-- Создание таблицы кастомных команд
CREATE TABLE IF NOT EXISTS custom_commands (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    name VARCHAR(50) NOT NULL,
    response TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by BIGINT NOT NULL,  -- Discord User ID
    UNIQUE (guild_id, name)
);

-- Создание таблицы предупреждений
CREATE TABLE IF NOT EXISTS warnings (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,  -- Discord User ID
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id, guild_id) REFERENCES members(id, guild_id)
);

-- Создание таблицы мутов
CREATE TABLE IF NOT EXISTS mutes (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,  -- Discord User ID
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id, guild_id) REFERENCES members(id, guild_id)
);

-- Создание таблицы банов
CREATE TABLE IF NOT EXISTS bans (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    user_id BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,  -- Discord User ID
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (user_id, guild_id) REFERENCES members(id, guild_id)
);

-- Создание таблицы верификаций
CREATE TABLE IF NOT EXISTS verifications (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    user_id BIGINT NOT NULL,
    verification_code VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    completed BOOLEAN DEFAULT FALSE
);

-- Создание таблицы защиты от рейдов
CREATE TABLE IF NOT EXISTS raid_protection (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    triggered_at TIMESTAMP DEFAULT NOW(),
    triggered_by VARCHAR(100),  -- Описание того, что вызвало триггер
    action_taken VARCHAR(50) NOT NULL,  -- lockdown, notify, etc.
    resolved_at TIMESTAMP,
    resolved_by BIGINT  -- Discord User ID
);

-- Создание таблицы статистики серверов
CREATE TABLE IF NOT EXISTS guild_stats (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    date TIMESTAMP DEFAULT NOW(),
    member_count INTEGER DEFAULT 0,
    message_count INTEGER DEFAULT 0,
    command_count INTEGER DEFAULT 0,
    join_count INTEGER DEFAULT 0,
    leave_count INTEGER DEFAULT 0
);

-- Создание таблицы ролей по реакциям
CREATE TABLE IF NOT EXISTS reaction_roles (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    channel_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    emoji VARCHAR(100) NOT NULL,
    role_id BIGINT NOT NULL,
    UNIQUE (guild_id, message_id, emoji)
);

-- Создание таблицы музыкальных сессий
CREATE TABLE IF NOT EXISTS music_sessions (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    created_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP,
    songs_played INTEGER DEFAULT 0
);

-- Создание таблицы использования команд
CREATE TABLE IF NOT EXISTS command_usage (
    id SERIAL PRIMARY KEY,
    guild_id BIGINT REFERENCES guilds(id),
    user_id BIGINT NOT NULL,
    command_name VARCHAR(50) NOT NULL,
    used_at TIMESTAMP DEFAULT NOW()
);

-- Создание таблицы пользователей веб-панели
CREATE TABLE IF NOT EXISTS web_users (
    id BIGINT PRIMARY KEY,  -- Discord User ID
    username VARCHAR(100) NOT NULL,
    email VARCHAR(100),
    password_hash VARCHAR(256),
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP
);

-- Создание таблицы сессий веб-панели
CREATE TABLE IF NOT EXISTS web_sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id BIGINT REFERENCES web_users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL,
    ip_address VARCHAR(50),
    user_agent VARCHAR(200)
);

-- Создание таблицы логов резервного копирования
CREATE TABLE IF NOT EXISTS backup_logs (
    id SERIAL PRIMARY KEY,
    backup_time TIMESTAMP DEFAULT NOW(),
    filename VARCHAR(100) NOT NULL,
    size_bytes BIGINT NOT NULL,
    status VARCHAR(20) NOT NULL,  -- success, failed
    destination VARCHAR(100)  -- local, google_drive, etc.
);

-- Создание индексов для оптимизации запросов
CREATE INDEX IF NOT EXISTS idx_members_guild_id ON members(guild_id);
CREATE INDEX IF NOT EXISTS idx_warnings_guild_user ON warnings(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_mutes_guild_user ON mutes(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_mutes_active ON mutes(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_bans_guild_user ON bans(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_bans_active ON bans(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_custom_commands_guild ON custom_commands(guild_id);
CREATE INDEX IF NOT EXISTS idx_command_usage_guild ON command_usage(guild_id);
CREATE INDEX IF NOT EXISTS idx_command_usage_user ON command_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_verifications_guild_user ON verifications(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_verifications_active ON verifications(completed) WHERE completed = FALSE;
CREATE INDEX IF NOT EXISTS idx_guild_stats_guild_date ON guild_stats(guild_id, date);