#!/usr/bin/env python3
"""
Google Drive Setup Script

This script helps you set up Google Drive authentication.

Steps:
1. Go to https://console.cloud.google.com/
2. Create a new project (or select existing)
3. Enable Google Drive API
4. Create OAuth 2.0 credentials (Desktop app)
5. Download the credentials JSON file
6. Save it as 'credentials.json' in this directory
7. Run this script to authenticate

The script will open a browser for OAuth consent and save a token for future use.
"""

import os
import sys

def main():
    print("="*70)
    print("GOOGLE DRIVE AUTHENTICATION SETUP")
    print("="*70)
    
    # Check if credentials file exists
    if not os.path.exists('credentials.json'):
        print("\n❌ credentials.json not found!")
        print("\nTo set up Google Drive integration:")
        print("1. Visit: https://console.cloud.google.com/")
        print("2. Create a project and enable Google Drive API")
        print("3. Create OAuth 2.0 credentials (Desktop app)")
        print("4. Download and save as 'credentials.json'")
        print("\nFor detailed instructions, see:")
        print("https://developers.google.com/drive/api/quickstart/python")
        return False
    
    print("\n✓ Found credentials.json")
    print("\nStarting authentication flow...")
    
    # Import and authenticate
    sys.path.insert(0, 'src')
    from drive_integration.drive_uploader import DriveUploader
    
    uploader = DriveUploader()
    if uploader.authenticate():
        print("\n" + "="*70)
        print("✓ AUTHENTICATION SUCCESSFUL!")
        print("="*70)
        print("\nYou can now use the Drive uploader in your scripts.")
        print("The token has been saved for future use.")
        return True
    else:
        print("\n❌ Authentication failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
