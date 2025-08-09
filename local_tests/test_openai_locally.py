#!/usr/bin/env python3
"""
Test script for OpenAI components without Egnyte dependencies
Run this to test your OpenAI Responses API implementation locally
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://localhost:5000"  # Change if your Flask app runs on different port
# BASE_URL = "https://your-app.onrender.com"  # For production testing

def test_openai_components(test_type="template"):
    """
    Test OpenAI components
    
    Args:
        test_type: 'template', 'pdf', or 'both'
    """
    print("=" * 60)
    print(f"🧪 TESTING OPENAI COMPONENTS: {test_type.upper()}")
    print("=" * 60)
    
    url = f"{BASE_URL}/test-openai-only"
    
    payload = {
        "test_type": test_type
    }
    
    try:
        print(f"📡 Making request to: {url}")
        print(f"📦 Payload: {json.dumps(payload, indent=2)}")
        
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=120)  # 2 minute timeout
        end_time = time.time()
        
        print(f"⏱️  Request took: {end_time - start_time:.2f} seconds")
        print(f"📊 Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"📋 Message: {result.get('message', 'No message')}")
            
            # Print summary
            summary = result.get('summary', {})
            print(f"📈 Summary:")
            print(f"   Total Tests: {summary.get('total_tests', 0)}")
            print(f"   Successful: {summary.get('successful_tests', 0)}")
            print(f"   Success Rate: {summary.get('success_rate', '0%')}")
            
            # Print detailed results
            results = result.get('results', {})
            for test_name, test_result in results.items():
                status = test_result.get('status', 'unknown')
                print(f"\n🔬 {test_name.upper()}:")
                print(f"   Status: {status}")
                
                if status == 'success':
                    print(f"   ✅ Length: {test_result.get('analysis_length', 0)} characters")
                    preview = test_result.get('analysis_preview', '')
                    if preview:
                        print(f"   📄 Preview: {preview[:100]}...")
                elif status == 'failed':
                    print(f"   ❌ Error: {test_result.get('error', 'Unknown error')}")
                elif status == 'error':
                    print(f"   💥 Exception: {test_result.get('error', 'Unknown exception')}")
            
            return True
            
        else:
            print(f"❌ FAILED!")
            print(f"📄 Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"💥 REQUEST ERROR: {e}")
        return False
    except Exception as e:
        print(f"💥 UNEXPECTED ERROR: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Starting OpenAI Component Testing...")
    print("This will test your new Responses API implementation without Egnyte")
    print()
    
    # Test individual components
    tests = [
        ("template", "Template Processing Only"),
        ("pdf", "PDF Processing Only"), 
        ("both", "Full Integration Test")
    ]
    
    results = []
    
    for test_type, description in tests:
        print(f"\n🧪 Starting: {description}")
        success = test_openai_components(test_type)
        results.append((description, success))
        
        if not success:
            print(f"⚠️  Test '{description}' failed. Check your OpenAI configuration.")
        
        # Small delay between tests
        time.sleep(2)
    
    # Final summary
    print("\n" + "=" * 60)
    print("📊 FINAL TEST RESULTS")
    print("=" * 60)
    
    for description, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {description}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)
    
    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("🎉 All tests passed! Your OpenAI implementation is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the logs above for details.")

if __name__ == "__main__":
    main()
