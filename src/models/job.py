from enum import Enum
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class StepName(str, Enum):
    INITIAL_RESEARCH = "initial_research"
    DOWNLOAD = "download"
    CLASSIFY = "classify"
    EXTRACT = "extract"
    PARSE = "parse"
    KPI = "kpi"
    MODEL = "model"
    MEMO = "memo"

class StepResult(BaseModel):
    """Result of a single pipeline step execution."""
    step: StepName
    status: str = "pending"
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    detail: Optional[str] = None
    artifacts: List[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)

class PipelineJob(BaseModel):
    """Tracks a full pipeline run for one company."""
    job_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    company_slug: str
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: str = "pending"
    steps: List[StepResult] = Field(default_factory=list)
    requested_steps: List[StepName] = Field(default_factory=list)
    provider_override: Optional[str] = None
    error: Optional[str] = None

    @property
    def current_step(self) -> Optional[StepResult]:
        for s in self.steps:
            if s.status == "running":
                return s
        return None

    @property
    def progress_pct(self) -> float:
        if not self.steps:
            return 0.0
        completed = sum(1 for s in self.steps if s.status in ("success", "skipped"))
        return completed / len(self.steps) * 100
