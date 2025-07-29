import requests
import time

# Your deployed API URL
API_URL = "https://flask-receiver-for-retool.onrender.com"

def test_threading():
    """Test that threading works correctly"""
    print("🧪 Testing Threading Functionality")
    print("=" * 50)
    
    # Test 1: Test the simple threading endpoint
    print("1. Testing simple threading endpoint...")
    start_time = time.time()
    
    response = requests.get(f"{API_URL}/test-thread")
    end_time = time.time()
    
    print(f"Response time: {end_time - start_time:.2f} seconds")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if end_time - start_time < 5:  # Should return immediately
        print("✅ Threading test passed - endpoint returned immediately!")
    else:
        print("❌ Threading test failed - endpoint took too long to respond")
    
    # Test 2: Test the folder generation endpoint
    print("\n2. Testing folder generation endpoint...")
    start_time = time.time()
    
    payload = {
        "molecule_code": "THREADTEST",
        "campaign_number": "1"
    }
    
    response = requests.post(
        f"{API_URL}/generate-folder-structure",
        json=payload,
        headers={"Content-Type": "application/json"}
    )
    end_time = time.time()
    
    print(f"Response time: {end_time - start_time:.2f} seconds")
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if end_time - start_time < 5:  # Should return immediately
        print("✅ Folder generation test passed - endpoint returned immediately!")
    else:
        print("❌ Folder generation test failed - endpoint took too long to respond")
    
    # Test 3: Check status immediately
    print("\n3. Checking job status...")
    status_response = requests.get(
        f"{API_URL}/folder-status",
        params={
            "molecule_code": "THREADTEST",
            "campaign_number": "1"
        }
    )
    
    print(f"Status Code: {status_response.status_code}")
    print(f"Status Response: {status_response.json()}")

def main():
    """Run the threading test"""
    print("🧪 Testing Threading at:", API_URL)
    print("=" * 50)
    
    # Test health first
    try:
        health_response = requests.get(f"{API_URL}/health")
        if health_response.status_code == 200:
            print("✅ API is responding")
        else:
            print("❌ API is not responding")
            return
    except Exception as e:
        print(f"❌ Cannot connect to API: {e}")
        return
    
    # Test threading
    test_threading()
    
    print("\n🎉 Threading test complete!")

if __name__ == "__main__":
    main() 