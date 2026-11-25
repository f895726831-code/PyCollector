"""
Background job scheduler with retry, deduplication, and observability.

The :class:`CollectionSchedulerService` runs on a daemon thread and
dispatches scheduled collection jobs for enabled entities.  Each job
executes in its own worker thread with configurable retry logic.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import logging
from enum import StrEnum
from threading import Event, Lock, Thread
from time import sleep

from pycollector.core.observability import (
    emit_structured_log,
    enrich_detail_with_alert_fields,
    enrich_detail_with_observability_summary,
)
from pycollector.domain.enums import ErrorCode

_WEEKDAY_INDEX = {
    "MONDAY": 0,
    "TUESDAY": 1,
    "WEDNESDAY": 2,
    "THURSDAY": 3,
    "FRIDAY": 4,
    "SATURDAY": 5,
    "SUNDAY": 6,
}

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class WeeklyScheduleConfig:
    """Weekly schedule definition."""

    enabled: bool
    weekday: int  # 0=Monday … 6=Sunday
    hour: int
    minute: int
    poll_interval_seconds: int


@dataclass(frozen=True, slots=True)
class RetryPolicyConfig:
    """Retry behaviour for failed jobs."""

    max_retry_count: int
    retry_interval_seconds: int


@dataclass(frozen=True, slots=True)
class EntityScheduleConfig:
    """Per-entity scheduling toggle."""

    entity_code: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class ScheduledDispatchResult:
    """Result of a single dispatch cycle."""

    entity_code: str
    job_id: str
    scheduled_fire_time: str


# ---------------------------------------------------------------------------
# Scheduler service
# ---------------------------------------------------------------------------


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class TriggerType(StrEnum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"


class CollectionSchedulerService:
    """Background scheduler for periodic collection jobs.

    Parameters
    ----------
    weekly_schedule:
        When and how often to fire.
    retry_policy:
        Retry count and interval for failed jobs.
    entity_schedules:
        Per-entity enable/disable mapping.
    create_scheduled_job:
        Callback that creates a job record and returns it (must have
        ``entity_code``, ``job_id``, and ``detail`` attributes/dict).
    run_job:
        Callback that executes a job by its ID and returns the result
        (must have ``status`` and ``detail`` attributes).
    update_job_detail:
        Callback that persists updated detail onto a job record.
    find_existing_scheduled_job:
        Optional callback for persistence-backed deduplication.
        Receives ``(entity_code, slot_key)`` → job-or-None.
    clock:
        Injectable clock (default: ``datetime.now``).
    sleep_fn:
        Injectable sleep (default: ``time.sleep``).
    worker_runner:
        Injectable thread runner (default: daemon ``Thread``).
    """

    _RETRYABLE_ERROR_CODES = {
        ErrorCode.SOURCE_FETCH_FAILED,
        ErrorCode.INTERNAL_ERROR,
        ErrorCode.BUSINESS_WRITE_FAILED,
    }

    def __init__(
        self,
        weekly_schedule: WeeklyScheduleConfig,
        retry_policy: RetryPolicyConfig,
        entity_schedules: Mapping[str, EntityScheduleConfig],
        create_scheduled_job: Callable[[str, dict], Any],
        run_job: Callable[[str], Any],
        update_job_detail: Callable[[str, dict], Any],
        find_existing_scheduled_job: Callable[[str, str], Any] | None = None,
        clock: Callable[[], datetime] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
        worker_runner: Callable[[Callable[[], None], str], None] | None = None,
    ) -> None:
        self._weekly_schedule = weekly_schedule
        self._retry_policy = retry_policy
        self._entity_schedules = dict(entity_schedules)
        self._create_scheduled_job = create_scheduled_job
        self._run_job = run_job
        self._update_job_detail = update_job_detail
        self._find_existing_scheduled_job = find_existing_scheduled_job
        self._clock = clock or datetime.now
        self._sleep = sleep_fn or sleep
        self._worker_runner = worker_runner or self._start_worker_thread
        self._last_dispatched_slot_by_entity: dict[str, str] = {}
        self._lock = Lock()
        self._stop_event = Event()
        self._thread: Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler daemon thread."""
        if not self._weekly_schedule.enabled:
            return
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run_loop,
            name="collection-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the scheduler to stop and wait for the thread."""
        self._stop_event.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def get_enabled_entity_codes(self) -> tuple[str, ...]:
        return tuple(
            code
            for code, config in self._entity_schedules.items()
            if config.enabled
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def run_pending(self, now: datetime | None = None) -> list[ScheduledDispatchResult]:
        """Check schedule and dispatch any pending jobs.

        Called from the run loop; also exposed for manual triggering
        in tests.
        """
        current_time = now or self._clock()
        if not self._is_due(current_time):
            return []

        slot_key = self._build_slot_key(current_time)
        scheduled_fire_time = current_time.isoformat()
        dispatched: list[ScheduledDispatchResult] = []

        for entity_code in self.get_enabled_entity_codes():
            decision = self._decide_dispatch(entity_code, slot_key)
            if decision != "DISPATCH":
                self._log_scheduler_event(
                    event="scheduler_dispatch_skipped",
                    event_category="scheduler_skipped",
                    entity_code=entity_code,
                    detail=self._enrich_scheduled_detail(
                        {
                            "scheduled_fire_time": scheduled_fire_time,
                            "scheduler_decision": decision,
                            "scheduler_metadata": self._build_scheduler_metadata(
                                entity_code=entity_code,
                                slot_key=slot_key,
                            ),
                        },
                        job_status=JobStatus.SUCCESS,
                    ),
                    status=JobStatus.SUCCESS,
                    level=logging.INFO,
                )
                continue

            initial_detail = self._enrich_scheduled_detail(
                self._build_initial_detail(
                    entity_code=entity_code,
                    scheduled_fire_time=scheduled_fire_time,
                    slot_key=slot_key,
                ),
                job_status=JobStatus.PENDING,
            )
            job = self._create_scheduled_job(entity_code, initial_detail)
            self._log_scheduler_event(
                event="scheduler_job_dispatched",
                event_category="scheduler_dispatched",
                entity_code=entity_code,
                job_id=job.job_id,
                detail=initial_detail,
                status=JobStatus.PENDING,
                trigger_type=TriggerType.SCHEDULED,
                level=logging.INFO,
            )
            self._worker_runner(
                lambda jid=job.job_id: self._run_job_with_retry(jid),
                f"scheduled-job-{job.job_id}",
            )
            self._mark_dispatched(entity_code, slot_key)
            dispatched.append(
                ScheduledDispatchResult(
                    entity_code=entity_code,
                    job_id=job.job_id,
                    scheduled_fire_time=scheduled_fire_time,
                )
            )
        return dispatched

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self.run_pending()
            self._stop_event.wait(self._weekly_schedule.poll_interval_seconds)

    # ------------------------------------------------------------------
    # Retry logic
    # ------------------------------------------------------------------

    def _run_job_with_retry(self, job_id: str) -> None:
        retry_count = 0
        last_failure_step: str | None = None
        while True:
            executed_job = self._run_job(job_id)
            current_detail = dict(getattr(executed_job, "detail", None) or {})
            current_failure_step = current_detail.get("failure_step")
            if current_failure_step:
                last_failure_step = str(current_failure_step)

            if getattr(executed_job, "status", None) == JobStatus.SUCCESS:
                final_detail = self._enrich_scheduled_detail(
                    self._merge_detail(
                        current_detail,
                        {
                            "retry_count": retry_count,
                            "retry_attempts": retry_count,
                            "max_retry_count": self._retry_policy.max_retry_count,
                            "retryable": False,
                            "last_failure_step": last_failure_step,
                            "scheduler_decision": "COMPLETED",
                        },
                    ),
                    job_status=JobStatus.SUCCESS,
                )
                self._update_job_detail(job_id, final_detail)
                self._log_scheduler_event(
                    event="scheduler_job_completed",
                    event_category="scheduler_completed",
                    entity_code=getattr(executed_job, "entity_code", ""),
                    job_id=job_id,
                    detail=final_detail,
                    status=JobStatus.SUCCESS,
                    level=self._resolve_log_level(final_detail),
                )
                return

            retryable = self._is_retryable(executed_job)
            if retryable and retry_count < self._retry_policy.max_retry_count:
                retry_count += 1
                retry_detail = self._enrich_scheduled_detail(
                    self._merge_detail(
                        current_detail,
                        {
                            "retry_count": retry_count,
                            "retry_attempts": retry_count,
                            "max_retry_count": self._retry_policy.max_retry_count,
                            "retryable": True,
                            "last_failure_step": last_failure_step,
                            "scheduler_decision": "RETRYING",
                        },
                    ),
                    job_status=JobStatus.FAILED,
                )
                self._update_job_detail(job_id, retry_detail)
                self._log_scheduler_event(
                    event="scheduler_job_retrying",
                    event_category="scheduler_retrying",
                    entity_code=getattr(executed_job, "entity_code", ""),
                    job_id=job_id,
                    detail=retry_detail,
                    status=JobStatus.FAILED,
                    level=self._resolve_log_level(retry_detail),
                )
                self._sleep(self._retry_policy.retry_interval_seconds)
                continue

            # Final failure
            final_detail = self._enrich_scheduled_detail(
                self._merge_detail(
                    current_detail,
                    {
                        "retry_count": retry_count,
                        "retry_attempts": retry_count,
                        "max_retry_count": self._retry_policy.max_retry_count,
                        "retryable": retryable,
                        "last_failure_step": last_failure_step,
                        "scheduler_decision": (
                            "RETRY_EXHAUSTED" if retryable else "NOT_RETRYABLE"
                        ),
                    },
                ),
                job_status=JobStatus.FAILED,
            )
            self._update_job_detail(job_id, final_detail)
            self._log_scheduler_event(
                event=(
                    "scheduler_retry_exhausted"
                    if retryable
                    else "scheduler_job_not_retryable"
                ),
                event_category=(
                    "scheduler_retry_exhausted"
                    if retryable
                    else "scheduler_not_retryable"
                ),
                entity_code=getattr(executed_job, "entity_code", ""),
                job_id=job_id,
                detail=final_detail,
                status=JobStatus.FAILED,
                level=self._resolve_log_level(final_detail),
            )
            return

    # ------------------------------------------------------------------
    # Decision helpers
    # ------------------------------------------------------------------

    def _is_due(self, now: datetime) -> bool:
        return (
            self._weekly_schedule.enabled
            and now.weekday() == self._weekly_schedule.weekday
            and now.hour == self._weekly_schedule.hour
            and now.minute == self._weekly_schedule.minute
        )

    def _build_slot_key(self, now: datetime) -> str:
        iso_year, iso_week, _ = now.isocalendar()
        return (
            f"{iso_year}-W{iso_week:02d}-"
            f"{self._weekly_schedule.weekday}-"
            f"{self._weekly_schedule.hour:02d}:"
            f"{self._weekly_schedule.minute:02d}"
        )

    def _decide_dispatch(self, entity_code: str, slot_key: str) -> str:
        with self._lock:
            if self._last_dispatched_slot_by_entity.get(entity_code) == slot_key:
                return "SKIP_IN_MEMORY_DUPLICATE"
        if self._find_existing_scheduled_job is None:
            return "DISPATCH"
        existing = self._find_existing_scheduled_job(entity_code, slot_key)
        if existing is None:
            return "DISPATCH"
        self._mark_dispatched(entity_code, slot_key)
        return "SKIP_PERSISTED_DUPLICATE"

    def _mark_dispatched(self, entity_code: str, slot_key: str) -> None:
        with self._lock:
            self._last_dispatched_slot_by_entity[entity_code] = slot_key

    def _is_retryable(self, job: Any) -> bool:
        error_code = getattr(job, "error_code", None)
        trigger_type = getattr(job, "trigger_type", None)
        if trigger_type != TriggerType.SCHEDULED or error_code is None:
            return False
        return error_code in self._RETRYABLE_ERROR_CODES

    # ------------------------------------------------------------------
    # Detail builders
    # ------------------------------------------------------------------

    def _build_initial_detail(
        self,
        *,
        entity_code: str,
        scheduled_fire_time: str,
        slot_key: str,
    ) -> dict:
        return {
            "retry_count": 0,
            "retry_attempts": 0,
            "max_retry_count": self._retry_policy.max_retry_count,
            "retryable": False,
            "scheduled_fire_time": scheduled_fire_time,
            "scheduler_decision": "DISPATCHED",
            "scheduler_metadata": self._build_scheduler_metadata(
                entity_code=entity_code,
                slot_key=slot_key,
            ),
        }

    def _build_scheduler_metadata(self, *, entity_code: str, slot_key: str) -> dict:
        return {
            "component_type": "scheduler",
            "component_name": self.__class__.__name__,
            "scheduler_type": "WEEKLY",
            "slot_key": slot_key,
            "poll_interval_seconds": self._weekly_schedule.poll_interval_seconds,
            "retry_interval_seconds": self._retry_policy.retry_interval_seconds,
            "entity_code": entity_code,
        }

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _merge_detail(base: dict, patch: dict) -> dict:
        merged = dict(base)
        for key, value in patch.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                nested = dict(merged[key])
                nested.update(value)
                merged[key] = nested
            elif value is not None:
                merged[key] = value
        return merged

    @staticmethod
    def _start_worker_thread(target: Callable[[], None], name: str) -> None:
        Thread(target=target, name=name, daemon=True).start()

    @staticmethod
    def _enrich_scheduled_detail(
        detail: dict,
        *,
        job_status: JobStatus,
        error_code: ErrorCode | None = None,
    ) -> dict:
        alert_enriched = enrich_detail_with_alert_fields(
            detail,
            job_status=job_status.value,
            error_code=error_code.value if error_code else None,
        )
        return enrich_detail_with_observability_summary(
            alert_enriched,
            job_status=job_status.value,
        )

    @staticmethod
    def _resolve_log_level(detail: dict) -> int:
        severity = str(detail.get("severity", "INFO")).upper()
        if severity == "ERROR":
            return logging.ERROR
        elif severity == "WARNING":
            return logging.WARNING
        return logging.INFO

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    def _log_scheduler_event(
        self,
        *,
        event: str,
        event_category: str,
        entity_code: str,
        detail: dict,
        status: JobStatus,
        level: int,
        job_id: str | None = None,
        trigger_type: TriggerType = TriggerType.SCHEDULED,
        error_code: ErrorCode | None = None,
    ) -> None:
        emit_structured_log(
            logger,
            level=level,
            event=event,
            event_category=event_category,
            payload={
                "job_id": job_id,
                "entity_code": entity_code,
                "trigger_type": trigger_type.value,
                "status": status.value,
                "error_code": error_code.value if error_code else None,
                "severity": detail.get("severity"),
                "alert_code": detail.get("alert_code"),
                "alert_candidate": detail.get("alert_candidate"),
                "retry_exhausted": detail.get("retry_exhausted"),
                "retry_count": detail.get("retry_count"),
                "retry_attempts": detail.get("retry_attempts"),
                "max_retry_count": detail.get("max_retry_count"),
                "retryable": detail.get("retryable"),
                "last_failure_step": detail.get("last_failure_step"),
                "scheduled_fire_time": detail.get("scheduled_fire_time"),
                "scheduler_decision": detail.get("scheduler_decision"),
                "scheduler_metadata": detail.get("scheduler_metadata"),
            },
        )


# ---------------------------------------------------------------------------
# Config builders
# ---------------------------------------------------------------------------


def parse_weekday(value: str) -> int:
    """Convert a weekday name (``"MONDAY"``, …) to its 0-based index."""
    normalized = str(value).strip().upper()
    if normalized not in _WEEKDAY_INDEX:
        supported = ", ".join(_WEEKDAY_INDEX)
        raise ValueError(
            f"unsupported weekday: {value}. expected one of {supported}"
        )
    return _WEEKDAY_INDEX[normalized]