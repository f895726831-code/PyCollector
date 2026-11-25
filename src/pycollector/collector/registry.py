"""
Collector registry — maps entity codes to collector factories.

This implements a **Factory + Registry** pattern:
1. Register each entity code → collector class mapping.
2. At startup, ``build_registered_collectors()`` instantiates every
   registered collector with its entity configuration.

To add a new collector:
1. Create a class that satisfies the :class:`Collector` Protocol.
2. Register it in ``_COLLECTOR_FACTORIES``.
3. Add its entity configuration in ``get_entity_configs()``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pycollector.collector.context import EntityConfig


CollectorFactory = Callable[[EntityConfig], Any]


@dataclass(frozen=True, slots=True)
class CollectorRegistration:
    """A registered entity + its collector factory."""

    entity: EntityConfig
    collector_factory: CollectorFactory


class CollectorRegistry:
    """Manages collector registration and instantiation.

    Parameters
    ----------
    entity_configs:
        Dict mapping entity code values to :class:`EntityConfig`.
    factories:
        Dict mapping entity code values to collector factory callables.
    """

    def __init__(
        self,
        entity_configs: dict[str, EntityConfig],
        factories: dict[str, CollectorFactory],
    ) -> None:
        self._entity_configs = entity_configs
        self._factories = factories

    def get_registrations(self) -> dict[str, CollectorRegistration]:
        """Return all registered entity + factory pairings."""
        return {
            code: CollectorRegistration(
                entity=self._entity_configs[code],
                collector_factory=factory,
            )
            for code, factory in self._factories.items()
        }

    def build_all(self) -> dict[str, Any]:
        """Instantiate every registered collector.

        Returns a dict mapping entity codes to collector instances.
        """
        registrations = self.get_registrations()
        return {
            code: reg.collector_factory(reg.entity)
            for code, reg in registrations.items()
        }

    def build_one(self, entity_code: str) -> Any:
        """Instantiate a single registered collector by entity code."""
        reg = self.get_registrations()[entity_code]
        return reg.collector_factory(reg.entity)