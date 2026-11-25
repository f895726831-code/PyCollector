"""
Collector framework — protocol, base class, registry, and context.

The collector package implements a **Plugin / Adapter** architecture:

1. Define a ``Protocol`` your collectors must satisfy (``protocol.py``).
2. Subclass ``BaseCollector`` for HTTP, error, and observability helpers (``base.py``).
3. Register each entity → collector mapping in a ``CollectorRegistry`` (``registry.py``).
4. Describe each entity with an ``EntityConfig`` (``context.py``).
5. Start new collectors from the scaffold in ``templates/new_collector.py``.
"""