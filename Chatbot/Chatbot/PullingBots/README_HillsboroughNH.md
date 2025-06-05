# Hillsborough County NH Registry Scraper

This scraper extracts registry of deeds records from Hillsborough County, New Hampshire using the AVA/FIDLAR system.

## Overview

The Hillsborough County NH scraper targets the official registry of deeds website at `https://ava.fidlar.com/NHHillsborough/AvaWeb/#/search` and extracts records for various document types including:

- Deeds
- Mortgages  
- Lis Pendens
- Liens
- Other recorded instruments

## Features

- **Automated Search**: Automatically searches for records within a date range (default: last 2 weeks)
- **Data Extraction**: Extracts key fields including document number, recorded date, parties, property information
- **Database Integration**: Stores records in PostgreSQL database with duplicate detection
- **CSV Export**: Exports results to timestamped CSV files
- **Google Sheets Integration**: Optional push to Google Sheets
- **Screenshot Debugging**: Captures screenshots for troubleshooting
- **Error Handling**: Robust error handling with detailed logging
- **🎯 Targeted Search**: Searches for "LIEN" documents from the last 7 days
- **📊 Data Extraction**: Extracts document numbers, dates, party names, and legal descriptions
- **🔍 OCR Integration**: Extracts property addresses from documents using optical character recognition
- **🧪 Test Mode**: Safe testing without database operations
- **🔄 Duplicate Prevention**: Avoids re-processing existing records

## Data Model

The scraper extracts the following fields for each record:

| Field | Description |
|-------|-------------|
| `document_number` | Unique document identifier |
| `document_url` | Link to document (if available) |
| `recorded_date` | Date the document was recorded |
| `instrument_type` | Type of document (DEED, MORTGAGE, etc.) |
| `grantor` | Party granting/selling property |
| `grantee` | Party receiving/buying property |
| `property_address` | Property address (if available) |
| `book_page` | Book and page reference |
| `consideration` | Sale price/consideration amount |
| `legal_description` | Legal property description |

## Prerequisites

### Dependencies
All required packages are listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

### Database Setup
You'll need a PostgreSQL database with a table named `hillsborough_nh_filing`. The required schema:

```sql
CREATE TABLE hillsborough_nh_filing (
    id SERIAL PRIMARY KEY,
    document_number VARCHAR UNIQUE NOT NULL,
    document_url VARCHAR,
    recorded_date DATE,
    instrument_type VARCHAR,
    grantor VARCHAR,
    grantee VARCHAR,
    property_address TEXT,
    book_page VARCHAR,
    consideration VARCHAR,
    legal_description TEXT,
    county VARCHAR DEFAULT 'Hillsborough NH',
    created_at TIMESTAMP DEFAULT NOW(),
    is_new BOOLEAN DEFAULT true,
    doc_type VARCHAR DEFAULT 'registry_deed',
    "userId" INTEGER
);
```

### Environment Variables
Create a `.env` file with the following variables:

```env
# Required
DB_URL=postgresql+asyncpg://username:password@host:port/database

# Optional - Google Sheets Integration
GOOGLE_CREDS=/path/to/google-service-account.json
GSHEET_NAME=Your_Spreadsheet_Name
HILLSBOROUGH_TAB=HillsboroughNH

# Optional - Custom settings
HILLSBOROUGH_TAB=HillsboroughNH  # Default tab name
```

## Installation

### 1. Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. OCR Setup (Required for Address Extraction)

For Windows users, you need to install Tesseract OCR separately:

1. **Download Tesseract installer** from: https://github.com/UB-Mannheim/tesseract/wiki
2. **Choose the appropriate version** (32-bit or 64-bit)
3. **Run the installer** and follow the setup wizard
4. **Default installation path** is usually: `C:\Program Files\Tesseract-OCR\tesseract.exe`

The scraper will automatically detect Tesseract at common installation locations:
- `C:\Program Files\Tesseract-OCR\tesseract.exe`
- `C:\Program Files (x86)\Tesseract-OCR\tesseract.exe`
- User's local AppData directory

**For Mac/Linux users:**
```bash
# macOS
brew install tesseract

# Ubuntu/Debian
sudo apt-get install tesseract-ocr
```

### 3. Environment Variables

Create a `.env` file with the following variables:

```env
# Database
DB_URL=postgresql+asyncpg://username:password@host:port/database

# Google Sheets (optional)
GOOGLE_CREDS=/path/to/google/credentials.json
GSHEET_NAME=Your_Google_Sheet_Name
HILLSBOROUGH_TAB=HillsboroughNH
```

## Usage

### Basic Usage
```bash
python HillsboroughNH.py --user-id 1
```

### With Custom Parameters
```bash
# Limit to 50 records
python HillsboroughNH.py --user-id 1 --max-records 50

# Run in headless mode (no browser window)
python HillsboroughNH.py --user-id 1 --headless

# Combined options
python HillsboroughNH.py --user-id 1 --max-records 25 --headless
```

