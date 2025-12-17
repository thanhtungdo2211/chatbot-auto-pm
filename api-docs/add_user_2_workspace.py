import requests
import json

# API endpoint
workspace_slug = "thang"
url = f"http://localhost:8000/api/workspaces/{workspace_slug}/add-member/"

# Member data
data = {
    "email": "testuser2@example.com",
    "role": 15
}

# Headers with API key
headers = {
    "Content-Type": "application/json",
    "x-api-key": "plane_api_d958d52c6c0845cb94b8dadd7fef425e"
}

# Make POST request
try:
    response = requests.post(url, headers=headers, json=data)
    
    # Check if request was successful
    if response.status_code in [200, 201]:
        print("Member added successfully!")
        print("Response:", response.json())
    else:
        print(f"Failed to add member. Status code: {response.status_code}")
        print("Response:", response.text)
        
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")