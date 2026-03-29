"""Scheduler — priority job queue, stall detection, and cron-based scheduling.

Features:
    - Priority job queue with ordering (high-priority first, then by last-run age)
    - Stall detection with configurable timeout and auto-restart
    - Cron expression support for scheduling patterns
    - Background execution with graceful shutdown
    - Integration with EventBus for real-time progress notifications
"""

import asyncio
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable

from ..config.loader import load_companies, load_settings
from ..pipeline.runner import run_company
from ..utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Job Priority & State
# ---------------------------------------------------------------------------

class JobPriority(int, Enum):
    """Job priority levels (lower number = higher priority)."""
    CRITICAL = 0
    HIGH = 1
    NORMAL = 2
    LOW = 3


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STALLED = "stalled"
    CANCELLED = "cancelled"


@dataclass
class ScheduledJob:
    """A job in the scheduler queue."""

    job_id: str
    company_slug: str
    priority: JobPriority = JobPriority.NORMAL
    status: JobStatus = JobStatus.QUEUED
    queued_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 2
    years_back: int = 1
    provider_override: Optional[str] = None

    @property
    def elapsed_seconds(self) -> Optional[float]:
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    @property
    def wait_seconds(self) -> float:
        start = self.started_at or datetime.now()
        return (start - self.queued_at).total_seconds()

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "company_slug": self.company_slug,
            "priority": self.priority.name,
            "status": self.status.value,
            "queued_at": self.queued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "error": self.error,
            "retries": self.retries,
        }


# ---------------------------------------------------------------------------
# Cron Expression Parser (simplified)
# ---------------------------------------------------------------------------

class CronSchedule:
    """Simplified cron expression matcher.

    Supports: minute hour day_of_month month day_of_week

    Examples:
        "0 6 * * *"     → every day at 06:00
        "0 */4 * * *"   → every 4 hours
        "0 0 * * 1"     → every Monday at midnight
        "0 8 1 * *"     → 1st of each month at 08:00
    """

    def __init__(self, expression: str):
        self.expression = expression.strip()
        parts = self.expression.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression: {expression} (expected 5 fields)")

        self._minute = self._parse_field(parts[0], 0, 59)
        self._hour = self._parse_field(parts[1], 0, 23)
        self._dom = self._parse_field(parts[2], 1, 31)
        self._month = self._parse_field(parts[3], 1, 12)
        self._dow = self._parse_field(parts[4], 0, 6)  # 0=Mon, 6=Sun

    @staticmethod
    def _parse_field(field_str: str, min_val: int, max_val: int) -> set:
        """Parse a single cron field into a set of valid values."""
        values = set()

        for part in field_str.split(","):
            part = part.strip()

            # Wildcard
            if part == "*":
                values.update(range(min_val, max_val + 1))
                continue

            # Step (*/N or M-N/S)
            step_match = re.match(r"^(\*|\d+-\d+)/(\d+)$", part)
            if step_match:
                range_part, step = step_match.groups()
                step = int(step)
                if range_part == "*":
                    start, end = min_val, max_val
                else:
                    start, end = map(int, range_part.split("-"))
                values.update(range(start, end + 1, step))
                continue

            # Range (M-N)
            range_match = re.match(r"^(\d+)-(\d+)$", part)
            if range_match:
                start, end = map(int, range_match.groups())
                values.update(range(start, end + 1))
                continue

            # Single value
            if part.isdigit():
                values.add(int(part))
                continue

            raise ValueError(f"Cannot parse cron field: {part}")

        return values

    def matches(self, dt: datetime) -> bool:
        """Check if a datetime matches this cron schedule."""
        return (
            dt.minute in self._minute
            and dt.hour in self._hour
            and dt.day in self._dom
            and dt.month in self._month
            and dt.weekday() in self._dow
        )

    def next_run(self, after: Optional[datetime] = None) -> datetime:
        """Calculate the next matching datetime after the given time."""
        if after is None:
            after = datetime.now()

        # Start checking from the next minute
        candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)

        # Search up to 366 days ahead
        max_checks = 366 * 24 * 60
        for _ in range(max_checks):
            if self.matches(candidate):
                return candidate
            candidate += timedelta(minutes=1)

        raise RuntimeError(f"No matching time found for cron expression: {self.expression}")


# ---------------------------------------------------------------------------
# Job Queue
# ---------------------------------------------------------------------------

