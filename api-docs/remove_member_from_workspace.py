import requests

# API endpoint configuration
workspace_slug = "workspace-mq"
member_id = "83d66dd9-9775-4178-ac4b-b7cdd9c7593d"
url = f"http://localhost:8000/api/workspaces/{workspace_slug}/remove-member/{member_id}/"

# Headers with API key
headers = {
    "x-api-key": "plane_api_ee8695a6d89a47638cc8850216e94e2e"
}

# Make DELETE request
try:
    response = requests.delete(url, headers=headers)
    
    # Check if request was successful
    if response.status_code in [200, 204]:
        print("Member removed from workspace successfully!")
        print(f"Status Code: {response.status_code}")
        if response.text:
            print("Response:", response.text)
    else:
        print(f"Failed to remove member. Status code: {response.status_code}")
        print("Response:", response.text)
        
except requests.exceptions.RequestException as e:
    print(f"Error making request: {e}")