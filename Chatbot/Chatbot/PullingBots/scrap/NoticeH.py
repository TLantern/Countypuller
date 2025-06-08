import time
import random
import pandas as pd
import os
import json
import sqlite3
import itertools
import re
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Try to import Google Sheets libraries, but continue if not available
GOOGLE_SHEETS_AVAILABLE = False
try:
    import gspread
    from google.oauth2.service_account import Credentials
    from gspread.exceptions import SpreadsheetNotFound, WorksheetNotFound, APIError
    from gspread_dataframe import set_with_dataframe
    GOOGLE_SHEETS_AVAILABLE = True
except ImportError:
    print("⚠️ Google Sheets libraries not installed. Google Sheets integration will be disabled.")
    print("   To enable, install required packages: pip install gspread google-auth gspread-dataframe")

# Load environment variables for configuration
load_dotenv()

# -------------------------------------
# CONFIG: User credentials
USERNAME = "TeniolaTheGreat"
PASSWORD = "StackBread2@"

# Google Sheets Configuration
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME = os.getenv("GSHEET_NAME")
NOTICE_TAB = os.getenv("NOTICE_TAB")  # Default to "Notice Records" if not set

# Database Configuration
DB_PATH = "data/county_records.db"

# Max new records to scrape (similar to LisPendens)
MAX_NEW_RECORDS = 200
# -------------------------------------

# List of user agents to randomize
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.0.0 Safari/537.36"
]

# Ensure directories exist
os.makedirs("screenshots", exist_ok=True)
os.makedirs("data", exist_ok=True)

# Function to normalize file numbers for consistent comparison
def normalize_file_number(file_no):
    """
    Normalize file numbers to a standard format for comparison.
    Example: transforms variations of RP-2025-12345 to RP-2025-12345
    """
    if not file_no:
        return ""
        
    # Clean up the file number
    file_no = file_no.strip().upper()
    
    # Check if it matches the expected format (RP-YYYY-XXXXX)
    rp_pattern = re.compile(r'(RP-\d{4}-\d+)')
    match = rp_pattern.search(file_no)
    
    if match:
        return match.group(1)
    
    return file_no

