"""
Collector Protocol — the contract every collector must fulfil.

Define your own Protocol by extending :class:`Collector` with the
``fetch_*`` and ``parse_*`` methods your domain needs.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


@dataclass
class FetchResult:
    """Result of a single HTTP fetch operation."""

    raw_content: str
    source_url: str
    fetched_at: datetime
    http_status: int = 200
    content_encoding: str = "utf-8"
    headers: dict[str, str] | None = None


@dataclass
class ParseResult:
    """Result of parsing fetched content into structured records."""

    records: list[dict]
    warnings: list[dict] = field(default_factory=list)
    skipped_items: list[dict] = field(default_factory=list)
    execution_steps: list[dict] = field(default_factory=list)


class Collector(Protocol):
    """Protocol that every collector must implement.

    A collector is responsible for:
    1. Fetching raw data from a remote source.
    2. Parsing the raw data into structured records.

    Concrete implementations can add domain-specific methods beyond
    the Protocol minimum.
    """

    def fetch(self) -> FetchResult: ...

    def parse(self, raw_content: str) -> ParseResult: ...

    def detect_available_items(self) -> set[str]:
        """Optional: lightweight detection of what is currently published.

        The default returns an empty set.
        """
        return set()