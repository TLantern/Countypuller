#!/usr/bin/env python3
"""
Test script for ATTOM skip trace functionality

This script tests the address enrichment pipeline with focus on:
1. Address validation (Google Maps/SmartyStreets/USPS)
2. ATTOM property data retrieval
3. Owner information extraction
4. Equity calculations
5. Skip trace fallback mechanisms

Usage:
    python test_attom_skip_trace.py
"""

import asyncio
import os
import json
import logging
from datetime import datetime
from address_enrichment_pipeline import AddressEnrichmentPipeline

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv('../.env')
    print("✅ Loaded environment variables from .env file")
except ImportError:
    print("⚠️  dotenv not available, using system environment variables")
except Exception as e:
    print(f"⚠️  Error loading .env file: {e}")

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_attom_skip_trace.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Test addresses - mix of different property types and locations
TEST_ADDRESSES = [
    "1600 Pennsylvania Avenue NW, Washington, DC 20500",  # White House (famous address)
    "350 Fifth Avenue, New York, NY 10118",  # Empire State Building
    "1 Apple Park Way, Cupertino, CA 95014",  # Apple Park
    "123 Main Street, Houston, TX 77001",  # Generic Houston address
    "456 Oak Avenue, Austin, TX 78701",  # Generic Austin address
    "789 Pine Street, Dallas, TX 75201",  # Generic Dallas address
    "2000 Post Oak Blvd, Houston, TX 77056",  # Houston business district
    "1234 Elm Street, Fort Worth, TX 76102",  # Generic Fort Worth address
]

async def test_environment_setup():
    """Test if required environment variables are set"""
    logger.info("=== Testing Environment Setup ===")
    
    required_vars = ['ATTOM_API_KEY']
    optional_vars = ['GOOGLE_MAPS_API_KEY', 'SMARTYSTREETS_AUTH_ID', 'SMARTYSTREETS_AUTH_TOKEN', 'USPS_USER_ID']
    
    missing_required = []
    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)
            logger.error(f"❌ Missing required environment variable: {var}")
        else:
            logger.info(f"✅ Found required environment variable: {var}")
    
    available_optional = []
    for var in optional_vars:
        if os.getenv(var):
            available_optional.append(var)
            logger.info(f"✅ Found optional environment variable: {var}")
        else:
            logger.warning(f"⚠️  Missing optional environment variable: {var}")
    
    if missing_required:
        logger.error(f"Cannot proceed without required variables: {missing_required}")
        return False
    
    logger.info(f"Environment check passed. Available validation methods: {available_optional}")
    return True

async def test_single_address_enrichment(pipeline, address):
    """Test enrichment of a single address with detailed logging"""
    logger.info(f"\n=== Testing Address: {address} ===")
    
    try:
        # Test the complete enrichment pipeline
        result = await pipeline.enrich_address(address)
        
        logger.info(f"✅ Enrichment completed for: {address}")
        logger.info(f"Raw result: {json.dumps(result, indent=2, default=str)}")
        
        # Analyze the results
        analysis = analyze_enrichment_result(result)
        logger.info(f"Analysis: {json.dumps(analysis, indent=2)}")
        
        return result, analysis
        
    except Exception as e:
        logger.error(f"❌ Enrichment failed for {address}: {str(e)}")
        return None, {"error": str(e)}

def analyze_enrichment_result(result):
    """Analyze the enrichment result and provide insights"""
    analysis = {
        "address_validation": "✅ Success" if result.get('canonical_address') else "❌ Failed",
        "attom_property_data": "✅ Found" if result.get('attomid') else "❌ Not found",
        "owner_information": {},
        "equity_data": {},
        "skip_trace_data": {}
    }
    
    # Check owner information
    owner_fields = ['owner_name', 'primary_phone', 'primary_email']
    for field in owner_fields:
        analysis["owner_information"][field] = "✅ Found" if result.get(field) else "❌ Missing"
    
    # Check equity data
    equity_fields = ['est_balance', 'available_equity', 'ltv', 'market_value', 'loans_count']
    for field in equity_fields:
        value = result.get(field)
        if value is not None:
            analysis["equity_data"][field] = f"✅ {value}"
        else:
            analysis["equity_data"][field] = "❌ Missing"
    
    # Overall score
    total_fields = len(owner_fields) + len(equity_fields) + 2  # +2 for address and attom data
    found_fields = sum([
        1 if result.get('canonical_address') else 0,
        1 if result.get('attomid') else 0,
        sum(1 for field in owner_fields if result.get(field)),
        sum(1 for field in equity_fields if result.get(field) is not None)
    ])
    
    analysis["completion_score"] = f"{found_fields}/{total_fields} ({found_fields/total_fields*100:.1f}%)"
    
    return analysis

