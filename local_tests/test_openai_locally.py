#!/usr/bin/env python3
"""
Test script for OpenAI components without Egnyte dependencies
Run this to test your OpenAI Responses API implementation locally
"""

import requests
import json
import time
import os
import sys

# Configuration
BASE_URL = "http://localhost:5000"  # Change if your Flask app runs on different port
# BASE_URL = "https://your-app.onrender.com"  # For production testing

def check_openai_config():
    """Check OpenAI configuration"""
    print("=" * 60)
    print("OPENAI CONFIGURATION DIAGNOSTIC")
    print("=" * 60)
    
    # Check environment variable
    env_key = os.getenv('OPENAI_API_KEY')
    print(f"Environment Variable OPENAI_API_KEY: {'SET' if env_key else 'NOT SET'}")
    if env_key:
        print(f"  Length: {len(env_key)} characters")
        print(f"  Starts with: {env_key[:10]}...")
        if env_key == "your-openai-api-key-here":
            print("  WARNING: Using placeholder value!")
    
    # Try to import from credentials
    try:
        # Add parent directory to path to import credentials
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from credentials import OPENAI_API_KEY
        print(f"Credentials file OPENAI_API_KEY: {'SET' if OPENAI_API_KEY else 'NOT SET'}")
        if OPENAI_API_KEY:
            print(f"  Length: {len(OPENAI_API_KEY)} characters")
            print(f"  Starts with: {OPENAI_API_KEY[:10]}...")
            if OPENAI_API_KEY == "your-openai-api-key-here":
                print("  WARNING: Using placeholder value!")
    except ImportError:
        print("Credentials file: NOT FOUND")
    except Exception as e:
        print(f"Credentials file: ERROR - {e}")
    
    # Test OpenAI client initialization
    print("\nTesting OpenAI client initialization...")
    try:
        from openai import OpenAI
        
        # Try to get API key from flask_api logic
        try:
            # Add parent directory to path to import flask_api
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from flask_api import OPENAI_API_KEY, OPENAI_AVAILABLE
            print(f"Flask API OPENAI_AVAILABLE: {OPENAI_AVAILABLE}")
            if OPENAI_API_KEY:
                print(f"Flask API OPENAI_API_KEY: SET ({len(OPENAI_API_KEY)} chars)")
                
                # Try to create client
                client = OpenAI(api_key=OPENAI_API_KEY)
                print("OpenAI client created successfully!")
                
                # Test a simple API call
                print("Testing simple API call...")
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": "Say 'Hello World'"}],
                    max_tokens=10
                )
                print(f"API call successful: {response.choices[0].message.content}")
                return True
                
            else:
                print("Flask API OPENAI_API_KEY: NOT SET")
                return False
                
        except Exception as e:
            print(f"Flask API import error: {e}")
            return False
            
    except ImportError:
        print("OpenAI library not installed")
        return False
    except Exception as e:
        print(f"OpenAI client error: {e}")
        return False

def test_openai_components(test_type="template"):
    """
    Test OpenAI components
    
    Args:
        test_type: 'template', 'pdf', or 'both'
    """
    print("=" * 60)
    print(f"TESTING OPENAI COMPONENTS: {test_type.upper()}")
    print("=" * 60)
    
    url = f"{BASE_URL}/test-openai-only"
    
    payload = {
        "test_type": test_type
    }
    
    try:
        print(f"Making request to: {url}")
        print(f"Payload: {json.dumps(payload, indent=2)}")
        
        start_time = time.time()
        response = requests.post(url, json=payload, timeout=120)  # 2 minute timeout
        end_time = time.time()
        
        print(f"Request took: {end_time - start_time:.2f} seconds")
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("SUCCESS!")
            print(f"Message: {result.get('message', 'No message')}")
            
            # Print summary
            summary = result.get('summary', {})
            print(f"Summary:")
            print(f"  Total Tests: {summary.get('total_tests', 0)}")
            print(f"  Successful: {summary.get('successful_tests', 0)}")
            print(f"  Success Rate: {summary.get('success_rate', '0%')}")
            
            # Print detailed results
            results = result.get('results', {})
            all_tests_passed = True
            
            for test_name, test_result in results.items():
                status = test_result.get('status', 'unknown')
                print(f"\n{test_name.upper()}:")
                print(f"  Status: {status}")
                
                if status == 'success':
                    print(f"  Length: {test_result.get('analysis_length', 0)} characters")
                    preview = test_result.get('analysis_preview', '')
                    if preview:
                        print(f"  Preview: {preview[:100]}...")
                elif status == 'failed':
                    print(f"  Error: {test_result.get('error', 'Unknown error')}")
                    all_tests_passed = False
                elif status == 'error':
                    print(f"  Exception: {test_result.get('error', 'Unknown exception')}")
                    all_tests_passed = False
            
            # Only return True if ALL tests actually passed
            return all_tests_passed
            
        else:
            print(f"FAILED!")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"REQUEST ERROR: {e}")
        return False
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        return False

def main():
    """Run all tests"""
    print("Starting OpenAI Component Testing...")
    print("This will test your new Responses API implementation without Egnyte")
    print()
    
    # First, check OpenAI configuration
    print("STEP 1: Checking OpenAI Configuration...")
    openai_ok = check_openai_config()
    
    if not openai_ok:
        print("\n" + "=" * 60)
        print("OPENAI CONFIGURATION FAILED")
        print("=" * 60)
        print("Cannot proceed with tests. Please fix OpenAI configuration:")
        print("1. Add OPENAI_API_KEY to your credentials.py file, or")
        print("2. Set OPENAI_API_KEY environment variable")
        print("3. Ensure your API key is valid and has sufficient credits")
        print("4. Make sure the openai library is installed: pip install openai")
        return
    
    print("\n" + "=" * 60)
    print("OPENAI CONFIGURATION OK - PROCEEDING WITH TESTS")
    print("=" * 60)
    
    # Test individual components
    tests = [
        ("template", "Template Processing Only"),
        ("pdf", "PDF Processing Only"), 
        ("both", "Full Integration Test")
    ]
    
    results = []
    
    for test_type, description in tests:
        print(f"\nStarting: {description}")
        success = test_openai_components(test_type)
        results.append((description, success))
        
        if not success:
            print(f"Test '{description}' failed. Check your OpenAI configuration.")
        
        # Small delay between tests
        time.sleep(2)
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL TEST RESULTS")
    print("=" * 60)
    
    for description, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{status} {description}")
    
    total_tests = len(results)
    passed_tests = sum(1 for _, success in results if success)
    
    print(f"\nOverall: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("All tests passed! Your OpenAI implementation is working correctly.")
    else:
        print("Some tests failed. Check the logs above for details.")
        print(f"\nFAILURE SUMMARY:")
        print(f"- {total_tests - passed_tests} out of {total_tests} tests failed")
        print(f"- This means your OpenAI functions are returning None")
        print(f"- Check the Flask server console for detailed error logs")
        print("\nTo fix the issues:")
        print("1. Check that your OpenAI API key is properly configured")
        print("2. Ensure your API key is valid and has sufficient credits")
        print("3. Check the Flask server logs for detailed error messages")
        print("4. Make sure the Flask server is running: python flask_api.py")

if __name__ == "__main__":
    main()
