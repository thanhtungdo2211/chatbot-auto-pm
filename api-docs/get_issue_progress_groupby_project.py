import requests
from datetime import datetime, timedelta, date
from collections import defaultdict
import json

# Configuration
PLANE_BASE_URL = "http://localhost:8000"
WORKSPACE_SLUG = "thang"
PLANE_API_KEY = "plane_api_321f6a302c724a5c90adfc32f0da479e"

def get_workspace_projects():
    """Fetch all projects in the workspace"""
    try:
        url = f"{PLANE_BASE_URL}/api/v1/workspaces/{WORKSPACE_SLUG}/projects/"
        headers = {"x-api-key": PLANE_API_KEY}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception as e:
        print(f"Error fetching projects: {e}")
        return []

def get_project_issues(project_id):
    """Fetch all issues for a project"""
    try:
        url = f"{PLANE_BASE_URL}/api/v1/workspaces/{WORKSPACE_SLUG}/projects/{project_id}/issues/"
        headers = {"x-api-key": PLANE_API_KEY}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
    except Exception as e:
        print(f"Error fetching issues for project {project_id}: {e}")
        return []

def get_issue_progress(project_id, issue_id, start_date=None, end_date=None):
    """Fetch daily progress for a specific issue"""
    try:
        url = f"{PLANE_BASE_URL}/api/workspaces/{WORKSPACE_SLUG}/projects/{project_id}/issues/{issue_id}/daily-progress/"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": PLANE_API_KEY
        }
        
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        
        response = requests.get(url, headers=headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Error fetching progress for issue {issue_id}: {e}")
        return []

def get_all_progress_grouped_by_project(start_date=None, end_date=None):
    """
    Get all issue progress grouped by project and day
    Returns: {
        "2024-01-15": {
            "project_name": {
                "project_id": "...",
                "issues": [
                    {
                        "issue_id": "...",
                        "issue_name": "...",
                        "progress": {...}
                    }
                ]
            }
        }
    }
    """
    # Data structure: day -> project -> issues
    grouped_data = defaultdict(lambda: defaultdict(lambda: {
        "project_id": None,
        "issues": []
    }))
    
    # Get all projects
    projects = get_workspace_projects()
    print(f"Found {len(projects)} projects in workspace '{WORKSPACE_SLUG}'")
    
    if start_date and end_date:
        print(f"Fetching progress from {start_date} to {end_date}\n")
    else:
        print("Fetching all progress entries\n")
    
    for project in projects:
        project_id = project.get("id")
        project_name = project.get("name")
        print(f"Processing project: {project_name}")
        
        # Get all issues in the project
        issues = get_project_issues(project_id)
        print(f"  Found {len(issues)} issues")
        
        for issue in issues:
            issue_id = issue.get("id")
            issue_name = issue.get("name")
            
            # Get progress for this issue
            progress_entries = get_issue_progress(project_id, issue_id, start_date, end_date)
            
            if progress_entries:
                print(f"    • {issue_name}: {len(progress_entries)} progress entries")
                
                # Group by day
                for progress in progress_entries:
                    day = progress.get("day")
                    
                    # Initialize project info if not set
                    if not grouped_data[day][project_name]["project_id"]:
                        grouped_data[day][project_name]["project_id"] = project_id
                    
                    # Add issue progress
                    grouped_data[day][project_name]["issues"].append({
                        "issue_id": issue_id,
                        "issue_name": issue_name,
                        "issue_sequence_id": progress.get("issue_sequence_id"),
                        "progress": progress
                    })
    
    return dict(grouped_data)

def format_and_display(grouped_data):
    """Format and display the grouped data"""
    print("\n" + "=" * 80)
    print("PROGRESS REPORT - GROUPED BY DAY AND PROJECT")
    print("=" * 80)
    
    if not grouped_data:
        print("No progress entries found")
        return
    
    # Sort by date (descending)
    sorted_days = sorted(grouped_data.keys(), reverse=True)
    
    for day in sorted_days:
        print(f"\n📅 {day}")
        print("-" * 80)
        
        projects = grouped_data[day]
        for project_name, project_data in projects.items():
            print(f"\n  📁 Project: {project_name}")
            print(f"     ID: {project_data['project_id']}")
            print(f"     Issues with progress: {len(project_data['issues'])}")
            
            for issue_data in project_data['issues']:
                progress = issue_data['progress']
                print(f"\n     • Issue #{issue_data['issue_sequence_id']}: {issue_data['issue_name']}")
                print(f"       ID: {issue_data['issue_id']}")
                print(f"       Notes: {progress.get('notes', 'No notes')[:100]}")
                
                if progress.get('daily_tasks'):
                    tasks = progress['daily_tasks']
                    if isinstance(tasks, dict) and tasks.get('tasks'):
                        print(f"       Tasks: {len(tasks['tasks'])} task(s)")
                        for task in tasks['tasks'][:3]:  # Show first 3 tasks
                            print(f"         - {task.get('title', 'Untitled')} ({task.get('status', 'unknown')})")

def save_to_json(grouped_data, filename="data/progress_by_project.json"):
    """Save the grouped data to JSON file"""
    import os
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(grouped_data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Results saved to {filename}")

def main():
    """Main function"""
    print("=" * 80)
    print(f"Fetching Progress Data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")
    
    # Option 1: Get all progress
    grouped_data = get_all_progress_grouped_by_project()
    
    # Option 2: Get progress for specific date range
    start_date = "2025-12-04"
    end_date = "2025-12-05"
    grouped_data = get_all_progress_grouped_by_project(start_date, end_date)
    
    # Option 3: Get progress for last 7 days
    # today = date.today()
    # last_week = today - timedelta(days=7)
    # grouped_data = get_all_progress_grouped_by_project(
    #     start_date=last_week.isoformat(),
    #     end_date=today.isoformat()
    # )
    
    # Display results
    format_and_display(grouped_data)
    
    # Save to file
    save_to_json(grouped_data)
    
    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    total_days = len(grouped_data)
    total_projects = set()
    total_issues = 0
    
    for day, projects in grouped_data.items():
        for project_name, project_data in projects.items():
            total_projects.add(project_name)
            total_issues += len(project_data['issues'])
    
    print(f"Total days with progress: {total_days}")
    print(f"Total projects: {len(total_projects)}")
    print(f"Total issue progress entries: {total_issues}")

if __name__ == "__main__":
    main()