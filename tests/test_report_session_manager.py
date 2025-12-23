from auto_pm_agent_api.application.report_session import ReportSessionManager


class DummyPlaneProject:
    def __init__(self, project_id: str, name: str = "P"):
        self.id = project_id
        self.name = name


class DummyIssue:
    def __init__(
        self,
        issue_id: str,
        name: str,
        project_id: str,
        assignees=None,
        start_date=None,
        target_date=None,
    ):
        self.id = issue_id
        self.name = name
        self.project = project_id
        self.assignees = assignees or []
        self.start_date = start_date
        self.target_date = target_date


class DummyPlaneAPI:
    def __init__(self, projects, issues_by_project):
        self._projects = projects
        self._issues_by_project = issues_by_project

    def list_projects(self):
        return self._projects

    def list_issues(self, project_id=None, **kwargs):
        # Fallback path in ReportSessionManager should not require assignee kwargs.
        return self._issues_by_project.get(project_id, [])


def test_get_report_target_issues_prefers_report_context():
    mgr = ReportSessionManager(general_bot=None, plane_factory=None)
    plane_api = DummyPlaneAPI(projects=[], issues_by_project={})

    state = {
        "report_context": {
            "staff": [
                {
                    "user_id": "u1",
                    "tasks": [
                        {
                            "project_id": "p1",
                            "issue": {"id": "i1", "name": "Task 1"},
                        }
                    ],
                }
            ]
        }
    }

    issues = mgr._get_report_target_issues(plane_api, state, plane_user_id="u1", today_str="2025-12-18")
    assert issues == [{"project_id": "p1", "issue_id": "i1", "issue_name": "Task 1", "start_date": None, "target_date": None}]


def test_get_report_target_issues_fallback_filters_assignees_and_today_range():
    mgr = ReportSessionManager(general_bot=None, plane_factory=None)
    projects = [DummyPlaneProject("p1")]
    issues_by_project = {
        "p1": [
            DummyIssue(
                issue_id="i_in",
                name="In range assigned",
                project_id="p1",
                assignees=["u1"],
                start_date="2025-12-10",
                target_date="2025-12-20",
            ),
            DummyIssue(
                issue_id="i_out",
                name="Out of range assigned",
                project_id="p1",
                assignees=["u1"],
                start_date="2025-12-01",
                target_date="2025-12-05",
            ),
            DummyIssue(
                issue_id="i_other",
                name="Different assignee",
                project_id="p1",
                assignees=["u2"],
                start_date="2025-12-10",
                target_date="2025-12-20",
            ),
        ]
    }
    plane_api = DummyPlaneAPI(projects=projects, issues_by_project=issues_by_project)

    state = {"report_context": {"staff": []}}
    issues = mgr._get_report_target_issues(plane_api, state, plane_user_id="u1", today_str="2025-12-18")

    assert len(issues) == 1
    assert getattr(issues[0], "id") == "i_in"

