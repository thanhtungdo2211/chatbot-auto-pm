# Plan: Task Evaluation & Analysis Feature for Manager Progress Reporting

## Overview
Build an automated task evaluation system that analyzes staff work reports for quality, risk, and trends, providing managers with actionable insights and recommendations alongside raw progress data.

## Implementation Steps

### 1. Create Domain Models for Task Evaluation

**File**: `src/auto_pm_agent_api/domain/models.py`

Add new models:

```python
from typing import List, Optional, Literal
from pydantic import BaseModel, Field

class TaskEvaluation(BaseModel):
    """Evaluation metrics for a single task report."""
    task_id: str
    quality_score: float = Field(ge=0.0, le=1.0, description="0-1 score for report quality")
    risk_level: Literal["low", "medium", "high"] = "low"
    insights: List[str] = Field(default_factory=list, description="Key observations")
    recommendations: List[str] = Field(default_factory=list, description="Actionable suggestions")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Evaluation confidence")

class DailyTasksWithEvaluation(DailyTasks):
    """Extended DailyTasks with evaluation metadata."""
    evaluation: Optional[TaskEvaluation] = None

class WorkReportDataWithAnalysis(WorkReportData):
    """Work report with comprehensive analysis."""
    overall_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    risk_summary: str = ""
    key_insights: List[str] = Field(default_factory=list)
    manager_recommendations: List[str] = Field(default_factory=list)
```

### 2. Build TaskAnalyzer Service

**File**: `src/auto_pm_agent_api/application/analysis_service/task_analyzer.py`

