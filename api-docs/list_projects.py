import requests
import json

url = "http://192.168.6.16:8000/api/v1/workspaces/thang/projects/"

headers = {"x-api-key": "plane_api_cc4469859d084733bcdcdbf7aa9c8979"}

response = requests.get(url, headers=headers)

print(json.dumps(response.json(), indent=2))