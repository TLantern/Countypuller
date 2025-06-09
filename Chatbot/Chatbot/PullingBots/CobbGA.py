"""
Cobb County Georgia Lien Index Scraper

This script scrapes lien records for Cobb County, Georgia from the
Georgia Superior Court Clerks' Cooperative Authority (GSCCCA) system.

Website: https://search.gsccca.org/Lien/namesearch.asp

Features:
- Searches for recent Cobb County lien records by date range
- Filters by instrument type (liens, lis pendens, etc.)
- Extracts structured data including case numbers, parties, dates
- Prevents duplicate records via database checking
- Exports results to CSV and optionally Google Sheets
- Supports test mode for development/debugging

Dependencies:
- Base scraper infrastructure (base_scrapers.py, config_schemas.py)
- playwright (browser automation)
- pandas (data manipulation)
- sqlalchemy (database operations)

Author: Generated using the modular county scraper factory
"""

import asyncio
import os
from datetime import datetime, date, timedelta
import time
from pathlib import Path
import pandas as pd
from typing import Optional, TypedDict, List, Dict, Any
from urllib.parse import urljoin
import argparse
import re
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Local imports
from base_scrapers import SearchFormScraper
from config_schemas import CountyConfig, ScrapingResult, ScrapingRecord

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────────────────────────────────────
class CobbRecord(TypedDict):
    case_number: str
    document_type: str  
    filing_date: str
    debtor_name: str
    claimant_name: str
    county: str
    book_page: str
    document_link: Optional[str]

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL = "https://search.gsccca.org/Lien/namesearch.asp"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MAX_NEW_RECORDS = 100  # Maximum number of new records to scrape per run
USER_ID = None  # Will be set from command line argument
COUNTY_NAME = "Cobb GA"

# Environment variables
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME = os.getenv("GSHEET_NAME")
COBB_TAB = os.getenv("COBB_TAB", "CobbGA")
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required")

# Database configuration
engine = create_async_engine(DB_URL, echo=False)

# You'll need to create this table first:
# CREATE TABLE cobb_ga_filing (
#   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#   case_number TEXT UNIQUE NOT NULL,
#   document_type TEXT,
#   filing_date TIMESTAMP,
#   debtor_name TEXT,
#   claimant_name TEXT,
#   county TEXT,
#   book_page TEXT,
#   document_link TEXT,
#   state TEXT DEFAULT 'GA',
#   created_at TIMESTAMP DEFAULT NOW(),
#   updated_at TIMESTAMP DEFAULT NOW(),
#   is_new BOOLEAN DEFAULT TRUE,
#   "userId" TEXT
# );

INSERT_SQL = """
INSERT INTO cobb_ga_filing
  (case_number, document_type, filing_date, debtor_name, claimant_name, 
   county, book_page, document_link, state, created_at, is_new, "userId")
VALUES
  (:case_number, :document_type, :filing_date, :debtor_name, :claimant_name,
   :county, :book_page, :document_link, :state, :created_at, :is_new, :userId)
ON CONFLICT (case_number) DO UPDATE
SET
  document_type = EXCLUDED.document_type,
  filing_date = EXCLUDED.filing_date,
  debtor_name = EXCLUDED.debtor_name,
  claimant_name = EXCLUDED.claimant_name,
  county = EXCLUDED.county,
  book_page = EXCLUDED.book_page,
  document_link = EXCLUDED.document_link,
  updated_at = EXCLUDED.created_at,
  is_new = EXCLUDED.is_new,
  "userId" = EXCLUDED."userId";
"""

# ─────────────────────────────────────────────────────────────────────────────
# UTILITY FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
def _log(msg: str):
    """Safe logging function that handles Unicode encoding issues"""
    try:
        print(f"[{datetime.now():%H:%M:%S}] {msg}")
    except UnicodeEncodeError:
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        print(f"[{datetime.now():%H:%M:%S}] {safe_msg}")

async def _safe(desc: str, coro):
    """Safe wrapper for async operations with error handling"""
    try:
        return await coro
    except Exception as e:
        _log(f"❌ {desc} → {e}")
        raise

