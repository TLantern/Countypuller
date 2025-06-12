"""
CSV to Cobb GA Filing Importer

This script reads the "Book 1(Sheet1).csv" file and imports the data into the 
cobb_ga_filing table after a 10-second delay (simulating clicking "pull records").

CSV columns: Street Address, Mortgage Amount, Tax Deed dated
Database fields: case_number, document_type, filing_date, debtor_name, claimant_name, etc.
"""

import pandas as pd
import asyncio
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv
import uuid
import re

# Load environment variables
load_dotenv()
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required")

# Configuration
CSV_FILE_PATH = Path(__file__).parent / "Book 1(Sheet1).csv"
USER_ID = "986a93f6-5273-412f-a52f-ef7dcee1006c"
DELAY_SECONDS = 10

def clean_text(text):
    """Clean and normalize text data"""
    if pd.isna(text) or text == "N/A":
        return ""
    return str(text).strip().replace('\n', ' ').replace('\r', '')

def parse_date(date_str):
    """Parse various date formats from the CSV"""
    if pd.isna(date_str) or not date_str or date_str == "N/A":
        return None
    
    date_str = clean_text(date_str)
    
    # Try various date formats
    formats = [
        "%d-%b-%y",      # 23-Jan-17
        "%B %d, %Y",     # May 7, 2024
        "%Y-%m-%d",      # 2024-05-07
        "%m/%d/%Y",      # 05/07/2024
        "%d/%m/%Y"       # 07/05/2024
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    # If no format matches, return None
    print(f"Warning: Could not parse date '{date_str}'")
    return None

def generate_case_number(address, index):
    """Generate a unique case number from address and index"""
    # Extract numbers and letters from address
    clean_addr = re.sub(r'[^\w\s]', '', address)
    words = clean_addr.split()[:3]  # Take first 3 words
    case_base = ''.join(words).upper()[:10]  # Max 10 chars
    return f"COBB-{case_base}-{index:04d}"

async def insert_csv_data():
    """Read CSV and insert data into cobb_ga_filing table"""
    try:
        print("🔄 Starting CSV import process...")
        print(f"📂 Reading CSV file: {CSV_FILE_PATH}")
        
        # Check if CSV file exists
        if not CSV_FILE_PATH.exists():
            raise FileNotFoundError(f"CSV file not found: {CSV_FILE_PATH}")
        
        # Read the CSV file
        df = pd.read_csv(CSV_FILE_PATH)
        print(f"📊 Found {len(df)} records in CSV")
        
        # Wait 10 seconds (simulating "pull records" delay)
        print(f"⏱️  Waiting {DELAY_SECONDS} seconds before processing records...")
        await asyncio.sleep(DELAY_SECONDS)
        
        # Prepare records for database insertion
        records = []
        current_time = datetime.now()
        
        for index, row in df.iterrows():
            # Map CSV columns to database fields
            street_address = clean_text(row.get('Street Address', ''))
            mortgage_amount = clean_text(row.get('Mortgage Amount', ''))
            tax_deed_date = parse_date(row.get('Tax Deed dated', ''))
            
            # Generate case number from address
            case_number = generate_case_number(street_address, index + 1)
            
            record = {
                'id': str(uuid.uuid4()),
                'case_number': case_number,
                'document_type': 'Tax Deed',  # Default document type
                'filing_date': tax_deed_date,
                'debtor_name': '',  # Not available in CSV
                'claimant_name': mortgage_amount,  # Store mortgage amount as claimant name for now
                'county': 'Cobb GA',
                'book_page': '',  # Not available in CSV
                'document_link': '',  # Not available in CSV
                'state': 'GA',
                'created_at': current_time,
                'updated_at': current_time,
                'is_new': True,
                'userId': USER_ID,
                'parsed_address': street_address,  # Store street address in parsed_address field
                'ocr_text_file': '',
                'screenshot_path': '',
                'source_url': f'CSV_IMPORT_{current_time.strftime("%Y%m%d_%H%M%S")}'
            }
            records.append(record)
        
        # Insert records into database
        if records:
            print(f"💾 Inserting {len(records)} records into database...")
            await insert_records_to_db(records)
            print("✅ CSV import completed successfully!")
        else:
            print("⚠️  No valid records found to import")
            
    except Exception as e:
        print(f"❌ Error during CSV import: {e}")
        raise

async def insert_records_to_db(records):
    """Insert records into the cobb_ga_filing table"""
    
    INSERT_SQL = """
    INSERT INTO cobb_ga_filing
      (id, case_number, document_type, filing_date, debtor_name, claimant_name, 
       county, book_page, document_link, state, created_at, updated_at, is_new, 
       "userId", parsed_address, ocr_text_file, screenshot_path, source_url)
    VALUES
      (:id, :case_number, :document_type, :filing_date, :debtor_name, :claimant_name,
       :county, :book_page, :document_link, :state, :created_at, :updated_at, :is_new, 
       :userId, :parsed_address, :ocr_text_file, :screenshot_path, :source_url)
    ON CONFLICT (case_number, "userId") DO UPDATE
    SET
      document_type = EXCLUDED.document_type,
      filing_date = EXCLUDED.filing_date,
      debtor_name = EXCLUDED.debtor_name,
      claimant_name = EXCLUDED.claimant_name,
      county = EXCLUDED.county,
      book_page = EXCLUDED.book_page,
      document_link = EXCLUDED.document_link,
      updated_at = EXCLUDED.updated_at,
      is_new = EXCLUDED.is_new,
      parsed_address = EXCLUDED.parsed_address,
      ocr_text_file = EXCLUDED.ocr_text_file,
      screenshot_path = EXCLUDED.screenshot_path,
      source_url = EXCLUDED.source_url;
    """
    
    try:
        async with create_async_engine(DB_URL).begin() as conn:
            await conn.execute(text(INSERT_SQL), records)
        print(f"✅ Successfully inserted {len(records)} records")
        
    except Exception as e:
        print(f"❌ Database insertion failed: {e}")
        raise

def main():
    """Main function to run the CSV import"""
    print("🚀 Starting Cobb GA CSV Import Tool")
    print(f"📝 Target User ID: {USER_ID}")
    print(f"📅 Import timestamp: {datetime.now()}")
    
    # Run the async import function
    asyncio.run(insert_csv_data())

if __name__ == "__main__":
    main() 