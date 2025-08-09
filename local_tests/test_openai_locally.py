#!/usr/bin/env python3
"""
Test script for the new simplified document generation function
Tests the upload_files_prompt_to_openai function with local files
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

def check_test_files():
    """Check if required test files exist"""
    print("=" * 60)
    print("TEST FILES CHECK")
    print("=" * 60)
    
    # Check if we're in the right directory
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    
    # Test files
    template_file = "IND_3.2.P.1_Template.docx"
    source_file = "THPG001009 Product Code.pdf"
    
    files_exist = True
    
    # Check template file
    if os.path.exists(template_file):
        size = os.path.getsize(template_file)
        print(f"✅ Template file found: {template_file} ({size} bytes)")
    else:
        print(f"❌ Template file missing: {template_file}")
        files_exist = False
    
    # Check source file
    if os.path.exists(source_file):
        size = os.path.getsize(source_file)
        print(f"✅ Source file found: {source_file} ({size} bytes)")
    else:
        print(f"❌ Source file missing: {source_file}")
        files_exist = False
    
    return files_exist

def test_document_generation():
    """Test the new simplified document generation function"""
    print("=" * 60)
    print("TESTING SIMPLIFIED DOCUMENT GENERATION")
    print("=" * 60)
    
    url = f"{BASE_URL}/test-document-generation"
    
    try:
        print(f"Making request to: {url}")
        print("This will test the new upload_files_prompt_to_openai function")
        print("Using files: IND_3.2.P.1_Template.docx and THPG001009 Product Code.pdf")
        
        start_time = time.time()
        response = requests.post(url, timeout=300)  # 5 minute timeout for document generation
        end_time = time.time()
        
        request_time = end_time - start_time
        print(f"Request took: {request_time:.2f} seconds")
        print(f"Response Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ SUCCESS!")
            print(f"Message: {result.get('message', 'No message')}")
            
            # Print detailed results
            print(f"\nDETAILED RESULTS:")
            print(f"  Processing time: {result.get('processing_time_seconds', 0):.2f} seconds")
            print(f"  Document size: {result.get('document_size_bytes', 0)} bytes")
            print(f"  Output filename: {result.get('output_filename', 'Unknown')}")
            
            details = result.get('details', {})
            print(f"  Template file: {details.get('template_file', 'Unknown')}")
            print(f"  Source document: {details.get('source_document', 'Unknown')}")
            print(f"  Prompt length: {details.get('prompt_length', 0)} characters")
            
            # Check if output file was created
            output_filename = result.get('output_filename')
            if output_filename and os.path.exists(output_filename):
                file_size = os.path.getsize(output_filename)
                print(f"  ✅ Generated file exists: {output_filename} ({file_size} bytes)")
            else:
                print(f"  ⚠️ Generated file not found: {output_filename}")
            
            return True
            
        else:
            print(f"❌ FAILED!")
            print(f"Response: {response.text}")
            
            # Try to parse error response
            try:
                error_result = response.json()
                print(f"Error message: {error_result.get('message', 'Unknown error')}")
                if 'error' in error_result:
                    print(f"Error details: {error_result['error']}")
            except:
                pass
            
            return False
            
    except requests.exceptions.Timeout:
        print("❌ REQUEST TIMEOUT")
        print("The request took too long (>5 minutes). This might indicate:")
        print("1. OpenAI API is slow")
        print("2. Large files are being processed")
        print("3. Network issues")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ CONNECTION ERROR")
        print("Could not connect to the Flask server. Make sure:")
        print("1. The Flask server is running: python flask_api.py")
        print("2. The server is accessible at the correct URL")
        print("3. No firewall is blocking the connection")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ REQUEST ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        return False

def main():
    """Run the complete test suite"""
    print("Starting Simplified Document Generation Testing...")
    print("This will test the new upload_files_prompt_to_openai function")
    print()
    
    # Step 1: Check OpenAI configuration
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
    print("OPENAI CONFIGURATION OK")
    print("=" * 60)
    
    # Step 2: Check test files
    print("\nSTEP 2: Checking Test Files...")
    files_ok = check_test_files()
    
    if not files_ok:
        print("\n" + "=" * 60)
        print("TEST FILES MISSING")
        print("=" * 60)
        print("Cannot proceed with tests. Please ensure these files exist:")
        print("1. IND_3.2.P.1_Template.docx")
        print("2. THPG001009 Product Code.pdf")
        print("\nThese files should be in the same directory as this test script.")
        return
    
    print("\n" + "=" * 60)
    print("TEST FILES OK")
    print("=" * 60)
    
    # Step 3: Test document generation
    print("\nSTEP 3: Testing Document Generation...")
    success = test_document_generation()
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL TEST RESULTS")
    print("=" * 60)
    
    if success:
        print("✅ ALL TESTS PASSED!")
        print("Your simplified document generation function is working correctly.")
        print("\nThe function successfully:")
        print("1. Uploaded the template and source documents to OpenAI")
        print("2. Generated a new document using the prompt and uploaded files")
        print("3. Converted the result to DOCX format")
        print("4. Saved the generated document locally")
    else:
        print("❌ TEST FAILED")
        print("The document generation test failed. Check the logs above for details.")
        print("\nCommon issues:")
        print("1. Flask server not running - start with: python flask_api.py")
        print("2. OpenAI API key issues - check configuration")
        print("3. File format issues - ensure files are valid DOCX/PDF")
        print("4. Network/API timeout - check internet connection and OpenAI status")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
