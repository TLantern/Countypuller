#!/usr/bin/env python3
"""
Test script for LisPendens Agent System

This script tests the complete flow of the agent system:
1. Scraping Harris County records
2. HCAD address lookups
3. Caching functionality
4. Result formatting
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_cache_system():
    """Test the cache system"""
    logger.info("🧪 Testing cache system...")
    
    try:
        from cache import CacheManager
        
        cache = CacheManager(redis_url="redis://localhost:6379/0")
        
        # Test set/get
        test_key = "test_key"
        test_value = {"test": "data", "timestamp": datetime.now().isoformat()}
        
        await cache.set(test_key, test_value, ttl_seconds=60)
        retrieved = await cache.get(test_key)
        
        assert retrieved == test_value, "Cache set/get failed"
        
        # Test exists
        exists = await cache.exists(test_key)
        assert exists, "Cache exists check failed"
        
        # Test stats
        stats = await cache.get_stats()
        logger.info(f"Cache stats: {stats}")
        
        # Test delete
        deleted = await cache.delete(test_key)
        assert deleted, "Cache delete failed"
        
        # Verify deletion
        retrieved_after_delete = await cache.get(test_key)
        assert retrieved_after_delete is None, "Cache delete verification failed"
        
        logger.info("✅ Cache system tests passed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Cache system test failed: {e}")
        return False

async def test_harris_scraper():
    """Test the Harris County scraper"""
    logger.info("🧪 Testing Harris County scraper...")
    
    try:
        from tools_1.scrape_harris_records import scrape_harris_records
        
        # Test with real data for June 2025
        filters = {
            'document_type': 'LisPendens',
            'date_from': '2025-06-10',
            'date_to': '2025-06-24',
            'page_size': 3,
            'user_id': 'test_user'
        }
        
        records = await scrape_harris_records(filters)
        
        assert isinstance(records, list), "Scraper should return a list"
        assert len(records) > 0, "Should return at least some records (real data)"
        
        # Verify record structure
        if records:
            record = records[0]
            required_fields = ['caseNumber', 'filingDate', 'subdivision', 'docType']
            for field in required_fields:
                assert field in record, f"Missing required field: {field}"
        
        logger.info(f"✅ Harris scraper test passed - {len(records)} records")
        return True
        
    except Exception as e:
        logger.error(f"❌ Harris scraper test failed: {e}")
        return False

async def test_hcad_lookup():
    """Test the HCAD lookup system"""
    logger.info("🧪 Testing HCAD lookup...")
    
    try:
        from tools_2.hcad_lookup import hcad_lookup
        
        # Test lookup with mock data
        legal_params = {
            'subdivision': 'MOCK SUBDIVISION',
            'section': '1',
            'block': '2',
            'lot': '5'
        }
        
        result = await hcad_lookup(legal_params)
        
        assert isinstance(result, dict), "HCAD lookup should return a dict"
        assert 'address' in result, "Result should have address field"
        assert 'parcel_id' in result, "Result should have parcel_id field"
        
        logger.info(f"✅ HCAD lookup test passed - {result}")
        return True
        
    except Exception as e:
        logger.error(f"❌ HCAD lookup test failed: {e}")
        return False

async def test_agent_core():
    """Test the main agent orchestration"""
    logger.info("🧪 Testing agent core...")
    
    try:
        from agent_core import agent_scrape
        
        # Test with small parameters
        county = "Harris"
        filters = {
            'document_type': 'LisPendens',
            'date_from': '2025-01-01',
            'date_to': '2025-01-31',
            'page_size': 2
        }
        user_id = "test_user"
        
        result = await agent_scrape(county, filters, user_id)
        
        assert isinstance(result, dict), "Agent should return a dict"
        assert 'records' in result, "Result should have records"
        assert 'metadata' in result, "Result should have metadata"
        
        # Verify structure
        records = result['records']
        metadata = result['metadata']
        
        assert isinstance(records, list), "Records should be a list"
        assert isinstance(metadata, dict), "Metadata should be a dict"
        assert metadata['county'] == county, "Metadata should include county"
        assert metadata['user_id'] == user_id, "Metadata should include user_id"
        
        # Verify record structure if any records exist
        if records:
            record = records[0]
            assert 'legal' in record, "Record should have legal description"
            legal = record['legal']
            assert 'case_number' in legal, "Legal should have case_number"
            assert 'filing_date' in legal, "Legal should have filing_date"
        
        logger.info(f"✅ Agent core test passed - {len(records)} enriched records")
        return True
        
    except Exception as e:
        logger.error(f"❌ Agent core test failed: {e}")
        return False

async def test_full_integration():
    """Test the complete end-to-end flow"""
    logger.info("🧪 Testing full integration...")
    
    try:
        from agent_core import LisPendensAgent, AgentScrapeParams
        
        # Create agent instance
        agent = LisPendensAgent()
        
        # Set up test parameters
        params = AgentScrapeParams(
            county="Harris",
            filters={
                'document_type': 'LisPendens',
                'date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                'date_to': datetime.now().strftime('%Y-%m-%d'),
                'page_size': 2
            },
            user_id="integration_test"
        )
        
        # Run the agent
        result = await agent.scrape(params)
        
        # Verify complete result structure
        assert 'records' in result
        assert 'metadata' in result
        
        metadata = result['metadata']
        assert 'total_found' in metadata
        assert 'processed' in metadata
        assert 'timestamp' in metadata
        
        logger.info("✅ Full integration test passed")
        logger.info(f"📊 Results: {metadata}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Full integration test failed: {e}")
        return False

async def run_performance_test():
    """Run a basic performance test"""
    logger.info("🧪 Running performance test...")
    
    try:
        from agent_core import agent_scrape
        
        start_time = datetime.now()
        
        # Test with slightly larger dataset
        result = await agent_scrape(
            "Harris",
            {
                'document_type': 'LisPendens',
                'date_from': '2025-01-01',
                'date_to': '2025-01-31',
                'page_size': 5
            },
            "perf_test"
        )
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        records_count = len(result.get('records', []))
        
        logger.info(f"✅ Performance test completed:")
        logger.info(f"   Duration: {duration:.2f} seconds")
        logger.info(f"   Records processed: {records_count}")
        logger.info(f"   Rate: {records_count/duration:.2f} records/second")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
        return False

async def main():
    """Run all tests"""
    logger.info("🚀 Starting LisPendens Agent Test Suite")
    logger.info("=" * 60)
    
    tests = [
        ("Cache System", test_cache_system),
        ("Harris Scraper", test_harris_scraper),
        ("HCAD Lookup", test_hcad_lookup),
        ("Agent Core", test_agent_core),
        ("Full Integration", test_full_integration),
        ("Performance", run_performance_test)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        logger.info(f"\n🔬 Running {test_name} test...")
        try:
            success = await test_func()
            results[test_name] = success
            if success:
                logger.info(f"✅ {test_name} test PASSED")
            else:
                logger.error(f"❌ {test_name} test FAILED")
        except Exception as e:
            logger.error(f"💥 {test_name} test CRASHED: {e}")
            results[test_name] = False
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for success in results.values() if success)
    total = len(results)
    
    for test_name, success in results.items():
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"  {test_name:<20} {status}")
    
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Agent system is ready.")
        return 0
    else:
        logger.error(f"⚠️  {total - passed} tests failed. Please review and fix issues.")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 