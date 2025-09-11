#!/usr/bin/env python3
"""Simple test script for crypto scheduler config"""

import os
import sys
from pathlib import Path

def test_config():
    print("Testing Crypto Scheduler Config")
    print("=" * 40)
    
    # Check .env file
    env_exists = Path('.env').exists()
    print(f"1. .env file exists: {env_exists}")
    
    if not env_exists:
        print("   ERROR: .env file not found!")
        return False
    
    # Test config import
    try:
        sys.path.append('.')
        from app.services.config import get_settings
        print("2. Config import: SUCCESS")
    except Exception as e:
        print(f"2. Config import: FAILED - {e}")
        return False
    
    # Test settings loading
    try:
        settings = get_settings()
        print("3. Settings loading: SUCCESS")
    except Exception as e:
        print(f"3. Settings loading: FAILED - {e}")
        return False
    
    # Check key values
    print(f"4. Wallet API URL: {settings.wallet_api_url}")
    print(f"5. Debug mode: {settings.debug}")
    print(f"6. GCP Project: {settings.google_cloud_project}")
    print(f"7. App name: {settings.app_name}")
    
    # Verify .env reading
    expected_url = "https://wallet-api-bigquery-qz6f5mkbmq-as.a.run.app"
    if settings.wallet_api_url == expected_url:
        print("8. .env reading: SUCCESS")
        return True
    else:
        print("8. .env reading: FAILED")
        print(f"   Expected: {expected_url}")
        print(f"   Got: {settings.wallet_api_url}")
        return False

if __name__ == "__main__":
    success = test_config()
    if success:
        print("\nALL TESTS PASSED! Your config is working.")
        print("Now run: python main.py")
    else:
        print("\nTESTS FAILED! Check the errors above.")
    sys.exit(0 if success else 1)