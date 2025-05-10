# County Records Scrapers

This collection of scripts allows you to scrape and collect various county records including Notice of Default, Lis Pendens, and other legal filings.

## Setup Instructions

### 1. Python Requirements

Install the required Python packages:

```bash
pip install selenium pandas gspread google-auth google-auth-oauthlib google-auth-httplib2 gspread-dataframe
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

### 4. ChromeDriver Setup

Ensure you have Chrome and ChromeDriver installed on your system. The scraper uses Selenium with Chrome.

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

## Troubleshooting

- If you encounter issues with the selectors, check the `screenshots/` directory for debugging screenshots
- For Google Sheets errors, verify your credentials and ensure the spreadsheet is shared with the service account
- For database issues, check the database file permissions

## Customization

- Modify date ranges in the script to collect records from different time periods
- Adjust database schema or Google Sheets worksheet settings as needed 