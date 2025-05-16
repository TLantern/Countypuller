# County Records Scrapers

This collection of scripts allows you to scrape and collect various county records including Notice of Default, Lis Pendens, Foreclosures, and other legal filings.

## Setup Instructions

### 1. Python Requirements

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 2. Database Setup

The scrapers automatically create and use an SQLite database located at `data/county_records.db`. No additional setup is required for the database.

### 3. Google Sheets Integration

To enable Google Sheets integration:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Sheets API and Google Drive API
4. Create a service account with permission to access Google Sheets
5. Download the JSON credentials file
6. Rename the credentials file to `google_credentials.json` and place it in the `data/` directory
7. Share your Google Sheet with the service account email address (found in the credentials file)
8. Update the `SPREADSHEET_ID` in the script to match your Google Sheet ID (found in the URL of your sheet)

A template for the credentials file is provided at `data/google_credentials_template.json`.

### 4. Optional Dependencies for Advanced Features

The Foreclosure scraper has enhanced address extraction capabilities with these optional dependencies:

- **Tesseract OCR**: For text extraction from images and PDFs
  - Windows: Download and install from [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki)
  - Linux: `sudo apt-get install tesseract-ocr`
  - macOS: `brew install tesseract`

- **Poppler**: For PDF to image conversion (used with Tesseract)
  - Windows: Download from [poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
  - Linux: `sudo apt-get install poppler-utils`
  - macOS: `brew install poppler`

- **PyMuPDF**: Alternative PDF processing (automatic fallback when Poppler isn't available)
  - Installed automatically with requirements.txt

### 5. Playwright Browser Setup

Foreclosure scraper uses Playwright for browser automation:

```bash
python -m playwright install chromium
```

## Running the Scrapers

### Notice of Default Scraper

```bash
python NoticeH.py
```

This will:
1. Search for NOTICE records from the last two weeks
2. Extract basic information and links
3. Save the data to:
   - CSV file (`data/harris_notice_links.csv`)
   - SQLite database
   - Google Sheets (if credentials are set up)

### Foreclosure Scraper

```bash
python ForeclosureH.py [options]
```

Command-line options:
- `--year YEAR`: Specify the year to scrape (defaults to current year)
- `--month MONTH`: Specify the month to scrape (defaults to latest available)
- `--limit LIMIT`: Limit the number of records to process (useful for testing)
- `--headless`: Run in headless mode without showing the browser window

Examples:
```bash
# Scrape current year/month with browser visible (for debugging)
python ForeclosureH.py

# Scrape January 2023 in headless mode
python ForeclosureH.py --year 2023 --month 1 --headless

# Process only 10 records for testing
python ForeclosureH.py --limit 10
```

The foreclosure scraper:
1. Searches for foreclosure records by year and month
2. Downloads PDF documents and extracts property addresses using OCR
3. Uses multiple fallback methods for text extraction (direct PDF text, Tesseract OCR, screenshots)
4. Filters out auction locations to avoid capturing them as property addresses
5. Saves records with valid addresses to:
   - CSV file (`data/harris_foreclosures_[timestamp].csv`)
   - SQL database
   - Google Sheets (if configured)
6. Provides detailed statistics about the scraping process

## Troubleshooting

- If you encounter issues with the selectors, check the `screenshots/` directory for debugging screenshots
- For Google Sheets errors, verify your credentials and ensure the spreadsheet is shared with the service account
- For database issues, check the database file permissions
- For OCR/PDF processing issues, ensure Tesseract and/or Poppler are properly installed and in your PATH

## Customization

- Modify date ranges in the script to collect records from different time periods
- Adjust database schema or Google Sheets worksheet settings as needed 