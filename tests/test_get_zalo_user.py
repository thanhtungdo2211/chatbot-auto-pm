import requests
import json

# API endpoint
url = "https://45fb5dd942c9.ngrok-free.app/api/users/"

# User data with Zalo metadata
data = {
    "email": "thang@example.com",
    "username": "thang",
    "first_name": "Test",
    "last_name": "User",
    "password": "SecurePassword123",
    "zalo_metadata": {
        "name": "Thang",
        "phone": "+84999999999",
        "zalo_user_id": "zalo_test_001",
        "description": "Test Account",
        "skills": ["Testing", "QA"],
        "role": "manager",
        "cv": "/uploads/cv/test_cv.pdf",
        "cv_data": {
            "experience": "2 years",
            "education": "Bachelor in IT"
        },
        "additional_info": {
            "location": "Hanoi"
        }
    }
}

headers = {
    "Content-Type": "application/json"
}

try:
    response = requests.post(url, headers=headers, json=data)
    
    if response.status_code in [200, 201]:
        print("✓ User created successfully!")
        print("Response:")
        print(json.dumps(response.json(), indent=2))
        
        # Now check if zalo_metadata was saved
        print("\n" + "="*50)
        print("Checking Zalo metadata in database...")
        print("="*50)
        
    else:
        print(f"✗ Failed to create user. Status code: {response.status_code}")
        print("Response:", response.text)
        
except requests.exceptions.RequestException as e:
    print(f"✗ Error making request: {e}")