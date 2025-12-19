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
import sys
from pathlib import Path

# Import Harris scraper from PullingBots
pullingbots_path = Path(__file__).parent.parent / "PullingBots"
if str(pullingbots_path) not in sys.path:
    sys.path.insert(0, str(pullingbots_path))
from HarrisTX import scrape_harris_records

import sys
from pathlib import Path
pullingbots_tools_path = Path(__file__).parent.parent / "PullingBots" / "tools"
if str(pullingbots_tools_path) not in sys.path:
    sys.path.insert(0, str(pullingbots_tools_path))
from hcad_lookup import hcad_lookup
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
        self.current_user_id = None  # Store user ID for filtering
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

        # Store user ID for location filtering
        self.current_user_id = params.user_id

        target_count = params.filters.get('target_count', 10)
        logger.info(f"🎯 Target: {target_count} valid records")

        try:
            # Initialize collections for progressive pulling
            all_raw_records = []
            all_enriched_records = []
            total_attempts = 0
            max_attempts = 3
            
            # Step 1: Progressive pulling until we have enough new records
            all_enriched_records = []
            attempts = 0
            
            # Check if this user has location filtering enabled (needs more attempts)
            from filter_configs import get_user_filter_config
            user_filter = get_user_filter_config(params.user_id)
            has_location_filter = bool(user_filter and user_filter.get('allowed_zip_codes'))
            
            max_attempts = 5 if has_location_filter else 3  # More attempts for filtered users
            current_page_size = 50  # Start with reasonable size
            
            if has_location_filter:
                logger.info(f"🔒 User has location filtering enabled - using {max_attempts} max attempts")
            
            while len(all_enriched_records) < target_count and attempts < max_attempts:
                attempts += 1
                logger.info(f"🔄 Pull attempt {attempts}: Need {target_count - len(all_enriched_records)} more valid records")
                
                # Increase page size on subsequent attempts
                if attempts > 1:
                    current_page_size = min(current_page_size * 2, 200)  # Cap at 200
                
                iteration_params = AgentScrapeParams(
                    county=params.county,
                    filters={**params.filters, 'page_size': current_page_size},
                    user_id=params.user_id
                )
                
                # Get raw records for this attempt
                batch_raw_records = await self._get_raw_records(iteration_params, skip_cache=(attempts > 1))
                logger.info(f"📥 Attempt {attempts}: Got {len(batch_raw_records)} raw records")
                
                if not batch_raw_records:
                    logger.warning(f"⚠️ No raw records found in attempt {attempts}")
                    break
                
                # Deduplicate within this batch
                unique_batch_records = self._deduplicate_raw_records(batch_raw_records)
                logger.info(f"🧹 Batch deduplication: {len(unique_batch_records)} unique records")
                
                # Remove records that already exist in database
                new_batch_records = await self._filter_existing_records(unique_batch_records, params.user_id)
                logger.info(f"🗄️ Database check: {len(new_batch_records)} new records")
                
                if not new_batch_records:
                    logger.warning(f"⚠️ Attempt {attempts}: All records already exist in database")
                    continue
                
                # Enrich the new records
                batch_enriched = await self._enrich_records(new_batch_records, target_count - len(all_enriched_records))
                
                # Add to final collection
                all_enriched_records.extend(batch_enriched)
                logger.info(f"📊 Attempt {attempts} complete: {len(batch_enriched)} enriched, total: {len(all_enriched_records)}/{target_count}")
                
                # Check if we need to increase page size if no records passed location filter
                if len(batch_enriched) == 0 and len(new_batch_records) > 0:
                    logger.warning(f"🚫 Attempt {attempts}: All {len(new_batch_records)} records filtered out by location restrictions (proximity rules)")
                    logger.info(f"🔄 Increasing page size for next attempt to find records in allowed areas")
                    current_page_size = min(current_page_size * 2, 500)  # Increase cap to 500 for filter scenarios
                
                # Break if we have enough
                if len(all_enriched_records) >= target_count:
                    break
            
            if not all_enriched_records:
                logger.warning("⚠️ No new records found after all attempts!")
                return {
                    "records": [],
                    "metadata": {
                        "county": params.county,
                        "filters": params.filters,
                        "total_found": 0,
                        "processed": 0,
                        "target_count": target_count,
                        "target_reached": False,
                        "attempts": attempts,
                        "timestamp": datetime.now().isoformat(),
                        "user_id": params.user_id,
                        "message": "All available records already exist in database"
                    }
                }
            
            # Step 2: Save to database (Harris County specific table)
            if params.county.lower() == 'harris' and params.user_id and all_enriched_records:
                records_data = [asdict(record) for record in all_enriched_records]
                save_success = await save_harris_records(records_data, params.user_id)
                if save_success:
                    logger.info(f"💾 Saved {len(all_enriched_records)} records to harris_county_filing table")
                else:
                    logger.warning("⚠️ Database save failed - records still returned in response")
            
            # Step 3: Generate summary
            result = {
                "records": [asdict(record) for record in all_enriched_records],
                "metadata": {
                    "county": params.county,
                    "filters": params.filters,
                    "total_found": len(all_enriched_records),  # Only count processed records
                    "processed": len(all_enriched_records),
                    "target_count": target_count,
                    "target_reached": len(all_enriched_records) >= target_count,
                    "attempts": attempts,
                    "timestamp": datetime.now().isoformat(),
                    "user_id": params.user_id
                }
            }
            
            if len(all_enriched_records) >= target_count:
                logger.info(f"🎉 Target reached! {len(all_enriched_records)} enriched records")
            else:
                logger.warning(f"⚠️ Target not fully reached: {len(all_enriched_records)}/{target_count} records")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Agent scrape failed: {e}")
            raise

    async def _get_raw_records(self, params: AgentScrapeParams, skip_cache: bool = False) -> List[Dict[str, Any]]:
        """Get raw records from scraper with caching"""
        
        # Create cache key based on parameters
        cache_key = f"raw_records_{params.county}_{hash(str(params.filters))}"
        
        # Check cache first (skip cache for subsequent attempts)
        if not skip_cache:
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

    def _deduplicate_raw_records(self, raw_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate records based on case number"""
        seen_case_numbers = set()
        unique_records = []
        
        for record in raw_records:
            # Extract case number using multiple possible field names
            case_number = (record.get('case_number') or 
                          record.get('caseNumber') or 
                          record.get('file_no') or 
                          '')
            
            if case_number and case_number not in seen_case_numbers:
                seen_case_numbers.add(case_number)
                unique_records.append(record)
            elif case_number:
                logger.debug(f"🔄 Skipping duplicate case number: {case_number}")
            else:
                # Keep records without case numbers (with warning)
                logger.warning(f"⚠️ Record without case number found: {record}")
                unique_records.append(record)
        
        return unique_records

    async def _filter_existing_records(self, raw_records: List[Dict[str, Any]], user_id: str) -> List[Dict[str, Any]]:
        """Remove records that already exist in the database for this user"""
        if not user_id or not raw_records:
            return raw_records
        
        try:
            import asyncpg
            import os
            
            # Get database URL
            DATABASE_URL = os.getenv("DATABASE_URL")
            if not DATABASE_URL:
                logger.warning("⚠️ No DATABASE_URL found - cannot check for existing records")
                return raw_records
            
            # Parse the database URL for asyncpg
            if DATABASE_URL.startswith("postgresql://"):
                DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgres://")
            
            # Extract case numbers from raw records
            case_numbers = []
            for record in raw_records:
                case_number = (record.get('case_number') or 
                              record.get('caseNumber') or 
                              record.get('file_no') or '')
                if case_number:
                    case_numbers.append(case_number)
            
            if not case_numbers:
                logger.warning("⚠️ No case numbers found in raw records")
                return raw_records
            
            # Connect to database and check for existing records
            conn = await asyncpg.connect(DATABASE_URL)
            
            # Query for existing case numbers for this user
            existing_query = """
                SELECT case_number 
                FROM harris_county_filing 
                WHERE "userId" = $1 AND case_number = ANY($2)
            """
            
            existing_records = await conn.fetch(existing_query, user_id, case_numbers)
            existing_case_numbers = {record['case_number'] for record in existing_records}
            
            await conn.close()
            
            # Filter out existing records
            new_records = []
            for record in raw_records:
                case_number = (record.get('case_number') or 
                              record.get('caseNumber') or 
                              record.get('file_no') or '')
                
                if case_number and case_number not in existing_case_numbers:
                    new_records.append(record)
                elif case_number:
                    logger.debug(f"🗄️ Skipping existing record: {case_number}")
                else:
                    # Keep records without case numbers
                    new_records.append(record)
            
            logger.info(f"📊 Database check: {len(existing_case_numbers)} existing, {len(new_records)} new records")
            return new_records
            
        except ImportError:
            logger.warning("⚠️ asyncpg not available - cannot check for existing records")
            return raw_records
        except Exception as e:
            logger.error(f"❌ Error checking existing records: {e}")
            return raw_records  # Return all records if check fails

    async def _enrich_records(self, raw_records: List[Dict[str, Any]], target_count: int) -> List[EnrichedRecord]:
        """Enrich raw records with full address enrichment pipeline and filtering"""
        
        enriched_records: List[EnrichedRecord] = []
        
        logger.info(f"🔄 Processing records in batches until we get {target_count} valid records")
        
        # Process records in batches until we have enough valid ones
        batch_size = 10
        start_idx = 0
        
        while len(enriched_records) < target_count and start_idx < len(raw_records):
            # Process current batch
            end_idx = min(start_idx + batch_size, len(raw_records))
            current_batch = raw_records[start_idx:end_idx]
            
            logger.info(f"📦 Processing batch {start_idx//batch_size + 1}: records {start_idx+1}-{end_idx} ({len(current_batch)} records)")
            
            batch_enriched = await self._process_record_batch(current_batch, target_count - len(enriched_records))
            
            # Filter batch results by city/zip before adding to final list
            valid_batch_records = []
            for record in batch_enriched:
                if self._should_include_record_by_location(record, self.current_user_id):
                    valid_batch_records.append(record)
                    logger.info(f"✅ Valid record {len(enriched_records) + len(valid_batch_records)}/{target_count}: {record.legal.case_number}")
                else:
                    logger.info(f"🚫 Filtered out {record.legal.case_number} (location not in allowed area)")
            
            enriched_records.extend(valid_batch_records)
            
            # Calculate progress percentage for frontend
            progress_percent = min(100, (len(enriched_records) / target_count) * 100)
            logger.info(f"📊 PROGRESS: {len(enriched_records)}/{target_count} valid records found ({progress_percent:.1f}%)")
            logger.info(f"📦 Batch complete: {len(valid_batch_records)} valid records from {len(current_batch)} processed. Total: {len(enriched_records)}/{target_count}")
            
            # Move to next batch
            start_idx = end_idx
            
            # Break if we have enough records
            if len(enriched_records) >= target_count:
                logger.info(f"🎉 TARGET REACHED: {len(enriched_records)}/{target_count} valid records found!")
                break
                
        logger.info(f"🎯 Enrichment complete: {len(enriched_records)} valid records found")
        return enriched_records[:target_count]  # Return exactly the target count

    async def _process_record_batch(self, batch_records: List[Dict[str, Any]], remaining_needed: int) -> List[EnrichedRecord]:
        """Process a batch of records with full enrichment"""
        batch_enriched: List[EnrichedRecord] = []
        
        for i, record in enumerate(batch_records):
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
                
                batch_enriched.append(enriched_record)
                
                # Rate limiting between requests
                if i < len(batch_records) - 1:
                    await asyncio.sleep(0.1)
                    
            except Exception as record_error:
                logger.error(f"Error processing record {i}: {record_error}")
                batch_enriched.append(EnrichedRecord(
                    legal=LegalDescription(
                        case_number=self._extract_field(record, ['case_number', 'caseNumber'], f"record_{i}"),
                        filing_date=self._extract_field(record, ['file_date', 'filing_date'])
                    ),
                    error="Processing failed"
                ))
        
        return batch_enriched

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

    def _should_include_record_by_location(self, record: EnrichedRecord, user_id: Optional[str]) -> bool:
        """
        Determines if a record should be included based on location restrictions (city/zip)
        """
        if not user_id:
            return True
        
        # Import the filtering function from harris_db_saver
        from harris_db_saver import should_filter_record_by_zip
        
        # Use the enriched address for filtering
        property_address = record.address
        
        # Return opposite of should_filter (filter=True means exclude, we want include)
        should_filter = should_filter_record_by_zip(user_id, property_address)
        return not should_filter
    
    def _should_include_record(self, record: EnrichedRecord, user_id: Optional[str]) -> bool:
        """
        Legacy method - kept for compatibility
        """
        return self._should_include_record_by_location(record, user_id)

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
