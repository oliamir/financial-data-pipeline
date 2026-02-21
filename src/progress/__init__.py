"""Progress tracking — EventBus pub/sub system for real-time pipeline updates.

Provides:
    - EventBus: Global publish/subscribe for pipeline events
    - ProgressTracker: Per-company, per-step progress tracking
    - PipelineEvent: Typed event objects for pipeline state changes

Both the terminal dashboard and web dashboard subscribe to
the EventBus to receive real-time progress updates.
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from ..utils.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------

class EventType(str, Enum):
    """Types of pipeline events published on the EventBus."""

    # Pipeline lifecycle
    PIPELINE_STARTED = "pipeline.started"
    PIPELINE_COMPLETED = "pipeline.completed"
    PIPELINE_FAILED = "pipeline.failed"

    # Step lifecycle
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    STEP_FAILED = "step.failed"
    STEP_SKIPPED = "step.skipped"

    # Progress updates
    PROGRESS_UPDATE = "progress.update"
    PROGRESS_MESSAGE = "progress.message"

    # Provider events
    PROVIDER_SWITCHED = "provider.switched"
    PROVIDER_FAILED = "provider.failed"

    # Scheduler events
    SCHEDULER_STARTED = "scheduler.started"
    SCHEDULER_STOPPED = "scheduler.stopped"
    SCHEDULER_JOB_QUEUED = "scheduler.job_queued"
    SCHEDULER_JOB_STARTED = "scheduler.job_started"
    SCHEDULER_JOB_COMPLETED = "scheduler.job_completed"
    SCHEDULER_STALL_DETECTED = "scheduler.stall_detected"


@dataclass
class PipelineEvent:
    """An event emitted by the pipeline system."""

    event_type: EventType
    company_slug: str = ""
    step_name: str = ""
    message: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize event for JSON/WebSocket transmission."""
        return {
            "event_type": self.event_type.value,
            "company_slug": self.company_slug,
            "step_name": self.step_name,
            "message": self.message,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }


# ---------------------------------------------------------------------------
# EventBus — singleton pub/sub
# ---------------------------------------------------------------------------

EventHandler = Callable[[PipelineEvent], None]


class EventBus:
    """Global publish/subscribe bus for pipeline events.

    Thread-safe singleton. Subscribers register for specific event types
    or use ``'*'`` to receive all events.

    Usage::

        bus = EventBus.instance()
        bus.subscribe(EventType.STEP_COMPLETED, my_handler)
        bus.publish(PipelineEvent(
            event_type=EventType.STEP_COMPLETED,
            company_slug="sofwave",
            step_name="extract",
            message="Extracted Q3 2024 financials",
        ))
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._wildcard_subscribers: List[EventHandler] = []
        self._event_history: List[PipelineEvent] = []
        self._max_history = 500
        self._sub_lock = threading.Lock()

    @classmethod
    def instance(cls) -> "EventBus":
        """Get or create the global EventBus singleton."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (useful for testing)."""
        with cls._lock:
            cls._instance = None

    # -- Subscribe / unsubscribe ------------------------------------------

    def subscribe(
        self,
        event_type: Optional[EventType],
        handler: EventHandler,
    ) -> None:
        """Subscribe to events of a specific type (or all events if None).

        Args:
            event_type: Event type to subscribe to, or ``None`` for all.
            handler:    Callable receiving a ``PipelineEvent``.
        """
        with self._sub_lock:
            if event_type is None:
                if handler not in self._wildcard_subscribers:
                    self._wildcard_subscribers.append(handler)
            else:
                key = event_type.value
                self._subscribers.setdefault(key, [])
                if handler not in self._subscribers[key]:
                    self._subscribers[key].append(handler)

    def unsubscribe(
        self,
        event_type: Optional[EventType],
        handler: EventHandler,
    ) -> None:
        """Remove a handler subscription."""
        with self._sub_lock:
            if event_type is None:
                if handler in self._wildcard_subscribers:
                    self._wildcard_subscribers.remove(handler)
            else:
                key = event_type.value
                if key in self._subscribers and handler in self._subscribers[key]:
                    self._subscribers[key].remove(handler)

    # -- Publish -----------------------------------------------------------

    def publish(self, event: PipelineEvent) -> None:
        """Publish an event to all matching subscribers.

        Events are delivered synchronously to handlers. If a handler raises,
        the exception is logged but does not prevent delivery to other handlers.
        """
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

        with self._sub_lock:
            handlers = list(self._wildcard_subscribers)
            specific = self._subscribers.get(event.event_type.value, [])
            handlers.extend(specific)

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error for {event.event_type}: {e}")

    # -- History -----------------------------------------------------------

    def recent_events(
        self,
        limit: int = 50,
        company_slug: Optional[str] = None,
        event_type: Optional[EventType] = None,
    ) -> List[PipelineEvent]:
        """Get recent events, optionally filtered."""
        events = self._event_history
        if company_slug:
            events = [e for e in events if e.company_slug == company_slug]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()


