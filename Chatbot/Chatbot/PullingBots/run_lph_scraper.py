"""
Enhanced Harris County Lis Pendens Scraper
Saves data to JSON, CSV, and database with comprehensive features
"""

import asyncio
import os
import sys
from datetime import date, timedelta, datetime
from pathlib import Path
from aspnet_scraper import AspNetSearchFormScraper
from lph_config import lph_config

# Configure Tesseract path for OCR functionality
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()  # Load .env file from current directory
    print("🔧 Loaded .env file")
except ImportError:
    print("⚠️ python-dotenv not installed, using system environment variables only")
except Exception as e:
    print(f"⚠️ Could not load .env file: {e}")

# Examples: 
# python run_lph_scraper.py                          # Last 7 days (default)
# python run_lph_scraper.py 2024-06-01 2024-06-15   # Custom range (YYYY-MM-DD)
# python run_lph_scraper.py 06/01/2024 06/15/2024   # Custom range (MM/DD/YYYY)

def setup_environment():
    """Setup and validate environment variables"""
    print("🔧 Environment Setup:")
    
    # Check for required environment variables
    required_vars = {
        'LP_USERNAME': 'Harris County login username',
        'LP_PASSWORD': 'Harris County login password', 
    }
    
    optional_vars = {
        'DATABASE_URL': 'Database connection string (optional)',
        'USER_ID': 'User ID for database records (optional)'
    }
    
    missing_required = []
    missing_optional = []
    
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_required.append(f"  {var}: {description}")
    
    for var, description in optional_vars.items():
        if not os.getenv(var):
            missing_optional.append(f"  {var}: {description}")
    
    if missing_required:
        print("❌ Missing REQUIRED environment variables:")
        for var in missing_required:
            print(var)
        print("\n💡 Set these variables before running:")
        print("   export LP_USERNAME='your_username'")
        print("   export LP_PASSWORD='your_password'")
        return False
    else:
        print("✅ All required environment variables are set")
    
    if missing_optional:
        print("⚠️ Missing OPTIONAL environment variables:")
        for var in missing_optional:
            print(var)
        print("💡 For full functionality, also set:")
        print("   export DATABASE_URL='postgresql+asyncpg://user:pass@host/db'")
        print("   export USER_ID='1'")
    else:
        print("✅ All environment variables are set")
    
    return True

def get_task_params():
    """Get search parameters from command line or defaults"""
    if len(sys.argv) >= 3:
        date_from = sys.argv[1]  # Format: MM/DD/YYYY or YYYY-MM-DD
        date_to = sys.argv[2]    # Format: MM/DD/YYYY or YYYY-MM-DD
        
        # Convert to MM/DD/YYYY format for Harris County system
        if '-' in date_from:  # Convert YYYY-MM-DD to MM/DD/YYYY
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
            date_from = dt_from.strftime('%m/%d/%Y')
        if '-' in date_to:    # Convert YYYY-MM-DD to MM/DD/YYYY
            dt_to = datetime.strptime(date_to, '%Y-%m-%d')
            date_to = dt_to.strftime('%m/%d/%Y')
    else:
        # Default: Last 7 days (smaller range for testing)
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        date_from = seven_days_ago.strftime('%m/%d/%Y')  # MM/DD/YYYY format
        date_to = today.strftime('%m/%d/%Y')              # MM/DD/YYYY format
    
    return {
        'date_range': {'from': date_from, 'to': date_to},
        'search_terms': ['L/P'],  # Instrument type for Lis Pendens
        'max_records': 10  # Hardcoded to 10 records
    }

async def run_harris_scraper():
    """Enhanced Harris County scraper with comprehensive features"""
    
    print("🚀 Starting Enhanced Harris County Lis Pendens Scraper")
    print(f"📊 Limited to 10 records per run")
    
    # Get search parameters
    task_params = get_task_params()
    print(f"📅 Searching from {task_params['date_range']['from']} to {task_params['date_range']['to']}")
    
    try:
        # Create scraper instance and run
        async with AspNetSearchFormScraper(lph_config) as scraper:
            print("🔍 Starting data extraction...")
            result = await scraper.scrape(task_params)
            
            if result.success:
                print(f"✅ Scraping completed successfully!")
                print(f"📊 Total records found: {len(result.records)}")
                print(f"📄 Pages scraped: {result.total_pages_scraped}")
                
                # Data is automatically saved by the enhanced scraper to:
                # - data/harris_lis_pendens_YYYYMMDD_HHMMSS.json
                # - data/harris_lis_pendens_YYYYMMDD_HHMMSS.csv  
                # - Database (if configured)
                print(f"💾 Data automatically saved to 'data/' directory")
                
                # Show sample of extracted data
                if result.records:
                    print(f"\n📋 Sample record:")
                    sample = result.records[0].data
                    for key, value in sample.items():
                        print(f"  {key}: {value}")
                        
                    # Show summary of fields extracted
                    print(f"\n📊 Extraction Summary:")
                    film_code_count = sum(1 for r in result.records if r.data.get('film_code_url'))
                    address_count = sum(1 for r in result.records if r.data.get('property_address'))
                    print(f"  Records with film code URLs: {film_code_count}/{len(result.records)}")
                    print(f"  Records with property addresses: {address_count}/{len(result.records)}")
                    
                    if film_code_count < len(result.records):
                        print(f"  ⚠️ {len(result.records) - film_code_count} records missing film code URLs")
                    if address_count < len(result.records):
                        print(f"  ⚠️ {len(result.records) - address_count} records missing property addresses")
                        
                else:
                    print("⚠️ No records found - check date range or search criteria")
                    
            else:
                print(f"❌ Scraping failed: {result.error_message}")
                return False
                
        return True
        
    except Exception as e:
        print(f"💥 Error running scraper: {e}")
        import traceback
        traceback.print_exc()
        return False

def print_usage():
    """Print usage instructions"""
    print("\n📖 Usage Instructions:")
    print("="*50)
    print("Basic usage (last 7 days):")
    print("  python run_lph_scraper.py")
    print()
    print("Custom date range:")
    print("  python run_lph_scraper.py 2024-01-01 2024-01-07")
    print("  python run_lph_scraper.py 01/01/2024 01/07/2024")
    print()
    print("📂 Output files saved to 'data/' directory:")
    print("  - harris_lis_pendens_YYYYMMDD_HHMMSS.json")
    print("  - harris_lis_pendens_YYYYMMDD_HHMMSS.csv")
    print()
    print("🔧 Required environment variables:")
    print("  LP_USERNAME  = Your Harris County username")
    print("  LP_PASSWORD  = Your Harris County password")
    print()
    print("🔧 Optional environment variables:")
    print("  DATABASE_URL = Database connection string")
    print("  USER_ID      = User ID for database records")
    print("="*50)

async def main():
    """Main execution function"""
    print_usage()
    print()
    
    # Setup and validate environment
    if not setup_environment():
        print("\n❌ Environment setup failed. Please configure required variables.")
        return
    
    print()
    
    # Run the scraper
    success = await run_harris_scraper()
    
    if success:
        print(f"\n🎉 Scraping completed successfully!")
        print(f"📁 Check the 'data/' directory for output files")
    else:
        print(f"\n💥 Scraping failed. Check error messages above.")

if __name__ == "__main__":
    asyncio.run(main()) 