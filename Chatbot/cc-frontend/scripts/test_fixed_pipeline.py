#!/usr/bin/env python3
"""
Test the fixed address enrichment pipeline with the working address
"""

import asyncio
import json
from dotenv import load_dotenv
from address_enrichment_pipeline import AddressEnrichmentPipeline

# Load environment variables
load_dotenv('../.env')

async def test_working_address():
    """Test the pipeline with the address we know works"""
    
    test_address = "7914 Woodsman Trail, Houston, TX 77040"
    
    print(f"🧪 Testing fixed pipeline with: {test_address}")
    print("=" * 60)
    
    async with AddressEnrichmentPipeline() as pipeline:
        result = await pipeline.enrich_address(test_address)
        
        print("✅ Enrichment Result:")
        print(json.dumps(result, indent=2, default=str))
        
        # Analyze the results
        print("\n📊 Analysis:")
        print(f"  Address validation: {'✅' if result.get('canonical_address') else '❌'}")
        print(f"  ATTOM ID found: {'✅' if result.get('attomid') else '❌'}")
        print(f"  Owner name: {'✅' if result.get('owner_name') else '❌'} - {result.get('owner_name', 'N/A')}")
        print(f"  Market value: {'✅' if result.get('market_value') else '❌'} - ${result.get('market_value', 0):,.0f}")
        print(f"  Loan balance: {'✅' if result.get('est_balance') else '❌'} - ${result.get('est_balance', 0):,.0f}")
        print(f"  Available equity: {'✅' if result.get('available_equity') else '❌'} - ${result.get('available_equity', 0):,.0f}")
        print(f"  LTV ratio: {'✅' if result.get('ltv') else '❌'} - {result.get('ltv', 0):.1f}%")
        print(f"  Phone: {'✅' if result.get('primary_phone') else '❌'} - {result.get('primary_phone', 'N/A')}")
        print(f"  Email: {'✅' if result.get('primary_email') else '❌'} - {result.get('primary_email', 'N/A')}")
        
        # Calculate completion score
        fields = ['canonical_address', 'attomid', 'owner_name', 'market_value', 'est_balance', 'available_equity', 'ltv', 'primary_phone', 'primary_email']
        found = sum(1 for field in fields if result.get(field))
        score = found / len(fields) * 100
        
        print(f"\n🎯 Completion Score: {found}/{len(fields)} ({score:.1f}%)")
        
        return result

if __name__ == "__main__":
    asyncio.run(test_working_address()) 