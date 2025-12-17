"""
Đọc data/plane_snapshot.json và in ra text dễ đọc:
- Projects, issues kèm assignees (id -> display_name/email)
- Members mapping

Cách chạy:
    PYTHONPATH=src python scripts/format_plane_snapshot.py \
        --input data/plane_snapshot.json \
        --output data/plane_snapshot_human.txt
"""

import argparse
import json
from typing import Dict, Any


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_member_map(members):
    m = {}
    for mem in members:
        mid = mem.get("id")
        name = mem.get("display_name") or mem.get("email") or mid
        email = mem.get("email")
        role = mem.get("role")
        m[mid] = {
            "display": name,
            "email": email,
            "role": role,
        }
    return m


def resolve_assignees(assignees, member_map):
    if not assignees:
        return "None"
    resolved = []
    if isinstance(assignees, str):
        assignees = [assignees]
    for aid in assignees:
        info = member_map.get(aid) or {}
        disp = info.get("display") or aid
        email = info.get("email")
        role = info.get("role")
        extra = []
        if email:
            extra.append(email)
        if role is not None:
            extra.append(f"role={role}")
        if extra:
            resolved.append(f"{disp} ({', '.join(extra)})")
        else:
            resolved.append(disp)
    return ", ".join(resolved)


def format_snapshot(data: Dict[str, Any]) -> str:
    members = data.get("workspace_members", [])
    projects = data.get("projects", [])
    projects_full = data.get("projects_full", [])
    member_map = build_member_map(members)

    lines = []
    lines.append("=== MEMBERS ===")
    for mem in members:
        lines.append(
            f"- {mem.get('display_name') or mem.get('email')} | id: {mem.get('id')} | email: {mem.get('email')} | role: {mem.get('role')}"
        )

    lines.append("")
    lines.append("=== PROJECTS ===")
    for p in projects:
        lines.append(f"- {p.get('name')} (id: {p.get('id')}, identifier: {p.get('identifier')})")

    lines.append("")
    lines.append("=== PROJECT DETAILS ===")
    for block in projects_full:
        pname = block.get("project_name")
        pid = block.get("project_id")
        issues = block.get("issues", [])
        pmembers = block.get("project_members", [])
        lines.append(f"\nProject: {pname} | id: {pid}")
        if pmembers:
            lines.append("  Members:")
            for mem in pmembers:
                lines.append(
                    f"    - {mem.get('display_name') or mem.get('email')} | id: {mem.get('id')} | email: {mem.get('email')} | role: {mem.get('role')}"
                )
        lines.append(f"  Issues ({len(issues)}):")
        for iss in issues:
            assignees = iss.get("assignees") or iss.get("assignee")
            assignee_str = resolve_assignees(assignees, member_map)
            lines.append(
                f"    • {iss.get('name')} | id: {iss.get('id')} | state: {iss.get('state')} | assignees: {assignee_str} | start: {iss.get('start_date')} | target: {iss.get('target_date')}"
            )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/plane_snapshot.json")
    parser.add_argument("--output", default="data/plane_snapshot_human.txt")
    args = parser.parse_args()

    data = load_json(args.input)
    text = format_snapshot(data)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"Written summary to {args.output}")


if __name__ == "__main__":
    main()

