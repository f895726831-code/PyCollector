"""
Template for creating a new entity-specific collector.

Copy this file, rename the class, and fill in the parser logic.
"""

from datetime import UTC, datetime
from urllib.error import HTTPError, URLError

from pycollector.collector.base import BaseCollector
from pycollector.collector.context import EntityConfig
from pycollector.collector.protocol import ParseResult
from pycollector.core.errors import AppError
from pycollector.domain.enums import ErrorCode


class NewEntityCollector(BaseCollector):
    """Minimal collector scaffold for onboarding a new entity.

    Fill in the parser internals while preserving:
    1. Single fetch entry-point.
    2. Adapter-only fetch/parse responsibility.
    3. Standardised record output via ``_build_standard_record()``.
    """

    def __init__(self, entity_config: EntityConfig) -> None:
        super().__init__(entity_config)

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def fetch(self):
        """Fetch the source page/API for this entity."""
        fetched_at = datetime.now(UTC)
        try:
            response = self._http_get(self.source_url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise AppError(
                error_code=ErrorCode.SOURCE_FETCH_FAILED,
                error_message=f"failed to fetch {self.entity_code} source: {exc}",
                status_code=500,
            ) from exc
        return self._build_fetch_result(response, fetched_at)

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def parse(self, raw_content: str) -> ParseResult:
        """Parse raw content into structured records.

        Replace this with entity-specific parsing logic.
        """
        rows: list[dict] = self._extract_rows(raw_content)
        records = [
            self._build_standard_record(**row)
            for row in rows
        ]
        if not records:
            raise AppError(
                error_code=ErrorCode.PARSE_RESULT_EMPTY,
                error_message=f"no records found for {self.entity_code}",
                status_code=500,
            )
        return ParseResult(records=records, warnings=[])

    # ------------------------------------------------------------------
    # Custom parsing logic — replace with entity-specific code
    # ------------------------------------------------------------------

    def _extract_rows(self, raw_content: str) -> list[dict]:
        """Extract raw rows from the fetched content.

        TODO: Replace with your entity-specific parsing logic
        (HTML parsing, JSON extraction, PDF text extraction, etc.).
        """
        # Example: return a list of dicts with your domain fields
        return []