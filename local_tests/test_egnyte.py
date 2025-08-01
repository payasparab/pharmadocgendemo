import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from egnyte_client import (
    get_token, 
    get_folder_details, 
    list_folder_contents, 
    create_folder, 
    test_folder_creation
)
from credentials import ROOT_FOLDER

def main():
    print("🚀 Egnyte Client Test")
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
    
    # Display folder URL for browser access
    folder_path = folder_details.get('path', '')
    folder_url = f"https://app4americanaitechdev.egnyte.com/app/index.do#storage/files/1{folder_path}"
    print(f"\n🌐 Browser Access URL:")
    print(f"   {folder_url}")
    print(f"   Path: {folder_path}")
    
    # List folder contents (rate limiting is now automatic)
    contents = list_folder_contents(token, ROOT_FOLDER)
    
    if contents:
        # Count folders and files
        folders = [item for item in contents if item.get("is_folder", False)]
        files = [item for item in contents if not item.get("is_folder", False)]
        
        print(f"\n📊 Summary:")
        print(f"   Total items: {len(contents)}")
        print(f"   Folders: {len(folders)}")
        print(f"   Files: {len(files)}")
    
    # Test folder creation
    print("\n" + "=" * 50)
    print("🧪 Testing Folder Creation")
    print("=" * 50)
    
    test_result = test_folder_creation()
    
    if test_result:
        print("\n✅ Folder creation test completed successfully!")
        
        # Display URL for the created test folder
        test_folder_path = test_result.get('path', '')
        test_folder_url = f"https://app4americanaitechdev.egnyte.com/app/index.do#storage/files/1{test_folder_path}"
        print(f"\n🌐 Test Folder Browser Access URL:")
        print(f"   {test_folder_url}")
        print(f"   Path: {test_folder_path}")
        print(f"   Folder ID: {test_result.get('folder_id', 'Unknown')}")
    else:
        print("\n❌ Folder creation test failed!")
    
    print("\n🎉 All tests completed!")

if __name__ == "__main__":
    main() 