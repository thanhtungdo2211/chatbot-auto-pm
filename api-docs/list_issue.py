import requests
import json


workspace_slug = "thang"
project_id = "3b694073-cc0e-4627-a392-fec50a428b69"

url = f"http://192.168.6.16:8000/api/v1/workspaces/{workspace_slug}/projects/{project_id}/issues/"

headers = {"x-api-key": "plane_api_cc4469859d084733bcdcdbf7aa9c8979"}

response = requests.get(url, headers=headers)

print(json.dumps(response.json(), indent=2))