# ---------------------------------------------------------------------------
# ProgressTracker — per-company progress
# ---------------------------------------------------------------------------

@dataclass
class StepProgress:
    """Progress state for a single pipeline step."""
    step_name: str
    status: str = "pending"  # pending, running, completed, failed, skipped
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    message: str = ""
    detail: str = ""
    error: Optional[str] = None

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        if self.started_at:
            return (datetime.now() - self.started_at).total_seconds()
        return None


class ProgressTracker:
    """Tracks pipeline progress per company with event emission.

    Each company has its own ProgressTracker instance. The tracker
    publishes events to the global EventBus as steps progress.

    Usage::

        tracker = ProgressTracker("sofwave")
        tracker.start_pipeline()
        tracker.start_step("download")
        tracker.update_step("download", "Downloading 5 reports...")
        tracker.complete_step("download", "Downloaded 5 reports")
        tracker.complete_pipeline()
    """

    # Class-level registry of all active trackers
    _active: Dict[str, "ProgressTracker"] = {}
    _active_lock = threading.Lock()

    def __init__(self, company_slug: str):
        self.company_slug = company_slug
        self.steps: Dict[str, StepProgress] = {}
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.status: str = "idle"  # idle, running, completed, failed
        self._bus = EventBus.instance()

        # Register in active trackers
        with self._active_lock:
            self._active[company_slug] = self

    @classmethod
    def get_active(cls) -> Dict[str, "ProgressTracker"]:
        """Get all active trackers (read-only copy)."""
        with cls._active_lock:
            return dict(cls._active)

    @classmethod
    def get_tracker(cls, slug: str) -> Optional["ProgressTracker"]:
        """Get the tracker for a specific company."""
        with cls._active_lock:
            return cls._active.get(slug)

    # -- Pipeline lifecycle ------------------------------------------------

    def start_pipeline(self, requested_steps: Optional[List[str]] = None) -> None:
        """Mark the pipeline as started."""
        self.started_at = datetime.now()
        self.completed_at = None
        self.status = "running"
        self.steps.clear()

        self._bus.publish(PipelineEvent(
            event_type=EventType.PIPELINE_STARTED,
            company_slug=self.company_slug,
            message=f"Pipeline started for {self.company_slug}",
            data={"requested_steps": requested_steps or []},
        ))

    def complete_pipeline(self) -> None:
        """Mark the pipeline as completed."""
        self.completed_at = datetime.now()
        self.status = "completed"

        elapsed = (self.completed_at - self.started_at).total_seconds() if self.started_at else 0
        self._bus.publish(PipelineEvent(
            event_type=EventType.PIPELINE_COMPLETED,
            company_slug=self.company_slug,
            message=f"Pipeline completed for {self.company_slug} in {elapsed:.1f}s",
            data={
                "duration_seconds": elapsed,
                "steps_completed": sum(1 for s in self.steps.values() if s.status == "completed"),
                "steps_failed": sum(1 for s in self.steps.values() if s.status == "failed"),
            },
        ))

    def fail_pipeline(self, error: str) -> None:
        """Mark the pipeline as failed."""
        self.completed_at = datetime.now()
        self.status = "failed"

        self._bus.publish(PipelineEvent(
            event_type=EventType.PIPELINE_FAILED,
            company_slug=self.company_slug,
            message=f"Pipeline failed for {self.company_slug}: {error}",
            data={"error": error},
        ))

    # -- Step lifecycle ----------------------------------------------------

    def start_step(self, step_name: str, message: str = "") -> None:
        """Mark a step as started."""
        step = StepProgress(
            step_name=step_name,
            status="running",
            started_at=datetime.now(),
            message=message,
        )
        self.steps[step_name] = step

        self._bus.publish(PipelineEvent(
            event_type=EventType.STEP_STARTED,
            company_slug=self.company_slug,
            step_name=step_name,
            message=message or f"Starting {step_name}",
        ))

    def update_step(self, step_name: str, message: str, detail: str = "") -> None:
        """Update progress message for a running step."""
        if step_name in self.steps:
            self.steps[step_name].message = message
            self.steps[step_name].detail = detail

        self._bus.publish(PipelineEvent(
            event_type=EventType.PROGRESS_UPDATE,
            company_slug=self.company_slug,
            step_name=step_name,
            message=message,
            data={"detail": detail},
        ))

    def complete_step(self, step_name: str, detail: str = "") -> None:
        """Mark a step as completed."""
        if step_name in self.steps:
            self.steps[step_name].status = "completed"
            self.steps[step_name].completed_at = datetime.now()
            self.steps[step_name].detail = detail

        duration = self.steps[step_name].duration_seconds if step_name in self.steps else None
        self._bus.publish(PipelineEvent(
            event_type=EventType.STEP_COMPLETED,
            company_slug=self.company_slug,
            step_name=step_name,
            message=f"{step_name} completed" + (f" ({detail})" if detail else ""),
            data={"detail": detail, "duration_seconds": duration},
        ))

    def fail_step(self, step_name: str, error: str) -> None:
        """Mark a step as failed."""
        if step_name in self.steps:
            self.steps[step_name].status = "failed"
            self.steps[step_name].completed_at = datetime.now()
            self.steps[step_name].error = error

        self._bus.publish(PipelineEvent(
            event_type=EventType.STEP_FAILED,
            company_slug=self.company_slug,
            step_name=step_name,
            message=f"{step_name} failed: {error}",
            data={"error": error},
        ))

    def skip_step(self, step_name: str, reason: str = "") -> None:
        """Mark a step as skipped."""
        step = StepProgress(
            step_name=step_name,
            status="skipped",
            message=reason,
        )
        self.steps[step_name] = step

        self._bus.publish(PipelineEvent(
            event_type=EventType.STEP_SKIPPED,
            company_slug=self.company_slug,
            step_name=step_name,
            message=reason or f"{step_name} skipped",
        ))

    # -- Status ------------------------------------------------------------

    @property
    def progress_pct(self) -> float:
        """Percentage of steps completed (0-100)."""
        if not self.steps:
            return 0.0
        done = sum(1 for s in self.steps.values() if s.status in ("completed", "skipped"))
        return done / len(self.steps) * 100

    @property
    def current_step_name(self) -> Optional[str]:
        """Name of the currently running step."""
        for name, step in self.steps.items():
            if step.status == "running":
                return name
        return None

    @property
    def elapsed_seconds(self) -> Optional[float]:
        """Total elapsed time."""
        if not self.started_at:
            return None
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize tracker state for API/WebSocket."""
        return {
            "company_slug": self.company_slug,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "progress_pct": self.progress_pct,
            "current_step": self.current_step_name,
            "steps": {
                name: {
                    "status": step.status,
                    "message": step.message,
                    "detail": step.detail,
                    "duration_seconds": step.duration_seconds,
                    "error": step.error,
                }
                for name, step in self.steps.items()
            },
        }

    def cleanup(self) -> None:
        """Remove this tracker from the active registry."""
        with self._active_lock:
            self._active.pop(self.company_slug, None)