async def test_attom_api_directly():
    """Test ATTOM API directly to understand response structure"""
    logger.info("\n=== Testing ATTOM API Directly ===")
    
    attom_api_key = os.getenv('ATTOM_API_KEY')
    if not attom_api_key:
        logger.error("❌ No ATTOM API key found")
        return
    
    import aiohttp
    
    # Test different ATTOM endpoints
    endpoints = [
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail',
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile',
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/expandedprofile'
    ]
    
    test_address = "1600 Pennsylvania Avenue NW, Washington, DC 20500"
    
    headers = {
        'apikey': attom_api_key,
        'accept': 'application/json'
    }
    
    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            logger.info(f"Testing endpoint: {endpoint}")
            
            # Try different parameter formats
            param_sets = [
                {'address': test_address},
                {'address1': '1600 Pennsylvania Avenue NW', 'address2': 'Washington, DC 20500'},
                {'address': '1600 Pennsylvania Avenue NW', 'locality': 'Washington', 'postalcode': '20500'}
            ]
            
            for i, params in enumerate(param_sets):
                try:
                    logger.info(f"  Attempt {i+1}: {params}")
                    async with session.get(endpoint, params=params, headers=headers) as response:
                        response_text = await response.text()
                        logger.info(f"  Status: {response.status}")
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                logger.info(f"  ✅ Success! Response keys: {list(data.keys())}")
                                
                                # Log property data structure if found
                                properties = data.get('property', [])
                                if properties:
                                    prop = properties[0]
                                    logger.info(f"  Property keys: {list(prop.keys())}")
                                    
                                    # Look for owner information
                                    owner_keys = [k for k in prop.keys() if 'owner' in k.lower()]
                                    if owner_keys:
                                        logger.info(f"  Owner-related keys: {owner_keys}")
                                        for key in owner_keys:
                                            logger.info(f"    {key}: {prop[key]}")
                                    
                                    # Look for assessment data
                                    if 'assessment' in prop:
                                        assess = prop['assessment']
                                        logger.info(f"  Assessment keys: {list(assess.keys())}")
                                        
                                        # Check for mortgage data
                                        if 'mortgage' in assess:
                                            mortgage = assess['mortgage']
                                            logger.info(f"  Mortgage keys: {list(mortgage.keys())}")
                                
                                # Save full response for analysis
                                with open(f'attom_response_{endpoint.split("/")[-1]}_attempt_{i+1}.json', 'w') as f:
                                    json.dump(data, f, indent=2, default=str)
                                
                                break  # Success, move to next endpoint
                                
                            except Exception as e:
                                logger.error(f"  ❌ JSON parse error: {str(e)}")
                                logger.error(f"  Response: {response_text[:500]}")
                        
                        elif response.status == 401:
                            logger.error(f"  ❌ Authentication failed - check API key")
                            break
                        
                        elif response.status == 429:
                            logger.warning(f"  ⚠️  Rate limited")
                            await asyncio.sleep(1)
                        
                        else:
                            logger.warning(f"  ❌ HTTP {response.status}: {response_text[:200]}")
                
                except Exception as e:
                    logger.error(f"  ❌ Request error: {str(e)}")

async def test_address_validation():
    """Test address validation methods"""
    logger.info("\n=== Testing Address Validation ===")
    
    pipeline = AddressEnrichmentPipeline()
    
    test_address = "1600 Pennsylvania Avenue NW, Washington, DC 20500"
    
    # Test Google Maps validation
    if os.getenv('GOOGLE_MAPS_API_KEY'):
        try:
            logger.info("Testing Google Maps validation...")
            raw, canonical = await pipeline.validate_address_google(test_address)
            logger.info(f"✅ Google Maps: {raw} -> {canonical}")
        except Exception as e:
            logger.error(f"❌ Google Maps validation failed: {str(e)}")
    
    # Test SmartyStreets validation
    if os.getenv('SMARTYSTREETS_AUTH_ID') and os.getenv('SMARTYSTREETS_AUTH_TOKEN'):
        try:
            logger.info("Testing SmartyStreets validation...")
            raw, canonical = await pipeline.validate_address_smartystreets(test_address)
            logger.info(f"✅ SmartyStreets: {raw} -> {canonical}")
        except Exception as e:
            logger.error(f"❌ SmartyStreets validation failed: {str(e)}")
    
    # Test USPS validation
    if os.getenv('USPS_USER_ID'):
        try:
            logger.info("Testing USPS validation...")
            raw, canonical = await pipeline.validate_address_usps_fallback(test_address)
            logger.info(f"✅ USPS: {raw} -> {canonical}")
        except Exception as e:
            logger.error(f"❌ USPS validation failed: {str(e)}")

async def main():
    """Main test function"""
    logger.info("🚀 Starting ATTOM Skip Trace Test Suite")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")
    
    # Test 1: Environment setup
    if not await test_environment_setup():
        logger.error("❌ Environment setup failed. Exiting.")
        return
    
    # Test 2: Address validation
    await test_address_validation()
    
    # Test 3: ATTOM API direct testing
    await test_attom_api_directly()
    
    # Test 4: Full pipeline testing
    logger.info("\n=== Testing Full Enrichment Pipeline ===")
    
    async with AddressEnrichmentPipeline() as pipeline:
        results = []
        
        for address in TEST_ADDRESSES[:3]:  # Test first 3 addresses to avoid rate limits
            result, analysis = await test_single_address_enrichment(pipeline, address)
            results.append({
                'address': address,
                'result': result,
                'analysis': analysis
            })
            
            # Rate limiting pause
            await asyncio.sleep(1)
        
        # Summary report
        logger.info("\n=== SUMMARY REPORT ===")
        
        successful_enrichments = sum(1 for r in results if r['result'] is not None)
        logger.info(f"Successful enrichments: {successful_enrichments}/{len(results)}")
        
        for r in results:
            if r['result']:
                logger.info(f"✅ {r['address']}: {r['analysis'].get('completion_score', 'N/A')}")
            else:
                logger.info(f"❌ {r['address']}: {r['analysis'].get('error', 'Unknown error')}")
        
        # Save detailed results
        with open('test_results.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.info("📊 Detailed results saved to test_results.json")
        logger.info("📊 Logs saved to test_attom_skip_trace.log")

if __name__ == "__main__":
    asyncio.run(main()) 