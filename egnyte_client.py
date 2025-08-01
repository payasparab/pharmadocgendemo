import requests
import json
import time
from datetime import datetime
from credentials import DOMAIN, CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD, ROOT_FOLDER

def get_token():
    """Get access token"""
    url = f"https://{DOMAIN}/puboauth/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {
        "grant_type": "password",
        "username": USERNAME,
        "password": PASSWORD,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    print("🔐 Getting access token...")
    response = requests.post(url, data=data, headers=headers)
    
    if response.status_code == 200:
        token_data = response.json()
        print("✅ Token obtained successfully!")
        return token_data["access_token"]
    else:
        print(f"❌ Failed to get token: {response.status_code}")
        print(f"Response: {response.text}")
        return None

def get_folder_details(access_token, folder_id):
    """Get folder details using persistent ID"""
    print(f"\n📁 Getting folder details for ID: {folder_id}")
    
    url = f"https://{DOMAIN}/pubapi/v1/fs/ids/folder/{folder_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        print(f"✅ Folder: {data.get('name', 'Unknown')}")
        print(f"   Path: {data.get('path', 'Unknown')}")
        print(f"   ID: {data.get('group_id', 'Unknown')}")
        
        return data
        
    except requests.HTTPError as e:
        print(f"❌ Failed to get folder: {e}")
        print(f"Response: {e.response.text}")
        return None

def list_folder_contents(access_token, folder_id):
    """List folder contents using persistent ID"""
    print(f"\n📁 Listing contents for folder ID: {folder_id}")
    
    url = f"https://{DOMAIN}/pubapi/v1/fs/ids/folder/{folder_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Use list_content=true to get folder contents
    params = {
        "list_content": "true",
        "count": "100"  # Get up to 100 items
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        # Get folders and files from the correct response structure
        folders = data.get("folders", [])
        files = data.get("files", [])
        
        total_items = len(folders) + len(files)
        
        if total_items == 0:
            print("📭 No items found in this folder")
            return []
        
        print(f"✅ Found {total_items} items:")
        
        # Print folders first
        if folders:
            print(f"\n📁 Folders ({len(folders)}):")
            for folder in folders:
                folder_id = folder.get('folder_id', folder.get('group_id', 'No ID'))
                print(f"   📁 {folder['name']} (ID: {folder_id})")
                if folder.get('path'):
                    print(f"      Path: {folder['path']}")
        
        # Print files
        if files:
            print(f"\n📄 Files ({len(files)}):")
            for file in files:
                size_str = f" ({file['size']} bytes)" if file.get('size') else ""
                file_id = file.get('entry_id', file.get('group_id', 'No ID'))
                print(f"   📄 {file['name']}{size_str} (ID: {file_id})")
                if file.get('path'):
                    print(f"      Path: {file['path']}")
                if file.get('uploaded_by'):
                    print(f"      Uploaded by: {file['uploaded_by']}")
        
        # Return combined list for compatibility
        return folders + files
        
    except requests.HTTPError as e:
        print(f"❌ Failed to list folder contents: {e}")
        print(f"Response: {e.response.text}")
        return []

def create_folder(access_token, parent_folder_id, folder_name):
    """Create a new folder in Egnyte"""
    print(f"\n📁 Creating folder: {folder_name}")
    
    url = f"https://{DOMAIN}/pubapi/v1/fs/ids/folder/{parent_folder_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    # Folder creation data
    data = {
        "action": "add_folder",
        "name": folder_name
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        print(f"✅ Folder created successfully!")
        print(f"   Name: {result.get('name', folder_name)}")
        print(f"   ID: {result.get('folder_id', 'Unknown')}")
        print(f"   Path: {result.get('path', 'Unknown')}")
        
        return result
        
    except requests.HTTPError as e:
        print(f"❌ Failed to create folder: {e}")
        print(f"Response: {e.response.text}")
        return None

def test_folder_creation():
    """Test folder creation with timestamp"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"TEST_{timestamp}"
    
    print("🧪 Testing folder creation...")
    
    # Get token
    token = get_token()
    if not token:
        print("❌ Failed to get token for test")
        return None
    
    # Create test folder in the root folder
    result = create_folder(token, ROOT_FOLDER, folder_name)
    
    if result:
        print(f"✅ Test folder '{folder_name}' created successfully!")
        return result
    else:
        print(f"❌ Failed to create test folder '{folder_name}'")
        return None

# This module provides Egnyte API functionality
# For testing, use: python local_tests/test_egnyte.py 