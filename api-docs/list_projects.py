import requests

url = "http://localhost:8000/api/v1/workspaces/thang/projects/"

headers = {"x-api-key": "plane_api_d958d52c6c0845cb94b8dadd7fef425e"}

response = requests.get(url, headers=headers)

print(response.json())