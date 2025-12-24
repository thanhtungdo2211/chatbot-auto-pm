from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime, timezone

from .report_models import DailyTasks, WorkReportData 

class TaskEvaluation(BaseModel):
    task_id: str
    quality_score: float          # 0-1 based on clarity, specificity, completeness
    risk_level: str               # "low", "medium", "high", "critical"
    risk_factors: List[str]       # ["deadline_risk", "blocker_unresolved", "low_velocity"]
    insights: List[str]           # Automated observations
    recommendations: List[str]    # Actionable suggestions
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())  # ISO 8601 timestamp

class DailyTasksWithEvaluation(DailyTasks):
    evaluations: Optional[Dict[str, TaskEvaluation]] = None  # task_id -> evaluation

class WorkReportDataWithAnalysis(WorkReportData):
    daily_tasks: DailyTasksWithEvaluation
    overall_health: Optional[str] = None      # "good", "warning", "critical"
    trend_analysis: Optional[dict] = None     # Velocity, blocker trends, etc.

class CompletionMetrics(BaseModel):
    """Metrics for tracking task completion across issues."""
    total_tasks: int = 0
    completed_tasks: int = 0
    in_progress_tasks: int = 0
    todo_tasks: int = 0
    blocked_tasks: int = 0
    average_progress: float = 0.0  # 0-100
    completion_rate: float = 0.0   # 0-1
    risk_distribution: Dict[str, int] = Field(default_factory=dict)  # {"low": 5, "medium": 2, "high": 1}

class AggregatedEvaluation(BaseModel):
    """Aggregated evaluation for an issue with multiple tasks."""
    issue_id: str
    issue_name: str
    project_id: str
    project_name: Optional[str] = None
    evaluations: Dict[str, TaskEvaluation] = Field(default_factory=dict)
    completion_metrics: CompletionMetrics
    overall_health: str  # "good", "warning", "critical"
    evaluated_at: str