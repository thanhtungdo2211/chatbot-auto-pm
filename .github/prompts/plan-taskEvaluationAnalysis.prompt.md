# Plan: Task Evaluation & Analysis Feature for Manager Progress Reporting

Build an automated task evaluation system that analyzes staff work reports for quality, risk, and trends, providing managers with actionable insights and recommendations alongside raw progress data.

## Steps

### 1. Create domain models for task evaluation

Add `TaskEvaluation`, `DailyTasksWithEvaluation`, and `WorkReportDataWithAnalysis` models with fields for quality scores (0-1), risk levels (low/medium/high), insights list, and recommendations list.

**File:** [src/auto_pm_agent_api/domain/models/__init__.py](src/auto_pm_agent_api/domain/models/__init__.py)

```python
class TaskEvaluation(BaseModel):
    task_id: str
    quality_score: float          # 0-1 based on clarity, specificity, completeness
    risk_level: str               # "low", "medium", "high", "critical"
    risk_factors: List[str]       # ["deadline_risk", "blocker_unresolved", "low_velocity"]
    insights: List[str]           # Automated observations
    recommendations: List[str]    # Actionable suggestions
    evaluated_at: Optional[str]   # ISO 8601 timestamp

class DailyTasksWithEvaluation(DailyTasks):
    evaluations: Optional[Dict[str, TaskEvaluation]] = None  # task_id -> evaluation

class WorkReportDataWithAnalysis(WorkReportData):
    daily_tasks: DailyTasksWithEvaluation
    overall_health: Optional[str] = None      # "good", "warning", "critical"
    trend_analysis: Optional[dict] = None     # Velocity, blocker trends, etc.
```

### 2. Build TaskAnalyzer service

Implement `TaskAnalyzer` class that uses LLM to evaluate report quality (output specificity, blocker detail, plan clarity), assess risk (deadline proximity, blocker severity), and generate actionable recommendations. Include method to fetch historical progress from `PlaneAPIClient.list_daily_progress()` for trend analysis.

**File:** [src/auto_pm_agent_api/application/analysis_service/task_analyzer.py](src/auto_pm_agent_api/application/analysis_service/task_analyzer.py)

