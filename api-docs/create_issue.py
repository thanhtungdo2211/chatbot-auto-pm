import requests


workspace_slug = "thang"
project_id = "c70f7676-43c6-4a5f-962a-931a122409cb"

url = f"http://localhost:8000/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

payload = { "name": "tung" }
headers = {
    "x-api-key": "plane_api_d958d52c6c0845cb94b8dadd7fef425e",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.json())