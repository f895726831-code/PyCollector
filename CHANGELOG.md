# Changelog

All notable changes to PyCollector will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2026-11-25

### Added — Initial Release

**Core Framework**

- `AppError` with enum-based error codes and pre-built FastAPI exception handlers (`core/errors.py`)
- JSON-structured logging, alert enrichment, and observability summary builders (`core/observability.py`)
- `BaseCollectorSettings` with pydantic-settings and `.env` file support (`core/settings.py`)
- SQLAlchemy 2.0 declarative base and lazy-initialised session factory with FastAPI dependency generator (`db/`)
- Generic `BaseRepository[ModelT]` with CRUD operations (`repository/base.py`)
- Modular FastAPI router builder (`api/router.py`)
- Application factory `create_app()` with lifespan management (`main.py`)

**Collector Framework**

- `Collector` Protocol defining `fetch()` / `parse()` / `detect_available_items()` contract (`collector/protocol.py`)
- `BaseCollector` with HTTP helpers (GET/POST/bytes), SSL context, execution-step tracking, structured warning/skipped-item builders, and error standardisation (`collector/base.py`)
- `CollectorRegistry` implementing Factory + Registry pattern for plugin-style collector registration (`collector/registry.py`)
- `EntityConfig` and `CollectorConfig` frozen dataclasses for per-entity configuration (`collector/context.py`)
- New collector scaffold template (`collector/templates/new_collector.py`)

**Background Scheduler**

- `CollectionSchedulerService` with daemon-thread execution, weekly scheduling, per-entity enable/disable, slot-key deduplication, configurable retry, and structured observability integration (`scheduler/service.py`)
- `WeeklyScheduleConfig`, `RetryPolicyConfig`, `EntityScheduleConfig` builder dataclasses

**Examples**

- `minimal_app.py` — 5-minute quick-start with two demo collectors
- `dividend_collector_demo/` — Full-stack demo: HTML static + API JSON collectors, ORM models (current + history), upsert repository with hash-based dedup, collection execution service, REST API, runnable app
- `pdf_collector_demo.py` — PDF parsing collector with pypdf integration, regex extraction, and 7 common PDF parsing pitfalls documented

**Documentation**

- `docs/ONBOARDING_GUIDE.md` — Four-step onboarding workflow (feasibility → implementation → acceptance → closeout)
- `docs/EXTENDING.md` — Extension guide covering 6 extension points (new domains, entities, error codes, settings, scheduling, repositories)
- `docs/DOMAIN_PATTERNS.md` — Multi-domain pattern reference with comparison matrix across 4 data domains, 9 data carrier types, and 7 path patterns

**Skills**

- `skills/collector_onboarding/SKILL.md` — Feasibility assessment skill (≤3 HTTP requests)
- `skills/collector_acceptance/SKILL.md` — Acceptance testing skill with 4-phase workflow and verification matrix

**Test Infrastructure**

- Pytest fixtures for in-memory SQLite and FastAPI `TestClient` (`tests/conftest.py`)

---

[0.1.0]: https://github.com/pycollector/pycollector/releases/tag/v0.1.0