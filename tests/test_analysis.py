"""Demo script to test TaskAnalyzer with Plane API integration and completion metrics."""

import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from auto_pm_agent_api.application.analysis_service.task_analyzer import TaskAnalyzer
from auto_pm_agent_api.domain.models import DailyTask, CompletionMetrics, AggregatedEvaluation
from auto_pm_agent_api.infrastructure.llm_providers.llm_client import LLMClient


# Mock Plane API client for testing
class MockPlaneAPI:
    """Mock Plane API client for testing."""
    
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.api_key = "test_api_key"
    
    def get_issues(self, workspace_slug: str, project_id: str) -> List[Dict[str, Any]]:
        """Return mock issues."""
        return [
            {
                "id": "issue-001",
                "name": "Implement user authentication system",
                "project_detail": {"name": "Backend API"},
                "target_date": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d"),
                "priority": "high"
            },
            {
                "id": "issue-002",
                "name": "Setup CI/CD pipeline",
                "project_detail": {"name": "DevOps"},
                "target_date": (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d"),
                "priority": "medium"
            }
        ]
    
    def list_daily_progress(
        self,
        project_id: str,
        issue_id: str,
        start_date: str = None,
        end_date: str = None
    ) -> List[Dict[str, Any]]:
        """Return mock progress data."""
        if issue_id == "issue-001":
            return [
                {
                    "day": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
                    "daily_tasks": {
                        "tasks": [
                            {
                                "id": "TASK-001",
                                "title": "Setup JWT authentication",
                                "status": "done",
                                "progress": 100,
                                "time_spent": "6h"
                            },
                            {
                                "id": "TASK-002",
                                "title": "Implement refresh token mechanism",
                                "status": "in_progress",
                                "progress": 75,
                                "time_spent": "4h"
                            }
                        ],
                        "blockers": [],
                        "achievements": ["Completed JWT setup with secure token generation"]
                    },
                    "notes": "Completed JWT authentication setup. Working on refresh token mechanism."
                },
                {
                    "day": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"),
                    "daily_tasks": {
                        "tasks": [
                            {
                                "id": "TASK-001",
                                "title": "Setup JWT authentication",
                                "status": "in_progress",
                                "progress": 60,
                                "time_spent": "5h"
                            }
                        ],
                        "blockers": ["Need clarification on token expiry policy"],
                        "achievements": []
                    },
                    "notes": "Started JWT implementation. Blocked on token expiry policy."
                }
            ]
        elif issue_id == "issue-002":
            return [
                {
                    "day": datetime.now().strftime("%Y-%m-%d"),
                    "daily_tasks": {
                        "tasks": [
                            {
                                "id": "TASK-003",
                                "title": "Configure GitHub Actions",
                                "status": "todo",
                                "progress": 20,
                                "time_spent": "2h"
                            }
                        ],
                        "blockers": ["Waiting for cloud provider access"],
                        "achievements": []
                    },
                    "notes": "Started CI/CD setup. Blocked on cloud access."
                }
            ]
        return []


def create_sample_tasks():
    """Create sample tasks for testing."""
    return [
        DailyTask(
            id="TASK-001",
            title="Implement user authentication API",
            status="in_progress",
            progress=75,
            time_spent="6h"
        ),
        DailyTask(
            id="TASK-002",
            title="Fix database connection pooling",
            status="done",
            progress=100,
            time_spent="3h"
        ),
        DailyTask(
            id="TASK-003",
            title="Review pull requests",
            status="todo",
            progress=30,
            time_spent="1h"
        ),
    ]


def create_sample_report():
    """Create sample report text."""
    return """
Daily Progress Report - 2025-12-24

1. User Authentication API (TASK-001):
   - Completed JWT token generation and validation
   - Implemented refresh token mechanism
   - Added unit tests for authentication flow
   - Progress: 75% (added 15% today)
   - Blocker: Need to clarify password reset flow with product team

2. Database Connection Pooling Fix (TASK-002):
   - Identified root cause: connection leak in transaction rollback
   - Implemented proper connection cleanup
   - Added connection pool monitoring
   - Deployed to staging and verified fix
   - Status: COMPLETED ✓

3. Pull Request Reviews (TASK-003):
   - Started reviewing authentication PR
   - Found several security issues that need addressing
   - Delayed by urgent production issue
   - Progress: 30%

Blockers:
- Password reset flow specification unclear
- Security review taking longer than expected

Achievements:
- Fixed critical database issue
- Completed authentication core features

Next Steps:
- Schedule meeting with product team for password reset clarification
- Continue security review tomorrow
- Complete authentication API testing
"""


def print_evaluation(task_id: str, evaluation):
    """Pretty print evaluation results."""
    print(f"\n{'='*80}")
    print(f"EVALUATION FOR: {task_id}")
    print(f"{'='*80}")
    
    if hasattr(evaluation, 'model_dump'):
        eval_dict = evaluation.model_dump()
    elif isinstance(evaluation, dict):
        eval_dict = evaluation
    else:
        eval_dict = vars(evaluation)
    
    print(f"\n📊 Quality Score: {eval_dict.get('quality_score', 'N/A'):.2f}/1.0")
    
    risk_level = eval_dict.get('risk_level', 'unknown')
    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}.get(risk_level, "⚪")
    print(f"{risk_emoji} Risk Level: {risk_level.upper()}")
    
    risk_factors = eval_dict.get('risk_factors', [])
    if risk_factors:
        print(f"\n⚠️  Risk Factors:")
        for factor in risk_factors:
            print(f"   - {factor}")
    
    insights = eval_dict.get('insights', [])
    if insights:
        print(f"\n💡 Insights:")
        for insight in insights:
            print(f"   - {insight}")
    
    recommendations = eval_dict.get('recommendations', [])
    if recommendations:
        print(f"\n✅ Recommendations:")
        for rec in recommendations:
            print(f"   - {rec}")
    
    print(f"\n📅 Evaluated at: {eval_dict.get('evaluated_at', 'N/A')}")


