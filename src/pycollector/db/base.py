"""SQLAlchemy declarative base.

Import this single base in all your ORM model modules.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy ORM models."""