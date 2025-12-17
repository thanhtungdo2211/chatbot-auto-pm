"""
Dump RAG input data for a staff (filter by assignee id).

Usage:
    PYTHONPATH=src \
    PLANE_BASE_URL=... \
    PLANE_API_KEY=... \
    PLANE_WORKSPACE_SLUG=thang \
    python scripts/dump_staff_rag.py --assignee 475a1d57-49ce-4fca-bda7-ec368c70f340

Output:
    data/staff_rag_<assignee>.json
"""

import argparse
import json
import os

from auto_pm_agent_api.infrastructure.plane_client.plane_api_client import PlaneAPIClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--assignee", required=True, help="Plane user id to filter issues")
    parser.add_argument("--output", default=None, help="Output path (optional)")
    args = parser.parse_args()

    assignee = args.assignee
    client = PlaneAPIClient()

    result = {
        "assignee": assignee,
        "projects": [],
        "issues": [],
        "members": [],
    }

    # Members
    try:
        members = client.list_members()
        result["members"] = [
            m.model_dump() if hasattr(m, "model_dump") else (m.dict() if hasattr(m, "dict") else m)
            for m in members
        ]
    except Exception as exc:
        result["members_error"] = str(exc)

    # Projects and filtered issues
    try:
        projects = client.list_projects()
        result["projects"] = [
            p.model_dump() if hasattr(p, "model_dump") else (p.dict() if hasattr(p, "dict") else p)
            for p in projects
        ]
        issues_all = []
        for p in projects:
            pid = getattr(p, "id", None) or p.get("id")
            pname = getattr(p, "name", None) or p.get("name")
            try:
                issues = client.list_issues(project_id=pid, assignee=assignee)
                for i in issues:
                    obj = i.model_dump() if hasattr(i, "model_dump") else (i.dict() if hasattr(i, "dict") else i)
                    # Ensure issue really has assignee match
                    raw_assignees = obj.get("assignees") or obj.get("assignee") or []
                    if isinstance(raw_assignees, str):
                        raw_assignees = [raw_assignees]
                    if assignee in raw_assignees:
                        issues_all.append(obj)
            except Exception as exc:
                issues_all.append({"project_id": pid, "project_name": pname, "error": str(exc)})
        result["issues"] = issues_all
    except Exception as exc:
        result["projects_error"] = str(exc)

    os.makedirs("data", exist_ok=True)
    out_path = args.output or f"data/staff_rag_{assignee}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()

