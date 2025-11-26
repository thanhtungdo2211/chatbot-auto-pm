"""Fetch all tasks and members for a specific Plane project."""

import argparse
import json
import logging
from typing import Any, Dict

from auto_pm_agent_api.infrastructure.plane_client.plane_api_client import (
    PlaneAPIClient,
    PlaneProject,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


def _matches_project(project: PlaneProject, key: str) -> bool:
    """Check if a project matches the provided key."""
    normalized_key = key.lower()
    return (
        project.id == key
        or (project.identifier and project.identifier.lower() == normalized_key)
        or project.name.lower() == normalized_key
    )


def resolve_project(plane_api: PlaneAPIClient, project_key: str) -> PlaneProject:
    """Find a project by id, identifier, or exact name."""
    projects = plane_api.list_projects()
    for project in projects:
        if _matches_project(project, project_key):
            return project
    available = [f"{p.name} ({p.identifier})" for p in projects]
    raise ValueError(
        f"Không tìm thấy project với id/identifier/name: {project_key}. "
        f"Các project hiện có: {', '.join(available) if available else 'không có'}."
    )


def collect_project_data(
    plane_api: PlaneAPIClient,
    project_key: str,
) -> Dict[str, Any]:
    """Collect project info, all tasks, and members."""
    project = resolve_project(plane_api, project_key)
    logger.info("Fetching tasks and members for project %s (%s)", project.name, project.id)

    tasks = plane_api.list_issues(project_id=project.id)
    members = plane_api.list_project_members(project.id)

    return {
        "project": project.model_dump(),
        "tasks": [task.model_dump() for task in tasks],
        "members": [
            {
                "id": member.id,
                "name": member.display_name,
                "email": member.email,
                "role": member.role,
                "raw": member.member,
            }
            for member in members
        ],
    }


def render_text(snapshot: Dict[str, Any]) -> str:
    """Format a human-friendly summary."""
    project = snapshot["project"]
    tasks = snapshot["tasks"]
    members = snapshot["members"]

    lines = [
        f"Project: {project.get('name')} ({project.get('identifier')})",
        f"Project ID: {project.get('id')}",
        f"Total tasks: {len(tasks)}",
    ]

    if tasks:
        lines.append("Tasks:")
        for idx, task in enumerate(tasks, 1):
            lines.append(
                f"  {idx}. {task.get('name')} "
                f"[state={task.get('state')}, priority={task.get('priority')}, assignee={task.get('assignee')}]"
            )
    else:
        lines.append("Tasks: none found.")

    lines.append(f"Total members: {len(members)}")
    if members:
        lines.append("Members:")
        for idx, member in enumerate(members, 1):
            lines.append(
                f"  {idx}. {member.get('name')} "
                f"(role={member.get('role') or 'unknown'}, email={member.get('email') or 'N/A'})"
            )
    else:
        lines.append("Members: none found.")

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Lấy toàn bộ tasks và members của 1 project trên Plane.",
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project id, identifier, hoặc tên chính xác.",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Override PLANE_BASE_URL nếu cần.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Override PLANE_API_KEY nếu cần.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Override PLANE_WORKSPACE_SLUG nếu cần.",
    )
    parser.add_argument(
        "--output",
        choices=["json", "text"],
        default="json",
        help="Định dạng output (json hoặc text).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        with PlaneAPIClient(
            base_url=args.base_url,
            api_key=args.api_key,
            workspace_slug=args.workspace,
        ) as plane_api:
            snapshot = collect_project_data(plane_api, args.project)

        if args.output == "json":
            print(json.dumps(snapshot, indent=2, ensure_ascii=False))
        else:
            print(render_text(snapshot))
    except Exception as exc:
        logger.error("Không thể lấy dữ liệu project: %s", exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
