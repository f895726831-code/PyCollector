"""
Entity context configuration.

Defines the frozen configuration objects that describe an entity
(e.g. a company, a data source) and its collector settings.
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, TypeVar

EntityCodeT = TypeVar("EntityCodeT", bound=StrEnum)


@dataclass(frozen=True, slots=True)
class CollectorConfig:
    """Per-collector overridable configuration.

    All fields are optional — missing values fall back to global defaults.
    """

    request_timeout_seconds: int | None = None
    api_path: str | None = None
    detail_path: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class EntityConfig(Generic[EntityCodeT]):
    """Immutable configuration for one entity (data source).

    Parameters
    ----------
    entity_code:
        Unique enum code identifying this entity.
    entity_name:
        Human-readable name.
    source_url:
        Primary URL for data collection.
    collector_config:
        Optional collector-level overrides.
    """

    entity_code: EntityCodeT
    entity_name: str
    source_url: str
    collector_config: CollectorConfig = field(default_factory=CollectorConfig)