def print_completion_metrics(metrics: CompletionMetrics):
    """Pretty print completion metrics."""
    print(f"\n{'='*80}")
    print("COMPLETION METRICS")
    print(f"{'='*80}")
    
    print(f"\n📋 Task Summary:")
    print(f"   - Total Tasks: {metrics.total_tasks}")
    print(f"   - Completed: {metrics.completed_tasks}")
    print(f"   - In Progress: {metrics.in_progress_tasks}")
    print(f"   - To Do: {metrics.todo_tasks}")
    print(f"   - Blocked: {metrics.blocked_tasks}")
    
    print(f"\n📊 Progress Metrics:")
    print(f"   - Average Progress: {metrics.average_progress:.1f}%")
    print(f"   - Completion Rate: {metrics.completion_rate:.1%}")
    
    print(f"\n⚠️  Risk Distribution:")
    for level, count in metrics.risk_distribution.items():
        if count > 0:
            emoji = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}.get(level, "⚪")
            print(f"   {emoji} {level.capitalize()}: {count}")


def print_aggregated_evaluation(agg_eval: AggregatedEvaluation):
    """Pretty print aggregated evaluation."""
    print(f"\n{'='*80}")
    print(f"AGGREGATED EVALUATION")
    print(f"{'='*80}")
    
    print(f"\n📁 Issue: {agg_eval.issue_name}")
    print(f"   ID: {agg_eval.issue_id}")
    if agg_eval.project_name:
        print(f"   Project: {agg_eval.project_name}")
    
    health_emoji = {"good": "✅", "warning": "⚠️", "critical": "🚨"}.get(agg_eval.overall_health, "⚪")
    print(f"\n{health_emoji} Overall Health: {agg_eval.overall_health.upper()}")
    
    print_completion_metrics(agg_eval.completion_metrics)
    
    print(f"\n{'='*80}")
    print(f"INDIVIDUAL TASK EVALUATIONS ({len(agg_eval.evaluations)})")
    print(f"{'='*80}")
    
    for task_id, evaluation in agg_eval.evaluations.items():
        print_evaluation(task_id, evaluation)