class JobQueue:
    """Priority-ordered job queue with thread-safe operations."""

    def __init__(self):
        self._queue: List[ScheduledJob] = []
        self._lock = threading.Lock()
        self._job_counter = 0

    def enqueue(
        self,
        company_slug: str,
        priority: JobPriority = JobPriority.NORMAL,
        years_back: int = 1,
        provider_override: Optional[str] = None,
    ) -> ScheduledJob:
        """Add a job to the queue.

        Jobs are sorted by priority (lower number first), then by queue time.
        """
        with self._lock:
            self._job_counter += 1
            job = ScheduledJob(
                job_id=f"job-{self._job_counter:05d}",
                company_slug=company_slug,
                priority=priority,
                years_back=years_back,
                provider_override=provider_override,
            )
            self._queue.append(job)
            self._queue.sort(key=lambda j: (j.priority.value, j.queued_at))
            logger.info(f"Queued {job.job_id} for {company_slug} (priority={priority.name})")
            return job

    def dequeue(self) -> Optional[ScheduledJob]:
        """Get and remove the highest-priority queued job."""
        with self._lock:
            for i, job in enumerate(self._queue):
                if job.status == JobStatus.QUEUED:
                    job.status = JobStatus.RUNNING
                    job.started_at = datetime.now()
                    return job
        return None

    def peek(self) -> Optional[ScheduledJob]:
        """See the next job without removing it."""
        with self._lock:
            for job in self._queue:
                if job.status == JobStatus.QUEUED:
                    return job
        return None

    @property
    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._queue if j.status == JobStatus.QUEUED)

    @property
    def running_count(self) -> int:
        with self._lock:
            return sum(1 for j in self._queue if j.status == JobStatus.RUNNING)

    def get_running_jobs(self) -> List[ScheduledJob]:
        with self._lock:
            return [j for j in self._queue if j.status == JobStatus.RUNNING]

    def get_all_jobs(self, limit: int = 50) -> List[ScheduledJob]:
        with self._lock:
            return list(self._queue[-limit:])

    def cancel(self, job_id: str) -> bool:
        """Cancel a queued job."""
        with self._lock:
            for job in self._queue:
                if job.job_id == job_id and job.status == JobStatus.QUEUED:
                    job.status = JobStatus.CANCELLED
                    return True
        return False

    def clear_completed(self, older_than_hours: int = 24) -> int:
        """Remove completed/failed jobs older than N hours."""
        cutoff = datetime.now() - timedelta(hours=older_than_hours)
        with self._lock:
            before = len(self._queue)
            self._queue = [
                j for j in self._queue
                if j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
                or (j.completed_at and j.completed_at > cutoff)
            ]
            return before - len(self._queue)


# ---------------------------------------------------------------------------
# Stall Detector
# ---------------------------------------------------------------------------

class StallDetector:
    """Detects stalled pipeline jobs and triggers recovery.

    A job is considered stalled if it has been running longer than
    ``stall_timeout_minutes`` without completing.
    """

    def __init__(self, stall_timeout_minutes: int = 30, max_restarts: int = 2):
        self.stall_timeout = timedelta(minutes=stall_timeout_minutes)
        self.max_restarts = max_restarts
        self._restart_count: Dict[str, int] = {}

    def check_stalled(self, queue: JobQueue) -> List[ScheduledJob]:
        """Check for stalled jobs and return them."""
        stalled = []
        now = datetime.now()

        for job in queue.get_running_jobs():
            if job.started_at and (now - job.started_at) > self.stall_timeout:
                stalled.append(job)
                logger.warning(
                    f"STALL DETECTED: {job.job_id} ({job.company_slug}) "
                    f"running for {job.elapsed_seconds:.0f}s"
                )

        return stalled

    def should_restart(self, job: ScheduledJob) -> bool:
        """Determine if a stalled job should be restarted."""
        count = self._restart_count.get(job.company_slug, 0)
        return count < self.max_restarts

    def record_restart(self, company_slug: str) -> None:
        """Record a restart for stall tracking."""
        self._restart_count[company_slug] = self._restart_count.get(company_slug, 0) + 1

    def reset(self, company_slug: str) -> None:
        """Reset restart counter after successful completion."""
        self._restart_count.pop(company_slug, None)


# ---------------------------------------------------------------------------
# Pipeline Scheduler
# ---------------------------------------------------------------------------

