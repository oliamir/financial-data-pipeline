"""Scheduler — periodic pipeline execution with priority-based intervals.

Runs high-priority companies daily and low-priority companies weekly
using a simple thread-based scheduler.
"""

import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Dict

from ..config.loader import load_companies, load_settings
from ..pipeline.runner import run_company
from ..utils.logging import get_logger

logger = get_logger(__name__)


class PipelineScheduler:
    """Runs pipeline jobs on a configurable schedule.

    High-priority companies run every 24 hours.
    Low-priority companies run every 168 hours (weekly).
    """

    def __init__(self):
        settings = load_settings()
        scheduler_config = settings.get("scheduler", {})

        self.high_interval = timedelta(
            hours=scheduler_config.get("high_priority_interval_hours", 24)
        )
        self.low_interval = timedelta(
            hours=scheduler_config.get("low_priority_interval_hours", 168)
        )
        self.enabled = scheduler_config.get("enabled", False)
        self._last_run: Dict[str, datetime] = {}
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start the scheduler loop."""
        if not self.enabled:
            logger.warning("Scheduler is disabled in settings.yaml")
            return

        logger.info("Scheduler started")
        logger.info(f"  High priority: every {self.high_interval}")
        logger.info(f"  Low priority: every {self.low_interval}")

        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Scheduler tick error: {e}")

            # Check every 5 minutes
            self._stop_event.wait(300)

    def stop(self) -> None:
        """Stop the scheduler."""
        self._stop_event.set()
        logger.info("Scheduler stopped")

    def _tick(self) -> None:
        """Check all companies and run if due."""
        companies = load_companies()
        now = datetime.now()

        for slug, company in companies.items():
            interval = (
                self.high_interval
                if company.priority.value == "high"
                else self.low_interval
            )

            last = self._last_run.get(slug)
            if last and (now - last) < interval:
                continue

            logger.info(f"Scheduler: Running pipeline for {slug}")
            try:
                import asyncio
                asyncio.run(run_company(slug=slug, years_back=1))
                self._last_run[slug] = now
            except Exception as e:
                logger.error(f"Scheduled run failed for {slug}: {e}")

    def run_in_background(self) -> threading.Thread:
        """Start scheduler in a background thread."""
        thread = threading.Thread(target=self.start, daemon=True, name="scheduler")
        thread.start()
        return thread
