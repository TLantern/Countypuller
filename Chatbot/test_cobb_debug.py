#!/usr/bin/env python3
"""
Test script for the cleaned up CobbGA.py with integrated HTML debugging
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to the Python path so we can import CobbGA
sys.path.insert(0, str(Path(__file__).parent))

# Import the cleaned up CobbGA module
import CobbGA

async def test_cobb_debug():
    """Test the CobbGA scraper with HTML debugging enabled"""
    
    print("🚀 Starting Cobb County GA scraper test with HTML debugging")
    print("🔧 This will run in test mode (visible browser) for debugging")
    
    try:
        # Run in test mode with a test user ID
        records = await CobbGA.run(
            max_new_records=5,  # Limit to 5 records for testing
            test_mode=True,     # Show browser for debugging
            user_id="test_debug_user"
        )
        
        print(f"✅ Test completed successfully!")
        print(f"📊 Found {len(records)} records")
        
        if records:
            print("\n📋 Sample records:")
            for i, record in enumerate(records[:3], 1):
                print(f"   {i}. Case: {record.get('case_number', 'N/A')}")
                print(f"      Type: {record.get('document_type', 'N/A')}")
                print(f"      Date: {record.get('filing_date', 'N/A')}")
                print(f"      Debtor: {record.get('debtor_name', 'N/A')[:50]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to run the test"""
    print("CobbGA HTML Debug Test")
    print("=" * 50)
    
    # Set the USER_ID for the module
    CobbGA.USER_ID = "test_debug_user"
    
    # Run the async test
    try:
        result = asyncio.run(test_cobb_debug())
        
        if result:
            print("\n🎉 All tests passed!")
            return 0
        else:
            print("\n💥 Tests failed!")
            return 1
            
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        return 0
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 