import requests
import json

# User ID to search (replace with actual UUID)
user_id = "4479fe53-9428-467a-a929-ca6f2f78658f"  # Replace with your user ID

# API endpoint
url = f"http://localhost:8000/api/users/{user_id}/with-zalo/"

headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        print(f"✓ User found!")
        user_data = response.json()
        
        print("\n" + "="*50)
        print("USER INFORMATION")
        print("="*50)
        print(json.dumps({
            "id": user_data.get('id'),
            "username": user_data.get('username'),
            "email": user_data.get('email'),
            "name": f"{user_data.get('first_name')} {user_data.get('last_name')}"
        }, indent=2))
        
        if user_data.get('zalo_metadata'):
            print("\n" + "="*50)
            print("ZALO METADATA")
            print("="*50)
            print(json.dumps(user_data['zalo_metadata'], indent=2))
        else:
            print("\n✗ No Zalo metadata found for this user")
        
    elif response.status_code == 404:
        print(f"✗ User not found with ID: {user_id}")
    else:
        print(f"✗ Failed. Status code: {response.status_code}")
        print("Response:", response.text)
        
except requests.exceptions.RequestException as e:
    print(f"✗ Error: {e}")