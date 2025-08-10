#!/usr/bin/env python3
"""
Simple script to check token status and test if rate limit has reset
"""

import os
import json
import requests
from datetime import datetime

def check_token_cache():
    """Check if token cache file exists and what's in it"""
    cache_file = 'egnyte_token_cache.json'
    
    print("🔍 Checking token cache status...")
    
    if os.path.exists(cache_file):
        print(f"✅ Token cache file exists: {cache_file}")
        try:
            with open(cache_file, 'r') as f:
                cache_data = json.load(f)
            print(f"📄 Cache data: {json.dumps(cache_data, indent=2)}")
            
            # Check if token is expired
            if 'expires_at' in cache_data:
                expires_at = datetime.fromisoformat(cache_data['expires_at'])
                now = datetime.now()
                if expires_at > now:
                    print(f"✅ Token is still valid (expires at {expires_at})")
                    return True
                else:
                    print(f"❌ Token has expired (expired at {expires_at})")
                    return False
            else:
                print("⚠️ No expiration info in cache")
                return True
                
        except Exception as e:
            print(f"❌ Error reading cache file: {e}")
            return False
    else:
        print(f"❌ Token cache file does not exist: {cache_file}")
        return False

def test_egnyte_connection():
    """Test if we can connect to Egnyte without rate limiting"""
    print("\n🌐 Testing Egnyte connection...")
    
    try:
        # Try to get a simple response from Egnyte
        response = requests.get('https://app4americanaitechdev.egnyte.com/api/v1/userinfo', 
                              timeout=10)
        
        if response.status_code == 200:
            print("✅ Egnyte connection successful")
            return True
        elif response.status_code == 401:
            print("⚠️ Egnyte connection requires authentication (expected)")
            return True
        elif response.status_code == 429:
            print("❌ Still hitting rate limit")
            if 'retry-after' in response.headers:
                print(f"   Retry-After: {response.headers['retry-after']}")
            return False
        else:
            print(f"⚠️ Unexpected status code: {response.status_code}")
            return True
            
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    print("=" * 60)
    print("TOKEN STATUS CHECK")
    print("=" * 60)
    
    # Check current time
    now = datetime.now()
    print(f"🕐 Current time: {now}")
    
    # Check token cache
    has_valid_cache = check_token_cache()
    
    # Test connection
    can_connect = test_egnyte_connection()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    if has_valid_cache:
        print("✅ You have a valid cached token - should work without rate limits")
    else:
        print("❌ No valid cached token found")
    
    if can_connect:
        print("✅ Egnyte connection is working")
    else:
        print("❌ Egnyte connection issues - may still be rate limited")
    
    if has_valid_cache and can_connect:
        print("\n🎉 You should be able to run your tests now!")
    else:
        print("\n⏳ You may need to wait longer for rate limit to reset")

if __name__ == "__main__":
    main()