def test_basic_evaluation():
    """Test basic task evaluation functionality."""
    print("\n" + "="*80)
    print("TEST 1: BASIC TASK EVALUATION")
    print("="*80)
    
    # Initialize LLM client
    print("\n🔧 Initializing LLM client...")
    try:
        llm_client = LLMClient()
        print("✅ LLM client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize LLM client: {e}")
        print("ℹ️  Make sure API keys are configured")
        return False
    
    # Initialize analyzer
    print("\n🔧 Initializing TaskAnalyzer...")
    analyzer = TaskAnalyzer(llm_client=llm_client)
    print("✅ TaskAnalyzer initialized")
    
    # Prepare test data
    tasks = create_sample_tasks()
    report_text = create_sample_report()
    
    print(f"\n📝 Sample Report Preview:")
    print("-" * 80)
    print(report_text[:200] + "...")
    print("-" * 80)
    
    print(f"\n🔍 Evaluating {len(tasks)} tasks...")
    
    # Test evaluation
    try:
        evaluations = analyzer.evaluate_report(
            report_text=report_text,
            tasks=tasks,
            issue_context={
                "target_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"),
                "priority": "high"
            }
        )
        
        print(f"\n✅ Evaluated {len(evaluations)} tasks")
        
        # Print each evaluation
        for task_id, evaluation in evaluations.items():
            print_evaluation(task_id, evaluation)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_plane_api_integration():
    """Test Plane API integration and aggregated evaluation."""
    print("\n\n" + "="*80)
    print("TEST 2: PLANE API INTEGRATION & AGGREGATED EVALUATION")
    print("="*80)
    
    # Initialize LLM client
    print("\n🔧 Initializing LLM client...")
    try:
        llm_client = LLMClient()
    except Exception as e:
        print(f"❌ Failed to initialize LLM client: {e}")
        return False
    
    # Initialize mock Plane API
    print("\n🔧 Initializing Mock Plane API...")
    mock_plane = MockPlaneAPI()
    
    # Initialize analyzer with Plane API
    print("\n🔧 Initializing TaskAnalyzer with Plane API...")
    analyzer = TaskAnalyzer(llm_client=llm_client, plane_api=mock_plane)
    print("✅ TaskAnalyzer initialized with Plane API")
    
    # Test evaluation
    print("\n🔍 Fetching and evaluating issues from Plane...")
    try:
        aggregated_evaluations = analyzer.evaluate_issues_from_plane(
            workspace_slug="test-workspace",
            project_id="test-project-123"
        )
        
        print(f"\n✅ Evaluated {len(aggregated_evaluations)} issues")
        
        # Print each aggregated evaluation
        for agg_eval in aggregated_evaluations:
            print_aggregated_evaluation(agg_eval)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Plane API evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_completion_metrics():
    """Test completion metrics calculation."""
    print("\n\n" + "="*80)
    print("TEST 3: COMPLETION METRICS CALCULATION")
    print("="*80)
    
    # Initialize analyzer (no LLM needed for this test)
    print("\n🔧 Initializing TaskAnalyzer...")
    try:
        llm_client = LLMClient()
        analyzer = TaskAnalyzer(llm_client=llm_client)
    except:
        # If LLM fails, we can still test metrics calculation
        analyzer = TaskAnalyzer(llm_client=None)
    
    # Create test data
    tasks = [
        DailyTask(id="T1", title="Task 1", status="done", progress=100),
        DailyTask(id="T2", title="Task 2", status="done", progress=100),
        DailyTask(id="T3", title="Task 3", status="in_progress", progress=60),
        DailyTask(id="T4", title="Task 4", status="in_progress", progress=40),
        DailyTask(id="T5", title="Task 5", status="todo", progress=10),
    ]
    
    # Create mock evaluations
    from auto_pm_agent_api.domain.models import TaskEvaluation
    evaluations = {
        "T1": TaskEvaluation(
            task_id="T1", quality_score=0.9, risk_level="low",
            risk_factors=[], insights=["Good progress"], recommendations=[]
        ),
        "T2": TaskEvaluation(
            task_id="T2", quality_score=0.85, risk_level="low",
            risk_factors=[], insights=["Completed"], recommendations=[]
        ),
        "T3": TaskEvaluation(
            task_id="T3", quality_score=0.7, risk_level="medium",
            risk_factors=["vague_reporting"], insights=["Needs detail"], recommendations=[]
        ),
        "T4": TaskEvaluation(
            task_id="T4", quality_score=0.5, risk_level="high",
            risk_factors=["blocker_unresolved", "low_velocity"],
            insights=["Blocked"], recommendations=["Review blockers"]
        ),
        "T5": TaskEvaluation(
            task_id="T5", quality_score=0.3, risk_level="critical",
            risk_factors=["deadline_risk", "low_progress"],
            insights=["Behind schedule"], recommendations=["Escalate"]
        ),
    }
    
    print("\n🔍 Calculating completion metrics...")
    
    try:
        metrics = analyzer.calculate_completion_metrics(tasks, evaluations)
        print_completion_metrics(metrics)
        
        # Test health determination
        health = analyzer._determine_health(metrics, evaluations)
        health_emoji = {"good": "✅", "warning": "⚠️", "critical": "🚨"}.get(health, "⚪")
        print(f"\n{health_emoji} Determined Health: {health.upper()}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Metrics calculation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test function."""
    print("="*80)
    print("TASK ANALYZER COMPREHENSIVE TEST SUITE")
    print(f"Running at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    results = {}
    
    # Run all tests
    results["basic_evaluation"] = test_basic_evaluation()
    results["plane_api_integration"] = test_plane_api_integration()
    results["completion_metrics"] = test_completion_metrics()
    
    # Print summary
    print("\n\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    total_tests = len(results)
    passed_tests = sum(1 for p in results.values() if p)
    
    print(f"\n📊 Results: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Please review the output above.")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    main()