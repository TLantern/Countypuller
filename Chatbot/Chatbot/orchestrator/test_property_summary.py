#!/usr/bin/env python3
"""
Test script for Property Summary Generator with custom prompt
"""

import asyncio
import json
import logging
from pathlib import Path
import sys
from pathlib import Path
pullingbots_tools_path = Path(__file__).parent.parent / "PullingBots" / "tools"
if str(pullingbots_tools_path) not in sys.path:
    sys.path.insert(0, str(pullingbots_tools_path))
from property_summary import generate_property_summary

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_with_custom_prompt():
    """Test the agent with the user's custom prompt"""
    logger.info("🧪 Testing property summary with custom underwriter prompt...")
    
    # User's custom prompt
    custom_prompt = """Write ≤1 sentence covering:
- price-per-sf vs zip median
- equity gap to assessed value
- build-year rehab risk
- delinquency years or liens
Return plain text, no line breaks."""
    
    # Sample property data
    test_property = {
        "address": "18414 WATER SCENE, CYPRESS, 77429",
        "parcel_id": "1248470010035",
        "owner_name": "ITANI TARIQ ZIAD",
        "impr_sqft": "7009",
        "market_value": "$317,745",
        "appraised_value": "$317,745",
        "legal_params": {
            "subdivision": "VILLAGES OF CYPRESS LAKES",
            "section": "6",
            "block": "1",
            "lot": "35"
        }
    }
    
    try:
        logger.info(f"🔄 Generating underwriter summary for parcel {test_property['parcel_id']}...")
        result = await generate_property_summary(test_property, custom_prompt)
        
        if result.get('error'):
            logger.error(f"❌ Summary generation failed: {result['error']}")
            return False
        
        logger.info("✅ Underwriter summary generated!")
        logger.info(f"📋 Parcel ID: {result['parcel_id']}")
        logger.info(f"📝 Underwriter Analysis: {result['summary']}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        return False

async def main():
    """Run the custom prompt test"""
    logger.info("🚀 Testing Property Summary with Custom Underwriter Prompt")
    logger.info("=" * 60)
    
    success = await test_with_custom_prompt()
    
    if success:
        logger.info("🎉 Custom prompt test passed!")
    else:
        logger.warning("⚠️ Test failed - check OpenAI API key configuration")

if __name__ == "__main__":
    asyncio.run(main()) 