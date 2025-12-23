from auto_pm_agent_api.application.report_session import ReportSessionManager


def test_manager_payload_accepts_direct_query_and_name_id_variants():
    mgr = ReportSessionManager(general_bot=None, plane_factory=None)

    payload = {
        "day": "2025-12-18",
        "projects": [
            {
                "id": "p1",
                "name": "Demo phase 2",
                "issues": [
                    {
                        "id": "i1",
                        "name": "Task 1",
                        "assignee_ids": ["u1"],
                        "has_report": False,
                    }
                ],
            }
        ],
    }

    normalized = mgr._build_manager_payload_only(payload, member_map={})
    assert normalized["manager_summary_day"] == "2025-12-18"
    q = normalized["manager"][0]["query"]
    assert q["projects"][0]["project_name"] == "Demo phase 2"
    assert q["projects"][0]["issues"][0]["issue_name"] == "Task 1"

