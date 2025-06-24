"""
LisPendens Scraper + Resolver Agent Core

This module provides the main orchestration for scraping Harris County lis pendens records
and enriching them with HCAD address lookups using a caching layer.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import sys
import os

# Add the PullingBots directory to the path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'PullingBots'))

from cache import CacheManager
from tools_1.scrape_harris_records import scrape_harris_records
from tools_2.hcad_lookup import hcad_lookup

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class LegalDescription:
    subdivision: str = ""
    section: str = ""
    block: str = ""
    lot: str = ""
    case_number: str = ""
    filing_date: str = ""
    doc_type: str = "LisPendens"

@dataclass
class EnrichedRecord:
    legal: LegalDescription
    address: Optional[str] = None
    parcel_id: Optional[str] = None
    summary: Optional[str] = None
    error: Optional[str] = None

@dataclass
class AgentScrapeParams:
    county: str
    filters: Dict[str, Any]
    user_id: Optional[str] = None

class LisPendensAgent:
    def __init__(self):
        self.cache = CacheManager()
        logger.info("🤖 LisPendens Agent initialized")

    async def scrape(self, params: AgentScrapeParams) -> Dict[str, Any]:
        """
        Main orchestration method that handles scraping and enrichment
        
        Args:
            params: AgentScrapeParams containing county, filters, and user_id
            
        Returns:
            Dict containing enriched records and metadata
        """
        logger.info(f"🚀 Starting agent scrape for {params.county} county")
        logger.info(f"📋 Filters: {params.filters}")

        try:
            # Step 1: Get or scrape raw records with caching
            raw_records = await self._get_raw_records(params)
            
            # Step 2: Enrich records with address lookups
            enriched_records = await self._enrich_records(raw_records)
            
            # Step 3: Generate summary
            result = {
                "records": [asdict(record) for record in enriched_records],
                "metadata": {
                    "county": params.county,
                    "filters": params.filters,
                    "total_found": len(raw_records),
                    "processed": len(enriched_records),
                    "timestamp": datetime.now().isoformat(),
                    "user_id": params.user_id
                }
            }
            
            logger.info(f"✅ Completed processing {len(enriched_records)} records")
            return result
            
        except Exception as e:
            logger.error(f"❌ Agent scrape failed: {e}")
            raise

    async def _get_raw_records(self, params: AgentScrapeParams) -> List[Dict[str, Any]]:
        """Get raw records from cache or by scraping"""
        
        # Create cache key based on parameters
        cache_key = f"scrape_{params.county}_{params.filters.get('date_from', '')}_{params.filters.get('date_to', '')}_{params.filters.get('document_type', '')}_{params.filters.get('page_size', 50)}"
        
        # Try to get from cache first
        cached_records = await self.cache.get(cache_key)
        if cached_records:
            logger.info("⚡ Cache hit - using cached scrape results")
            return cached_records
        
        logger.info("📡 Cache miss - calling scraper")
        
        # Add _mock flag for testing if needed
        scraper_filters = params.filters.copy()
        if params.filters.get('_mock', False) or params.filters.get('use_mock', False):
            scraper_filters['_mock'] = True
        
        # Call appropriate scraper based on county
        if params.county.lower() == 'harris':
            raw_records = await scrape_harris_records(scraper_filters)
        else:
            raise ValueError(f"County '{params.county}' not supported yet")
        
        # Cache the results for 24 hours
        await self.cache.set(cache_key, raw_records, ttl_seconds=24 * 60 * 60)
        logger.info(f"💾 Cached {len(raw_records)} records with key: {cache_key}")
        
        return raw_records

    async def _enrich_records(self, raw_records: List[Dict[str, Any]]) -> List[EnrichedRecord]:
        """Enrich raw records with HCAD address lookups"""
        
        enriched_records: List[EnrichedRecord] = []
        max_records = min(len(raw_records), 20)  # Limit to prevent rate limiting
        
        logger.info(f"🔄 Processing {max_records} records for address enrichment")
        
        for i, record in enumerate(raw_records[:max_records]):
            try:
                # Create legal description from raw record
                legal_desc = LegalDescription(
                    subdivision=self._extract_field(record, ['subdivision', 'desc']),
                    section=self._extract_field(record, ['section', 'sec']),
                    block=self._extract_field(record, ['block', 'blk']),
                    lot=self._extract_field(record, ['lot']),
                    case_number=self._extract_field(record, ['case_number', 'caseNumber', 'file_no']),
                    filing_date=self._extract_field(record, ['file_date', 'filing_date', 'filingDate']),
                    doc_type=self._extract_field(record, ['document_type', 'doc_type', 'docType'], 'LisPendens')
                )
                
                enriched_record = EnrichedRecord(legal=legal_desc)
                
                # Try HCAD lookup if we have legal description components
                if any([legal_desc.subdivision, legal_desc.lot, legal_desc.block]):
                    try:
                        hcad_result = await hcad_lookup({
                            'subdivision': legal_desc.subdivision,
                            'section': legal_desc.section,
                            'block': legal_desc.block,
                            'lot': legal_desc.lot
                        })
                        
                        if hcad_result.get('address'):
                            enriched_record.address = hcad_result['address']
                            enriched_record.parcel_id = hcad_result.get('parcel_id')
                            
                            # Generate summary
                            enriched_record.summary = f"Lis Pendens filed on {legal_desc.filing_date} against {enriched_record.address}"
                            if enriched_record.parcel_id:
                                enriched_record.summary += f" (Parcel: {enriched_record.parcel_id})"
                            enriched_record.summary += "."
                            
                    except Exception as hcad_error:
                        logger.warning(f"HCAD lookup failed for case {legal_desc.case_number}: {hcad_error}")
                        enriched_record.error = "Address lookup failed"
                
                # Fallback to existing property_address if available
                if not enriched_record.address:
                    property_address = self._extract_field(record, ['property_address', 'address'])
                    if property_address:
                        enriched_record.address = property_address
                        enriched_record.summary = f"Lis Pendens filed on {legal_desc.filing_date} for case {legal_desc.case_number}."
                
                enriched_records.append(enriched_record)
                
                # Rate limiting between requests
                if i < max_records - 1:
                    await asyncio.sleep(0.1)
                    
            except Exception as record_error:
                logger.error(f"Error processing record {i}: {record_error}")
                enriched_records.append(EnrichedRecord(
                    legal=LegalDescription(
                        case_number=self._extract_field(record, ['case_number', 'caseNumber'], f"record_{i}"),
                        filing_date=self._extract_field(record, ['file_date', 'filing_date'])
                    ),
                    error="Processing failed"
                ))
        
        return enriched_records

    def _extract_field(self, record: Dict[str, Any], field_names: List[str], default: str = "") -> str:
        """Extract field value from record using multiple possible field names"""
        for field_name in field_names:
            if field_name in record and record[field_name]:
                return str(record[field_name]).strip()
        return default

# Main async function for standalone usage
async def agent_scrape(county: str, filters: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Standalone function to scrape and enrich lis pendens records
    
    Args:
        county: County name (e.g., "Harris")
        filters: Dictionary containing search filters
        user_id: Optional user identifier
        
    Returns:
        Dictionary containing enriched records and metadata
    """
    agent = LisPendensAgent()
    params = AgentScrapeParams(
        county=county,
        filters=filters,
        user_id=user_id
    )
    return await agent.scrape(params)

# CLI interface for testing
async def main():
    """Main function for command-line testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='LisPendens Scraper + Resolver')
    parser.add_argument('--county', default='Harris', help='County to scrape')
    parser.add_argument('--date-from', help='Start date (YYYY-MM-DD)')
    parser.add_argument('--date-to', help='End date (YYYY-MM-DD)')
    parser.add_argument('--page-size', type=int, default=50, help='Number of records to fetch')
    parser.add_argument('--user-id', help='User ID for tracking')
    parser.add_argument('--mock', action='store_true', help='Use mock data for testing')
    
    args = parser.parse_args()
    
    # Set default dates if not provided
    if not args.date_from:
        args.date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not args.date_to:
        args.date_to = datetime.now().strftime('%Y-%m-%d')
    
    filters = {
        'document_type': 'LisPendens',
        'date_from': args.date_from,
        'date_to': args.date_to,
        'page_size': args.page_size,
        '_mock': args.mock
    }
    
    try:
        result = await agent_scrape(args.county, filters, args.user_id)
        print(json.dumps(result, indent=2))
    except Exception as e:
        logger.error(f"CLI execution failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