```python
"""Service for analyzing and evaluating task reports."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from auto_pm_agent_api.domain.models import (
    DailyTask, 
    DailyTasks, 
    TaskEvaluation,
    WorkReportData
)
from auto_pm_agent_api.domain.prompts import PROMPT_TASK_EVALUATION

logger = logging.getLogger(__name__)


class TaskAnalyzer:
    """Analyze task reports for quality, risk, and trends."""
    
    def __init__(self, llm_client, plane_api=None):
        """
        Initialize the analyzer.
        
        Args:
            llm_client: LLM client for evaluation
            plane_api: Optional PlaneAPIClient for historical data
        """
        self.llm = llm_client
        self.plane_api = plane_api
    
    def evaluate_report(
        self,
        report_text: str,
        tasks: List[DailyTask],
        issue_context: Optional[Dict[str, Any]] = None,
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, TaskEvaluation]:
        """
        Evaluate tasks in a report.
        
        Args:
            report_text: Full report text
            tasks: List of DailyTask objects
            issue_context: Issue metadata (deadline, priority, etc.)
            historical_data: Previous progress entries for trend analysis
            
        Returns:
            Dict mapping task_id to TaskEvaluation
        """
        evaluations = {}
        
        for task in tasks:
            try:
                evaluation = self._evaluate_single_task(
                    task=task,
                    report_text=report_text,
                    issue_context=issue_context,
                    historical_data=historical_data
                )
                if task.id:
                    evaluations[task.id] = evaluation
            except Exception as exc:
                logger.warning(f"Failed to evaluate task {task.id}: {exc}")
                continue
        
        return evaluations
    
    def _evaluate_single_task(
        self,
        task: DailyTask,
        report_text: str,
        issue_context: Optional[Dict[str, Any]],
        historical_data: Optional[List[Dict[str, Any]]]
    ) -> TaskEvaluation:
        """Evaluate a single task using LLM."""
        # Build context for LLM
        context_parts = [
            f"Task: {task.title}",
            f"Status: {task.status}",
            f"Progress: {task.progress}%",
        ]
        
        if task.time_spent:
            context_parts.append(f"Time spent: {task.time_spent}")
        
        if issue_context:
            if issue_context.get("target_date"):
                context_parts.append(f"Deadline: {issue_context['target_date']}")
            if issue_context.get("priority"):
                context_parts.append(f"Priority: {issue_context['priority']}")
        
        # Add historical context
        if historical_data:
            history_summary = self._summarize_history(historical_data, task.id)
            if history_summary:
                context_parts.append(f"Historical context: {history_summary}")
        
        task_context = "\n".join(context_parts)
        
        # Build prompt
        prompt = PROMPT_TASK_EVALUATION.format(
            task_context=task_context,
            report_text=report_text
        )
        
        try:
            result = self.llm.generate_response(prompt, TaskEvaluation)
            
            # Ensure task_id is set
            if isinstance(result, dict):
                result["task_id"] = task.id or "unknown"
                result["evaluated_at"] = datetime.now(timezone.utc).isoformat()
                return TaskEvaluation(**result)
            elif isinstance(result, TaskEvaluation):
                result.task_id = task.id or "unknown"
                result.evaluated_at = datetime.now(timezone.utc).isoformat()
                return result
            else:
                raise ValueError(f"Unexpected result type: {type(result)}")
                
        except Exception as exc:
            logger.error(f"LLM evaluation failed: {exc}", exc_info=True)
            # Return minimal fallback evaluation
            return self._create_fallback_evaluation(task, issue_context)
    
    def _summarize_history(
        self, 
        historical_data: List[Dict[str, Any]], 
        task_id: Optional[str]
    ) -> str:
        """Summarize historical progress for context."""
        if not historical_data:
            return ""
        
        summaries = []
        for entry in historical_data[:5]:  # Last 5 entries
            day = entry.get("day", "unknown")
            daily_tasks = entry.get("daily_tasks", {})
            tasks = daily_tasks.get("tasks", [])
            
            # Find matching task by ID or title
            matching_task = None
            for t in tasks:
                if task_id and t.get("id") == task_id:
                    matching_task = t
                    break
            
            if matching_task:
                status = matching_task.get("status", "unknown")
                progress = matching_task.get("progress", 0)
                summaries.append(f"{day}: {status} ({progress}%)")
            
            # Include blockers if present
            blockers = daily_tasks.get("blockers", [])
            if blockers:
                summaries.append(f"  Blockers: {', '.join(blockers[:2])}")
        
        return " | ".join(summaries) if summaries else ""
    
    def _create_fallback_evaluation(
        self, 
        task: DailyTask,
        issue_context: Optional[Dict[str, Any]]
    ) -> TaskEvaluation:
        """Create basic evaluation when LLM fails."""
        risk_factors = []
        risk_level = "low"
        
        # Simple heuristics
        if task.progress < 50:
            risk_factors.append("low_progress")
            risk_level = "medium"
        
        if task.status == "todo" and task.progress > 0:
            risk_factors.append("status_progress_mismatch")
        
        if issue_context and issue_context.get("priority") in ["urgent", "high"]:
            risk_factors.append("high_priority")
            risk_level = "high"
        
        return TaskEvaluation(
            task_id=task.id or "unknown",
            quality_score=0.5,
            risk_level=risk_level,
            risk_factors=risk_factors,
            insights=["Automated evaluation unavailable"],
            recommendations=["Review task progress manually"],
            evaluated_at=datetime.now(timezone.utc).isoformat()
        )
    
    def fetch_history(
        self,
        project_id: str,
        issue_id: str,
        days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Fetch historical progress entries from Plane API.
        
        Args:
            project_id: Project ID
            issue_id: Issue ID
            days: Number of days to fetch (default 7)
            
        Returns:
            List of progress entries
        """
        if not self.plane_api:
            logger.warning("No Plane API client configured")
            return []
        
        try:
            end_date = datetime.now(timezone.utc).date()
            start_date = end_date - timedelta(days=days)
            
            entries = self.plane_api.list_daily_progress(
                project_id=project_id,
                issue_id=issue_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )
            
            return entries if isinstance(entries, list) else []
            
        except Exception as exc:
            logger.warning(f"Failed to fetch history: {exc}")
            return []
    
    def analyze_trends(
        self,
        historical_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze trends from historical data.
        
        Args:
            historical_data: List of progress entries
            
        Returns:
            Dict with trend analysis
        """
        if not historical_data:
            return {
                "velocity": None,
                "blocker_frequency": 0,
                "average_quality": None,
                "trend": "insufficient_data"
            }
        
        # Calculate metrics
        total_tasks = 0
        completed_tasks = 0
        blocker_count = 0
        quality_scores = []
        
        for entry in historical_data:
            daily_tasks = entry.get("daily_tasks", {})
            tasks = daily_tasks.get("tasks", [])
            blockers = daily_tasks.get("blockers", [])
            
            total_tasks += len(tasks)
            completed_tasks += sum(1 for t in tasks if t.get("status") == "done")
            blocker_count += len(blockers)
            
            # Extract quality scores if available
            evaluation = entry.get("evaluation", {})
            if isinstance(evaluation, dict):
                evaluations = evaluation.get("evaluations", {})
                for eval_data in evaluations.values():
                    if isinstance(eval_data, dict) and "quality_score" in eval_data:
                        quality_scores.append(eval_data["quality_score"])
        
        days = len(historical_data)
        velocity = completed_tasks / days if days > 0 else 0
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else None
        
        # Determine trend
        if velocity < 0.5:
            trend = "slow"
        elif velocity > 1.5:
            trend = "fast"
        else:
            trend = "normal"
        
        return {
            "velocity": round(velocity, 2),
            "blocker_frequency": blocker_count,
            "average_quality": round(avg_quality, 2) if avg_quality else None,
            "trend": trend,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "days_analyzed": days
        }
```

