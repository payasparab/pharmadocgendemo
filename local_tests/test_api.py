import requests
import json

# Your deployed API URL
API_URL = "https://flask-receiver-for-retool.onrender.com"

def test_health_check():
    """Test the health check endpoint"""
    print("🔍 Testing Health Check...")
    try:
        response = requests.get(f"{API_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        print("✅ Health check successful!\n")
        return True
    except Exception as e:
        print(f"❌ Health check failed: {e}\n")
        return False

def test_list_folders():
    """Test the list folders endpoint"""
    print("📁 Testing List Folders...")
    try:
        response = requests.get(f"{API_URL}/list-folders")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        print("✅ List folders successful!\n")
        return True
    except Exception as e:
        print(f"❌ List folders failed: {e}\n")
        return False

def test_generate_folder_structure(molecule_code="TEST001", campaign_number="1"):
    """Test the folder generation endpoint"""
    print(f"🚀 Testing Generate Folder Structure...")
    print(f"Molecule Code: {molecule_code}")
    print(f"Campaign Number: {campaign_number}")
    
    payload = {
        "molecule_code": molecule_code,
        "campaign_number": campaign_number
    }
    
    try:
        response = requests.post(
            f"{API_URL}/generate-folder-structure",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Folder generation successful!")
            data = response.json()
            if "data" in data:
                print(f"📂 Project Folder: {data['data']['project_folder']['name']}")
                print(f"📂 Campaign Folder: {data['data']['campaign_folder']['name']}")
                print(f"📂 Reg Doc Folder: {data['data']['reg_doc_folder']['name']}")
        else:
            print("❌ Folder generation failed!")
        print()
        return response.json()
    except Exception as e:
        print(f"❌ Folder generation failed: {e}\n")
        return None

def test_deposit_file_with_path(folder_id, file_name="test.txt", file_content="This is a test file"):
    """Test the deposit file with path endpoint"""
    print(f"📤 Testing Deposit File with Path...")
    print(f"Folder ID: {folder_id}")
    print(f"File Name: {file_name}")
    
    import base64
    file_data = base64.b64encode(file_content.encode()).decode()
    
    payload = {
        "file_path": "/test/path",
        "folder_id": folder_id,
        "file_name": file_name,
        "file_data": file_data
    }
    
    try:
        response = requests.post(
            f"{API_URL}/deposit-file-with-path",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ File deposit successful!")
        else:
            print("❌ File deposit failed!")
        print()
        return response.json()
    except Exception as e:
        print(f"❌ File deposit failed: {e}\n")
        return None

def main():
    """Run all tests"""
    print("🧪 Testing Flask API at:", API_URL)
    print("=" * 50)
    
    # Test 1: Health Check
    if not test_health_check():
        print("❌ API is not responding. Please check your deployment.")
        return
    
    # Test 2: List Folders
    test_list_folders()
    
    # Test 3: Generate Folder Structure
    result = test_generate_folder_structure("THPG001", "3")
    
    # Test 4: Deposit File (if folder generation was successful)
    if result and "data" in result:
        # Use the project folder ID for file upload
        project_folder_id = result["data"]["project_folder"]["id"]
        test_deposit_file_with_path(project_folder_id, "test_document.txt", "This is a test document for the API.")
    
    print("🎉 Testing complete!")

if __name__ == "__main__":
    main() 