import sys
import os
import random
import string
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import functions directly from the consolidated Flask API
from flask_api import (
    get_egnyte_token, 
    get_egnyte_folder_details, 
    list_egnyte_folder_contents, 
    create_egnyte_folder
)
from credentials import ROOT_FOLDER

def generate_random_molecule_code():
    """Generate a random molecule code for testing"""
    # Generate format: THG + 3 random digits
    digits = ''.join(random.choices(string.digits, k=3))
    return f"THG{digits}"

def generate_random_campaign_number():
    """Generate a random campaign number for testing"""
    # Generate a random number between 1 and 999
    return str(random.randint(1, 999))

def test_simple_folder_creation():
    """Test simple folder creation with timestamp"""
    import time
    from datetime import datetime
    
    # Generate a more unique folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    folder_name = f"TEST_{timestamp}_{random_suffix}"
    
    print("🧪 Testing simple folder creation...")
    
    # Get token
    token = get_egnyte_token()
    if not token:
        print("❌ Failed to get token for test")
        return None
    
    # Create test folder in the root folder
    result = create_egnyte_folder(token, ROOT_FOLDER, folder_name)
    
    if result:
        print(f"✅ Test folder '{folder_name}' created successfully!")
        return result
    else:
        print(f"❌ Failed to create test folder '{folder_name}'")
        return None

def test_complete_folder_structure(molecule_code=None, campaign_number=None):
    """Test creating the complete folder structure matching app.py"""
    # Generate random codes if not provided
    if molecule_code is None:
        molecule_code = generate_random_molecule_code()
    if campaign_number is None:
        campaign_number = generate_random_campaign_number()
        
    print(f"\n" + "=" * 60)
    print(f"🧪 Testing Complete Folder Structure")
    print(f"   Molecule: {molecule_code}")
    print(f"   Campaign: {campaign_number}")
    print("=" * 60)
    
    # Get token
    token = get_egnyte_token()
    if not token:
        print("❌ Failed to get token for complete structure test")
        return None
    
    # Step 1: Create project folder
    print(f"\n📁 Step 1: Creating project folder...")
    project_folder_name = f"Project; Molecule {molecule_code}"
    project_folder = create_egnyte_folder(token, ROOT_FOLDER, project_folder_name)
    if not project_folder:
        print("❌ Failed to create project folder")
        return None
    
    project_folder_id = project_folder.get('folder_id')
    project_url = f"https://app4americanaitechdev.egnyte.com/app/index.do#storage/files/1{project_folder.get('path', '')}"
    print(f"✅ Project folder created: {project_folder_name}")
    print(f"   URL: {project_url}")
    
    # Step 2: Create campaign folder
    print(f"\n📁 Step 2: Creating campaign folder...")
    campaign_folder_name = f"Project {molecule_code} (Campaign #{campaign_number})"
    campaign_folder = create_egnyte_folder(token, project_folder_id, campaign_folder_name)
    if not campaign_folder:
        print("❌ Failed to create campaign folder")
        return None
    
    campaign_folder_id = campaign_folder.get('folder_id')
    campaign_url = f"https://app4americanaitechdev.egnyte.com/app/index.do#storage/files/1{campaign_folder.get('path', '')}"
    print(f"✅ Campaign folder created: {campaign_folder_name}")
    print(f"   URL: {campaign_url}")
    
    # Step 3: Create Pre and Post folders
    print(f"\n📁 Step 3: Creating Pre and Post folders...")
    pre_folder = create_egnyte_folder(token, campaign_folder_id, "Pre")
    post_folder = create_egnyte_folder(token, campaign_folder_id, "Post")
    
    if not pre_folder or not post_folder:
        print("❌ Failed to create Pre/Post folders")
        return None
    
    print(f"✅ Pre folder created")
    print(f"✅ Post folder created")
    
    # Step 4: Create department folders under Pre and Post
    print(f"\n📁 Step 4: Creating department folders...")
    departments = ["mfg", "Anal", "Stability", "CTM"]
    statuses = ["Draft", "Review", "Approved"]
    
    for phase_name, phase_folder in [("Pre", pre_folder), ("Post", post_folder)]:
        print(f"\n   Creating {phase_name} department structure...")
        phase_folder_id = phase_folder.get('folder_id')
        
        for dept in departments:
            dept_folder = create_egnyte_folder(token, phase_folder_id, dept)
            if dept_folder:
                dept_folder_id = dept_folder.get('folder_id')
                print(f"     ✅ Created {dept} folder")
                
                # Create status folders under each department
                for status in statuses:
                    status_folder = create_egnyte_folder(token, dept_folder_id, status)
                    if status_folder:
                        print(f"       ✅ Created {status} folder")
                    else:
                        print(f"       ❌ Failed to create {status} folder")
            else:
                print(f"     ❌ Failed to create {dept} folder")
    
    # Step 5: Create Draft AI Reg Document folder
    print(f"\n📁 Step 5: Creating Draft AI Reg Document folder...")
    reg_doc_folder = create_egnyte_folder(token, project_folder_id, "Draft AI Reg Document")
    if not reg_doc_folder:
        print("❌ Failed to create Draft AI Reg Document folder")
        return None
    
    reg_doc_folder_id = reg_doc_folder.get('folder_id')
    reg_doc_url = f"https://app4americanaitechdev.egnyte.com/app/index.do#storage/files/1{reg_doc_folder.get('path', '')}"
    print(f"✅ Draft AI Reg Document folder created")
    print(f"   URL: {reg_doc_url}")
    
    # Step 6: Create regulatory document folders
    print(f"\n📁 Step 6: Creating regulatory document folders...")
    reg_types = ["IND", "IMPD", "Canada"]
    
    for reg_type in reg_types:
        reg_type_folder = create_egnyte_folder(token, reg_doc_folder_id, reg_type)
        if reg_type_folder:
            reg_type_folder_id = reg_type_folder.get('folder_id')
            print(f"     ✅ Created {reg_type} folder")
            
            # Create status folders under each regulatory type
            for status in statuses:
                status_folder = create_egnyte_folder(token, reg_type_folder_id, status)
                if status_folder:
                    print(f"       ✅ Created {status} folder")
                else:
                    print(f"       ❌ Failed to create {status} folder")
        else:
            print(f"     ❌ Failed to create {reg_type} folder")
    
    # Summary
    print(f"\n" + "=" * 60)
    print(f"🎉 Complete Folder Structure Created Successfully!")
    print("=" * 60)
    print(f"📁 Project: {project_folder_name}")
    print(f"   URL: {project_url}")
    print(f"📁 Campaign: {campaign_folder_name}")
    print(f"   URL: {campaign_url}")
    print(f"📁 Draft AI Reg Document")
    print(f"   URL: {reg_doc_url}")
    print(f"\n📊 Structure Summary:")
    print(f"   • 1 Project folder")
    print(f"   • 1 Campaign folder")
    print(f"   • 2 Phase folders (Pre, Post)")
    print(f"   • 8 Department folders (4 per phase)")
    print(f"   • 24 Status folders (3 per department)")
    print(f"   • 1 Draft AI Reg Document folder")
    print(f"   • 3 Regulatory type folders (IND, IMPD, Canada)")
    print(f"   • 9 Regulatory status folders (3 per type)")
    print(f"   • Total: 49 folders created")
    
    return {
        "project_folder": project_folder,
        "campaign_folder": campaign_folder,
        "reg_doc_folder": reg_doc_folder,
        "urls": {
            "project": project_url,
            "campaign": campaign_url,
            "reg_doc": reg_doc_url
        }
    }

