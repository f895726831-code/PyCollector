"""
Structured observability framework.

Provides helpers for:
- JSON-structured log emission
- Alert enrichment (severity, alert codes)
- Observability summary building for job/collection execution tracking
"""

import json
import logging
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------


def emit_structured_log(
    logger: logging.Logger,
    *,
    level: int,
    event: str,
    event_category: str,
    payload: dict,
) -> None:
    """Emit a single JSON-structured log line.

    Parameters
    ----------
    logger:
        The logger instance to use.
    level:
        Python logging level (e.g. ``logging.INFO``).
    event:
        Short event identifier (e.g. ``"collector_request_failed"``).
    event_category:
        Broad category for filtering (e.g. ``"collector_failed"``).
    payload:
        Arbitrary key-value data to include in the log line.
    """
    logger.log(
        level,
        json.dumps(
            {
                "event": event,
                "event_category": event_category,
                **payload,
            },
            ensure_ascii=False,
            default=_json_default,
            sort_keys=True,
        ),
    )


# ---------------------------------------------------------------------------
# Alert enrichment
# ---------------------------------------------------------------------------


def enrich_detail_with_alert_fields(
    detail: dict,
    *,
    job_status: str,
    error_code: str | None = None,
) -> dict:
    """Add alert-related fields (severity, alert_code) to a detail dict.

    Returns a new dict with the following keys added:
    - ``severity``: ``"ERROR"``, ``"WARNING"``, or ``"INFO"``
    - ``alert_code``: compound alert identifier or ``None``
    - ``alert_candidate``: ``True`` if this job warrants attention
    - ``retry_exhausted``: ``True`` if the scheduler gave up retrying
    """
    enriched_detail = dict(detail)
    warning_count = int(enriched_detail.get("warning_count", 0))
    skipped_count = int(enriched_detail.get("skipped_count", 0))
    scheduler_decision = enriched_detail.get("scheduler_decision")
    retry_exhausted = scheduler_decision == "RETRY_EXHAUSTED"
    failed = job_status == "FAILED"
    alert_candidate = failed or retry_exhausted or warning_count > 0 or skipped_count > 0

    if failed or retry_exhausted:
        severity = "ERROR"
    elif warning_count > 0 or skipped_count > 0 or scheduler_decision == "RETRYING":
        severity = "WARNING"
    else:
        severity = "INFO"

    if retry_exhausted:
        alert_code = "SCHEDULER_RETRY_EXHAUSTED"
    elif failed and error_code:
        alert_code = f"JOB_FAILED_{error_code}"
    elif failed:
        alert_code = "JOB_FAILED"
    elif warning_count > 0:
        alert_code = "JOB_WARNING_PRESENT"
    elif skipped_count > 0:
        alert_code = "JOB_SKIPPED_ITEMS_PRESENT"
    else:
        alert_code = None

    enriched_detail["severity"] = severity
    enriched_detail["alert_code"] = alert_code
    enriched_detail["alert_candidate"] = alert_candidate
    enriched_detail["retry_exhausted"] = retry_exhausted
    return enriched_detail


# ---------------------------------------------------------------------------
# Observability summary
# ---------------------------------------------------------------------------


def build_observability_summary(
    detail: dict,
    *,
    job_status: str,
    parsed_record_count: int | None = None,
    deduped_count: int | None = None,
    inserted_count: int | None = None,
    updated_count: int | None = None,
    unchanged_count: int | None = None,
    failed_count: int | None = None,
) -> dict:
    """Build a flat observability summary dict from job execution detail.

    The summary is suitable for dashboarding, alert rules, and post-mortem
    analysis.  Counts that are not explicitly provided are carried forward
    from any previous summary already present in *detail*.
    """
    previous_summary = dict(detail.get("observability_summary") or {})
    warning_count = _safe_int(detail.get("warning_count"), default=0)
    skipped_count = _safe_int(detail.get("skipped_count"), default=0)
    successful_record_count = _safe_int(detail.get("successful_record_count"), default=0)
    warning_record_count = _safe_int(
        detail.get("warning_record_count"),
        default=warning_count,
    )
    http_request_count = _safe_int(
        detail.get("http_request_count"),
        default=_safe_int(
            dict(detail.get("collector_context") or {}).get("http_request_count"),
            default=0,
        ),
    )
    retry_attempts = _safe_int(detail.get("retry_attempts"), default=0)
    execution_steps = list(detail.get("execution_steps") or [])
    execution_step_count = _safe_int(
        detail.get("execution_step_count"),
        default=len(execution_steps),
    )
    dedupe_trace = dict(detail.get("dedupe_trace") or {})

    return {
        "job_status": job_status,
        "severity": detail.get("severity"),
        "alert_code": detail.get("alert_code"),
        "alert_candidate": bool(detail.get("alert_candidate", False)),
        "warning_count": warning_count,
        "skipped_count": skipped_count,
        "failed_count": _resolve_summary_count(
            explicit_value=failed_count,
            previous_summary=previous_summary,
            summary_key="failed_count",
        ),
        "parsed_record_count": _resolve_summary_count(
            explicit_value=parsed_record_count,
            previous_summary=previous_summary,
            summary_key="parsed_record_count",
        ),
        "successful_record_count": successful_record_count,
        "warning_record_count": warning_record_count,
        "http_request_count": http_request_count,
        "retry_attempts": retry_attempts,
        "execution_step_count": execution_step_count,
        "deduped_count": _resolve_summary_count(
            explicit_value=deduped_count,
            previous_summary=previous_summary,
            summary_key="deduped_count",
        ),
        "inserted_count": _resolve_summary_count(
            explicit_value=inserted_count,
            previous_summary=previous_summary,
            summary_key="inserted_count",
        ),
        "updated_count": _resolve_summary_count(
            explicit_value=updated_count,
            previous_summary=previous_summary,
            summary_key="updated_count",
        ),
        "unchanged_count": _resolve_summary_count(
            explicit_value=unchanged_count,
            previous_summary=previous_summary,
            summary_key="unchanged_count",
        ),
        "failure_step": detail.get("failure_step"),
        "last_failure_step": detail.get("last_failure_step"),
        "scheduler_decision": detail.get("scheduler_decision"),
        "has_dedupe_trace": bool(dedupe_trace),
        "has_conflict": bool(dedupe_trace.get("conflict")),
    }


def enrich_detail_with_observability_summary(
    detail: dict,
    *,
    job_status: str,
    parsed_record_count: int | None = None,
    deduped_count: int | None = None,
    inserted_count: int | None = None,
    updated_count: int | None = None,
    unchanged_count: int | None = None,
    failed_count: int | None = None,
) -> dict:
    """Return *detail* with an ``observability_summary`` key added."""
    enriched_detail = dict(detail)
    enriched_detail["observability_summary"] = build_observability_summary(
        enriched_detail,
        job_status=job_status,
        parsed_record_count=parsed_record_count,
        deduped_count=deduped_count,
        inserted_count=inserted_count,
        updated_count=updated_count,
        unchanged_count=unchanged_count,
        failed_count=failed_count,
    )
    return enriched_detail


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _json_default(value: object) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _safe_int(value: object, *, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_summary_count(
    *,
    explicit_value: int | None,
    previous_summary: dict,
    summary_key: str,
) -> int:
    if explicit_value is not None:
        return int(explicit_value)
    return _safe_int(previous_summary.get(summary_key), default=0)