# Initialize database connection
def init_database():
    """Create the database and tables if they don't exist"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create notice records table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notice_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_no TEXT UNIQUE,
        file_date TEXT,
        instrument_type TEXT,
        volume TEXT,
        page TEXT,
        detail_link TEXT,
        row_text TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    return conn

# Function to get existing file numbers from database
def get_existing_file_numbers(conn):
    """Get all existing file numbers from the database to avoid duplicates"""
    cursor = conn.cursor()
    
    cursor.execute("SELECT file_no FROM notice_records")
    results = cursor.fetchall()
    
    # Normalize all file numbers for consistent comparison
    existing_file_nos = {normalize_file_number(row[0]) for row in results if row[0]}
    
    print(f"Found {len(existing_file_nos)} existing records in database")
    return existing_file_nos

# Function to save records to database
def save_to_database(records, conn, existing_file_nos):
    """Save the records to the SQLite database, skipping duplicates"""
    cursor = conn.cursor()
    
    new_count = 0
    skipped_count = 0
    
    for record in records:
        # Extract fields from the record, with defaults if not present
        file_no = record.get('File No', '')
        if not file_no:
            skipped_count += 1
            continue
            
        # Normalize the file number for comparison
        normalized_file_no = normalize_file_number(file_no)
        
        # Skip if this file number already exists in the database
        if normalized_file_no and normalized_file_no in existing_file_nos:
            print(f"Skipping duplicate file: {file_no} (normalized: {normalized_file_no})")
            skipped_count += 1
            continue
            
        file_date = record.get('File Date', '')
        instrument_type = record.get('Instrument Type', '')
        volume = record.get('Volume', '')
        page = record.get('Page', '')
        detail_link = record.get('Detail Link', '')
        row_text = record.get('Row Text', '')
        
        try:
            # Insert into database
            cursor.execute('''
            INSERT INTO notice_records 
            (file_no, file_date, instrument_type, volume, page, detail_link, row_text)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (file_no, file_date, instrument_type, volume, page, detail_link, row_text))
            
            new_count += 1
            existing_file_nos.add(normalized_file_no)  # Add to existing set to prevent duplicates in batch
            print(f"Added new record: {file_no}")
        except sqlite3.IntegrityError:
            # This could happen if the same file_no was inserted by another process
            skipped_count += 1
            print(f"IntegrityError for file: {file_no} - already exists in database")
    
    conn.commit()
    print(f"✅ Saved {new_count} new records to database (skipped {skipped_count} duplicates)")
    return new_count

# Google Sheets integration - matches LisPendensH.py approach
MAX_ROWS_PER_BATCH = 500

def _push_sheet(df: pd.DataFrame):
    """Update Google Sheets with the dataframe"""
    if not GOOGLE_SHEETS_AVAILABLE:
        print("❌ Google Sheets integration is disabled due to missing libraries.")
        return False
        
    if not GOOGLE_CREDS_FILE or not os.path.exists(GOOGLE_CREDS_FILE):
        print(f"⚠️ Google Sheets credentials file not found at {GOOGLE_CREDS_FILE}")
        return False
        
    if not GSHEET_NAME or not NOTICE_TAB:
        print("⚠️ Spreadsheet name or worksheet name not configured.")
        return False
    
    worksheet_name = NOTICE_TAB
    
    try:
        # Clean up dataframe for Google Sheets
        # Remove any empty rows or NaN values
        df = df.dropna(how='all').reset_index(drop=True)
        df = df.fillna("").astype(str)
        
        # Remove any completely empty rows
        df = df[df.apply(lambda x: x.str.strip().str.len() > 0).any(axis=1)]
        
        # Sort dataframe by file number if it exists
        if 'File No' in df.columns:
            df = df.sort_values('File No', ascending=False).reset_index(drop=True)
            
        print(f"Prepared {len(df)} records for Google Sheets (no empty rows)")
        
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scope)
        client = gspread.authorize(creds)

        # 1) Open the spreadsheet
        try:
            sh = client.open(GSHEET_NAME)
        except SpreadsheetNotFound:
            print(f"❌ Spreadsheet not found: {GSHEET_NAME}")
            return False

        # 2) Get or create the worksheet
        try:
            ws = sh.worksheet(worksheet_name)
            print(f"✔ Found existing worksheet '{worksheet_name}' – clearing contents.")
            ws.clear()
        except WorksheetNotFound:
            print(f"➕ Creating worksheet '{worksheet_name}'.")
            ws = sh.add_worksheet(
                title=worksheet_name,
                rows=len(df) + 10,
                cols=len(df.columns) + 5,
            )

        # 3) Batch-update the data - ensure no spaces between records
        header = [df.columns.tolist()]
        rows = df.values.tolist()
        
        # Remove any completely empty rows from data
        rows = [row for row in rows if any(cell.strip() != "" for cell in row)]
        
        batches = []
        current_batch = []
        
        # Create batches without empty rows
        for row in rows:
            current_batch.append(row)
            if len(current_batch) >= MAX_ROWS_PER_BATCH:
                batches.append(current_batch)
                current_batch = []
                
        # Add any remaining rows to the last batch
        if current_batch:
            batches.append(current_batch)
        
        # Upload each batch
        for i, batch in enumerate(batches):
            payload = header + batch if i == 0 else batch  # Only include header in first batch
            tries, delay = 0, 1
            
            while True:
                try:
                    # For first batch, include the header
                    if i == 0:
                        ws.update(values=payload)
                    else:
                        # For subsequent batches, append to the existing data without headers
                        # This ensures there are no gaps between the batches
                        start_row = 1 + len(header) + sum(len(b) for b in batches[:i])
                        ws.update(f'A{start_row}', values=payload)
                    break
                    
                except APIError as e:
                    code = int(e.response.status_code) if e.response else None
                    if code in (429,) or (code is not None and 500 <= code < 600 and tries < 5):
                        print(f"⚠️ APIError {code}, retrying in {delay}s…")
                        time.sleep(delay)
                        tries += 1
                        delay *= 2
                    else:
                        raise

        print(f"✅ Sheet updated → {GSHEET_NAME}/{worksheet_name} with {len(rows)} records in {len(batches)} batches")
        return True
        
    except Exception as e:
        print(f"❌ Error updating Google Sheet: {e}")
        return False

# Main scraping function with pagination
def scrape_notice_records(driver, wait, existing_file_nos):
    """Scrape notice records from all pages until reaching max new records"""
    all_records = []
    new_records_count = 0
    page_num = 1
    has_next_page = True
    
    while has_next_page and new_records_count < MAX_NEW_RECORDS:
        print(f"📄 Processing page {page_num}...")
        
        try:
            # Get records from current page
            page_records = extract_records_from_page(driver)
            
            if page_records:
                # Check which records are new by comparing normalized file numbers
                new_page_records = []
                for record in page_records:
                    if not record.get('File No'):
                        continue
                    
                    normalized_file_no = normalize_file_number(record.get('File No'))
                    if normalized_file_no and normalized_file_no not in existing_file_nos:
                        new_page_records.append(record)
                        print(f"New record found: {record.get('File No')} (normalized: {normalized_file_no})")
                
                new_records_count += len(new_page_records)
                all_records.extend(page_records)
                
                print(f"✅ Found {len(page_records)} records on page {page_num} ({len(new_page_records)} new). Total new so far: {new_records_count}")
                
                # If we've reached our limit, stop
                if new_records_count >= MAX_NEW_RECORDS:
                    print(f"🎯 Reached target of {MAX_NEW_RECORDS} new records.")
                    break
            else:
                print(f"⚠️ No records found on page {page_num}")
                break
                
            # Check for Next button
            next_button = None
            try:
                # Look for Next button with multiple selectors
                next_button_selectors = [
                    "input[id*='BtnNext'][value='Next']",
                    "input[id*='ContentPlaceHolder1_BtnNext']", 
                    "input[value='Next']",
                    "a[href*='Page$Next']"
                ]
                
                for selector in next_button_selectors:
                    next_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                    if next_buttons:
                        next_button = next_buttons[0]
                        print(f"✅ Found Next button using selector: {selector}")
                        break
            except Exception as e:
                print(f"Error looking for Next button: {e}")
            
            if next_button:
                # Click Next button and wait for page to load
                print("⏭️ Clicking Next button to go to next page...")
                try:
                    driver.execute_script("arguments[0].scrollIntoView();", next_button)
                    next_button.click()
                    # Wait for page to load after clicking Next
                    wait.until(EC.presence_of_element_located((By.XPATH, "//span[contains(@id, 'ContentPlaceHolder1_ListView1')]")))
                    time.sleep(2)  # Small delay to ensure page is loaded
                    page_num += 1
                except Exception as e:
                    print(f"❌ Error clicking Next button: {e}")
                    driver.save_screenshot(f"screenshots/page_navigation_error_{page_num}.png")
                    has_next_page = False
            else:
                print("⚠️ No Next button found - reached last page")
                has_next_page = False
                
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")
            driver.save_screenshot(f"screenshots/page_{page_num}_error.png")
            break
    
    return all_records

# Function to extract records from the current page
def extract_records_from_page(driver):
    """Extract notice records from the current page"""
    records = []
    
    try:
        # Look for rows that contain file numbers
        rows = driver.find_elements(By.XPATH, "//tr[.//span[contains(@id, 'lblFileNo')]]")
        print(f"Found {len(rows)} notice records on current page")
        
        # If no rows found with primary method, try alternative selectors
        if not rows:
            rows = driver.find_elements(By.XPATH, "//table[@id='itemPlaceholderContainer']//tr[td]")
            print(f"Found {len(rows)} notice records with alternative selector")
            
        # Process each row
        for i, row in enumerate(rows):
            try:
                # Extract data from each row
                file_no = ""
                file_date = ""
                instrument_type = ""
                detail_link = ""
                
                # Try to get file number
                try:
                    file_no_elem = row.find_element(By.XPATH, ".//span[contains(@id, 'lblFileNo')]")
                    file_no = file_no_elem.text
                except:
                    pass
                
                # Try to get file date
                try:
                    file_date_elem = row.find_element(By.XPATH, ".//span[contains(@id, 'lblFileDate')]")
                    file_date = file_date_elem.text
                except:
                    pass
                
                # Get the detail link
                try:
                    link_elem = row.find_element(By.XPATH, ".//a[contains(@id, 'lnkdetailtest')]")
                    detail_link = link_elem.get_attribute("href")
                    instrument_type = link_elem.text
                except:
                    pass
                
                # Get any other visible data
                try:
                    volume = row.find_element(By.XPATH, ".//span[contains(@id, 'lblVolNo')]").text
                except:
                    volume = ""
                    
                try:
                    page_no = row.find_element(By.XPATH, ".//span[contains(@id, 'lblPageNo')]").text
                except:
                    page_no = ""
                
                record = {
                    "File No": file_no,
                    "File Date": file_date,
                    "Instrument Type": instrument_type,
                    "Volume": volume, 
                    "Page": page_no,
                    "Detail Link": detail_link
                }
                
                records.append(record)
                
            except Exception as e:
                print(f"Error processing row {i+1}: {e}")
        
        # If no records found, try alternative approach
        if not records:
            # Try to get all links that could be detail links
            detail_links = driver.find_elements(By.XPATH, "//a[contains(@id, 'ContentPlaceHolder1_ListView1') and contains(@id, 'lnkdetailtest')]")
            print(f"Found {len(detail_links)} potential detail links")
            
            for i, link in enumerate(detail_links):
                try:
                    href = link.get_attribute("href")
                    text = link.text
                    
                    # Try to find the parent row to extract more data
                    parent_row = link.find_element(By.XPATH, "./ancestor::tr")
                    
                    # Extract any visible data in the row
                    row_text = parent_row.text
                    row_cells = row_text.split('\n')
                    
                    record = {
                        "Link Index": i+1,
                        "Instrument Type": text,
                        "Detail Link": href,
                        "Row Text": row_text
                    }
                    
                    # Try to parse the row text into fields
                    if len(row_cells) >= 1:
                        record["File No"] = row_cells[0]
                    if len(row_cells) >= 2:
                        record["File Date"] = row_cells[1]
                    
                    records.append(record)
                    
                except Exception as e:
                    print(f"Error processing link {i+1}: {e}")
                
    except Exception as e:
        print(f"Error extracting records from page: {e}")
        
    return records

try:
    # Initialize database
    db_conn = init_database()
    
    # Get existing records to avoid duplicates
    existing_file_nos = get_existing_file_numbers(db_conn)
    
    # Set up Chrome options (disable headless for debugging if needed)
    options = Options()
    # options.add_argument('--headless')  # Uncomment to run headless
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument(f'--user-agent={random.choice(user_agents)}')

    print("Starting Chrome driver...")
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)  # Increased timeout to 20 seconds

    # Calculate date range for the last 2 weeks
    today = datetime.now()
    to_date = today.strftime("%m/%d/%Y")
    from_date = (today - timedelta(days=14)).strftime("%m/%d/%Y")
    print(f"Date range: {from_date} to {to_date}")

    # --------------------- PHASE 1: Scrape Main Listing ---------------------
    main_url = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
    print(f"Navigating to {main_url}...")
    driver.get(main_url)
    time.sleep(random.uniform(3, 6))

    try:
        print("Checking if page loaded correctly...")
        page_title = driver.title
        print(f"Page title: {page_title}")
        
        # Take a screenshot for debugging
        screenshot_path = "screenshots/page_load.png"
        driver.save_screenshot(screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")
        
        # 1. Enter "NOTICE" in the Instrument Type field
        print("Entering 'NOTICE' in instrument field...")
        instrument_input = wait.until(EC.presence_of_element_located(
            (By.ID, "ctl00_ContentPlaceHolder1_txtInstrument")
        ))
        instrument_input.clear()
        instrument_input.send_keys("NOTICE")
        print("✅ Successfully entered NOTICE")

        # 2. Set "Date (From)" to two weeks ago
        print(f"Setting from date to {from_date}...")
        from_input = wait.until(EC.presence_of_element_located(
            (By.ID, "ctl00_ContentPlaceHolder1_txtFrom")
        ))
        from_input.clear()
        from_input.send_keys(from_date)
        print("✅ Successfully set FROM date")

        # 3. Set "Date (To)" to today
        print(f"Setting to date to {to_date}...")
        to_input = wait.until(EC.presence_of_element_located(
            (By.ID, "ctl00_ContentPlaceHolder1_txtTo")
        ))
        to_input.clear()
        to_input.send_keys(to_date)
        print("✅ Successfully set TO date")

        # Take a screenshot before search
        driver.save_screenshot("screenshots/before_search.png")
        print("Screenshot saved before search")

        # 4. Click the "Search" button
        print("Clicking search button...")
        search_btn = wait.until(EC.element_to_be_clickable(
            (By.ID, "ctl00_ContentPlaceHolder1_btnSearch")
        ))
        search_btn.click()
        print("✅ Search button clicked")

        # 5. Wait for the results to load
        print("Waiting for results to load...")
        try:
            # Updated selector based on the screenshots - looking for ListView instead of GridView
            wait.until(EC.presence_of_element_located(
                (By.XPATH, "//span[contains(@id, 'ContentPlaceHolder1_ListView1')]")
            ))
            print(f"✅ Search for NOTICE between {from_date} and {to_date} executed successfully.")
            
            # Take a screenshot after search
            driver.save_screenshot("screenshots/after_search.png")
            print("Screenshot saved after search")
            
        except TimeoutException:
            print("⚠️ Timed out waiting for results. Taking screenshot...")
            driver.save_screenshot("screenshots/timeout_error.png")
            print("Checking for error messages on page...")
            
            # Check for error messages that might be displayed
            try:
                error_msgs = driver.find_elements(By.XPATH, "//*[contains(@class, 'error') or contains(@class, 'alert')]")
                for msg in error_msgs:
                    print(f"Error message found: {msg.text}")
            except:
                print("No specific error messages found on page")
                
        # 6. Scrape records with pagination
        all_records = scrape_notice_records(driver, wait, existing_file_nos)
        print(f"🔍 Scraping complete: {len(all_records)} records found")
        
        # -------------------------------------
        # PHASE 2: Save Data to Multiple Destinations
        # -------------------------------------
        if all_records:
            # 1. Save to CSV
            df = pd.DataFrame(all_records)
            csv_filename = f'data/harris_notice_links_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            df.to_csv(csv_filename, index=False)
            print(f"✅ Saved {len(all_records)} notice records to CSV: {csv_filename}")
            
            # 2. Save to database (filtering out duplicates)
            new_records_count = save_to_database(all_records, db_conn, existing_file_nos)
            
            # 3. Save to Google Sheets using the updated approach
            if GOOGLE_SHEETS_AVAILABLE:
                _push_sheet(df)
            
        else:
            print("❌ No records found to save.")

    except Exception as e:
        print(f"❌ Error during scraping: {e}")
        driver.save_screenshot("screenshots/exception_error.png")
        print("Screenshot saved at error point")

except Exception as e:
    print(f"Critical error in script: {e}")

finally:
    # Close database connection if it was opened
    try:
        if 'db_conn' in locals():
            db_conn.close()
            print("Database connection closed")
    except:
        pass
        
    # Close the browser
    try:
        driver.quit()
        print("Browser closed successfully")
    except:
        print("Failed to close browser properly")