### 3. Create evaluation prompt

Add `PROMPT_TASK_EVALUATION` that instructs LLM to score task reports on specificity (concrete deliverables vs vague percentages), blocker actionability, and next-step clarity, while detecting risks like deadline misses, prolonged blockers, and velocity drops.

**File:** [src/auto_pm_agent_api/domain/prompts/__init__.py](src/auto_pm_agent_api/domain/prompts/__init__.py)

Add this prompt:

```python
PROMPT_TASK_EVALUATION = """You are an expert project manager evaluating task progress reports.

Analyze the following task and provide a structured evaluation:

{task_context}

Full Report:
{report_text}

Evaluate based on these criteria:

1. **Quality Score (0.0 - 1.0)**:
   - 1.0: Excellent - Specific deliverables mentioned (e.g., "completed API endpoint /users/login with JWT auth"), clear blockers with details, concrete next steps
   - 0.7: Good - Some specifics but mixed with vague statements (e.g., "made good progress on login feature")
   - 0.5: Acceptable - Mostly vague (e.g., "worked on login, 70% done")
   - 0.3: Poor - Only percentages or generic statements, no details
   - 0.0: Unacceptable - No meaningful information

2. **Risk Level** (low/medium/high/critical):
   - LOW: On track, no blockers, clear progress
   - MEDIUM: Minor blockers, slightly behind schedule, or vague reporting
   - HIGH: Significant blockers, deadline risk, or stalled progress
   - CRITICAL: Severe blockers, missed deadline, or no progress for extended period

3. **Risk Factors** (list applicable):
   - deadline_risk: Target date approaching with low progress
   - blocker_unresolved: Blocker persisting multiple days
   - low_velocity: Progress slower than expected
   - vague_reporting: Insufficient detail in report
   - status_mismatch: Status doesn't align with progress %
   - dependency_blocked: Waiting on external team/resource
   - scope_creep: Indication of expanding scope

4. **Insights** (2-3 key observations):
   - Objective findings about the task state
   - Pattern detection (e.g., "Task blocked for 3 consecutive days")
   - Progress trends (e.g., "Velocity decreased 40% this week")

5. **Recommendations** (1-3 actionable items):
   - Specific actions manager or team should take
   - Examples: "Schedule blocker review with backend team", "Clarify requirements for authentication flow", "Consider reassigning if blocked beyond 5 days"

Return ONLY valid JSON matching TaskEvaluation schema with these exact fields:
- task_id (string)
- quality_score (float 0-1)
- risk_level (string: "low"/"medium"/"high"/"critical")
- risk_factors (array of strings)
- insights (array of strings)
- recommendations (array of strings)

Be concise but specific. Focus on actionable intelligence for managers.
"""
```

