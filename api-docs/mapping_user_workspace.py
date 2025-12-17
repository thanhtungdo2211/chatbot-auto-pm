import requests
from typing import List, Dict, Optional
import json

# Configuration
ZALO_WEBHOOK_BASE_URL = "http://zalooawebhook.demo.mqsolutions.vn/api"
PLANE_BASE_URL = "http://localhost"
WORKSPACE_SLUG = "workspacetdt"
PROJECT_ID = "dfaac5a5-301c-4907-b8e7-8065427782a8"
PLANE_API_KEY = "plane_api_55017c632ac040c993f6ab73e74eb736"

def get_user_from_zalo(email: str) -> Optional[Dict]:
    """
    Fetch user details from Zalo webhook server by email
    """
    try:
        url = f"{ZALO_WEBHOOK_BASE_URL}/users/email/{email}"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status") == "success":
            return data.get("user")
        return None
    except Exception as e:
        print(f"Error fetching user from Zalo for {email}: {e}")
        return None

def get_plane_workspace_members() -> List[Dict]:
    """
    Fetch workspace members from Plane
    """
    try:
        url = f"{PLANE_BASE_URL}/api/v1/workspaces/{WORKSPACE_SLUG}/members/"
        headers = {"x-api-key": PLANE_API_KEY}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching Plane workspace members: {e}")
        return []

def map_zalo_user_to_plane_format(plane_member: Dict, zalo_user: Optional[Dict]) -> Dict:
    """
    Map Zalo user data to Plane member format with additional fields
    """
    mapped_user = {
        "id": plane_member.get("id"),
        "first_name": plane_member.get("first_name"),
        "last_name": plane_member.get("last_name"),
        "email": plane_member.get("email"),
        "avatar": plane_member.get("avatar"),
        "avatar_url": plane_member.get("avatar_url"),
        "display_name": plane_member.get("display_name"),
        "role": plane_member.get("role"),
    }
    
    if zalo_user:
        mapped_user.update({
            "phone": zalo_user.get("phone"),
            "zalo_user_id": zalo_user.get("zalo_user_id"),
            "skills": zalo_user.get("skills", []),
            "cv": zalo_user.get("cv"),
            "cv_data": zalo_user.get("cv_data", {}),
            "description": zalo_user.get("description"),
            "experience_level": zalo_user.get("cv_data", {}).get("experience_level"),
            "experience_years": zalo_user.get("cv_data", {}).get("experience_years"),
            "projects": zalo_user.get("cv_data", {}).get("projects", []),
            "strengths": zalo_user.get("cv_data", {}).get("strengths", []),
            "zalo_role": zalo_user.get("role"),
            "is_active": zalo_user.get("is_active"),
            "created_at": zalo_user.get("created_at"),
            "updated_at": zalo_user.get("updated_at"),
        })
    else:
        mapped_user.update({
            "phone": None,
            "zalo_user_id": None,
            "skills": [],
            "cv": None,
            "cv_data": {},
            "description": None,
            "experience_level": None,
            "experience_years": None,
            "projects": [],
            "strengths": [],
            "zalo_role": None,
            "is_active": None,
            "created_at": None,
            "updated_at": None,
        })
    
    return mapped_user

def get_enriched_workspace_members() -> List[Dict]:
    """
    Get Plane workspace members enriched with Zalo user data
    """
    plane_members = get_plane_workspace_members()
    enriched_members = []
    
    for member in plane_members:
        email = member.get("email")
        zalo_user = get_user_from_zalo(email) if email else None
        enriched_member = map_zalo_user_to_plane_format(member, zalo_user)
        enriched_members.append(enriched_member)
    
    return enriched_members

# Main execution
if __name__ == "__main__":
    enriched_members = get_enriched_workspace_members()
    print(json.dumps(enriched_members, indent=2, ensure_ascii=False))