### Command Line Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--user-id` | Yes | - | User ID for database records |
| `--max-records` | No | 100 | Maximum new records to scrape |
| `--headless` | No | False | Run browser in headless mode |

### OCR Address Extraction

```bash
# Enable address extraction (slower but complete)
python HillsboroughNH.py --test-mode --extract-addresses --max-records 3

# Disable address extraction (faster)
python HillsboroughNH.py --test-mode --no-extract-addresses --max-records 10
```

### Command Line Options

- `--max-records N`: Maximum number of records to process (default: 100)
- `--user-id ID`: User ID for database records (required for production)
- `--test-mode`: Run without database operations (for testing)
- `--extract-addresses`: Enable OCR address extraction (slower)
- `--no-extract-addresses`: Disable address extraction (faster)
- `--headless`: Run browser in headless mode

## Configuration

### Search Parameters
The scraper is configured to search for records from the last 2 weeks by default. You can modify this in the `_apply_search_filters()` function:

```python
# Current: last 2 weeks
two_weeks_ago = today - timedelta(days=14)

# Example: last 30 days
thirty_days_ago = today - timedelta(days=30)
```

### Output Directory
CSV exports are saved to the `data/` directory by default. You can change this by modifying:

```python
EXPORT_DIR = Path("data")
```

## System Architecture

### Main Components

1. **Navigation & Loading**: Handles the Angular-based AVA application loading
2. **Search Filtering**: Applies date range and document type filters
3. **Data Extraction**: Parses search results and extracts record data
4. **Data Processing**: Cleans and standardizes extracted data
5. **Storage**: Saves to database with duplicate detection
6. **Export**: Creates CSV files and optionally uploads to Google Sheets

### Key Functions

- `_wait_for_page_load()`: Waits for Angular app to fully load
- `_apply_search_filters()`: Sets search criteria and date ranges
- `_execute_search()`: Triggers the search
- `_extract_records_from_results()`: Parses results table
- `upsert_records()`: Saves to database with conflict resolution

## Error Handling & Debugging

### Screenshots
The scraper automatically captures screenshots for debugging:
- `debug_hillsborough_initial.png`: Initial page load
- `debug_hillsborough_results.png`: Search results
- `debug_hillsborough_error.png`: Error state (if error occurs)

### OCR Debug
When OCR is enabled, files are saved to `ocr_debug/`:
- `document_[NUMBER].png` - Original document screenshot
- `document_[NUMBER]_processed.png` - Preprocessed image for OCR

### Logging
All operations are logged with timestamps. Look for:
- ✅ Success indicators
- ❌ Error indicators  
- ⚠️ Warning messages

### Common Issues

1. **Page Loading Issues**: The AVA system uses Angular, which can take time to load. Increase timeout if needed.

2. **Selector Changes**: If the website structure changes, update the selector arrays in:
   - `_apply_search_filters()`
   - `_execute_search()`
   - `_extract_records_from_results()`

3. **Database Connection**: Ensure your `DB_URL` is correct and the database is accessible.

## Customization

### Adding Document Type Filters
To filter for specific document types, modify the `_apply_search_filters()` function:

```python
# Example: Filter for only deeds
if await page.locator(selector).count():
    await page.select_option(selector, "DEED")
```

### Adjusting Extraction Logic
The data extraction logic is modular. To modify field extraction, update the `record_data` dictionary in `_extract_records_from_results()`.

### Pagination Support
If you need to handle pagination, add logic after the initial extraction:

```python
# Check for next page button
next_button = page.locator("button:has-text('Next')")
if await next_button.count():
    await next_button.click()
    # Continue extraction...
```

## Integration with Other Systems

### Scheduled Execution
For automated runs, consider using cron jobs or task schedulers:

```bash
# Example cron job - run daily at 6 AM
0 6 * * * /path/to/python /path/to/HillsboroughNH.py --user-id 1 --headless
```

### API Integration
The scraper can be integrated into larger systems by importing and calling the `run()` function:

```python
from HillsboroughNH import run

# Run programmatically
await run(max_new_records=50)
```

## Maintenance

### Regular Updates
- Monitor the AVA website for structural changes
- Update selectors if the interface changes
- Review and adjust date ranges as needed
- Check database performance and optimize as needed

### Performance Optimization
- Use headless mode for production runs
- Adjust `max_records` based on system capacity
- Consider running during off-peak hours
- Monitor memory usage for large result sets

## Support

For issues or questions:
1. Check the debug screenshots
2. Review the log output
3. Verify database connectivity
4. Test with a small `--max-records` value first
5. Try running without `--headless` to see browser behavior

## Version History

- **v1.0**: Initial implementation with basic search and extraction
- Targets AVA/FIDLAR system for Hillsborough County NH
- Supports date range filtering and document type extraction
- Includes database integration and CSV export functionality 