"""
Base collector with HTTP helpers, execution-step tracking, and error builders.

Subclass :class:`BaseCollector` to create entity-specific collectors.
The base class provides:

- HTTP GET / POST helpers with timeout and SSL context.
- Execution-step tracking (start/finish/duration).
- Structured warning and skipped-item builders.
- Standardised error construction for parse and request failures.
- Structured logging integration.
"""

import json
import logging
import ssl
from datetime import UTC, datetime
from typing import Any
from urllib.request import Request, urlopen

from pycollector.collector.context import EntityConfig
from pycollector.collector.protocol import FetchResult
from pycollector.core.errors import AppError
from pycollector.core.observability import emit_structured_log
from pycollector.core.settings import get_settings
from pycollector.domain.enums import ErrorCode

logger = logging.getLogger(__name__)


class BaseCollector:
    """Foundation for entity-specific web data collectors.

    Parameters
    ----------
    entity_config:
        Immutable configuration for the entity this collector targets.
    """

    STEP_STATUS_SUCCESS = "SUCCESS"
    STEP_STATUS_SKIPPED = "SKIPPED"
    STEP_STATUS_FAILED = "FAILED"

    def __init__(self, entity_config: EntityConfig) -> None:
        self._entity_config = entity_config
        self._last_fetched_at: datetime | None = None
        self._http_request_count = 0
        self._ssl_context = self._create_ssl_context()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def entity_code(self) -> str:
        return self._entity_config.entity_code.value

    @property
    def entity_name(self) -> str:
        return self._entity_config.entity_name

    @property
    def source_url(self) -> str:
        return self._entity_config.source_url

    @property
    def request_timeout_seconds(self) -> int:
        return (
            self._entity_config.collector_config.request_timeout_seconds
            or get_settings().collector_http_timeout_seconds
        )

    @property
    def collector_config(self) -> Any:
        return self._entity_config.collector_config

    @property
    def collector_component_name(self) -> str:
        return self.__class__.__name__

    @property
    def http_request_count(self) -> int:
        return self._http_request_count

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _reset_collection_metrics(self) -> None:
        self._last_fetched_at = None
        self._http_request_count = 0

    # ------------------------------------------------------------------
    # SSL
    # ------------------------------------------------------------------

    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        """Return the SSL context used for all HTTP requests.

        Subclasses MAY override this to customise TLS behaviour
        (e.g. enable ``OP_LEGACY_SERVER_CONNECT`` for older servers).
        """
        return ssl.create_default_context()

    # ------------------------------------------------------------------
    # Time helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _utc_now() -> datetime:
        return datetime.now(UTC)

    def _start_step(self) -> datetime:
        return self._utc_now()

    def _remember_fetch(self, fetched_at: datetime) -> None:
        self._last_fetched_at = fetched_at

    def _resolve_collected_at(self) -> datetime:
        return self._last_fetched_at or datetime.now(UTC)

    # ------------------------------------------------------------------
    # Fetch result builder
    # ------------------------------------------------------------------

    def _build_fetch_result(
        self,
        response: dict[str, Any],
        fetched_at: datetime,
    ) -> FetchResult:
        self._remember_fetch(fetched_at)
        return FetchResult(
            raw_content=str(response["content"]),
            source_url=self.source_url,
            fetched_at=fetched_at,
            http_status=int(response.get("status", 200)),
            content_encoding=str(response.get("encoding", "utf-8")),
            headers=response.get("headers"),
        )

    # ------------------------------------------------------------------
    # Record builder (override in subclass for domain-specific fields)
    # ------------------------------------------------------------------

    def _build_standard_record(self, **fields: Any) -> dict[str, Any]:
        """Build a standard record dict. Override to add domain fields."""
        return {
            "entity_code": self.entity_code,
            "entity_name": self.entity_name,
            "source_url": self.source_url,
            "collected_at": self._resolve_collected_at(),
            **fields,
        }

    # ------------------------------------------------------------------
    # Dict utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_dict(payload: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in payload.items()
            if value is not None and value != []
        }

    # ------------------------------------------------------------------
    # Execution steps
    # ------------------------------------------------------------------

    def _build_execution_step(
        self,
        *,
        step: str,
        status: str,
        message: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_ms: int | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        normalized_started_at = started_at or self._utc_now()
        normalized_finished_at = finished_at or self._utc_now()
        if normalized_finished_at < normalized_started_at:
            normalized_finished_at = normalized_started_at
        normalized_duration_ms = (
            duration_ms
            if duration_ms is not None
            else int(
                max(
                    (normalized_finished_at - normalized_started_at).total_seconds() * 1000,
                    0,
                )
            )
        )
        return self._clean_dict(
            {
                "step": step,
                "status": status,
                "message": message,
                "started_at": normalized_started_at.isoformat(),
                "finished_at": normalized_finished_at.isoformat(),
                "duration_ms": normalized_duration_ms,
                **extra,
            }
        )

    # ------------------------------------------------------------------
    # Warning / skipped-item builders
    # ------------------------------------------------------------------

    def _build_warning(
        self,
        *,
        reason_code: str,
        message: str,
        step: str,
        item_type: str,
        **extra: Any,
    ) -> dict[str, Any]:
        return self._clean_dict(
            {
                "entity_code": self.entity_code,
                "reason_code": reason_code,
                "message": message,
                "step": step,
                "item_type": item_type,
                **extra,
            }
        )

    def _build_skipped_item(
        self,
        *,
        reason_code: str,
        message: str,
        step: str,
        item_type: str,
        **extra: Any,
    ) -> dict[str, Any]:
        return self._clean_dict(
            {
                "entity_code": self.entity_code,
                "reason_code": reason_code,
                "message": message,
                "step": step,
                "item_type": item_type,
                **extra,
            }
        )

    # ------------------------------------------------------------------
    # Failure detail builder
    # ------------------------------------------------------------------

    def _build_failure_detail(
        self,
        *,
        failure_step: str,
        warnings: list[dict] | None = None,
        skipped_items: list[dict] | None = None,
        execution_steps: list[dict] | None = None,
        failed_count: int | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        normalized_warnings = list(warnings or [])
        normalized_skipped_items = list(skipped_items or [])
        normalized_steps = list(execution_steps or [])
        return self._clean_dict(
            {
                "failure_step": failure_step,
                "failed_count": failed_count
                if failed_count is not None
                else max(len(normalized_skipped_items), len(normalized_warnings), 1),
                "warning_count": len(normalized_warnings),
                "warnings": normalized_warnings,
                "skipped_count": len(normalized_skipped_items),
                "skipped_items": normalized_skipped_items,
                "execution_steps": normalized_steps,
                **extra,
            }
        )

    # ------------------------------------------------------------------
    # Error builders
    # ------------------------------------------------------------------

    def _standardize_app_error(
        self,
        exc: AppError,
        *,
        failure_step: str,
        warnings: list[dict] | None = None,
        skipped_items: list[dict] | None = None,
        execution_steps: list[dict] | None = None,
        **extra: Any,
    ) -> AppError:
        detail = dict(exc.detail)
        merged_warnings = list(detail.get("warnings") or warnings or [])
        merged_skipped_items = list(detail.get("skipped_items") or skipped_items or [])
        merged_execution_steps = list(detail.get("execution_steps") or execution_steps or [])
        merged_extra = {
            key: value
            for key, value in detail.items()
            if key
            not in {
                "failure_step",
                "failed_count",
                "warning_count",
                "warnings",
                "skipped_count",
                "skipped_items",
                "execution_steps",
            }
        }
        merged_extra.update(extra)
        exc.detail = self._build_failure_detail(
            failure_step=str(detail.get("failure_step") or failure_step),
            warnings=merged_warnings,
            skipped_items=merged_skipped_items,
            execution_steps=merged_execution_steps,
            failed_count=(
                int(detail["failed_count"])
                if detail.get("failed_count") is not None
                else None
            ),
            **merged_extra,
        )
        self._log_collector_issue(
            event="collector_app_error_standardized",
            event_category="collector_failed",
            error_code=exc.error_code,
            error_message=exc.error_message,
            detail=exc.detail,
        )
        return exc

    def _build_parse_error(
        self,
        *,
        failure_step: str,
        message: str,
        error_code: ErrorCode = ErrorCode.PARSE_RESULT_EMPTY,
        warnings: list[dict] | None = None,
        skipped_items: list[dict] | None = None,
        execution_steps: list[dict] | None = None,
        **extra: Any,
    ) -> AppError:
        detail = self._build_failure_detail(
            failure_step=failure_step,
            warnings=warnings,
            skipped_items=skipped_items,
            execution_steps=execution_steps,
            **extra,
        )
        self._log_collector_issue(
            event="collector_parse_error",
            event_category="collector_failed",
            error_code=error_code,
            error_message=message,
            detail=detail,
        )
        return AppError(
            error_code=error_code,
            error_message=message,
            status_code=500,
            detail=detail,
        )

    def _build_request_failure_error(
        self,
        *,
        failure_step: str,
        request_url: str,
        message: str,
        exc: Exception,
        warnings: list[dict] | None = None,
        skipped_items: list[dict] | None = None,
        execution_steps: list[dict] | None = None,
    ) -> AppError:
        error_text = self._format_request_error(exc)
        failed_step = self._build_execution_step(
            step=failure_step,
            status=self.STEP_STATUS_FAILED,
            request_url=request_url,
            timeout_seconds=self.request_timeout_seconds,
            error_type=type(exc).__name__,
            error_message=error_text,
        )
        merged_steps = list(execution_steps or [])
        merged_steps.append(failed_step)
        detail = self._build_failure_detail(
            failure_step=failure_step,
            warnings=warnings,
            skipped_items=skipped_items,
            execution_steps=merged_steps,
            request_url=request_url,
            request_timeout_seconds=self.request_timeout_seconds,
            error_type=type(exc).__name__,
        )
        self._log_collector_issue(
            event="collector_request_failed",
            event_category="collector_failed",
            error_code=ErrorCode.SOURCE_FETCH_FAILED,
            error_message=f"{message}: {error_text}",
            detail=detail,
        )
        return AppError(
            error_code=ErrorCode.SOURCE_FETCH_FAILED,
            error_message=f"{message}: {error_text}",
            status_code=500,
            detail=detail,
        )

    def _format_request_error(self, exc: Exception) -> str:
        if isinstance(exc, TimeoutError):
            return (
                f"request timed out after {self.request_timeout_seconds}s "
                f"({type(exc).__name__})"
            )
        message = str(exc).strip()
        if not message:
            return type(exc).__name__
        return f"{type(exc).__name__}: {message}"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _http_get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._http_request_count += 1
        request_headers = {"User-Agent": "Mozilla/5.0"}
        if headers:
            request_headers.update(headers)
        request = Request(url=url, headers=request_headers, method="GET")
        with urlopen(request, timeout=self.request_timeout_seconds, context=self._ssl_context) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            raw_body = response.read()
            return {
                "content": raw_body.decode(content_type, errors="replace"),
                "status": response.status,
                "encoding": content_type,
                "headers": dict(response.headers.items()),
            }

    def _http_get_bytes(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._http_request_count += 1
        request_headers = {"User-Agent": "Mozilla/5.0"}
        if headers:
            request_headers.update(headers)
        request = Request(url=url, headers=request_headers, method="GET")
        with urlopen(request, timeout=self.request_timeout_seconds, context=self._ssl_context) as response:
            raw_body = response.read()
            return {
                "content": raw_body,
                "status": response.status,
                "headers": dict(response.headers.items()),
            }

    def _http_post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        self._http_request_count += 1
        request_headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
        }
        if headers:
            request_headers.update(headers)
        request = Request(
            url=url,
            headers=request_headers,
            method="POST",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        with urlopen(request, timeout=self.request_timeout_seconds, context=self._ssl_context) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            raw_body = response.read()
            return {
                "content": raw_body.decode(content_type, errors="replace"),
                "status": response.status,
                "encoding": content_type,
                "headers": dict(response.headers.items()),
            }

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_collector_issue(
        self,
        *,
        event: str,
        event_category: str,
        error_code: ErrorCode,
        error_message: str,
        detail: dict[str, Any],
    ) -> None:
        emit_structured_log(
            logger,
            level=logging.ERROR,
            event=event,
            event_category=event_category,
            payload={
                "entity_code": self.entity_code,
                "source_url": self.source_url,
                "error_code": error_code.value,
                "error_message": error_message,
                "failure_step": detail.get("failure_step"),
                "warning_count": detail.get("warning_count", 0),
                "skipped_count": detail.get("skipped_count", 0),
                "http_request_count": self.http_request_count,
                "request_url": detail.get("request_url"),
                "request_timeout_seconds": detail.get("request_timeout_seconds"),
                "error_type": detail.get("error_type"),
            },
        )