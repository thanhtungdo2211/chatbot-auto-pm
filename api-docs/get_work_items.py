import requests
import json

url = "http://localhost:8000/api/v1/workspaces/thang/projects/c70f7676-43c6-4a5f-962a-931a122409cb/issues/"

headers = {"x-api-key": "plane_api_d6a253ae1c904aeaa224d2fd63a0d5b6"}

response = requests.get(url, headers=headers)

try:
    data = response.json()
except ValueError:
    # not JSON, save raw text
    data = response.text

with open("work_items.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

if not response.ok:
    print(f"Request failed: {response.status_code}")