### 4. Integrate analysis into report push flow

Modify `_push_report_to_plane` in `ReportSessionManager` to call `TaskAnalyzer.evaluate_report()` before creating daily progress entries, enriching Plane payload with evaluation metadata (if API supports custom fields) or storing in parallel cache layer.

**File:** [src/auto_pm_agent_api/application/report_session.py](src/auto_pm_agent_api/application/report_session.py)

**Changes needed:**
1. Import `TaskAnalyzer` at the top
2. Initialize analyzer in `__init__` (accept optional param or create on-demand)
3. In `_push_report_to_plane`, before `plane_api.create_daily_progress()`:
   - Extract `WorkReportData` from `report_text` using `WorkReportExtractor`
   - Call `analyzer.evaluate_report()` with tasks, issue context, and historical data
   - Add evaluation results to payload under `evaluation` key

```python
# In _push_report_to_plane method:

from auto_pm_agent_api.application.analysis_service import TaskAnalyzer
from auto_pm_agent_api.application.report_service import WorkReportExtractor

# After extracting report_text and before loop:
try:
    # Extract structured data
    extractor = WorkReportExtractor(self.general_bot)
    report_data = extractor.extract(report_text)
    
    # Initialize analyzer
    analyzer = TaskAnalyzer(self.general_bot, plane_api)
except Exception as exc:
    logger.warning(f"Failed to extract/analyze report: {exc}")
    report_data = None
    analyzer = None

# Inside loop for each issue:
if analyzer and report_data:
    try:
        # Fetch historical data
        historical_data = analyzer.fetch_history(project_id, issue_id, days=7)
        
        # Build issue context
        issue_context = {
            "target_date": getattr(issue, "target_date", None),
            "priority": getattr(issue, "priority", None),
            "start_date": getattr(issue, "start_date", None),
        }
        
        # Evaluate tasks
        evaluations = analyzer.evaluate_report(
            report_text=report_text,
            tasks=report_data.daily_tasks.tasks,
            issue_context=issue_context,
            historical_data=historical_data
        )
        
        # Add to payload
        payload["evaluation"] = {
            "evaluations": {k: v.dict() for k, v in evaluations.items()},
            "evaluated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as exc:
        logger.warning(f"Failed to evaluate report for issue {issue_id}: {exc}")
```

### 5. Enhance manager view with insights

Update `_build_manager_first_response` to parse evaluation data from progress entries and display quality scores, risk indicators (🟢🟡🔴), key insights ("Blocker persisting 3 days"), and top recommendation per task using structured formatting.

**File:** [src/auto_pm_agent_api/application/report_session.py](src/auto_pm_agent_api/application/report_session.py)

In the section where progress entries are formatted (around line 450-480), enhance the display:

