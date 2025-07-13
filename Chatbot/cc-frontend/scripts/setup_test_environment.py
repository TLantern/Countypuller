#!/usr/bin/env python3
"""
Setup script for ATTOM skip trace test environment

This script helps configure the required environment variables for testing.
"""

import os
import sys

def setup_environment():
    """Interactive setup for environment variables"""
    print("🔧 ATTOM Skip Trace Test Environment Setup")
    print("=" * 50)
    
    # Check current environment
    print("\n📋 Current Environment Status:")
    
    env_vars = {
        'ATTOM_API_KEY': 'Required for property data',
        'GOOGLE_MAPS_API_KEY': 'Address validation (recommended)',
        'SMARTYSTREETS_AUTH_ID': 'Address validation (alternative)',
        'SMARTYSTREETS_AUTH_TOKEN': 'Address validation (alternative)',
        'USPS_USER_ID': 'Address validation (fallback)'
    }
    
    current_values = {}
    for var, description in env_vars.items():
        value = os.getenv(var)
        current_values[var] = value
        status = "✅ SET" if value else "❌ MISSING"
        print(f"  {var}: {status} - {description}")
    
    print("\n" + "=" * 50)
    
    # Check if we have minimum requirements
    if not current_values['ATTOM_API_KEY']:
        print("❌ ATTOM_API_KEY is required but not set!")
        print("\n📝 To get an ATTOM API key:")
        print("   1. Go to https://api.attomdata.com/")
        print("   2. Sign up for a developer account")
        print("   3. Create a new API key")
        print("   4. Set the environment variable:")
        print("      export ATTOM_API_KEY='your_api_key_here'")
        print("   5. Or add it to your .env file")
        return False
    
    # Check address validation
    has_address_validation = any([
        current_values['GOOGLE_MAPS_API_KEY'],
        current_values['SMARTYSTREETS_AUTH_ID'] and current_values['SMARTYSTREETS_AUTH_TOKEN'],
        current_values['USPS_USER_ID']
    ])
    
    if not has_address_validation:
        print("⚠️  No address validation API configured!")
        print("\n📝 Recommended: Set up Google Maps API:")
        print("   1. Go to https://console.cloud.google.com/")
        print("   2. Create a new project or select existing")
        print("   3. Enable the Geocoding API")
        print("   4. Create an API key")
        print("   5. Set the environment variable:")
        print("      export GOOGLE_MAPS_API_KEY='your_api_key_here'")
        print("\n   Note: For server-side usage, don't restrict the API key to HTTP referrers")
        return False
    
    print("✅ Environment setup looks good!")
    return True

def create_env_file():
    """Create a .env file template"""
    env_template = """# ATTOM Skip Trace Environment Variables
# Copy this file to .env and fill in your API keys

# Required: ATTOM API for property data
ATTOM_API_KEY=your_attom_api_key_here

# Address Validation (choose one or more)
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
# SMARTYSTREETS_AUTH_ID=your_smartystreets_auth_id_here
# SMARTYSTREETS_AUTH_TOKEN=your_smartystreets_auth_token_here
# USPS_USER_ID=your_usps_user_id_here

# Optional: Skip trace services (not currently implemented)
# SEARCHBUG_API_KEY=your_searchbug_api_key_here
# WHITEPAGES_API_KEY=your_whitepages_api_key_here
# BEENVERIFIED_API_KEY=your_beenverified_api_key_here
"""
    
    with open('.env.template', 'w') as f:
        f.write(env_template)
    
    print("📄 Created .env.template file")
    print("   Copy this to .env and fill in your API keys")

def main():
    """Main setup function"""
    if setup_environment():
        print("\n🚀 Ready to run tests!")
        print("   Run: python test_attom_skip_trace.py")
    else:
        print("\n❌ Setup incomplete. Please configure the missing environment variables.")
        
        create_env_file()
        
        print("\n💡 Quick setup commands:")
        print("   # For bash/zsh:")
        print("   export ATTOM_API_KEY='your_key_here'")
        print("   export GOOGLE_MAPS_API_KEY='your_key_here'")
        print()
        print("   # For PowerShell:")
        print("   $env:ATTOM_API_KEY = 'your_key_here'")
        print("   $env:GOOGLE_MAPS_API_KEY = 'your_key_here'")
        print()
        print("   # Or create a .env file (recommended for development)")

if __name__ == "__main__":
    main() 