"""
Dump Plane data (projects, issues, members) to JSON without workspace block.

Usage:
    PYTHONPATH=src \
    PLANE_BASE_URL=https://... \
    PLANE_API_KEY=... \
    PLANE_WORKSPACE_SLUG=thang \
    python scripts/dump_plane_snapshot.py

Output:
    data/plane_snapshot.json
    data/plane_snapshot.log (stdout content)
"""

import json
import os
import sys
from auto_pm_agent_api.infrastructure.plane_client.plane_api_client import PlaneAPIClient


def main() -> None:
    client = PlaneAPIClient()
    result = {
        "projects": [],
        "workspace_members": [],
    }

    # Workspace members
    try:
        wm = client.list_members()
        result["workspace_members"] = [
            m.model_dump() if hasattr(m, "model_dump") else (m.dict() if hasattr(m, "dict") else m)
            for m in wm
        ]
        print(f"Workspace members: {len(result['workspace_members'])}")
    except Exception as e:
        result["workspace_members_error"] = str(e)
        print("Workspace members error:", e, file=sys.stderr)

    # Projects
    projects = []
    try:
        projects = client.list_projects()
        result["projects"] = [
            p.model_dump() if hasattr(p, "model_dump") else (p.dict() if hasattr(p, "dict") else p)
            for p in projects
        ]
        print(f"Projects: {len(projects)}")
    except Exception as e:
        result["projects_error"] = str(e)
        print("Projects error:", e, file=sys.stderr)

    # Details per project
    proj_blocks = []
    for p in projects:
        pid = getattr(p, "id", None) or p.get("id")
        pname = getattr(p, "name", None) or p.get("name")
        block = {"project_id": pid, "project_name": pname, "issues": [], "project_members": []}
        # Issues
        try:
            issues = client.list_issues(project_id=pid)
            block["issues"] = [
                i.model_dump() if hasattr(i, "model_dump") else (i.dict() if hasattr(i, "dict") else i)
                for i in issues
            ]
            print(f"  Issues for {pname}: {len(block['issues'])}")
        except Exception as e:
            block["issues_error"] = str(e)
            print(f"  Issues error for {pname}:", e, file=sys.stderr)
        # Project members
        try:
            pmembers = client.list_project_members(project_id=pid)
            block["project_members"] = [
                m.model_dump() if hasattr(m, "model_dump") else (m.dict() if hasattr(m, "dict") else m)
                for m in pmembers
            ]
            print(f"  Members for {pname}: {len(block['project_members'])}")
        except Exception as e:
            block["project_members_error"] = str(e)
            print(f"  Members error for {pname}:", e, file=sys.stderr)
        proj_blocks.append(block)

    result["projects_full"] = proj_blocks

    os.makedirs("data", exist_ok=True)
    out_path = "data/plane_snapshot.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    main()

