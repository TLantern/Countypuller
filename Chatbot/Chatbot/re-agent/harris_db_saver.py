"""
Harris County Database Saver
Saves enriched Harris County records to the harris_county_filing table
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        
        # Prepare records for insertion
        processed_records = []
        for record in records:
            legal = record.get('legal', {})
            
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
                'case_number': legal.get('case_number', ''),
                'filing_date': filing_date,
                'doc_type': legal.get('doc_type', 'L/P'),
                'subdivision': legal.get('subdivision', ''),
                'section': legal.get('section', ''),
                'block': legal.get('block', ''),
                'lot': legal.get('lot', ''),
                'property_address': record.get('address'),
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
            updated_at = EXCLUDED.updated_at
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
        logger.info(f"✅ Successfully saved {inserted_count} Harris County records to database")
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