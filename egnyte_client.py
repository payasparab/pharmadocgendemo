import requests
import json
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

def main():
    print("🚀 Egnyte Client")
    print("=" * 50)
    print(f"Target Folder ID: {ROOT_FOLDER}")
    print("=" * 50)
    
    # Get token
    token = get_token()
    if not token:
        return
    
    # Get folder details
    folder_details = get_folder_details(token, ROOT_FOLDER)
    
    if not folder_details:
        print("❌ Could not get folder details")
        return
    
    # List folder contents
    contents = list_folder_contents(token, ROOT_FOLDER)
    
    if contents:
        # Count folders and files
        folders = [item for item in contents if item.get("is_folder", False)]
        files = [item for item in contents if not item.get("is_folder", False)]
        
        print(f"\n📊 Summary:")
        print(f"   Total items: {len(contents)}")
        print(f"   Folders: {len(folders)}")
        print(f"   Files: {len(files)}")
    
    print("\n🎉 Test completed!")

if __name__ == "__main__":
    main() 