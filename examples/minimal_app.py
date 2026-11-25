"""
Example: Minimal PyCollector application.

This demonstrates the full wiring: entity configs, collector
implementations, registry, and app factory.

Run with:
    uvicorn examples.minimal_app:app --reload
"""

from enum import StrEnum

from fastapi import APIRouter

from pycollector.collector.base import BaseCollector
from pycollector.collector.context import CollectorConfig, EntityConfig
from pycollector.collector.protocol import ParseResult
from pycollector.collector.registry import CollectorRegistry
from pycollector.core.settings import BaseCollectorSettings
from pycollector.main import create_app


# ---------------------------------------------------------------------------
# 1. Define entity codes
# ---------------------------------------------------------------------------


class SiteCode(StrEnum):
    EXAMPLE_COM = "EXAMPLE_COM"
    JSONPLACEHOLDER = "JSONPLACEHOLDER"


# ---------------------------------------------------------------------------
# 2. Implement collectors
# ---------------------------------------------------------------------------


class ExampleComCollector(BaseCollector):
    """Collector that fetches and parses example.com."""

    def fetch(self):
        fetched_at = self._utc_now()
        response = self._http_get(self.source_url)
        return self._build_fetch_result(response, fetched_at)

    def parse(self, raw_content: str) -> ParseResult:
        # Trivial parser: extract the <title> text
        import re
        match = re.search(r"<title>(.*?)</title>", raw_content, re.IGNORECASE)
        title = match.group(1) if match else "No title found"
        record = self._build_standard_record(title=title, content_length=len(raw_content))
        return ParseResult(records=[record], warnings=[])


class JsonPlaceholderCollector(BaseCollector):
    """Collector that fetches JSON from jsonplaceholder."""

    def fetch(self):
        fetched_at = self._utc_now()
        response = self._http_get(self.source_url)
        return self._build_fetch_result(response, fetched_at)

    def parse(self, raw_content: str) -> ParseResult:
        import json
        data = json.loads(raw_content)
        if isinstance(data, list):
            records = [
                self._build_standard_record(**item)
                for item in data[:5]  # Take first 5 posts
            ]
        else:
            records = [self._build_standard_record(**data)]
        return ParseResult(records=records, warnings=[])


# ---------------------------------------------------------------------------
# 3. Entity configs and registry
# ---------------------------------------------------------------------------


entity_configs = {
    "EXAMPLE_COM": EntityConfig(
        entity_code=SiteCode.EXAMPLE_COM,
        entity_name="Example.com",
        source_url="https://example.com",
        collector_config=CollectorConfig(request_timeout_seconds=10),
    ),
    "JSONPLACEHOLDER": EntityConfig(
        entity_code=SiteCode.JSONPLACEHOLDER,
        entity_name="JSONPlaceholder",
        source_url="https://jsonplaceholder.typicode.com/posts",
    ),
}

factories = {
    "EXAMPLE_COM": ExampleComCollector,
    "JSONPLACEHOLDER": JsonPlaceholderCollector,
}

registry = CollectorRegistry(entity_configs, factories)


# ---------------------------------------------------------------------------
# 4. API routes
# ---------------------------------------------------------------------------


api_router = APIRouter()


@api_router.get("/collectors")
def list_collectors():
    """List all registered collectors."""
    return {
        code: {
            "entity_code": reg.entity.entity_code,
            "entity_name": reg.entity.entity_name,
            "source_url": reg.entity.source_url,
            "collector_class": reg.collector_factory.__name__,
        }
        for code, reg in registry.get_registrations().items()
    }


@api_router.get("/collect/{entity_code}")
def collect_entity(entity_code: str):
    """Trigger a one-off collection for a given entity."""
    collector = registry.build_one(entity_code)
    fetch_result = collector.fetch()
    parse_result = collector.parse(fetch_result.raw_content)
    return {
        "entity_code": entity_code,
        "http_status": fetch_result.http_status,
        "record_count": len(parse_result.records),
        "warning_count": len(parse_result.warnings),
        "skipped_count": len(parse_result.skipped_items),
        "records": parse_result.records,
    }


# ---------------------------------------------------------------------------
# 5. Create the app
# ---------------------------------------------------------------------------


class MySettings(BaseCollectorSettings):
    """Application-specific settings."""
    model_config = BaseCollectorSettings.model_config
    app_name: str = "pycollector-example"


app = create_app(
    api_routers=[(api_router, "/api/v1", "collectors")],
    title="PyCollector Example",
)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)