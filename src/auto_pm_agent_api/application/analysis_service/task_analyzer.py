"""Service for analyzing and evaluating task reports."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from auto_pm_agent_api.domain.models import (
    DailyTask, 
    DailyTasks, 
    TaskEvaluation,
    WorkReportData,
    CompletionMetrics,
    AggregatedEvaluation
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
    
    def evaluate_issues_from_plane(
        self,
        workspace_slug: str,
        project_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        issue_ids: Optional[List[str]] = None
    ) -> List[AggregatedEvaluation]:
        """
        Query issues from Plane API and evaluate them.
        
        Args:
            workspace_slug: Workspace slug
            project_id: Project ID
            start_date: Optional start date filter (ISO format)
            end_date: Optional end date filter (ISO format)
            issue_ids: Optional list of specific issue IDs to evaluate
            
        Returns:
            List of AggregatedEvaluation objects
        """
        if not self.plane_api:
            logger.error("Plane API client not configured")
            return []
        
        try:
            # Fetch issues
            issues = self._fetch_issues(workspace_slug, project_id, issue_ids)
            logger.info(f"Found {len(issues)} issues to evaluate")
            
            aggregated_evaluations = []
            
            for issue in issues:
                issue_id = issue.get("id")
                issue_name = issue.get("name", "Untitled Issue")
                
                # Fetch progress data for this issue
                progress_entries = self._fetch_issue_progress(
                    workspace_slug, project_id, issue_id, start_date, end_date
                )
                
                if not progress_entries:
                    logger.warning(f"No progress data found for issue {issue_id}")
                    continue
                
                # Aggregate tasks from all progress entries
                all_tasks = []
                all_reports = []
                
                for entry in progress_entries:
                    daily_tasks = entry.get("daily_tasks", {})
                    tasks = daily_tasks.get("tasks", [])
                    notes = entry.get("notes", "")
                    
                    # Convert to DailyTask objects
                    for task_data in tasks:
                        task = DailyTask(
                            id=task_data.get("id"),
                            title=task_data.get("title", "Untitled"),
                            status=task_data.get("status", "todo"),
                            progress=task_data.get("progress", 0),
                            time_spent=task_data.get("time_spent")
                        )
                        all_tasks.append(task)
                    
                    all_reports.append(notes)
                
                # Evaluate all tasks
                report_text = "\n\n---\n\n".join(all_reports)
                issue_context = {
                    "target_date": issue.get("target_date"),
                    "priority": issue.get("priority"),
                    "issue_id": issue_id,
                    "issue_name": issue_name
                }
                
                evaluations = self.evaluate_report(
                    report_text=report_text,
                    tasks=all_tasks,
                    issue_context=issue_context,
                    historical_data=progress_entries
                )
                
                # Calculate completion metrics
                completion_metrics = self.calculate_completion_metrics(all_tasks, evaluations)
                
                # Determine overall health
                overall_health = self._determine_health(completion_metrics, evaluations)
                
                # Create aggregated evaluation
                agg_eval = AggregatedEvaluation(
                    issue_id=issue_id,
                    issue_name=issue_name,
                    project_id=project_id,
                    project_name=issue.get("project_detail", {}).get("name"),
                    evaluations=evaluations,
                    completion_metrics=completion_metrics,
                    overall_health=overall_health,
                    evaluated_at=datetime.now(timezone.utc).isoformat()
                )
                
                aggregated_evaluations.append(agg_eval)
            
            return aggregated_evaluations
            
        except Exception as exc:
            logger.error(f"Failed to evaluate issues from Plane: {exc}", exc_info=True)
            return []
    
    def _fetch_issues(
        self,
        workspace_slug: str,
        project_id: str,
        issue_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch issues from Plane API."""
        try:
            # Use plane_api client to fetch issues
            if hasattr(self.plane_api, 'get_issues'):
                issues = self.plane_api.get_issues(workspace_slug, project_id)
            else:
                # Fallback to direct API call if method doesn't exist
                import requests
                url = f"{self.plane_api.base_url}/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"
                headers = {"x-api-key": self.plane_api.api_key}
                response = requests.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()
                issues = data.get("results", [])
            
            # Filter by issue_ids if provided
            if issue_ids:
                issues = [i for i in issues if i.get("id") in issue_ids]
            
            return issues
            
        except Exception as exc:
            logger.error(f"Failed to fetch issues: {exc}")
            return []
    
    def _fetch_issue_progress(
        self,
        workspace_slug: str,
        project_id: str,
        issue_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch progress entries for an issue."""
        try:
            # Use plane_api client
            if hasattr(self.plane_api, 'list_daily_progress'):
                return self.plane_api.list_daily_progress(
                    project_id=project_id,
                    issue_id=issue_id,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # Fallback to direct API call
                import requests
                url = f"{self.plane_api.base_url}/api/workspaces/{workspace_slug}/projects/{project_id}/issues/{issue_id}/daily-progress/"
                headers = {"x-api-key": self.plane_api.api_key, "Content-Type": "application/json"}
                params = {}
                if start_date:
                    params["start_date"] = start_date
                if end_date:
                    params["end_date"] = end_date
                
                response = requests.get(url, headers=headers, params=params)
                response.raise_for_status()
                return response.json()
                
        except Exception as exc:
            logger.error(f"Failed to fetch progress for issue {issue_id}: {exc}")
            return []
    
    def calculate_completion_metrics(
        self,
        tasks: List[DailyTask],
        evaluations: Dict[str, TaskEvaluation]
    ) -> CompletionMetrics:
        """
        Calculate completion metrics from tasks and evaluations.
        
        Args:
            tasks: List of DailyTask objects
            evaluations: Dict of task evaluations
            
        Returns:
            CompletionMetrics object
        """
        if not tasks:
            return CompletionMetrics()
        
        total_tasks = len(tasks)
        completed_tasks = sum(1 for t in tasks if t.status == "done")
        in_progress_tasks = sum(1 for t in tasks if t.status == "in_progress")
        todo_tasks = sum(1 for t in tasks if t.status == "todo")
        
        # Count blocked tasks (tasks with blockers in evaluations)
        blocked_tasks = 0
        risk_distribution = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        
        for task_id, evaluation in evaluations.items():
            # Count risk levels
            risk_level = evaluation.risk_level
            if risk_level in risk_distribution:
                risk_distribution[risk_level] += 1
            
            # Check for blocker-related risks
            if "blocker_unresolved" in evaluation.risk_factors or \
               "dependency_blocked" in evaluation.risk_factors:
                blocked_tasks += 1
        
        # Calculate average progress
        total_progress = sum(t.progress for t in tasks)
        average_progress = total_progress / total_tasks if total_tasks > 0 else 0.0
        
        # Calculate completion rate
        completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0.0
        
        return CompletionMetrics(
            total_tasks=total_tasks,
            completed_tasks=completed_tasks,
            in_progress_tasks=in_progress_tasks,
            todo_tasks=todo_tasks,
            blocked_tasks=blocked_tasks,
            average_progress=round(average_progress, 2),
            completion_rate=round(completion_rate, 2),
            risk_distribution=risk_distribution
        )
    
    def _determine_health(
        self,
        metrics: CompletionMetrics,
        evaluations: Dict[str, TaskEvaluation]
    ) -> str:
        """
        Determine overall health based on metrics and evaluations.
        
        Returns: "good", "warning", or "critical"
        """
        # Critical conditions
        if metrics.risk_distribution.get("critical", 0) > 0:
            return "critical"
        
        if metrics.completion_rate < 0.3 and metrics.total_tasks > 0:
            return "critical"
        
        # Warning conditions
        high_risk_count = metrics.risk_distribution.get("high", 0)
        if high_risk_count > metrics.total_tasks * 0.3:  # More than 30% high risk
            return "warning"
        
        if metrics.blocked_tasks > metrics.total_tasks * 0.2:  # More than 20% blocked
            return "warning"
        
        if metrics.average_progress < 40 and metrics.todo_tasks > metrics.in_progress_tasks:
            return "warning"
        
        # Good conditions
        return "good"
    
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
            
            # LLM should return TaskEvaluation directly
            if isinstance(result, TaskEvaluation):
                # Set evaluated_at if not already set by LLM
                if not result.evaluated_at:
                    result.evaluated_at = datetime.now(timezone.utc).isoformat()
                # Ensure task_id is correct
                if not result.task_id or result.task_id == "unknown":
                    result.task_id = task.id or "unknown"
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