```python
# After extracting progress details:
evaluation_data = entry.get("evaluation", {})
evaluations = evaluation_data.get("evaluations", {})

# Display evaluation summary
if evaluations:
    # Aggregate scores and risks
    scores = [e.get("quality_score", 0) for e in evaluations.values() if isinstance(e, dict)]
    risks = [e.get("risk_level", "low") for e in evaluations.values() if isinstance(e, dict)]
    
    avg_score = sum(scores) / len(scores) if scores else 0
    highest_risk = "low"
    if "critical" in risks:
        highest_risk = "critical"
    elif "high" in risks:
        highest_risk = "high"
    elif "medium" in risks:
        highest_risk = "medium"
    
    # Risk emoji mapping
    risk_emoji = {
        "low": "🟢",
        "medium": "🟡", 
        "high": "🔴",
        "critical": "🚨"
    }
    
    # Add evaluation summary to display
    eval_summary = f"Quality: {avg_score:.1f}/1.0 | Risk: {risk_emoji.get(highest_risk, '⚪')} {highest_risk.title()}"
    progress_details.insert(0, eval_summary)
    
    # Add key insights and recommendations
    all_insights = []
    all_recommendations = []
    for eval_item in evaluations.values():
        if isinstance(eval_item, dict):
            all_insights.extend(eval_item.get("insights", []))
            all_recommendations.extend(eval_item.get("recommendations", []))
    
    if all_insights:
        progress_details.append(f"💡 Insight: {all_insights[0]}")
    if all_recommendations:
        progress_details.append(f"🎯 Recommendation: {all_recommendations[0]}")
```

### 6. Add analysis API endpoints

Create `POST /reports/analyze` for on-demand evaluation with realtime/historical modes, and `GET /reports/trends` for multi-day metrics (velocity, blocker frequency, quality trends) using `PlaneAPIClient` date range queries.

**File:** [src/auto_pm_agent_api/infrastructure/api/routes.py](src/auto_pm_agent_api/infrastructure/api/routes.py)