```python
import logging
from typing import List, Dict, Any, Optional
from datetime import date, timedelta

from auto_pm_agent_api.domain.prompts import PROMPT_TASK_EVALUATION
from auto_pm_agent_api.domain.models import (
    TaskEvaluation,
    WorkReportData,
    WorkReportDataWithAnalysis
)

logger = logging.getLogger(__name__)


class TaskAnalyzer:
    """Analyze task reports for quality, risk, and actionable insights."""

    def __init__(self, llm_client, plane_api_factory):
        self.llm = llm_client
        self.plane_api_factory = plane_api_factory

    def evaluate_report(
        self,
        report: WorkReportData,
        project_id: str,
        issue_id: str,
        user_id: int,
        historical_days: int = 7
    ) -> WorkReportDataWithAnalysis:
        """
        Evaluate a work report with quality scoring and risk assessment.
        
        Args:
            report: Raw work report data
            project_id: Project identifier
            issue_id: Issue identifier
            user_id: User who submitted report
            historical_days: Days of history to fetch for trend analysis
            
        Returns:
            Enhanced report with evaluation and insights
        """
        try:
            # Fetch historical progress for trend analysis
            history = self._fetch_historical_progress(
                user_id, project_id, issue_id, historical_days
            )
            
            # Build evaluation prompt
            prompt = self._build_evaluation_prompt(report, history)
            
            # Get LLM evaluation
            evaluation = self.llm.generate_response(
                prompt,
                output_format=TaskEvaluation
            )
            
            if isinstance(evaluation, dict):
                evaluation = TaskEvaluation(**evaluation)
            
            # Build enhanced report
            return WorkReportDataWithAnalysis(
                **report.model_dump(),
                overall_quality=evaluation.quality_score,
                risk_summary=self._format_risk_summary(evaluation),
                key_insights=evaluation.insights,
                manager_recommendations=evaluation.recommendations
            )
            
        except Exception as e:
            logger.error(f"Task evaluation failed: {e}", exc_info=True)
            # Return report with default/safe values on error
            return WorkReportDataWithAnalysis(**report.model_dump())

    def _fetch_historical_progress(
        self,
        user_id: int,
        project_id: str,
        issue_id: str,
        days: int
    ) -> List[Dict[str, Any]]:
        """Fetch historical daily progress entries."""
        try:
            plane_api = self.plane_api_factory.get_api(user_id)
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            entries = plane_api.list_daily_progress(
                project_id=project_id,
                issue_id=issue_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )
            return entries or []
        except Exception as e:
            logger.warning(f"Could not fetch historical progress: {e}")
            return []

    def _build_evaluation_prompt(
        self,
        report: WorkReportData,
        history: List[Dict[str, Any]]
    ) -> str:
        """Build structured prompt for LLM evaluation."""
        # Format current report
        current_tasks = []
        daily = report.daily_tasks or {}
        for task in daily.tasks or []:
            current_tasks.append(
                f"- {task.title}: {task.status}, {task.progress}%, "
                f"time: {task.time_spent or 'N/A'}"
            )
        
        # Format historical trends
        history_summary = []
        for idx, entry in enumerate(history[-5:], 1):  # Last 5 entries
            day = entry.get("day", "unknown")
            notes = entry.get("notes", "")[:100]  # Truncate long notes
            history_summary.append(f"{idx}. {day}: {notes}")
        
        return PROMPT_TASK_EVALUATION.format(
            current_tasks="\n".join(current_tasks) or "No tasks reported",
            blockers=", ".join(daily.blockers or []) or "None",
            achievements=", ".join(daily.achievements or []) or "None",
            notes=report.notes or "No additional notes",
            history="\n".join(history_summary) or "No history available"
        )

    def _format_risk_summary(self, evaluation: TaskEvaluation) -> str:
        """Format risk level into human-readable summary."""
        risk_emoji = {
            "low": "🟢",
            "medium": "🟡",
            "high": "🔴"
        }
        emoji = risk_emoji.get(evaluation.risk_level, "⚪")
        return f"{emoji} {evaluation.risk_level.upper()} risk"

    def analyze_trends(
        self,
        user_id: int,
        project_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze multi-day trends across all tasks in a project.
        
        Returns metrics like velocity, blocker frequency, quality trends.
        """
        try:
            plane_api = self.plane_api_factory.get_api(user_id)
            issues = plane_api.list_issues(project_id=project_id)
            
            trends = {
                "total_tasks": len(issues),
                "avg_quality": 0.0,
                "blocker_frequency": 0.0,
                "velocity_trend": "stable",
                "at_risk_tasks": []
            }
            
            # Aggregate metrics across all issues
            # ... implementation details ...
            
            return trends
            
        except Exception as e:
            logger.error(f"Trend analysis failed: {e}", exc_info=True)
            return {}
```

### 3. Create Evaluation Prompt

**File**: `src/auto_pm_agent_api/domain/prompts.py`

Add new prompt:

```python
PROMPT_TASK_EVALUATION = """
You are a project management analyst. Evaluate this staff work report for quality and risk.

**Current Report:**
Tasks:
{current_tasks}

Blockers: {blockers}
Achievements: {achievements}
Notes: {notes}

**Recent History (last 5 days):**
{history}

**Evaluation Criteria:**

1. **Quality Score (0-1):**
   - Specificity: Concrete deliverables vs vague percentages
   - Blocker detail: Root cause analysis vs surface symptoms
   - Plan clarity: Actionable next steps vs generic statements
   
2. **Risk Assessment:**
   - HIGH: Deadline < 2 days + no progress, blocker > 3 days, velocity drop > 50%
   - MEDIUM: Vague reports, new blockers, inconsistent progress
   - LOW: Concrete outputs, clear plan, steady velocity

3. **Insights:** Key observations (max 3, focus on actionable items)

4. **Recommendations:** Manager actions (max 3, specific and prioritized)

Return JSON with this exact schema:
{{
  "task_id": "string",
  "quality_score": 0.0-1.0,
  "risk_level": "low" | "medium" | "high",
  "insights": ["insight1", "insight2"],
  "recommendations": ["action1", "action2"],
  "confidence": 0.0-1.0
}}

Focus on actionable intelligence. Avoid generic advice.
"""
```

### 4. Integrate Analysis into Report Push Flow

