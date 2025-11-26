"""Plane API Client for project management integration."""

import os
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PlaneProject(BaseModel):
    """Plane project model."""
    id: str
    name: str
    identifier: Optional[str] = None
    description: Optional[str] = None
    workspace: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PlaneIssue(BaseModel):
    """Plane issue model."""
    id: str
    name: str
    description: Optional[str] = None
    project: str
    state: Optional[str] = None
    priority: Optional[str] = None
    assignee: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PlaneMember(BaseModel):
    """Plane member model."""
    id: str
    member: Optional[Dict[str, Any]] = None
    role: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    display_name: Optional[str] = None
    
    @property
    def display_name(self) -> str:
        """Get member display name."""
        member_obj = self.member or {}
        return (
            self.display_name
            or member_obj.get("display_name")
            or member_obj.get("email")
            or self.email
            or member_obj.get("first_name")
            or "Unknown"
        )
    
    @property
    def email(self) -> str:
        """Get member email."""
        member_obj = self.member or {}
        return self.__dict__.get("email") or member_obj.get("email", "")


class PlaneAPIClient:
    """Client for interacting with Plane API."""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        workspace_slug: Optional[str] = None,
        timeout: float = 30.0
    ):
        """
        Initialize Plane API client.
        
        Args:
            base_url: Base URL for Plane API (e.g., http://192.168.6.16:8000)
            api_key: API key for authentication
            workspace_slug: Workspace slug
            timeout: Request timeout in seconds
        """
        self.base_url = (base_url or os.getenv("PLANE_BASE_URL", "http://192.168.6.16:8000")).rstrip("/")
        self.api_key = api_key or os.getenv("PLANE_API_KEY", "plane_api_d958d52c6c0845cb94b8dadd7fef425e")
        self.workspace_slug = workspace_slug or os.getenv("PLANE_WORKSPACE_SLUG", "thang")
        self.timeout = timeout
        
        if not self.base_url:
            raise ValueError("PLANE_BASE_URL must be set")
        if not self.api_key:
            raise ValueError("PLANE_API_KEY must be set")
        if not self.workspace_slug:
            raise ValueError("PLANE_WORKSPACE_SLUG must be set")
        
        # Configure client to follow redirects
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={
                "x-api-key": self.api_key,
                "Content-Type": "application/json"
            },
            timeout=timeout,
            follow_redirects=True  # Important: follow redirects automatically
        )
    
    def _get_workspace_url(self) -> str:
        """Get workspace base URL."""
        return f"/api/v1/workspaces/{self.workspace_slug}"
    
    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """Handle API response."""
        try:
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Plane API error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise
    
    # Workspace operations
    def get_workspace(self) -> Dict[str, Any]:
        """Get workspace details."""
        url = f"{self._get_workspace_url()}/"  # Added trailing slash
        response = self.client.get(url)
        return self._handle_response(response)
    
    # Project operations
    def list_projects(self) -> List[PlaneProject]:
        """List all projects in workspace."""
        url = f"{self._get_workspace_url()}/projects/"  # Added trailing slash
        logger.info(f"Fetching projects from: {url}")
        response = self.client.get(url)
        data = self._handle_response(response)
        return [PlaneProject(**project) for project in data.get("results", [])]
    
    def get_project(self, project_id: str) -> PlaneProject:
        """Get project by ID."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/"  # Added trailing slash
        response = self.client.get(url)
        data = self._handle_response(response)
        return PlaneProject(**data)
    
    def find_project_by_name(self, name: str) -> Optional[PlaneProject]:
        """Find project by name (case-insensitive partial match)."""
        name_lower = name.lower()
        projects = self.list_projects()
        for project in projects:
            if name_lower in project.name.lower():
                return project
        return None
    
    def create_project(
        self,
        name: str,
        identifier: str,
        description: Optional[str] = None,
        **kwargs
    ) -> PlaneProject:
        """
        Create a new project.
        
        Args:
            name: Project name
            identifier: Project identifier (unique short code)
            description: Project description
            **kwargs: Additional project fields
        
        Returns:
            PlaneProject instance
        """
        import re
        
        url = f"{self._get_workspace_url()}/projects/"  # Added trailing slash
        
        # Clean identifier: extract uppercase letters, max 6 chars (like old code)
        clean_identifier = re.sub(r"[^A-Z]", "", identifier.upper())[:6]
        
        payload = {
            "name": name,
            "identifier": clean_identifier,
            "description": description or "",
            "network": 2,  # From old update_plane.py
            "is_deployed": True,  # From old update_plane.py
            **kwargs
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        
        response = self.client.post(url, json=payload)
        data = self._handle_response(response)
        logger.info(f"✅ Created Project: {data.get('name')} ({data.get('id')})")
        return PlaneProject(**data)
    
    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        identifier: Optional[str] = None,
        description: Optional[str] = None,
        **kwargs
    ) -> PlaneProject:
        """Update a project."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/"  # Added trailing slash
        payload = {}
        if name is not None:
            payload["name"] = name
        if identifier is not None:
            payload["identifier"] = identifier
        if description is not None:
            payload["description"] = description
        payload.update(kwargs)
        
        response = self.client.patch(url, json=payload)
        data = self._handle_response(response)
        return PlaneProject(**data)
    
    # Member operations
    def list_members(self) -> List[PlaneMember]:
        """List all members in workspace."""
        url = f"{self._get_workspace_url()}/members/"  # Added trailing slash
        try:
            response = self.client.get(url)
            data = self._handle_response(response)
            payload = data.get("results") if isinstance(data, dict) else data
            if not isinstance(payload, list):
                logger.warning("Unexpected members payload; returning empty list.")
                return []
            return [PlaneMember(**member) for member in payload]
        except Exception as e:
            logger.warning(f"Could not fetch members: {e}")
            return []

    def list_project_members(self, project_id: str) -> List[PlaneMember]:
        """List all members belonging to a specific project."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/members/"  # Added trailing slash
        try:
            response = self.client.get(url)
            data = self._handle_response(response)
            members_data = data.get("results") if isinstance(data, dict) else data
            if not isinstance(members_data, list):
                logger.warning("Unexpected project members payload; returning empty list.")
                return []
            return [PlaneMember(**member) for member in members_data]
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(
                    "Project members endpoint not available; falling back to workspace members."
                )
                return self.list_members()
            logger.warning(f"Could not fetch project members: {e}")
            return []
        except Exception as e:
            logger.warning(f"Could not fetch project members: {e}")
            return []

    def add_member_to_project(self, project_id: str, email: str, role: int) -> Dict[str, Any]:
        """Add a workspace member to a specific project."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/add-member/"  # Added trailing slash
        payload = {"email": email, "role": role}
        try:
            response = self.client.post(url, json=payload)
            return self._handle_response(response)
        except Exception as e:
            logger.error(f"Failed to add member {email} to project {project_id}: {e}")
            raise

    def remove_member_from_workspace(self, member_id: str) -> bool:
        """Remove a member from the workspace (and associated projects)."""
        url = f"{self._get_workspace_url()}/remove-member/{member_id}/"  # Added trailing slash
        try:
            response = self.client.delete(url)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to remove member {member_id} from workspace: {e}")
            raise

    def delete_project(self, project_id: str) -> bool:
        """Delete a project."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/"  # Added trailing slash
        response = self.client.delete(url)
        response.raise_for_status()
        return True

    # Issue operations
    def list_issues(
        self,
        project_id: Optional[str] = None,
        state: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None
    ) -> List[PlaneIssue]:
        """List issues with optional filters."""
        if project_id:
            url = f"{self._get_workspace_url()}/projects/{project_id}/issues/"  # Added trailing slash
        else:
            url = f"{self._get_workspace_url()}/issues/"  # Added trailing slash
        
        params = {}
        if state:
            params["state"] = state
        if priority:
            params["priority"] = priority
        if assignee:
            params["assignee"] = assignee
        
        response = self.client.get(url, params=params)
        data = self._handle_response(response)
        return [PlaneIssue(**issue) for issue in data.get("results", [])]
    
    def get_issue(self, project_id: str, issue_id: str) -> PlaneIssue:
        """Get issue by ID."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/issues/{issue_id}/"  # Added trailing slash
        response = self.client.get(url)
        data = self._handle_response(response)
        return PlaneIssue(**data)
    
    def create_issue(
        self,
        project_id: str,
        name: str,
        description: Optional[str] = None,
        state: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        **kwargs
    ) -> PlaneIssue:
        """Create a new issue."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/issues/"  # Added trailing slash
        payload = {
            "name": name,
            "description": description or "",
            **kwargs
        }
        
        if state is not None:
            payload["state"] = state
        if priority is not None:
            payload["priority"] = priority
        if assignee is not None:
            payload["assignee"] = assignee
        
        response = self.client.post(url, json=payload)
        data = self._handle_response(response)
        logger.info(f"🧩 Created Task: {name}")
        return PlaneIssue(**data)
    
    def update_issue(
        self,
        project_id: str,
        issue_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        state: Optional[str] = None,
        priority: Optional[str] = None,
        assignee: Optional[str] = None,
        **kwargs
    ) -> PlaneIssue:
        """Update an issue."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/issues/{issue_id}/"  # Added trailing slash
        payload = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if state is not None:
            payload["state"] = state
        if priority is not None:
            payload["priority"] = priority
        if assignee is not None:
            payload["assignee"] = assignee
        payload.update(kwargs)
        
        response = self.client.patch(url, json=payload)
        data = self._handle_response(response)
        return PlaneIssue(**data)
    
    def delete_issue(self, project_id: str, issue_id: str) -> bool:
        """Delete an issue."""
        url = f"{self._get_workspace_url()}/projects/{project_id}/issues/{issue_id}/"  # Added trailing slash
        response = self.client.delete(url)
        response.raise_for_status()
        return True
    
    def close(self):
        """Close the HTTP client."""
        self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
