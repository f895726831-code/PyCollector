"""PyCollector test fixtures.

Provides pytest fixtures for in-memory SQLite testing with FastAPI
TestClient integration.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from pycollector.db.base import Base
from pycollector.db.session import get_db_session, reset_session_factory


@pytest.fixture
def in_memory_db():
    """Create all tables in an in-memory SQLite database, yield, then drop."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(in_memory_db):
    """Yield a session connected to the in-memory database."""
    Session = sessionmaker(bind=in_memory_db, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app():
    """Create a FastAPI test app with overridden DB session."""
    from pycollector.main import create_app

    application = create_app()
    application.dependency_overrides[get_db_session] = _override_get_db
    return application


@pytest.fixture
def client(app):
    """Return a TestClient for the test app."""
    return TestClient(app)


# Internal override — set by in_memory_db fixture
_override_session = None


def _override_get_db():
    global _override_session
    yield _override_session


@pytest.fixture(autouse=True)
def _setup_override(db_session):
    global _override_session
    _override_session = db_session
    reset_session_factory()
    yield
    _override_session = None
    reset_session_factory()