import requests
import time
import json

# Your deployed API URL
API_URL = "https://flask-receiver-for-retool.onrender.com"

def test_async_folder_generation():
    """Test the async folder generation with polling"""
    print("🚀 Testing Async Folder Generation")
    print("=" * 50)
    
    # Step 1: Start the folder generation job
    print("1. Starting folder generation job...")
    payload = {
        "molecule_code": "TEST001",
        "campaign_number": "1"
    }
    
    response = requests.post(
        f"{API_URL}/generate-folder-structure",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    
    print(f"Status Code: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    
    if result.get("status") != "started":
        print("❌ Failed to start job")
        return
    
    job_key = result.get("job_key")
    print(f"✅ Job started with key: {job_key}")
    
    # Step 2: Poll for status
    print("\n2. Polling for job status...")
    max_attempts = 30  # 5 minutes max (10 second intervals)
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        print(f"   Poll attempt {attempt}/{max_attempts}...")
        
        status_response = requests.get(
            f"{API_URL}/folder-status",
            params={
                "molecule_code": "TEST001",
                "campaign_number": "1"
            }
        )
        
        status_result = status_response.json()
        print(f"   Status: {status_result.get('status')} - {status_result.get('message')}")
        
        if status_result.get("status") == "completed":
            print("✅ Job completed successfully!")
            print(f"   Project Folder: {status_result['data']['project_folder']['name']}")
            print(f"   Campaign Folder: {status_result['data']['campaign_folder']['name']}")
            print(f"   Reg Doc Folder: {status_result['data']['reg_doc_folder']['name']}")
            break
        elif status_result.get("status") == "failed":
            print("❌ Job failed!")
            print(f"   Error: {status_result.get('message')}")
            break
        elif status_result.get("status") == "running":
            progress = status_result.get("progress", 0)
            print(f"   Progress: {progress}%")
        
        # Wait 10 seconds before next poll
        time.sleep(10)
    
    if attempt >= max_attempts:
        print("⏰ Timeout - job took too long to complete")

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

def main():
    """Run the async test"""
    print("🧪 Testing Async Flask API at:", API_URL)
    print("=" * 50)
    
    # Test health first
    if not test_health_check():
        print("❌ API is not responding. Please check your deployment.")
        return
    
    # Test async folder generation
    test_async_folder_generation()
    
    print("\n🎉 Testing complete!")

if __name__ == "__main__":
    main() 