**Modification**: `src/auto_pm_agent_api/application/report_session.py`

Update `_push_report_to_plane` method:

```python
def _push_report_to_plane(self, user_id: int, state: dict) -> str:
    """Push report with evaluation to Plane."""
    if not self.plane_factory:
        return "Không thể đẩy lên Plane vì thiếu cấu hình Plane API."

    report_text = (state.get("report_text") or "").strip()
    if not report_text:
        return "Không có nội dung báo cáo để đẩy lên Plane."

    try:
        plane_api = self.plane_factory.get_api(user_id)
    except Exception as exc:
        self.logger.warning("Không khởi tạo được Plane API: %s", exc)
        return "Không thể đẩy báo cáo lên Plane (khởi tạo API lỗi)."

    # ... existing code to get plane_user_id and issues ...

    # NEW: Initialize analyzer
    from auto_pm_agent_api.application.analysis_service.task_analyzer import TaskAnalyzer
    analyzer = TaskAnalyzer(self.general_bot, self.plane_factory)

    updated_count = 0
    failed = 0
    
    for issue in issues:
        try:
            # ... existing code to extract project_id, issue_id, issue_name ...
            
            # NEW: Extract structured report for analysis
            from auto_pm_agent_api.application.report_service.work_report_extractor import WorkReportExtractor
            extractor = WorkReportExtractor(self.general_bot)
            structured_report = extractor.extract(report_text)
            
            # NEW: Evaluate report
            analyzed_report = analyzer.evaluate_report(
                report=structured_report,
                project_id=project_id,
                issue_id=issue_id,
                user_id=user_id,
                historical_days=7
            )
            
            # Build payload with evaluation metadata
            payload = {
                "day": today_str,
                "notes": f"{report_text}\n\n[Analysis]\n"
                        f"Quality: {analyzed_report.overall_quality:.2f}\n"
                        f"Risk: {analyzed_report.risk_summary}\n"
                        f"Insights: {'; '.join(analyzed_report.key_insights[:2])}",
                "daily_tasks": analyzed_report.daily_tasks.model_dump() if analyzed_report.daily_tasks else {}
            }

            # ... existing code to create/update daily progress ...
            
        except Exception as exc:
            failed += 1
            self.logger.warning("Không cập nhật được issue %s: %s", issue_id, exc)
            continue

    # ... existing return message ...
```

### 5. Enhance Manager View with Insights

**Modification**: `src/auto_pm_agent_api/application/report_session.py`

Update `_build_manager_first_response` method:

```python
def _build_manager_first_response(self, state: dict, user_id: int, history_str: str) -> str:
    ctx = state.get("report_context") or {}
    # ... existing code ...
    
    # NEW: Parse evaluation data from progress entries
    for p in projects:
        lines.append(f"- Dự án: {p.get('project_name')} (id: {p.get('project_id')})")
        issues = p.get("issues") or []
        for iss in issues:
            progress_entries = iss.get("progress_entries") or []
            
            # Extract evaluation from notes if available
            evaluation_summary = ""
            if progress_entries:
                latest = progress_entries[0]
                notes = latest.get("notes", "")
                if "[Analysis]" in notes:
                    # Parse embedded analysis
                    analysis_section = notes.split("[Analysis]")[1]
                    evaluation_summary = f"\n      📊 {analysis_section[:150]}..."
            
            has_report = iss.get("has_report")
            assignees = iss.get("assignee_details") or []
            assignees_text = ", ".join([a.get("resolved", str(a)) for a in assignees])
            
            status_indicator = "✅" if has_report else "⏳"
            lines.append(
                f"  {status_indicator} {iss.get('issue_name')} | "
                f"assignees: {assignees_text}{evaluation_summary}"
            )
    
    # ... rest of existing prompt building ...
```

### 6. Add Analysis API Endpoints

