#!/usr/bin/env python3
"""
Test script focused on residential addresses to understand ATTOM API responses
"""

import asyncio
import aiohttp
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('../.env')

async def test_residential_address():
    """Test ATTOM API with typical residential addresses"""
    
    attom_api_key = os.getenv('ATTOM_API_KEY')
    if not attom_api_key:
        print("❌ No ATTOM API key found")
        return
    
    # Test with typical residential addresses
    test_addresses = [
        {
            "address": "123 Main Street, Houston, TX 77001",
            "address1": "123 Main Street",
            "address2": "Houston, TX 77001"
        },
        {
            "address": "456 Oak Avenue, Austin, TX 78701", 
            "address1": "456 Oak Avenue",
            "address2": "Austin, TX 78701"
        },
        {
            "address": "7914 Woodsman Trail, Houston, TX 77040",
            "address1": "7914 Woodsman Trail", 
            "address2": "Houston, TX 77040"
        }
    ]
    
    headers = {
        'apikey': attom_api_key,
        'accept': 'application/json'
    }
    
    # Test different ATTOM endpoints
    endpoints = [
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/detail',
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile',
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/expandedprofile',
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/avm',
        'https://api.gateway.attomdata.com/propertyapi/v1.0.0/saleshistory/detail'
    ]
    
    async with aiohttp.ClientSession() as session:
        for addr_info in test_addresses:
            print(f"\n{'='*60}")
            print(f"Testing: {addr_info['address']}")
            print(f"{'='*60}")
            
            for endpoint in endpoints:
                endpoint_name = endpoint.split('/')[-1]
                print(f"\n--- Testing {endpoint_name} endpoint ---")
                
                # Try different parameter formats
                param_sets = [
                    {'address1': addr_info['address1'], 'address2': addr_info['address2']},
                    {'address': addr_info['address']}
                ]
                
                for i, params in enumerate(param_sets):
                    try:
                        print(f"  Attempt {i+1}: {params}")
                        async with session.get(endpoint, params=params, headers=headers) as response:
                            response_text = await response.text()
                            print(f"  Status: {response.status}")
                            
                            if response.status == 200:
                                try:
                                    data = await response.json()
                                    print(f"  ✅ Success! Response structure:")
                                    print(f"    Top-level keys: {list(data.keys())}")
                                    
                                    # Check for property data
                                    if 'property' in data and data['property']:
                                        prop = data['property'][0] if isinstance(data['property'], list) else data['property']
                                        print(f"    Property keys: {list(prop.keys())}")
                                        
                                        # Look for assessment data (where mortgage info usually is)
                                        if 'assessment' in prop:
                                            assess = prop['assessment']
                                            print(f"    Assessment keys: {list(assess.keys())}")
                                            
                                            # Check for mortgage data
                                            if 'mortgage' in assess:
                                                mortgage = assess['mortgage']
                                                print(f"    Mortgage data: {mortgage}")
                                            
                                            # Check for market value
                                            if 'market' in assess:
                                                market = assess['market']
                                                print(f"    Market data: {market}")
                                        
                                        # Check for sale data
                                        if 'sale' in prop:
                                            sale = prop['sale']
                                            print(f"    Sale data keys: {list(sale.keys())}")
                                        
                                        # Check for AVM data
                                        if 'avm' in prop:
                                            avm = prop['avm']
                                            print(f"    AVM data: {avm}")
                                    
                                    # Save response for detailed analysis
                                    filename = f"attom_{endpoint_name}_{addr_info['address1'].replace(' ', '_')}_attempt_{i+1}.json"
                                    with open(filename, 'w') as f:
                                        json.dump(data, f, indent=2, default=str)
                                    print(f"    Saved to: {filename}")
                                    
                                    break  # Success, move to next endpoint
                                    
                                except Exception as e:
                                    print(f"  ❌ JSON parse error: {str(e)}")
                                    print(f"  Response: {response_text[:300]}")
                            
                            elif response.status == 401:
                                print(f"  ❌ Authentication failed")
                                break
                            
                            elif response.status == 400:
                                print(f"  ❌ Bad request: {response_text[:200]}")
                            
                            elif response.status == 429:
                                print(f"  ⚠️  Rate limited")
                                await asyncio.sleep(1)
                            
                            else:
                                print(f"  ❌ HTTP {response.status}: {response_text[:200]}")
                    
                    except Exception as e:
                        print(f"  ❌ Request error: {str(e)}")
                
                # Small delay between endpoints
                await asyncio.sleep(0.5)

if __name__ == "__main__":
    asyncio.run(test_residential_address()) 