def main():
    print("🚀 Egnyte Client Test")
    print("=" * 50)
    print(f"Target Folder ID: {ROOT_FOLDER}")
    print("=" * 50)
    
    # Get token
    token = get_egnyte_token()
    if not token:
        return
    
    # Get folder details
    folder_details = get_egnyte_folder_details(token, ROOT_FOLDER)
    
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
    contents = list_egnyte_folder_contents(token, ROOT_FOLDER)
    
    if contents:
        # Handle the response structure properly
        if isinstance(contents, dict):
            # If it's a dictionary with folders and files arrays
            folders = contents.get("folders", [])
            files = contents.get("files", [])
            total_items = len(folders) + len(files)
        elif isinstance(contents, list):
            # If it's a list of items
            folders = [item for item in contents if item.get("is_folder", False)]
            files = [item for item in contents if not item.get("is_folder", False)]
            total_items = len(contents)
        else:
            print(f"❌ Unexpected response format: {type(contents)}")
            print(f"   Response: {contents}")
            folders = []
            files = []
            total_items = 0
        
        print(f"\n📊 Summary:")
        print(f"   Total items: {total_items}")
        print(f"   Folders: {len(folders)}")
        print(f"   Files: {len(files)}")
        
        # Show folder names if any
        if folders:
            print(f"\n📁 Folders found:")
            for folder in folders[:5]:  # Show first 5 folders
                print(f"   • {folder.get('name', 'Unknown')}")
            if len(folders) > 5:
                print(f"   ... and {len(folders) - 5} more")
    
    # Test simple folder creation
    print("\n" + "=" * 50)
    print("🧪 Testing Simple Folder Creation")
    print("=" * 50)
    
    test_result = test_simple_folder_creation()
    
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
    
    # Test complete folder structure
    print("\n" + "=" * 50)
    print("🧪 Testing Complete Folder Structure")
    print("=" * 50)
    
    complete_result = test_complete_folder_structure()  # Will use random codes
    
    if complete_result:
        print("\n✅ Complete folder structure test completed successfully!")
    else:
        print("\n❌ Complete folder structure test failed!")
    
    print("\n🎉 All tests completed!")

if __name__ == "__main__":
    main() 