# ─────────────────────────────────────────────────────────────────────────────
# COBB COUNTY SCRAPER CLASS
# ─────────────────────────────────────────────────────────────────────────────
class CobbScraper(SearchFormScraper):
    """Cobb County Georgia lien index scraper implementation"""
    
    async def setup_search_parameters(self, task_params: Dict[str, Any]):
        """Setup Cobb County-specific search parameters"""
        
        # Navigate to search page
        await self.navigate_to_url(self.config.search_config.search_url)
        await self.page.wait_for_timeout(2000)
        
        # Set instrument type to focus on liens and lis pendens
        instrument_types = task_params.get('instrument_types', ['All Instruments'])
        if instrument_types != ['All Instruments']:
            for instrument_type in instrument_types:
                await self.page.select_option('select[name="InstrumentType"]', instrument_type)
                break  # Select first one for now
        
        # Set party type if specified
        party_type = task_params.get('party_type', 'All Parties')
        await self.page.select_option('select[name="PartyType"]', party_type)
        
        # Always set county to COBB for this scraper
        await self.page.select_option('select[name="County"]', 'COBB')
        
        # Set date range
        date_from = task_params.get('date_from')
        date_to = task_params.get('date_to')
        
        if date_from:
            await self.page.fill('input[name="DateFrom"]', date_from)
        if date_to:
            await self.page.fill('input[name="DateTo"]', date_to)
        
        # Set results per page to maximum
        await self.page.select_option('select[name="DisplayResults"]', '100')
        
        _log(f"✅ Search parameters configured")
        
    def clean_record_data(self, record_data: dict) -> CobbRecord:
        """Clean and validate scraped record data"""
        
        def clean_text(text: str) -> str:
            if not text:
                return ""
            return re.sub(r'\s+', ' ', text).strip()
        
        def parse_date(date_str: str) -> str:
            if not date_str:
                return ""
            try:
                # Handle MM/DD/YYYY format
                if re.match(r'\d{1,2}/\d{1,2}/\d{4}', date_str):
                    return datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                return date_str
            except:
                return date_str
        
        return CobbRecord(
            case_number=clean_text(record_data.get('case_number', '')),
            document_type=clean_text(record_data.get('document_type', '')),
            filing_date=parse_date(record_data.get('filing_date', '')),
            debtor_name=clean_text(record_data.get('debtor_name', '')),
            claimant_name=clean_text(record_data.get('claimant_name', '')),
            county=clean_text(record_data.get('county', '')),
            book_page=clean_text(record_data.get('book_page', '')),
            document_link=record_data.get('document_link', '')
        )

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def get_existing_case_numbers() -> set:
    """Get existing case numbers from database to avoid duplicates"""
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                text("SELECT case_number FROM cobb_ga_filing WHERE case_number IS NOT NULL")
            )
            existing = {row[0] for row in result.fetchall()}
            _log(f"📊 Found {len(existing)} existing records in database")
            return existing
    except Exception as e:
        _log(f"⚠️ Database check failed: {e}")
        return set()

