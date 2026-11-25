"""
Generic repository base class for SQLAlchemy.

Provides common CRUD operations that concrete repositories can inherit.
"""

from collections.abc import Sequence
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from pycollector.db.base import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic SQLAlchemy repository for a single entity type.

    Parameters
    ----------
    session:
        An active SQLAlchemy session.
    model_class:
        The ORM model class this repository manages.
    """

    def __init__(self, session: Session, model_class: type[T]) -> None:
        self._session = session
        self._model_class = model_class

    def get_by_id(self, entity_id: int) -> T | None:
        return self._session.get(self._model_class, entity_id)

    def list_all(self) -> Sequence[T]:
        return self._session.scalars(select(self._model_class)).all()

    def add(self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        return entity

    def update(self, entity: T) -> T:
        self._session.merge(entity)
        self._session.flush()
        return entity

    def delete(self, entity: T) -> None:
        self._session.delete(entity)
        self._session.flush()