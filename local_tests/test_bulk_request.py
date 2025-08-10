#!/usr/bin/env python3
"""
Test script for the reg_docs_bulk_request function
Tests bulk document generation with Egnyte files using the provided dataframe
"""

import requests
import json
import time
import os
import sys
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"  # Change if your Flask app runs on different port
# BASE_URL = "https://your-app.onrender.com"  # For production testing

def create_test_dataframe():
    """Create the test dataframe based on the image data"""
    test_data = [
        {
            "id": 22,
            "filing_type": "IND",
            "project": "THPG001",
            "module": "3.2.P",
            "draft_section": "P.1",
            "cdmo": "CDMO X",
            "campaign": "#4",
            "ctm": "25 mg Tabl",
            "product_code": "THPG0010",
            "mfg_lot": "2506103",
            "mfg_type": "GMP",
            "source_document": "",
            "template": "",
            "prompt": "",
            "prompt_material": "",
            "generate": "Create pro"
        },
        {
            "id": 24,
            "filing_type": "IND",
            "project": "THPG001",
            "module": "3.2.P",
            "draft_section": "P.1",
            "cdmo": "CDMO X",
            "campaign": "#4",
            "ctm": "PBO 25 mg",
            "product_code": "THPG0010",
            "mfg_lot": "2506100",
            "mfg_type": "GMP",
            "source_document": "",
            "template": "",
            "prompt": "THPG0010",
            "prompt_material": "",
            "generate": "Create pro"
        }
    ]
    
    # Add the required fields for the reg_docs_bulk_request function
    # These fields are needed for the matching logic
    for item in test_data:
        # Add reg_doc_version fields (these would normally come from your database)
        item["reg_doc_version_active"] = "IND_3.2.P.1_Template v1.0 v2.0"
        item["reg_doc_version_placebo"] = "IND_3.2.P.1_Template v1.0 v2.0"
        item["section"] = item["draft_section"]
        
        # Add any other required fields
        item["molecule_code"] = "THPG001"
        item["campaign_number"] = "4"
        item["dosage_form"] = "Tablet"
    
    return test_data

def check_api_availability():
    """Check if the Flask API is running"""
    try:
        # Use an existing endpoint for health check
        response = requests.get(f"{BASE_URL}/egnyte-list-templates", timeout=10)
        if response.status_code == 200:
            print("✅ API is available")
            return True
        elif response.status_code == 401 or response.status_code == 500:
            # API is running but might have auth issues - that's OK for testing
            print("✅ API is available (auth issues expected)")
            return True
        else:
            print(f"❌ API returned status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to API: {e}")
        print(f"   Make sure the Flask app is running on {BASE_URL}")
        return False

