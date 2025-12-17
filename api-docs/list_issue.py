import requests
import json


workspace_slug = "thang"
project_id = "c70f7676-43c6-4a5f-962a-931a122409cb"

url = f"http://localhost:8000/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

headers = {"x-api-key": "plane_api_321f6a302c724a5c90adfc32f0da479e"}

response = requests.get(url, headers=headers)

print(json.dumps(response.json(), indent=2))