class PipelineScheduler:
    """Production-grade scheduler with job queue, stall detection, and cron.

    Supports:
        - Priority-ordered job execution
        - Stall detection with automatic restart
        - Cron expressions for periodic scheduling
        - Background thread execution with graceful shutdown
        - Event emission for real-time monitoring

    Usage::

        sched = PipelineScheduler()
        sched.start()       # blocking
        sched.stop()

        # Or run in background
        thread = sched.run_in_background()
    """

    def __init__(self):
        settings = load_settings()
        scheduler_config = settings.get("scheduler", {})

        self.enabled = scheduler_config.get("enabled", False)
        self.check_interval = scheduler_config.get("check_interval_seconds", 300)
        self.max_concurrent = scheduler_config.get("max_concurrent_jobs", 1)

        # Job queue
        self.queue = JobQueue()

        # Stall detection
        stall_timeout = scheduler_config.get("stall_timeout_minutes", 30)
        max_restarts = scheduler_config.get("max_restarts", 2)
        self.stall_detector = StallDetector(stall_timeout, max_restarts)

        # Cron schedules per priority tier
        self._cron_schedules: Dict[str, CronSchedule] = {}
        cron_config = scheduler_config.get("cron", {})
        for tier, expr in cron_config.items():
            try:
                self._cron_schedules[tier] = CronSchedule(expr)
                logger.info(f"Cron schedule for {tier}: {expr}")
            except ValueError as e:
                logger.warning(f"Invalid cron expression for {tier}: {e}")

        # Fallback: interval-based scheduling
        self.high_interval = timedelta(
            hours=scheduler_config.get("high_priority_interval_hours", 24)
        )
        self.low_interval = timedelta(
            hours=scheduler_config.get("low_priority_interval_hours", 168)
        )

        # State
        self._last_run: Dict[str, datetime] = {}
        self._stop_event = threading.Event()
        self._last_cron_check: Optional[datetime] = None

        # EventBus integration (lazy import to avoid circular deps)
        self._bus = None

    def _get_bus(self):
        """Lazy-load EventBus to avoid import cycles."""
        if self._bus is None:
            try:
                from ..progress import EventBus, EventType, PipelineEvent
                self._bus = EventBus.instance()
                self._EventType = EventType
                self._PipelineEvent = PipelineEvent
            except ImportError:
                pass
        return self._bus

    def _emit(self, event_type, message: str, data: dict = None):
        """Emit an event if EventBus is available."""
        bus = self._get_bus()
        if bus:
            bus.publish(self._PipelineEvent(
                event_type=event_type,
                message=message,
                data=data or {},
            ))

    # -- Public API --------------------------------------------------------

    def start(self) -> None:
        """Start the scheduler loop (blocking)."""
        if not self.enabled:
            logger.warning("Scheduler is disabled in settings.yaml")
            return

        logger.info("Scheduler started")
        logger.info(f"  Check interval: {self.check_interval}s")
        logger.info(f"  Max concurrent: {self.max_concurrent}")
        logger.info(f"  Cron schedules: {list(self._cron_schedules.keys()) or 'none (using intervals)'}")

        self._emit(
            self._EventType.SCHEDULER_STARTED if self._get_bus() else None,
            "Scheduler started",
        ) if self._get_bus() else None

        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")

            self._stop_event.wait(self.check_interval)

    def stop(self) -> None:
        """Stop the scheduler gracefully."""
        self._stop_event.set()
        logger.info("Scheduler stopped")

        if self._get_bus():
            self._emit(self._EventType.SCHEDULER_STOPPED, "Scheduler stopped")

    def run_in_background(self) -> threading.Thread:
        """Start scheduler in a background thread."""
        thread = threading.Thread(target=self.start, daemon=True, name="scheduler")
        thread.start()
        return thread

    def enqueue_company(
        self,
        slug: str,
        priority: JobPriority = JobPriority.NORMAL,
        years_back: int = 1,
        provider_override: Optional[str] = None,
    ) -> ScheduledJob:
        """Manually add a company to the job queue."""
        job = self.queue.enqueue(
            company_slug=slug,
            priority=priority,
            years_back=years_back,
            provider_override=provider_override,
        )

        if self._get_bus():
            self._emit(
                self._EventType.SCHEDULER_JOB_QUEUED,
                f"Job queued: {slug}",
                {"job_id": job.job_id, "company_slug": slug, "priority": priority.name},
            )

        return job

    def get_status(self) -> dict:
        """Get scheduler status for API/CLI."""
        return {
            "enabled": self.enabled,
            "running": not self._stop_event.is_set(),
            "queue": {
                "pending": self.queue.pending_count,
                "running": self.queue.running_count,
            },
            "jobs": [j.to_dict() for j in self.queue.get_all_jobs()],
            "cron_schedules": {
                tier: sched.expression
                for tier, sched in self._cron_schedules.items()
            },
            "last_runs": {
                slug: dt.isoformat()
                for slug, dt in self._last_run.items()
            },
        }

    # -- Internal tick -----------------------------------------------------

    def _tick(self) -> None:
        """Single scheduler tick: check cron, detect stalls, process queue."""
        now = datetime.now()

        # 1. Check cron schedules and enqueue companies due for runs
        self._check_cron_schedules(now)

        # 2. Check interval-based scheduling (fallback if no cron)
        if not self._cron_schedules:
            self._check_interval_schedules(now)

        # 3. Detect stalled jobs
        self._handle_stalled_jobs()

        # 4. Process job queue
        self._process_queue()

    def _check_cron_schedules(self, now: datetime) -> None:
        """Enqueue companies if their cron schedule matches."""
        if not self._cron_schedules:
            return

        # Only check once per minute
        current_minute = now.replace(second=0, microsecond=0)
        if self._last_cron_check and current_minute <= self._last_cron_check:
            return
        self._last_cron_check = current_minute

        companies = load_companies()
        for slug, company in companies.items():
            tier = company.priority.value
            cron = self._cron_schedules.get(tier)
            if cron and cron.matches(now):
                # Don't re-queue if already pending or running
                existing = [
                    j for j in self.queue.get_all_jobs()
                    if j.company_slug == slug
                    and j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
                ]
                if not existing:
                    priority = (
                        JobPriority.HIGH if tier == "high" else JobPriority.LOW
                    )
                    self.enqueue_company(slug, priority=priority)
                    logger.info(f"Cron triggered: {slug} ({tier})")

    def _check_interval_schedules(self, now: datetime) -> None:
        """Fallback interval-based scheduling."""
        companies = load_companies()

        for slug, company in companies.items():
            interval = (
                self.high_interval
                if company.priority.value == "high"
                else self.low_interval
            )

            last = self._last_run.get(slug)
            if last and (now - last) < interval:
                continue

            # Don't re-queue if already pending or running
            existing = [
                j for j in self.queue.get_all_jobs()
                if j.company_slug == slug
                and j.status in (JobStatus.QUEUED, JobStatus.RUNNING)
            ]
            if not existing:
                priority = (
                    JobPriority.HIGH
                    if company.priority.value == "high"
                    else JobPriority.LOW
                )
                self.enqueue_company(slug, priority=priority, years_back=1)

    def _handle_stalled_jobs(self) -> None:
        """Detect and handle stalled jobs."""
        stalled = self.stall_detector.check_stalled(self.queue)

        for job in stalled:
            job.status = JobStatus.STALLED
            job.completed_at = datetime.now()
            job.error = f"Stalled after {job.elapsed_seconds:.0f}s"

            logger.warning(f"Job {job.job_id} stalled: {job.company_slug}")

            if self._get_bus():
                self._emit(
                    self._EventType.SCHEDULER_STALL_DETECTED,
                    f"Stall detected: {job.company_slug}",
                    {"job_id": job.job_id, "elapsed_seconds": job.elapsed_seconds},
                )

            # Auto-restart if within retry limit
            if self.stall_detector.should_restart(job):
                self.stall_detector.record_restart(job.company_slug)
                restarted = self.enqueue_company(
                    job.company_slug,
                    priority=JobPriority.HIGH,
                    years_back=job.years_back,
                    provider_override=job.provider_override,
                )
                restarted.retries = job.retries + 1
                logger.info(f"Auto-restarting {job.company_slug} (retry {restarted.retries})")
            else:
                logger.error(
                    f"Max restarts reached for {job.company_slug}, "
                    f"not restarting"
                )

    def _process_queue(self) -> None:
        """Execute jobs from the queue up to max_concurrent."""
        while self.queue.running_count < self.max_concurrent:
            job = self.queue.dequeue()
            if not job:
                break

            # Execute in a thread to allow concurrent jobs
            thread = threading.Thread(
                target=self._execute_job,
                args=(job,),
                daemon=True,
                name=f"job-{job.company_slug}",
            )
            thread.start()

    def _execute_job(self, job: ScheduledJob) -> None:
        """Execute a single pipeline job."""
        logger.info(f"Executing {job.job_id}: {job.company_slug}")

        if self._get_bus():
            self._emit(
                self._EventType.SCHEDULER_JOB_STARTED,
                f"Job started: {job.company_slug}",
                {"job_id": job.job_id},
            )

        try:
            asyncio.run(run_company(
                slug=job.company_slug,
                years_back=job.years_back,
                provider_override=job.provider_override,
            ))

            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            self._last_run[job.company_slug] = datetime.now()
            self.stall_detector.reset(job.company_slug)

            logger.info(
                f"Job {job.job_id} completed: {job.company_slug} "
                f"({job.elapsed_seconds:.1f}s)"
            )

            if self._get_bus():
                self._emit(
                    self._EventType.SCHEDULER_JOB_COMPLETED,
                    f"Job completed: {job.company_slug}",
                    {"job_id": job.job_id, "duration": job.elapsed_seconds},
                )

        except Exception as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error = str(e)

            logger.error(f"Job {job.job_id} failed: {job.company_slug}: {e}")

            # Retry if within limit
            if job.retries < job.max_retries:
                restarted = self.enqueue_company(
                    job.company_slug,
                    priority=job.priority,
                    years_back=job.years_back,
                    provider_override=job.provider_override,
                )
                restarted.retries = job.retries + 1
                logger.info(
                    f"Retrying {job.company_slug} "
                    f"(attempt {restarted.retries + 1}/{job.max_retries + 1})"
                )