def test_bulk_request():
    """Test the reg_docs_bulk_request endpoint"""
    print("=" * 80)
    print("TESTING REG_DOCS_BULK_REQUEST")
    print("=" * 80)
    
    # Create test data
    test_data = create_test_dataframe()
    print(f"Created test data with {len(test_data)} rows")
    
    # Print the test data for verification
    print("\nTest Data:")
    for i, item in enumerate(test_data):
        print(f"Row {i+1}:")
        print(f"  Product Code: {item['product_code']}")
        print(f"  CTM: {item['ctm']}")
        print(f"  Manufacturing Lot: {item['mfg_lot']}")
        print(f"  Active Reg Doc Version: {item['reg_doc_version_active']}")
        print(f"  Placebo Reg Doc Version: {item['reg_doc_version_placebo']}")
        print(f"  Section: {item['section']}")
        print()
    
    # Make the API request
    print("Sending bulk request to API...")
    start_time = time.time()
    
    try:
        response = requests.post(
            f"{BASE_URL}/reg-docs-bulk-request",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=300  # 5 minutes timeout for bulk processing
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        print(f"Response received in {processing_time:.2f} seconds")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Bulk request successful!")
            
            # Parse and display results
            result = response.json()
            
            if "total_match_report" in result:
                report = result["total_match_report"]
                
                # Display campaign summary
                if "campaign_summary" in report:
                    summary = report["campaign_summary"]
                    print(f"\n📊 CAMPAIGN SUMMARY:")
                    print(f"   Total Requests: {summary.get('total_requests', 0)}")
                    print(f"   Successful Matches: {summary.get('successful_matches', 0)}")
                    print(f"   Unique Product Codes: {summary.get('unique_product_codes', [])}")
                    print(f"   Processing Timestamp: {summary.get('processing_timestamp', 'N/A')}")
                
                # Display status breakdown
                if "status_breakdown" in report:
                    print(f"\n📈 STATUS BREAKDOWN:")
                    for status_item in report["status_breakdown"]:
                        print(f"   {status_item['status']}: {status_item['count']} rows ({status_item['percentage']}%)")
                
                # Display generated documents
                if "generated_documents" in report:
                    docs = report["generated_documents"]
                    if docs:
                        print(f"\n📄 GENERATED DOCUMENTS ({len(docs)}):")
                        for i, doc in enumerate(docs, 1):
                            print(f"   Document {i}:")
                            print(f"     Product Code: {doc.get('product_code', 'N/A')}")
                            print(f"     Section: {doc.get('section', 'N/A')}")
                            print(f"     DOCX Filename: {doc.get('docx_filename', 'N/A')}")
                            print(f"     PDF Filename: {doc.get('pdf_filename', 'N/A')}")
                            if doc.get('docx_url'):
                                print(f"     DOCX URL: {doc['docx_url']}")
                            if doc.get('pdf_url'):
                                print(f"     PDF URL: {doc['pdf_url']}")
                            print()
                    else:
                        print(f"\n📄 No documents were generated")
                
                # Display detailed results
                if "detailed_results" in report:
                    print(f"\n🔍 DETAILED RESULTS:")
                    for i, detail in enumerate(report["detailed_results"], 1):
                        print(f"   Row {i}:")
                        print(f"     Product Code: {detail.get('product_code', 'N/A')}")
                        print(f"     Generation Success: {detail.get('generation_result', {}).get('success', False)}")
                        if detail.get('generation_result', {}).get('success'):
                            print(f"     DOCX Filename: {detail['generation_result'].get('docx_filename', 'N/A')}")
                            print(f"     PDF Filename: {detail['generation_result'].get('pdf_filename', 'N/A')}")
                        else:
                            error = detail.get('generation_result', {}).get('error', 'Unknown error')
                            print(f"     Error: {error}")
                        print()
            
            else:
                print("❌ No total_match_report in response")
                print(f"Response: {json.dumps(result, indent=2)}")
        
        else:
            print("❌ Bulk request failed!")
            print(f"Status Code: {response.status_code}")
            try:
                error_response = response.json()
                print(f"Error Response: {json.dumps(error_response, indent=2)}")
            except:
                print(f"Error Text: {response.text}")
    
    except requests.exceptions.Timeout:
        print("❌ Request timed out (took longer than 5 minutes)")
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse JSON response: {e}")
        print(f"Response text: {response.text}")

def test_egnyte_connection():
    """Test Egnyte connection and file access"""
    print("=" * 80)
    print("TESTING EGNYTE CONNECTION")
    print("=" * 80)
    
    try:
        # Test basic Egnyte endpoints
        endpoints = [
            "/egnyte-list-templates",
            "/egnyte-list-source-documents"
        ]
        
        for endpoint in endpoints:
            print(f"\nTesting {endpoint}...")
            try:
                response = requests.get(f"{BASE_URL}{endpoint}", timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if "files" in result:
                        files = result["files"]
                        print(f"✅ Found {len(files)} files")
                        for i, file in enumerate(files[:5]):  # Show first 5 files
                            print(f"   {i+1}. {file.get('name', 'N/A')} (ID: {file.get('entry_id', 'N/A')})")
                        if len(files) > 5:
                            print(f"   ... and {len(files) - 5} more files")
                    else:
                        print(f"❌ No 'files' key in response")
                else:
                    print(f"❌ Status code: {response.status_code}")
                    try:
                        error = response.json()
                        print(f"   Error: {error}")
                    except:
                        print(f"   Error text: {response.text}")
            except Exception as e:
                print(f"❌ Error testing {endpoint}: {e}")
    
    except Exception as e:
        print(f"❌ Egnyte connection test failed: {e}")

def main():
    """Run the complete test suite"""
    print("Starting Bulk Request Testing...")
    print("This will test the reg_docs_bulk_request function with Egnyte files")
    print()
    
    # Step 1: Check API availability
    print("STEP 1: Checking API Availability...")
    if not check_api_availability():
        print("\nCannot proceed with tests. Please start the Flask app first.")
        return
    
    # Step 2: Test Egnyte connection
    print("\nSTEP 2: Testing Egnyte Connection...")
    test_egnyte_connection()
    
    # Step 3: Test bulk request
    print("\nSTEP 3: Testing Bulk Request...")
    test_bulk_request()
    
    # Final summary
    print("\n" + "=" * 80)
    print("TESTING COMPLETED")
    print("=" * 80)
    print("Check the output above for results and any errors.")
    print("If documents were generated successfully, you should see URLs to the generated files.")

if __name__ == "__main__":
    main()