async def upsert_records(records: List[dict]):
    """Insert or update records in database"""
    if not records:
        return
    
    try:
        async with AsyncSession(engine) as session:
            for record in records:
                await session.execute(text(INSERT_SQL), {
                    'case_number': record['case_number'],
                    'document_type': record['document_type'],
                    'filing_date': record['filing_date'] if record['filing_date'] else None,
                    'debtor_name': record['debtor_name'],
                    'claimant_name': record['claimant_name'],
                    'county': record['county'],
                    'book_page': record['book_page'],
                    'document_link': record['document_link'],
                    'state': 'GA',
                    'created_at': datetime.now(),
                    'is_new': True,
                    'userId': USER_ID
                })
            
            await session.commit()
            _log(f"💾 Saved {len(records)} records to database")
            
    except Exception as e:
        _log(f"❌ Database insert failed: {e}")
        raise

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def export_to_csv(df: pd.DataFrame) -> Path:
    """Export DataFrame to CSV file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = EXPORT_DIR / f"cobb_ga_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    _log(f"📊 Exported {len(df)} records to {csv_file}")
    return csv_file

def export_to_google_sheets(df: pd.DataFrame):
    """Export DataFrame to Google Sheets"""
    if not GOOGLE_CREDS_FILE or not GSHEET_NAME:
        _log("⚠️ Google Sheets credentials not configured, skipping")
        return
    
    try:
        credentials = Credentials.from_service_account_file(GOOGLE_CREDS_FILE)
        gc = gspread.authorize(credentials)
        sheet = gc.open(GSHEET_NAME)
        
        try:
            worksheet = sheet.worksheet(COBB_TAB)
        except:
            worksheet = sheet.add_worksheet(title=COBB_TAB, rows=1000, cols=20)
        
        # Clear existing data and add headers
        worksheet.clear()
        worksheet.append_row(list(df.columns))
        
        # Add data in batches
        batch_size = 100
        for i in range(0, len(df), batch_size):
            batch = df.iloc[i:i+batch_size]
            batch_values = [row.tolist() for _, row in batch.iterrows()]
            worksheet.append_rows(batch_values)
        
        _log(f"📊 Exported {len(df)} records to Google Sheets")
        
    except Exception as e:
        _log(f"❌ Google Sheets export failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION FUNCTION
# ─────────────────────────────────────────────────────────────────────────────
async def run(max_new_records: int = MAX_NEW_RECORDS, test_mode: bool = False, 
              from_date: str = None, to_date: str = None, 
              instrument_types: List[str] = None, counties: List[str] = None):
    """Main scraping function"""
    
    _log(f"🚀 Starting Cobb County GA Lien Index scraper")
    _log(f"📊 Max records: {max_new_records}, Test mode: {test_mode}")
    
    # Load configuration
    config = CountyConfig.from_json_file("configs/cobb_ga.json")
    config.headless = not test_mode  # Show browser in test mode
    
    # Set default date range (last 30 days)
    if not from_date:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%m/%d/%Y')
    if not to_date:
        to_date = datetime.now().strftime('%m/%d/%Y')
    
    # Set default instrument types (focus on liens and lis pendens)
    if not instrument_types:
        instrument_types = ['Lien', 'Lis Pendens', 'Federal Tax Lien']
    
    # Get existing case numbers
    existing_case_numbers = await get_existing_case_numbers()
    
    # Prepare task parameters
    task_params = {
        'max_records': max_new_records,
        'test_mode': test_mode,
        'date_from': from_date,
        'date_to': to_date,
        'instrument_types': instrument_types,
        'party_type': 'All Parties'
    }
    
    # Run scraper
    try:
        async with CobbScraper(config) as scraper:
            await scraper.setup_search_parameters(task_params)
            result = await scraper.scrape(task_params)
            
            if result.success and result.records:
                # Filter out existing records
                new_records = []
                for record in result.records:
                    clean_record = scraper.clean_record_data(record.data)
                    if clean_record['case_number'] not in existing_case_numbers:
                        new_records.append(clean_record)
                
                _log(f"📊 Found {len(new_records)} new records out of {len(result.records)} total")
                
                if new_records and not test_mode:
                    # Save to database
                    await upsert_records(new_records)
                    
                    # Export to files
                    df = pd.DataFrame(new_records)
                    await export_to_csv(df)
                    export_to_google_sheets(df)
                
                _log(f"✅ Scraping completed successfully")
                return new_records
                
            else:
                _log(f"⚠️ No records found or scraping failed")
                return []
                
    except Exception as e:
        _log(f"❌ Scraping failed: {e}")
        raise

# ─────────────────────────────────────────────────────────────────────────────
# COMMAND LINE INTERFACE
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description="Cobb County GA Lien Index Scraper")
    parser.add_argument("--max-records", type=int, default=MAX_NEW_RECORDS,
                        help="Maximum number of records to scrape")
    parser.add_argument("--test", action="store_true",
                        help="Run in test mode (visible browser, no database writes)")
    parser.add_argument("--from-date", 
                        help="Start date (MM/DD/YYYY)")
    parser.add_argument("--to-date",
                        help="End date (MM/DD/YYYY)")
    parser.add_argument("--instrument-types", nargs="+",
                        help="Instrument types to search for")

    parser.add_argument("--user-id", required=True,
                        help="User ID for database records")
    
    args = parser.parse_args()
    
    global USER_ID
    USER_ID = args.user_id
    
    try:
        records = await run(
            max_new_records=args.max_records,
            test_mode=args.test,
            from_date=args.from_date,
            to_date=args.to_date,
            instrument_types=args.instrument_types
        )
        
        _log(f"🎉 Scraping completed! Found {len(records)} new records")
        
    except Exception as e:
        _log(f"💥 Scraping failed: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    import sys
    if sys.version_info >= (3, 7):
        sys.exit(asyncio.run(main()))
    else:
        loop = asyncio.get_event_loop()
        sys.exit(loop.run_until_complete(main())) 