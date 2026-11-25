"""
Database session management.

Provides lazy-initialised engine/session-factory singletons and a
FastAPI-compatible ``get_db_session`` dependency generator.

Supports both SQLite (local dev / test) and PostgreSQL via the
``DATABASE_URL`` setting.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from pycollector.core.settings import get_settings

_engine = None
_session_factory = None


def get_engine():
    """Return the (lazily-created) SQLAlchemy engine singleton."""
    global _engine
    if _engine is None:
        settings = get_settings()
        engine_kwargs: dict = {"future": True}
        if settings.database_url.startswith("sqlite"):
            engine_kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in settings.database_url:
                engine_kwargs["poolclass"] = StaticPool
        _engine = create_engine(settings.database_url, **engine_kwargs)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the (lazily-created) session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _session_factory


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a session and closes it after the request."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_session_factory() -> None:
    """Reset engine and session factory (useful in tests)."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None