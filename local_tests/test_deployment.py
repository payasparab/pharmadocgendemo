import requests

# Your deployed API URL
API_URL = "https://flask-receiver-for-retool.onrender.com"

def test_endpoints():
    """Test which endpoints are available"""
    print("🔍 Testing Available Endpoints")
    print("=" * 50)
    
    endpoints = [
        ("/health", "GET"),
        ("/test-thread", "GET"),
        ("/generate-folder-structure", "POST"),
        ("/folder-status", "GET"),
        ("/list-folders", "GET")
    ]
    
    for endpoint, method in endpoints:
        print(f"\nTesting {method} {endpoint}...")
        try:
            if method == "GET":
                response = requests.get(f"{API_URL}{endpoint}")
            elif method == "POST":
                response = requests.post(f"{API_URL}{endpoint}", json={})
            
            print(f"  Status Code: {response.status_code}")
            if response.status_code == 200:
                print(f"  ✅ Available")
                try:
                    print(f"  Response: {response.json()}")
                except:
                    print(f"  Response: {response.text[:100]}...")
            elif response.status_code == 404:
                print(f"  ❌ Not Found (404)")
            elif response.status_code == 405:
                print(f"  ⚠️ Method Not Allowed (405)")
            else:
                print(f"  ⚠️ Status: {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Error: {e}")

def test_health_detailed():
    """Test health endpoint in detail"""
    print("\n🔍 Testing Health Endpoint in Detail")
    print("=" * 50)
    
    try:
        response = requests.get(f"{API_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"JSON Response: {data}")
            except:
                print("Response is not valid JSON")
        else:
            print("Health endpoint is not working")
            
    except Exception as e:
        print(f"Error testing health: {e}")

def main():
    """Run the deployment test"""
    print("🧪 Testing Deployment at:", API_URL)
    print("=" * 50)
    
    # Test health first
    test_health_detailed()
    
    # Test all endpoints
    test_endpoints()
    
    print("\n🎉 Deployment test complete!")

if __name__ == "__main__":
    main() 