```python
from auto_pm_agent_api.application.analysis_service import TaskAnalyzer

@router.post("/reports/analyze")
async def analyze_report(
    project_id: str,
    issue_id: str,
    day: Optional[str] = None,
    mode: str = "realtime",  # "realtime" or "historical"
    user_id: Optional[int] = None
):
    """
    Analyze a task report on-demand.
    
    Args:
        project_id: Project ID
        issue_id: Issue ID
        day: Specific day (YYYY-MM-DD), defaults to today
        mode: "realtime" (current data) or "historical" (with trends)
        user_id: User ID for Plane API authentication
    """
    try:
        if not day:
            day = datetime.now(timezone.utc).date().isoformat()
        
        # Get Plane API client
        plane_api = plane_factory.get_api(user_id) if user_id else plane_factory.get_default_api()
        
        # Fetch progress entries
        entries = plane_api.list_daily_progress(project_id, issue_id, day=day)
        
        if not entries:
            return {
                "success": False,
                "message": "No report found for specified day",
                "data": None
            }
        
        entry = entries[0]
        daily_tasks = entry.get("daily_tasks", {})
        tasks = daily_tasks.get("tasks", [])
        
        if not tasks:
            return {
                "success": False,
                "message": "No tasks found in report",
                "data": None
            }
        
        # Initialize analyzer
        analyzer = TaskAnalyzer(llm_client, plane_api)
        
        # Fetch historical data if needed
        historical_data = None
        if mode == "historical":
            historical_data = analyzer.fetch_history(project_id, issue_id, days=14)
        
        # Get issue details for context
        issue = plane_api.get_issue(project_id, issue_id)
        issue_context = {
            "target_date": getattr(issue, "target_date", None),
            "priority": getattr(issue, "priority", None),
            "start_date": getattr(issue, "start_date", None),
        }
        
        # Convert dict tasks to DailyTask objects
        task_objects = [DailyTask(**t) for t in tasks]
        
        # Evaluate
        evaluations = analyzer.evaluate_report(
            report_text=entry.get("notes", ""),
            tasks=task_objects,
            issue_context=issue_context,
            historical_data=historical_data
        )
        
        # Analyze trends if historical mode
        trend_analysis = None
        if mode == "historical" and historical_data:
            trend_analysis = analyzer.analyze_trends(historical_data)
        
        return {
            "success": True,
            "data": {
                "evaluations": {k: v.dict() for k, v in evaluations.items()},
                "trend_analysis": trend_analysis,
                "evaluated_at": datetime.now(timezone.utc).isoformat()
            }
        }
        
    except Exception as exc:
        logger.error(f"Analysis failed: {exc}", exc_info=True)
        return {
            "success": False,
            "message": str(exc),
            "data": None
        }


@router.get("/reports/trends")
async def get_report_trends(
    project_id: str,
    start_date: str,
    end_date: str,
    metrics: str = "velocity,blockers,quality",  # comma-separated
    user_id: Optional[int] = None
):
    """
    Get trend analysis across multiple days.
    
    Args:
        project_id: Project ID
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        metrics: Comma-separated list of metrics to compute
        user_id: User ID for Plane API authentication
    """
    try:
        # Get Plane API client
        plane_api = plane_factory.get_api(user_id) if user_id else plane_factory.get_default_api()
        
        # Parse metrics
        requested_metrics = [m.strip() for m in metrics.split(",")]
        
        # Get all issues in project
        issues = plane_api.list_issues(project_id=project_id)
        
        results = {}
        
        for issue in issues:
            issue_id = getattr(issue, "id", None)
            if not issue_id:
                continue
            
            # Fetch historical data
            entries = plane_api.list_daily_progress(
                project_id,
                issue_id,
                start_date=start_date,
                end_date=end_date
            )
            
            if not entries:
                continue
            
            # Initialize analyzer
            analyzer = TaskAnalyzer(llm_client, plane_api)
            
            # Compute trends
            trends = analyzer.analyze_trends(entries)
            
            results[issue_id] = {
                "issue_name": getattr(issue, "name", "Unknown"),
                "trends": trends
            }
        
        return {
            "success": True,
            "data": {
                "project_id": project_id,
                "start_date": start_date,
                "end_date": end_date,
                "issues": results
            }
        }
        
    except Exception as exc:
        logger.error(f"Trend analysis failed: {exc}", exc_info=True)
        return {
            "success": False,
            "message": str(exc),
            "data": None
        }
```

## Further Considerations

### 1. Storage Strategy

**Options:**
- **Plane custom fields** (if supported): Single source of truth, but requires API modification
- **Redis cache**: Fast retrieval with key format `evaluation:{project}:{issue}:{day}`, 24h TTL
- **PostgreSQL table**: Rich querying for time-series analysis, production-grade persistence

**Recommendation:** Start with Redis for MVP (fast, simple), migrate to PostgreSQL for production scale with historical analysis needs.

### 2. Historical Analysis Depth

**Configuration:**
- Default: Last 7 days for context in evaluations
- Trends endpoint: Configurable range (7-90 days)
- Balance: More data = better insights but higher API cost/latency

**Recommendations:**
- Implement caching for historical fetches (Redis, 1h TTL)
- Allow team-specific configuration via settings
- Add `days` parameter to `/reports/analyze` endpoint

### 3. LLM Cost Optimization

**Strategies:**
1. **Aggressive caching**: Store evaluations for 24h, recompute only if report changes
2. **Lighter models**: Use GPT-3.5-turbo for scoring, GPT-4 only for complex cases
3. **Batch processing**: Evaluate multiple tasks in single prompt (JSON array output)
4. **Rule-based fallback**: Use heuristics for simple cases (no blockers + 100% progress = good)
5. **Lazy evaluation**: Compute on-demand for manager view, not on every staff report

**Implementation:**
```python
# In TaskAnalyzer.__init__:
self.use_lightweight_model = True  # Config flag
self.enable_caching = True
self.cache_ttl = 86400  # 24 hours
```

### 4. Evaluation Accuracy Validation

