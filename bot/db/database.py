"""
Database connection and session management for the Discord bot.
"""
import os
import logging
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from bot.db.models import Base

logger = logging.getLogger(__name__)

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    # Construct from individual parts if not provided as a complete URL
    DB_HOST = os.getenv("PGHOST", "localhost")
    DB_PORT = os.getenv("PGPORT", "5432")
    DB_NAME = os.getenv("PGDATABASE", "discordbot")
    DB_USER = os.getenv("PGUSER", "postgres")
    DB_PASS = os.getenv("PGPASSWORD", "")
    
    # Ensure DATABASE_URL starts with postgresql+asyncpg://
    DATABASE_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set to True for SQL query logging
    pool_pre_ping=True,
    poolclass=NullPool,  # Use NullPool to avoid keeping connections open
)

# Create session factory
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.
    
    Usage:
    ```
    async with get_db_session() as session:
        # Use session here
    ```
    """
    session = async_session_factory()
    try:
        yield session
    finally:
        await session.close()

async def init_db():
    """
    Initialize the database by creating all tables.
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