**New File**: `src/auto_pm_agent_api/api/routes/analysis.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal

from auto_pm_agent_api.application.analysis_service.task_analyzer import TaskAnalyzer
from auto_pm_agent_api.infrastructure.llm.llm_client import LLMClient
from auto_pm_agent_api.infrastructure.plane_client.plane_api_factory import PlaneAPIFactory

router = APIRouter(prefix="/reports", tags=["analysis"])


class AnalyzeRequest(BaseModel):
    user_id: int
    project_id: str
    issue_id: str
    mode: Literal["realtime", "historical"] = "realtime"
    days: Optional[int] = 7


@router.post("/analyze")
async def analyze_report(
    request: AnalyzeRequest,
    llm_client: LLMClient = Depends(),
    plane_factory: PlaneAPIFactory = Depends()
):
    """On-demand task evaluation."""
    try:
        analyzer = TaskAnalyzer(llm_client, plane_factory)
        
        if request.mode == "historical":
            # Analyze trends over time
            trends = analyzer.analyze_trends(
                user_id=request.user_id,
                project_id=request.project_id,
                days=request.days
            )
            return {"status": "success", "trends": trends}
        else:
            # Analyze latest report
            plane_api = plane_factory.get_api(request.user_id)
            progress = plane_api.list_daily_progress(
                project_id=request.project_id,
                issue_id=request.issue_id,
                day=date.today().isoformat()
            )
            
            if not progress:
                raise HTTPException(404, "No report found for today")
            
            # ... extract and evaluate ...
            
            return {"status": "success", "evaluation": evaluation}
            
    except Exception as e:
        raise HTTPException(500, f"Analysis failed: {str(e)}")


@router.get("/trends")
async def get_trends(
    user_id: int,
    project_id: str,
    days: int = 30,
    llm_client: LLMClient = Depends(),
    plane_factory: PlaneAPIFactory = Depends()
):
    """Multi-day trend analysis."""
    analyzer = TaskAnalyzer(llm_client, plane_factory)
    trends = analyzer.analyze_trends(user_id, project_id, days)
    return {"status": "success", "data": trends}
```

## Further Considerations

### 1. Storage Strategy

**Options:**
- **Plane custom fields** (if supported): Store evaluation metadata directly in issue
- **Redis cache**: Key pattern `evaluation:{project}:{issue}:{day}`, 24h TTL
- **PostgreSQL table**: Rich querying, historical analysis, audit trail

**Recommendation:** Redis for MVP (fast, simple), migrate to database for production scale.

### 2. Historical Analysis Depth

- Default: 7 days (balance insight vs cost)
- Trends endpoint: 30 days configurable
- Manager dashboard: Aggregate weekly summaries
- Consider API rate limits when fetching bulk history

### 3. LLM Cost Optimization

**Strategies:**
- Cache evaluations (24h TTL, invalidate on new report)
- Use lighter models for scoring (GPT-3.5 Turbo vs GPT-4)
- Batch analyze multiple tasks in single prompt
- Rule-based fallback for simple cases (e.g., "100% done" = high quality)
- Implement token budgets per user/project

### 4. Evaluation Accuracy Validation

**Approaches:**
- A/B test prompts with sample reports
- Manager feedback loop ("Was this helpful?" button)
- Display confidence scores to indicate uncertainty
- Human-in-loop review for high-risk findings
- Periodic audit of false positives/negatives

## Implementation Timeline

**Phase 1 (Week 1):** Core analysis service + domain models
**Phase 2 (Week 2):** Integration with report push flow + manager view
**Phase 3 (Week 3):** API endpoints + optimization + testing

## Success Metrics

- Evaluation accuracy: >80% manager agreement
- Response time: <3s for realtime analysis
- LLM cost: <$0.10 per report
- Manager engagement: >60% click-through on insights
- Risk detection: Catch 90% of deadline misses

## Risk Mitigation

- Graceful degradation: Return reports without analysis on LLM failure
- Rate limiting: Protect against abuse
- Privacy: Mask sensitive info in prompts
- Monitoring: Alert on evaluation errors, quality drops