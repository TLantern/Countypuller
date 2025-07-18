"""
Harris County Database Saver
Saves enriched Harris County records to the harris_county_filing table
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Set
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Zip code restrictions for specific user IDs
RESTRICTED_USER_ZIP_CODES = {
    '6b3d5d75-f440-46d3-b0a6-8c6e49b211a5': {
        # Cypress, TX
        '77429', '77433',
        # Katy, TX  
        '77449', '77450', '77493', '77494',
        # Humble, TX
        '77338', '77339', '77345', '77346', '77396',
        # Other Misc
        '77033', '77047', '77088',
        # Special case: 77021 only for Harris for the one record type they can pull
        '77021'
    },
    '08c8ffaa-0bfb-4db3-abbb-ebe1eef036aa': {
        # Cypress, TX
        '77429', '77433',
        # Katy, TX  
        '77449', '77450', '77493', '77494',
        # Humble, TX
        '77338', '77339', '77345', '77346', '77396',
        # Other Misc
        '77033', '77047', '77088',
        # Special case: 77021 only for Harris for the one record type they can pull
        '77021'
    },
    '867ebb10-afd9-4892-b781-208ba8098306': {
        # Cypress, TX
        '77429', '77433',
        # Katy, TX  
        '77449', '77450', '77493', '77494',
        # Humble, TX
        '77338', '77339', '77345', '77346', '77396',
        # Other Misc
        '77033', '77047', '77088',
        # Special case: 77021 only for Harris for the one record type they can pull
        '77021'
    }
}

def extract_zip_code_from_address(address: str) -> Optional[str]:
    """
    Extract zip code from property address string
    
    Args:
        address: Property address string (e.g., "123 Main St, Houston, TX 77001")
        
    Returns:
        str: Zip code if found, None otherwise
    """
    if not address:
        return None
    
    # Look for 5-digit zip codes, optionally followed by -4 digits
    zip_pattern = r'\b(\d{5})(?:-\d{4})?\b'
    match = re.search(zip_pattern, address)
    
    if match:
        return match.group(1)  # Return just the 5-digit zip code
    
    return None

def should_filter_record_by_zip(user_id: str, property_address: str) -> bool:
    """
    Check if a record should be filtered out based on city and zip code restrictions
    
    Args:
        user_id: User ID to check restrictions for
        property_address: Enriched property address to extract city/zip from
        
    Returns:
        bool: True if record should be filtered out (blocked), False if allowed
    """
    # Only apply restrictions to specific user IDs
    if user_id not in RESTRICTED_USER_ZIP_CODES:
        return False  # No restrictions for this user, allow all records
    
    if not property_address:
        logger.debug(f"🚫 No address provided for restricted user {user_id}")
        return True  # Filter out records without addresses
    
    allowed_zip_codes = RESTRICTED_USER_ZIP_CODES[user_id]
    
    # Define allowed cities for restricted users (Cypress, Humble, Katy areas)
    allowed_cities = ['CYPRESS', 'HUMBLE', 'KATY', 'SPRING', 'TOMBALL', 'HOUSTON']
    
    address_upper = property_address.upper()
    
    # Check if address contains allowed city names
    for city in allowed_cities:
        if city in address_upper:
            logger.debug(f"✅ Allowed record for user {user_id}: city '{city}' found in address")
            return False  # Allow this record
    
    # Extract and check zip code
    extracted_zip = extract_zip_code_from_address(property_address)
    
    if extracted_zip and extracted_zip in allowed_zip_codes:
        logger.debug(f"✅ Allowed record for user {user_id}: zip code {extracted_zip} is permitted")
        return False  # Allow this record
    
    # If no city or zip code match found, filter out
    if not extracted_zip:
        logger.debug(f"🚫 Filtered out record for user {user_id}: no valid city or zip code found in '{property_address}'")
    else:
        logger.debug(f"🚫 Filtered out record for user {user_id}: zip code {extracted_zip} not in allowed list, city not in allowed cities")
    
    return True  # Filter out this record

async def save_harris_records(records: List[Dict[str, Any]], user_id: str) -> bool:
    """
    Save Harris County agent records to the database
    
    Args:
        records: List of enriched records from the agent
        user_id: User ID for the records
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Import database dependencies
        import asyncpg
        from datetime import datetime
        
        # Get database URL from environment
        DATABASE_URL = os.getenv("DATABASE_URL")
        if not DATABASE_URL:
            logger.error("❌ No DATABASE_URL found in environment variables")
            return False
        
        # Parse the database URL for asyncpg
        if DATABASE_URL.startswith("postgresql://"):
            DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgres://")
        
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        
        # Prepare records for insertion with zip code filtering
        processed_records = []
        filtered_count = 0
        seen_case_numbers = set()  # Track duplicates in this batch
        
        for record in records:
            legal = record.get('legal', {})
            property_address = record.get('address')  # This is the enriched/canonical address
            case_number = legal.get('case_number', '')
            
            # Skip duplicate case numbers in this batch
            if case_number and case_number in seen_case_numbers:
                logger.debug(f"🔄 Skipping duplicate case number in batch: {case_number}")
                continue
            elif case_number:
                seen_case_numbers.add(case_number)
            
            # Apply zip code filtering before processing
            if should_filter_record_by_zip(user_id, property_address):
                filtered_count += 1
                logger.debug(f"Skipping record {case_number or 'unknown'} due to zip code restriction")
                continue
            
            # Parse filing date
            filing_date = None
            if legal.get('filing_date'):
                try:
                    # Try multiple date formats
                    date_str = legal.get('filing_date', '')
                    if '/' in date_str:  # MM/DD/YYYY format
                        filing_date = datetime.strptime(date_str, '%m/%d/%Y')
                    elif '-' in date_str:  # YYYY-MM-DD format
                        filing_date = datetime.strptime(date_str, '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Could not parse filing date: {legal.get('filing_date')}")
            
            processed_record = {
                'case_number': case_number,
                'filing_date': filing_date,
                'doc_type': legal.get('doc_type', 'L/P'),
                'subdivision': legal.get('subdivision', ''),
                'section': legal.get('section', ''),
                'block': legal.get('block', ''),
                'lot': legal.get('lot', ''),
                'property_address': property_address,
                'parcel_id': record.get('parcel_id'),
                'ai_summary': record.get('summary'),
                'county': 'Harris',
                'state': 'TX',
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
                'is_new': True,
                'userId': user_id
            }
            processed_records.append(processed_record)
        
        # Log filtering results if applicable
        if user_id in RESTRICTED_USER_ZIP_CODES:
            total_input_records = len(records)
            allowed_records = len(processed_records)
            logger.debug(f"🔒 Zip code filtering for user {user_id}: {allowed_records}/{total_input_records} records allowed, {filtered_count} filtered out")
        
        # SQL for Harris County filings with UPSERT
        insert_sql = """
        INSERT INTO harris_county_filing
        (case_number, filing_date, doc_type, subdivision, section, block, lot, 
         property_address, parcel_id, ai_summary, county, state, created_at, updated_at, is_new, "userId")
        VALUES
        ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
        ON CONFLICT (case_number) DO UPDATE
        SET
            filing_date = EXCLUDED.filing_date,
            doc_type = EXCLUDED.doc_type,
            subdivision = EXCLUDED.subdivision,
            section = EXCLUDED.section,
            block = EXCLUDED.block,
            lot = EXCLUDED.lot,
            property_address = EXCLUDED.property_address,
            parcel_id = EXCLUDED.parcel_id,
            ai_summary = EXCLUDED.ai_summary,
            updated_at = EXCLUDED.updated_at,
            "userId" = EXCLUDED."userId"
        """
        
        # Insert records
        inserted_count = 0
        for record in processed_records:
            if record['case_number']:  # Only insert if we have a case number
                try:
                    await conn.execute(
                        insert_sql,
                        record['case_number'],
                        record['filing_date'],
                        record['doc_type'],
                        record['subdivision'],
                        record['section'],
                        record['block'],
                        record['lot'],
                        record['property_address'],
                        record['parcel_id'],
                        record['ai_summary'],
                        record['county'],
                        record['state'],
                        record['created_at'],
                        record['updated_at'],
                        record['is_new'],
                        record['userId']
                    )
                    inserted_count += 1
                except Exception as e:
                    logger.warning(f"Failed to insert record {record['case_number']}: {e}")
        
        await conn.close()
        
        # Enhanced logging with deduplication info
        total_input = len(records)
        duplicates_removed = total_input - len(processed_records) - filtered_count
        
        if user_id in RESTRICTED_USER_ZIP_CODES:
            logger.info(f"✅ Successfully saved {inserted_count} Harris County records to database")
            logger.debug(f"📊 Processing summary: {total_input} input → {duplicates_removed} duplicates removed → {filtered_count} location filtered → {inserted_count} saved")
            logger.debug(f"✅ User {user_id} is zip code restricted")
        else:
            logger.info(f"✅ Successfully saved {inserted_count} Harris County records to database")
            if duplicates_removed > 0:
                logger.info(f"🧹 Removed {duplicates_removed} duplicates during save process")
        return True
        
    except ImportError as e:
        logger.error(f"⚠️ Database dependencies not available: {e}")
        logger.error("⚠️ Install: pip install asyncpg")
        return False
    except Exception as e:
        logger.error(f"❌ Database save error: {e}")
        return False

async def test_save():
    """Test function for database saving"""
    test_records = [
        {
            "legal": {
                "subdivision": "TEST SUBDIVISION",
                "section": "1",
                "block": "2",
                "lot": "3",
                "case_number": "RP-2025-TEST001",
                "filing_date": "06/27/2025",
                "doc_type": "L/P"
            },
            "address": "123 TEST ST, HOUSTON, TX 77001",
            "parcel_id": "1234567890123",
            "summary": "Test property summary",
            "error": None
        }
    ]
    
    result = await save_harris_records(test_records, "test-user-123")
    print(f"Test save result: {result}")

if __name__ == "__main__":
    asyncio.run(test_save()) 