**Quality Assurance:**
1. **Confidence scores**: LLM returns confidence (0-1) with each evaluation
2. **Manager feedback loop**: Add "👍 Helpful / 👎 Not helpful" buttons in UI
3. **Sample testing**: Validate with 50+ real reports before production
4. **Human review threshold**: Flag critical/high-risk evaluations for manual verification
5. **Prompt tuning**: Iteratively refine based on feedback data

**Monitoring:**
```python
# Track evaluation accuracy metrics
metrics = {
    "total_evaluations": counter,
    "manager_thumbs_up": counter,
    "manager_thumbs_down": counter,
    "override_rate": percentage,
    "avg_confidence": float
}
```

### 5. Privacy & Access Control

**Considerations:**
- Evaluation data may contain sensitive performance assessments
- Only managers should see evaluations (not staff or peers)
- Audit log for who accessed evaluation data
- Configurable evaluation criteria per team/project

**Implementation:**
```python
# Role-based filtering in API endpoints
if user_role != "manager":
    # Strip evaluation data from response
    response["evaluation"] = None
```

### 6. Performance & Scalability

**Potential Bottlenecks:**
1. **LLM latency**: 2-5s per task evaluation
2. **Plane API calls**: Historical fetches for many issues
3. **Large teams**: 50+ reports/day = 100+ LLM calls

**Solutions:**
- Async/background processing for report push (Celery queue)
- Batch evaluation during off-peak hours
- Pre-compute trends nightly for dashboard views
- Rate limiting on analysis endpoints

### 7. Error Handling & Graceful Degradation

**Failure Modes:**
1. LLM unavailable → Use rule-based fallback evaluation
2. Plane API timeout → Show reports without evaluation, add "Analyze now" button
3. Invalid report format → Skip evaluation, log for manual review
4. Historical data missing → Evaluate without trend context

**Principle:** Never block report submission due to evaluation failure.

## Implementation Phases

### Phase 1: Foundation (Week 1-2)
- ✅ Domain models
- ✅ TaskAnalyzer service core
- ✅ Evaluation prompt
- ✅ Integration into report push flow (optional evaluation)
- ✅ Basic manager view enhancement

**Deliverable:** Staff reports automatically scored, managers see quality/risk in summary.

### Phase 2: Historical Analysis (Week 3-4)
- ✅ Historical data fetching from Plane
- ✅ Trend analysis (velocity, blockers)
- ✅ Enhanced insights with patterns
- ✅ Redis caching layer

**Deliverable:** Managers see "Task blocked 3 days" insights, velocity trends.

### Phase 3: API & Dashboard (Week 5-6)
- ✅ `/reports/analyze` endpoint
- ✅ `/reports/trends` endpoint
- ✅ On-demand re-analysis
- ✅ PostgreSQL migration for persistence

**Deliverable:** Manager dashboard with metrics, exportable reports, alert system.

## Success Metrics

1. **Adoption**: % of manager views that include evaluation data
2. **Accuracy**: Manager feedback score (thumbs up/down ratio > 80%)
3. **Actionability**: % of recommendations marked as "acted upon"
4. **Performance**: Evaluation latency < 3s, report push delay < 5s
5. **Cost**: LLM API cost per report < $0.05

## Risk Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM inaccuracy | High | Medium | Validation testing, confidence scores, human review threshold |
| Cost overrun | Medium | High | Aggressive caching, lightweight models, batch processing |
| Plane API limitations | High | Low | Fallback to Redis storage, graceful degradation |
| Performance degradation | Medium | Medium | Async processing, background jobs, rate limiting |
| Privacy concerns | High | Low | Role-based access, audit logs, configurable criteria |

## Next Steps

1. **Review & Refine Plan**: Get feedback from team on approach
2. **Set Up Development Branch**: `feat/analysis` (already created)
3. **Implement Phase 1**: Start with domain models and core analyzer
4. **Write Tests**: Unit tests for TaskAnalyzer, integration tests for report flow
5. **Deploy to Staging**: Validate with sample data before production
