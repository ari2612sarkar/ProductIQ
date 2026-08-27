from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager, contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from config.settings import settings
from db.schema.models import Base


def get_sync_database_url() -> str:
    """Get synchronous database URL for SQLAlchemy sync engine."""
    url = settings.database_url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://")
    return url


def get_async_database_url() -> str:
    """Get asynchronous database URL for SQLAlchemy async engine."""
    url = settings.database_url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    return url


# Sync engine for migrations and scripts
sync_engine = create_engine(
    get_sync_database_url(),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
    pool_pre_ping=True,
    echo=settings.is_development,
)

# Async engine for API
async_engine = create_async_engine(
    get_async_database_url(),
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_timeout=settings.database_pool_timeout,
    pool_recycle=settings.database_pool_recycle,
    pool_pre_ping=True,
    echo=settings.is_development,
)

# Session factories
SyncSessionLocal = sessionmaker(
    bind=sync_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# Read-only engine for SQL agent (separate connection pool)
def get_readonly_database_url() -> str:
    """Get read-only database URL."""
    if settings.database_readonly_url:
        return settings.database_readonly_url
    # Fallback: use main URL but we'll set read-only at session level
    return get_sync_database_url()


readonly_engine = create_engine(
    get_readonly_database_url(),
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
    echo=False,
)

ReadOnlySessionLocal = sessionmaker(
    bind=readonly_engine,
    class_=Session,
    expire_on_commit=False,
    autoflush=False,
)


@event.listens_for(readonly_engine, "before_cursor_execute")
def enforce_read_only(conn, cursor, statement, parameters, context, executemany):
    """Enforce read-only queries by checking for write operations."""
    write_keywords = [
        "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
        "GRANT", "REVOKE", "COPY", "VACUUM", "ANALYZE",
    ]
    stmt_upper = statement.strip().upper()
    for keyword in write_keywords:
        if stmt_upper.startswith(keyword) or f" {keyword} " in f" {stmt_upper} ":
            raise PermissionError(f"Write operation '{keyword}' not allowed on read-only connection")


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Get synchronous database session."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Get asynchronous database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def get_readonly_session() -> Generator[Session, None, None]:
    """Get read-only database session for SQL agent."""
    session = ReadOnlySessionLocal()
    try:
        # Set transaction to read-only
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Initialize database - create all tables."""
    Base.metadata.create_all(bind=sync_engine)


def drop_db() -> None:
    """Drop all tables (use with caution!)."""
    Base.metadata.drop_all(bind=sync_engine)


async def init_db_async() -> None:
    """Initialize database asynchronously."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database connections."""
    await async_engine.dispose()
    sync_engine.dispose()
    readonly_engine.dispose()


# Dependency for FastAPI
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session."""
    async with get_async_session() as session:
        yield session


def get_db_sync() -> Generator[Session, None, None]:
    """FastAPI dependency for sync database session."""
    with get_sync_session() as session:
        yield session


def get_readonly_db() -> Generator[Session, None, None]:
    """FastAPI dependency for read-only database session."""
    with get_readonly_session() as session:
        yield session
