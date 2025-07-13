"""
LisPendens Scraper + Resolver Agent Core

This module provides the main orchestration for scraping Harris County lis pendens records
and enriching them with HCAD address lookups using a caching layer.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from cache import CacheManager
from tools_1.scrape_harris_records import scrape_harris_records
from tools_2.hcad_lookup import hcad_lookup
from harris_db_saver import save_harris_records

# Add import for address enrichment
import os
import aiohttp

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
            
            # Step 2: Enrich records with full address enrichment
            enriched_records = await self._enrich_records(raw_records)
            
            # Step 3: Save to database (Harris County specific table)
            if params.county.lower() == 'harris' and params.user_id:
                records_data = [asdict(record) for record in enriched_records]
                save_success = await save_harris_records(records_data, params.user_id)
                if save_success:
                    logger.info(f"💾 Saved {len(enriched_records)} records to harris_county_filing table")
                else:
                    logger.warning("⚠️ Database save failed - records still returned in response")
            
            # Step 4: Generate summary
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
            
            logger.info(f"✅ Agent scrape completed: {len(enriched_records)} enriched records")
            return result
            
        except Exception as e:
            logger.error(f"❌ Agent scrape failed: {e}")
            raise

    async def _get_raw_records(self, params: AgentScrapeParams) -> List[Dict[str, Any]]:
        """Get raw records from scraper with caching"""
        
        # Create cache key based on parameters
        cache_key = f"raw_records_{params.county}_{hash(str(params.filters))}"
        
        # Check cache first
        cached_records = await self.cache.get(cache_key)
        if cached_records:
            logger.info(f"⚡ Cache hit! Using {len(cached_records)} cached records")
            return cached_records
        
        logger.info(f"🔍 Cache miss - fetching fresh records from {params.county}")
        
        # Build scraper filters
        scraper_filters = {
            'document_type': params.filters.get('documentType', 'LisPendens'),
            'date_from': params.filters.get('dateFrom'),
            'date_to': params.filters.get('dateTo'),
            'page_size': params.filters.get('pageSize', 50),
            '_mock': params.filters.get('_mock', False)
        }
        
        # Get raw records from appropriate scraper
        if params.county.lower() == 'harris':
            raw_records = await scrape_harris_records(scraper_filters)
        else:
            raise ValueError(f"County '{params.county}' not supported yet")
        
        # Cache the results for 24 hours
        await self.cache.set(cache_key, raw_records, ttl_seconds=24 * 60 * 60)
        logger.info(f"💾 Cached {len(raw_records)} records with key: {cache_key}")
        
        return raw_records

    async def _enrich_records(self, raw_records: List[Dict[str, Any]]) -> List[EnrichedRecord]:
        """Enrich raw records with full address enrichment pipeline"""
        
        enriched_records: List[EnrichedRecord] = []
        max_records = min(len(raw_records), 20)  # Limit to prevent rate limiting
        
        logger.info(f"🔄 Processing {max_records} records for full address enrichment")
        
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
                
                # Extract raw address from record
                raw_address = self._extract_field(record, ['property_address', 'address', 'scraped_address'])
                
                if raw_address and raw_address.strip():
                    logger.info(f"🏠 Enriching address for case {legal_desc.case_number}: {raw_address}")
                    
                    # Use full address enrichment pipeline
                    enriched_address_data = await self._enrich_single_address(raw_address)
                    
                    if enriched_address_data:
                        # Use the canonical (enriched) address
                        enriched_record.address = enriched_address_data.get('canonical_address', raw_address)
                        
                        # Extract additional data if available
                        if enriched_address_data.get('attomid'):
                            enriched_record.parcel_id = enriched_address_data.get('attomid')
                        
                        # Generate summary with enriched data
                        enriched_record.summary = self._generate_summary(legal_desc, enriched_record.address or raw_address, enriched_address_data)
                        
                        logger.info(f"✅ Address enriched: {raw_address} → {enriched_record.address}")
                    else:
                        # Fallback to raw address if enrichment fails
                        enriched_record.address = raw_address
                        enriched_record.summary = f"Lis Pendens filed on {legal_desc.filing_date} for case {legal_desc.case_number}."
                        logger.warning(f"⚠️ Address enrichment failed for {raw_address}, using raw address")
                else:
                    # Try HCAD lookup as fallback if no direct address but have legal description
                    if any([legal_desc.subdivision, legal_desc.lot, legal_desc.block]):
                        try:
                            hcad_result = await hcad_lookup({
                                'subdivision': legal_desc.subdivision,
                                'section': legal_desc.section,
                                'block': legal_desc.block,
                                'lot': legal_desc.lot,
                                'owner_name': self._extract_field(record, ['grantee', 'granteeName', 'owner_name'])
                            })
                            
                            if hcad_result.get('address'):
                                # Enrich the HCAD address
                                enriched_address_data = await self._enrich_single_address(hcad_result['address'])
                                enriched_record.address = enriched_address_data.get('canonical_address', hcad_result['address']) if enriched_address_data else hcad_result['address']
                                enriched_record.parcel_id = hcad_result.get('parcel_id')
                                enriched_record.summary = self._generate_summary(legal_desc, enriched_record.address or hcad_result['address'], enriched_address_data)
                                logger.info(f"✅ HCAD address found and enriched: {enriched_record.address}")
                            else:
                                enriched_record.summary = f"Lis Pendens filed on {legal_desc.filing_date} for case {legal_desc.case_number}."
                                logger.warning(f"⚠️ No address found via HCAD lookup for case {legal_desc.case_number}")
                        except Exception as hcad_error:
                            logger.warning(f"HCAD lookup failed for case {legal_desc.case_number}: {hcad_error}")
                            enriched_record.error = "Address lookup failed"
                            enriched_record.summary = f"Lis Pendens filed on {legal_desc.filing_date} for case {legal_desc.case_number}."
                    else:
                        enriched_record.summary = f"Lis Pendens filed on {legal_desc.filing_date} for case {legal_desc.case_number}."
                        logger.warning(f"⚠️ No address or legal description available for case {legal_desc.case_number}")
                
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

    async def _enrich_single_address(self, raw_address: str) -> Optional[Dict[str, Any]]:
        """Enrich a single address using the address enrichment pipeline"""
        try:
            # Import the address enrichment pipeline
            pipeline_path = os.path.join(os.path.dirname(__file__), '..', '..', 'cc-frontend', 'scripts')
            if pipeline_path not in sys.path:
                sys.path.append(pipeline_path)
            
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(
                    "address_enrichment_pipeline", 
                    os.path.join(pipeline_path, "address_enrichment_pipeline.py")
                )
                if spec is None or spec.loader is None:
                    logger.error("Address enrichment pipeline not found. Make sure address_enrichment_pipeline.py exists in cc-frontend/scripts/")
                    return None
                
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                AddressEnrichmentPipeline = module.AddressEnrichmentPipeline
            except Exception as import_error:
                logger.error(f"Failed to import address enrichment pipeline: {import_error}")
                return None
            
            # Get API keys from environment
            google_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
            smartystreets_auth_id = os.getenv('SMARTYSTREETS_AUTH_ID')
            smartystreets_auth_token = os.getenv('SMARTYSTREETS_AUTH_TOKEN')
            usps_user_id = os.getenv('USPS_USER_ID')
            attom_api_key = os.getenv('ATTOM_API_KEY')
            
            # Check if we have at least one address validation method
            if not google_api_key and not (smartystreets_auth_id and smartystreets_auth_token) and not usps_user_id:
                logger.warning("No address validation API keys found (GOOGLE_MAPS_API_KEY, SMARTYSTREETS_AUTH_ID/TOKEN, or USPS_USER_ID)")
                return None
            
            # Initialize the enrichment pipeline with SmartyStreets support
            async with AddressEnrichmentPipeline(
                usps_user_id=usps_user_id,
                attom_api_key=attom_api_key,
                smartystreets_auth_id=smartystreets_auth_id,
                smartystreets_auth_token=smartystreets_auth_token
            ) as pipeline:
                # Enrich the address
                result = await pipeline.enrich_address(raw_address)
                return result
                
        except Exception as e:
            logger.error(f"Address enrichment failed for '{raw_address}': {e}")
            return None

    def _generate_summary(self, legal_desc: LegalDescription, address: str, enriched_data: Optional[Dict[str, Any]] = None) -> str:
        """Generate a summary for the enriched record"""
        base_summary = f"Lis Pendens filed on {legal_desc.filing_date} against {address}"
        
        if enriched_data:
            equity_info = []
            if enriched_data.get('available_equity'):
                equity_info.append(f"${enriched_data['available_equity']:,.0f} equity")
            if enriched_data.get('ltv'):
                equity_info.append(f"{enriched_data['ltv']*100:.1f}% LTV")
            if enriched_data.get('owner_name'):
                equity_info.append(f"Owner: {enriched_data['owner_name']}")
            
            if equity_info:
                base_summary += f" ({', '.join(equity_info)})"
        
        return base_summary

    def _extract_field(self, record: Dict[str, Any], field_names: List[str], default: str = "") -> str:
        """Extract field value from record using multiple possible field names"""
        for field_name in field_names:
            if field_name in record and record[field_name]:
                value = record[field_name]
                # If the value is a list (e.g., multiple grantees), take the first item
                if isinstance(value, list):
                    if value:
                        return str(value[0]).strip()
                else:
                    return str(value).strip()
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
