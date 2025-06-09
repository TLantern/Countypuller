import asyncio
import os
from datetime import datetime, date, timedelta
import time
import itertools
from pathlib import Path
import pandas as pd
from typing import Optional, TypedDict, List, Dict, Any
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Frame
import argparse
import re
import json
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv
import gspread
from gspread.exceptions import (
    SpreadsheetNotFound,
    WorksheetNotFound,
    APIError,
)
from google.oauth2.service_account import Credentials
from dateutil.relativedelta import relativedelta
import pytesseract
from PIL import Image
import cv2
import numpy as np
import pyap  # For address parsing
import pygetwindow as gw

# ─────────────────────────────────────────────────────────────────────────────
# DATA MODEL
# ─────────────────────────────────────────────────────────────────────────────
class HillsboroughRecord(TypedDict):
    document_number: str
    document_url: Optional[str]
    recorded_date: str
    instrument_type: str
    grantor: str
    grantee: str
    property_address: str
    book_page: str
    consideration: Optional[str]
    legal_description: Optional[str]

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL = "https://ava.fidlar.com/NHHillsborough/AvaWeb/#/search"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
OCR_DEBUG_DIR = Path("ocr_debug"); OCR_DEBUG_DIR.mkdir(exist_ok=True)
HEADLESS = False
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
MAX_NEW_RECORDS = 10   # Maximum number of new records to scrape per run (default)
USER_ID = None  # Will be set from command line argument
COUNTY_NAME = "Hillsborough NH"
EXTRACT_ADDRESSES = True  # Enable/disable address extraction via OCR
DOWNLOAD_ORIGINAL_IMAGES = True  # Enable/disable downloading original document images (better quality)

# Environment variables
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME = os.getenv("GSHEET_NAME")
HILLSBOROUGH_TAB = os.getenv("HILLSBOROUGH_TAB", "HillsboroughNH")
EXPORT_DIR = (Path(__file__).parent / "data").resolve()
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required for database connection")

# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────
engine = create_async_engine(DB_URL, echo=False)
INSERT_SQL = """
INSERT INTO hillsborough_nh_filing
  (id,
   document_number,
   document_url,
   recorded_date,
   instrument_type,
   grantor,
   grantee,
   property_address,
   book_page,
   consideration,
   legal_description,
   county,
   state,
   filing_date,
   amount,
   parties,
   location,
   status,
   created_at,
   updated_at,
   is_new,
   doc_type,
   "userId")
VALUES
  (gen_random_uuid(),
   :document_number,
   :document_url,
   :recorded_date,
   :instrument_type,
   :grantor,
   :grantee,
   :property_address,
   :book_page,
   :consideration,
   :legal_description,
   :county,
   :state,
   :filing_date,
   :amount,
   :parties,
   :location,
   :status,
   :created_at,
   :updated_at,
   :is_new,
   :doc_type,
   :userId)
ON CONFLICT (document_number) DO UPDATE
SET
  document_url       = EXCLUDED.document_url,
  recorded_date      = EXCLUDED.recorded_date,
  instrument_type    = EXCLUDED.instrument_type,
  grantor           = EXCLUDED.grantor,
  grantee           = EXCLUDED.grantee,
  property_address  = EXCLUDED.property_address,
  book_page         = EXCLUDED.book_page,
  consideration     = EXCLUDED.consideration,
  legal_description = EXCLUDED.legal_description,
  county            = EXCLUDED.county,
  state             = EXCLUDED.state,
  filing_date       = EXCLUDED.filing_date,
  amount            = EXCLUDED.amount,
  parties           = EXCLUDED.parties,
  location          = EXCLUDED.location,
  status            = EXCLUDED.status,
  updated_at        = EXCLUDED.updated_at,
  is_new            = EXCLUDED.is_new,
  doc_type          = EXCLUDED.doc_type,
  "userId"          = EXCLUDED."userId";
"""

# ─────────────────────────────────────────────────────────────────────────────
# LOG + SAFE WRAPPER
# ─────────────────────────────────────────────────────────────────────────────
def _log(msg: str):
    try:
        print(f"[{datetime.now():%H:%M:%S}] {msg}")
    except UnicodeEncodeError:
        # Fallback for Windows console encoding issues
        safe_msg = msg.encode('ascii', 'replace').decode('ascii')
        print(f"[{datetime.now():%H:%M:%S}] {safe_msg}")

async def _safe(desc: str, coro):
    try:
        return await coro
    except Exception as e:
        _log(f"❌ {desc} → {e}")
        raise

# ─────────────────────────────────────────────────────────────────────────────
# DISCLAIMER AND NAVIGATION
# ─────────────────────────────────────────────────────────────────────────────
async def _maybe_accept_disclaimer(page: Page):
    """Accept any disclaimer or agreement pop-ups"""
    disclaimer_selectors = [
        "button:has-text('Accept')",
        "button:has-text('I Accept')",
        "button:has-text('Accept Agreement')",
        "input[value='Accept']",
        "input[value='I Accept']",
        r"text=/^Accept$/i",
        r"text=/^I\s*Accept$/i",
        r"text=/Accept\s*Agreement/i",
    ]
    
    for sel in disclaimer_selectors:
        try:
            if await page.locator(sel).count():
                _log(f"Accepting disclaimer via {sel}")
                await page.locator(sel).first.click()
                await page.wait_for_load_state("networkidle", timeout=10000)
                return True
        except Exception as e:
            _log(f"Warning: Could not use disclaimer selector {sel}: {e}")
    
    return False

async def _wait_for_page_load(page: Page, timeout: int = 30000):
    """Wait for the AVA application to fully load"""
    try:
        # Wait for the Angular app to load
        await page.wait_for_load_state("networkidle", timeout=min(timeout, 15000))  # Cap at 15 seconds
        
        # Look for key elements that indicate the search form is ready
        search_indicators = [
            "[data-ng-model]",  # Angular model bindings
            "input[type='text']",  # Basic input fields
            "select",  # Dropdown selectors
            ".form-control",  # Bootstrap form controls
        ]
        
        for indicator in search_indicators:
            try:
                await page.wait_for_selector(indicator, timeout=3000)  # Reduced from 5000
                _log(f"Page loaded - found {indicator}")
                return True
            except:
                continue
        
        _log("Warning: Could not detect specific search form elements")
        return False
        
    except Exception as e:
        _log(f"Error waiting for page load: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH AND FILTERING
# ─────────────────────────────────────────────────────────────────────────────
async def _apply_search_filters(page: Page) -> bool:
    """
    Apply search filters to find recent records
    - Last 7 days for date range
    - "liens" for document type
    """
    try:
        # Calculate date range (last 14 days instead of 7 to get more records)
        today = date.today()
        fourteen_days_ago = today - timedelta(days=14)
        
        _log(f"Setting date range: {fourteen_days_ago} to {today}")
        
        # Wait for the form elements to be ready
        await page.wait_for_timeout(1000)  # Reduced from 2000
        
        # Start Date - using the specific selector from the HTML
        start_date_selector = "input[id='mat-input-0']"
        try:
            await page.wait_for_selector(start_date_selector, timeout=5000)  # Reduced from 10000
            await page.fill(start_date_selector, fourteen_days_ago.strftime("%m/%d/%Y"))
            _log(f"✅ Set start date to {fourteen_days_ago.strftime('%m/%d/%Y')}")
            await page.wait_for_timeout(200)  # Reduced from 500
        except Exception as e:
            _log(f"❌ Error setting start date: {e}")
            return False
        
        # End Date - using the specific selector from the HTML  
        end_date_selector = "input[id='mat-input-1']"
        try:
            await page.fill(end_date_selector, today.strftime("%m/%d/%Y"))
            _log(f"✅ Set end date to {today.strftime('%m/%d/%Y')}")
            await page.wait_for_timeout(200)  # Reduced from 500
        except Exception as e:
            _log(f"❌ Error setting end date: {e}")
            return False
        
        # Document Type - using the specific selector for the autocomplete field
        doc_type_selector = "input[id='mat-input-2']"
        try:
            await page.wait_for_selector(doc_type_selector, timeout=5000)  # Reduced from 10000
            
            # Click on the field first to focus it and open dropdown
            await page.click(doc_type_selector)
            await page.wait_for_timeout(300)  # Reduced from 500
            
            # Clear any existing content and type "lien" to trigger autocomplete
            await page.fill(doc_type_selector, "")
            await page.type(doc_type_selector, "lien", delay=50)  # Reduced delay from 100
            _log("✅ Typed 'lien' in document type field")
            
            # Wait for autocomplete dropdown to appear
            await page.wait_for_timeout(800)  # Reduced from 1500
            
            # Select the third option (index 2) specifically
            try:
                # Method 1: Try to select by nth-child (3rd option)
                third_option_selectors = [
                    "mat-option:nth-child(3)",
                    ".mat-option:nth-child(3)",
                    "mat-option[id='mat-option-2']",
                    "[role='option']:nth-child(3)"
                ]
                
                option_selected = False
                for selector in third_option_selectors:
                    try:
                        if await page.locator(selector).count():
                            await page.locator(selector).click()
                            _log(f"✅ Selected third option (index 2) using {selector}")
                            option_selected = True
                            break
                    except Exception as e:
                        _log(f"Warning: Could not use selector {selector}: {e}")
                
                if not option_selected:
                    # Method 2: Use keyboard navigation to select third option
                    _log("Using keyboard navigation to select third option...")
                    
                    # Press Down arrow 3 times to get to third option (index 2)
                    await page.keyboard.press("ArrowDown")  # Option 0
                    await page.wait_for_timeout(100)  # Reduced from 200
                    await page.keyboard.press("ArrowDown")  # Option 1  
                    await page.wait_for_timeout(100)  # Reduced from 200
                    await page.keyboard.press("ArrowDown")  # Option 2 (third option)
                    await page.wait_for_timeout(100)  # Reduced from 200
                    
                    # Press Enter to select
                    await page.keyboard.press("Enter")
                    _log("✅ Selected third option using keyboard navigation")
                    option_selected = True
                
                if not option_selected:
                    # Method 3: Get all options and select the third one
                    _log("Using index-based selection...")
                    all_options = page.locator("mat-option, .mat-option, [role='option']")
                    option_count = await all_options.count()
                    _log(f"Found {option_count} total options")
                    
                    if option_count >= 3:
                        # Select the third option (index 2)
                        await all_options.nth(2).click()
                        _log("✅ Selected third option by index (2)")
                        option_selected = True
                    else:
                        _log(f"❌ Not enough options found. Expected at least 3, found {option_count}")
                
            except Exception as e:
                _log(f"❌ Error selecting specific option: {e}")
                return False
            
            await page.wait_for_timeout(200)  # Reduced from 500
            
            # Verify the selection by checking the input value
            try:
                selected_value = await page.input_value(doc_type_selector)
                _log(f"✅ Document type field now contains: '{selected_value}'")
            except Exception as e:
                _log(f"Warning: Could not verify selection: {e}")
            
        except Exception as e:
            _log(f"❌ Error setting document type: {e}")
            return False
        
        _log("✅ All search filters applied successfully")
        return True
        
    except Exception as e:
        _log(f"❌ Error applying search filters: {e}")
        return False

async def _execute_search(page: Page) -> bool:
    """Execute the search after filters are applied"""
    try:
        _log("🔍 Executing search using Enter key...")
        
        # Method 1: Press Enter to submit the form
        try:
            await page.keyboard.press("Enter")
            _log("✅ Pressed Enter to execute search")
            
            # Wait for search results to load
            _log("⏳ Waiting for search results to load...")
            await page.wait_for_load_state("networkidle", timeout=15000)  # Reduced from 30000
            
            # Additional wait for Angular to update the results
            await page.wait_for_timeout(2000)  # Reduced from 5000
            
            _log("✅ Search results should be loaded")
            return True
            
        except Exception as e:
            _log(f"Warning: Enter key method failed: {e}")
            
            # Fallback: Try clicking the search button as backup
            _log("Trying fallback search button click...")
            
            search_button_selectors = [
                "button.red",  # Primary selector based on the HTML
                "button:has-text('Search')",
                "button i.fa-search",
                "button[form='searchForm']",
                ".buttonContainer button.red",
            ]
            
            search_clicked = False
            for selector in search_button_selectors:
                try:
                    if await page.locator(selector).count():
                        _log(f"Found search button: {selector}")
                        
                        # Scroll the button into view if needed
                        await page.locator(selector).scroll_into_view_if_needed()
                        await page.wait_for_timeout(200)  # Reduced from 500
                        
                        # Click the search button
                        await page.locator(selector).click()
                        _log(f"✅ Clicked search button using {selector}")
                        search_clicked = True
                        break
                        
                except Exception as e:
                    _log(f"Warning: Could not use search button selector {selector}: {e}")
                    continue
            
            if not search_clicked:
                _log("❌ Could not find or click search button")
                return False
            
            # Wait for search results to load
            _log("⏳ Waiting for search results to load...")
            try:
                # Wait for the page to finish loading after search
                await page.wait_for_load_state("networkidle", timeout=15000)  # Reduced from 30000
                await page.wait_for_timeout(3000)  # Reduced from 10000
                # Additional wait for Angular to update the results
                
                
                _log("✅ Search results should be loaded")
                return True
                
            except Exception as e:
                _log(f"Warning: Timeout waiting for results, continuing anyway: {e}")
                return True  # Continue even if timeout, results might still be there
        
    except Exception as e:
        _log(f"❌ Error executing search: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# DATA EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
async def _extract_records_from_results(page: Page, max_records: int = 100) -> List[HillsboroughRecord]:
    """Extract record data from search results - limits to max_records NEW records only"""
    records = []
    seen_document_numbers = set()  # Track document numbers to avoid duplicates
    new_records_count = 0  # Track count of NEW records only
    
    # Get existing document numbers to check against (unless in test mode)
    try:
        existing_doc_numbers = await get_existing_document_numbers()
        _log(f"📊 Found {len(existing_doc_numbers)} existing records in database")
    except Exception as e:
        _log(f"⚠️ Could not fetch existing records (test mode?): {e}")
        existing_doc_numbers = set()  # Empty set for test mode
    
    try:
        # Take a screenshot first to see what we're working with
        try:
            await page.screenshot(path="debug_extraction_start.png", timeout=10000)
            _log("📸 Screenshot saved: debug_extraction_start.png")
        except Exception as screenshot_error:
            _log(f"Warning: Could not take extraction screenshot: {screenshot_error}")
        
        # Look for the results based on the actual HTML structure
        results_selectors = [
            "div.resultRowSummary",  # Primary selector - more specific for row summaries
            ".resultRowSummary",     # Alternative class-only selector
            "div.resultRow",         # Original selector as fallback
            ".resultRow",            # Class-only fallback
            "div[class*='resultRowSummary']",  # Partial class match for resultRowSummary
            "div[class*='resultRow']",         # Partial class match for resultRow
            "div.searchResultsAvaSectionContent div.ng-star-inserted div.resultRow",  # Full path fallback
        ]
        
        rows = None
        rows_selector_used = None
        
        for selector in results_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    rows = page.locator(selector)
                    rows_selector_used = selector
                    _log(f"✅ Found {count} result rows using '{selector}'")
                    break
            except Exception as e:
                _log(f"Warning: Could not use results selector '{selector}': {e}")
        
        if not rows:
            _log("⚠️ Could not find results table with standard selectors - trying alternative approaches...")
            
            # Don't return early - try alternative approaches to find results
            # Try more generic selectors for any clickable elements that might be records
            alternative_selectors = [
                "div[ng-repeat]",  # Angular repeated elements
                ".ng-star-inserted",  # Angular inserted elements
                "div[class*='result']",  # Any div with 'result' in class name
                "div[class*='row']",  # Any div with 'row' in class name
                "button",  # Any buttons that might be clickable records
                "a[href]",  # Any links
                "div:has(label)",  # Divs containing labels
                "*[ng-click]",  # Elements with ng-click handlers
                ".mat-button",  # Material buttons
                ".mat-card",  # Material cards
            ]
            
            for alt_selector in alternative_selectors:
                try:
                    alt_count = await page.locator(alt_selector).count()
                    if alt_count > 0:
                        _log(f"🔍 Found {alt_count} elements with alternative selector: {alt_selector}")
                        rows = page.locator(alt_selector)
                        rows_selector_used = alt_selector
                        _log(f"✅ Using alternative selector for results: {alt_selector}")
                        break
                except Exception as e:
                    _log(f"Warning: Could not use alternative selector '{alt_selector}': {e}")
            
            # If still no rows found, try to find any indication of results or no results message
            if not rows:
                no_results_selectors = [
                    "text=/no results/i",
                    "text=/no records/i", 
                    "text=/no documents/i",
                    ".no-results",
                    ".empty-results"
                ]
                
                for selector in no_results_selectors:
                    try:
                        if await page.locator(selector).count():
                            _log(f"Found 'no results' message: {selector}")
                            return records
                    except:
                        continue
                
                # Log page content for debugging but continue processing
                _log("📄 Taking screenshot and logging page content for debugging...")
                try:
                    await page.screenshot(path="debug_no_results_found.png", timeout=10000)
                    _log("Screenshot saved: debug_no_results_found.png")
                except Exception as screenshot_error:
                    _log(f"Warning: Could not take debug screenshot: {screenshot_error}")
                
                page_text = await page.text_content("body")
                _log(f"Page content preview (first 1000 chars): {page_text[:1000]}...")
                
                # Don't return early - continue to see if we can extract anything
                _log("⚠️ No standard results found, but continuing to check for any extractable content...")
                
                # Try to find ANY clickable elements and treat them as potential records
                generic_elements = await page.locator("*").all()
                _log(f"🔍 Found {len(generic_elements)} total elements on page - will try to process some of them")
                
                # Limit to reasonable number to avoid infinite processing
                if len(generic_elements) > 50:
                    # Filter to elements that might contain meaningful content
                    potential_records = []
                    for element in generic_elements[:100]:  # Check first 100 elements
                        try:
                            element_text = await element.text_content()
                            if element_text and len(element_text.strip()) > 10:  # Has meaningful text
                                potential_records.append(element)
                                if len(potential_records) >= 10:  # Limit to 10 potential records
                                    break
                        except:
                            continue
                    
                    if potential_records:
                        _log(f"🎯 Found {len(potential_records)} elements with meaningful content - treating as potential records")
                        rows = page.locator("body").locator("*").filter(lambda x: x in potential_records)
                        rows_selector_used = "generic_content_elements"
                    else:
                        _log("❌ No elements with meaningful content found")
                        return records
                else:
                    _log("❌ Too few elements on page - likely no results")
                    return records
        
        # Extract data from each row
        count = await rows.count()
        _log(f"Found {count} total rows, processing until we get {max_records} NEW records...")
        
        for i in range(count):  # Process all rows, but stop when we hit max NEW records
            # Check if we've reached our limit of NEW records
            if new_records_count >= max_records:
                _log(f"✅ Reached maximum of {max_records} new records, stopping at row {i+1}")
                break
            try:
                row = rows.nth(i)
                
                # Get all labels from this row
                labels = row.locator("label.resultRowLabel")
                label_count = await labels.count()
                
                _log(f"Row {i+1}: Found {label_count} labels")
                
                # Extract text from all labels in this row
                label_texts = []
                for j in range(label_count):
                    try:
                        label_text = await labels.nth(j).inner_text()
                        if label_text and label_text.strip():
                            label_texts.append(label_text.strip())
                    except Exception as e:
                        _log(f"Warning: Could not extract label {j}: {e}")
                
                _log(f"Row {i+1} label texts: {label_texts}")
                
                # Parse the labels to extract structured data
                # Based on the structure, the labels typically contain:
                # [0] = Document Number
                # [1] = Document Type  
                # [2] = Date/Time
                # [3] = Party 1 name
                # [4] = Party 2 name  
                # [5] = Location/Legal description
                
                if len(label_texts) < 3:
                    _log(f"Skipping row {i+1} - insufficient data ({len(label_texts)} labels)")
                    continue
                
                # Extract document number with improved regex
                document_number = ""
                if label_texts:
                    # Look for document number pattern in all labels (more flexible)
                    for text in label_texts:
                        # Enhanced patterns for document numbers
                        doc_patterns = [
                            r'(\d{9,})',                    # 9+ digit numbers like 250017944
                            r'Doc(?:ument)?[#\s]*(\d{8,})', # "Doc #12345678" or "Document 12345678"
                            r'(\d{6,})',                    # 6+ digit numbers as fallback
                            r'#(\d{5,})',                   # Numbers prefixed with #
                        ]
                        
                        for pattern in doc_patterns:
                            doc_match = re.search(pattern, text, re.IGNORECASE)
                            if doc_match:
                                document_number = doc_match.group(1)
                                break
                        
                        if document_number:
                            break
                
                if not document_number:
                    _log(f"Skipping row {i+1} - no document number found")
                    continue
                
                # Check for duplicates in this session
                if document_number in seen_document_numbers:
                    _log(f"Skipping duplicate document number: {document_number}")
                    continue
                seen_document_numbers.add(document_number)
                
                # Check if this record already exists in database
                if document_number in existing_doc_numbers:
                    _log(f"Skipping existing record: {document_number}")
                    continue
                
                # This is a NEW record - increment our counter
                new_records_count += 1
                _log(f"📝 Processing NEW record {new_records_count}/{max_records}: {document_number}")
                
                # Extract other fields
                instrument_type = ""
                recorded_date = ""
                grantor = ""
                grantee = ""
                legal_description = ""
                
                # Look for LIEN type
                for text in label_texts:
                    if "LIEN" in text.upper():
                        instrument_type = "LIEN"
                        break
                
                # Look for date pattern
                for text in label_texts:
                    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
                    if date_match:
                        recorded_date = date_match.group(1)
                        break
                
                # Extract party names (typically the longer text labels)
                party_labels = [text for text in label_texts if len(text) > 10 and not re.search(r'^\d', text)]
                if len(party_labels) >= 1:
                    grantor = party_labels[0]
                if len(party_labels) >= 2:
                    grantee = party_labels[1]
                if len(party_labels) >= 3:
                    legal_description = party_labels[2]
                
                # Extract property address using OCR (if enabled)
                property_address = ""
                document_url = ""
                if EXTRACT_ADDRESSES:
                    try:
                        # Store current page URL for returning
                        current_url = page.url
                        _log(f"🔍 Starting address extraction for document {document_number}")
                        
                        property_address, document_url = await _click_and_extract_address(page, row, document_number)
                        _log(f"✅ Address extraction completed for {document_number}: {property_address[:50] if property_address else 'No address found'}")
                        _log(f"📄 Document URL captured: {document_url}")
                        
                        # Enhanced logic to return to results page
                        await _ensure_back_to_results(page, current_url, rows_selector_used)
                        
                        # Re-get the rows since we might have navigated
                        try:
                            rows = page.locator(rows_selector_used)
                            current_count = await rows.count()
                            _log(f"🔄 Back to results - found {current_count} rows")
                        except Exception as e:
                            _log(f"⚠️ Could not re-locate rows: {e}")
                        
                    except Exception as e:
                        _log(f"❌ Address extraction failed for {document_number}: {e}")
                        property_address = ""
                        document_url = ""
                        
                        # Try to get back to results even on error
                        try:
                            await _ensure_back_to_results(page, BASE_URL, rows_selector_used)
                            rows = page.locator(rows_selector_used)
                        except Exception as recovery_error:
                            _log(f"⚠️ Error recovering to results page: {recovery_error}")
                else:
                    _log(f"⚡ Skipping address extraction for {document_number} (disabled for speed)")
                
                # Create record
                record_data = {
                    'document_number': document_number,
                    'instrument_type': instrument_type,
                    'recorded_date': recorded_date,
                    'grantor': grantor,
                    'grantee': grantee,
                    'book_page': legal_description,  # Use legal info as book_page
                    'consideration': "",  # Not available in this interface
                    'legal_description': legal_description,
                    'property_address': property_address,  # Now populated via OCR
                    'document_url': document_url,  # Now captured from actual document page
                }
                
                # Clean and format the data
                record_data = _clean_record_data(record_data)
                
                records.append(record_data)
                _log(f"✅ Extracted record {i+1}: Doc#{record_data['document_number']}, "
                     f"Type: {record_data['instrument_type']}, "
                     f"Date: {record_data['recorded_date']}, "
                     f"Grantor: {record_data['grantor'][:30]}..., "
                     f"Address: {record_data['property_address'][:50]}...")
                
            except Exception as e:
                _log(f"❌ Error extracting record {i+1}: {e}")
                continue
        
        _log(f"✅ Successfully extracted {len(records)} unique records from {count} total rows")
        return records
        
    except Exception as e:
        _log(f"❌ Error extracting records from results: {e}")
        return records

async def _extract_cell_text(row, selectors: List[str]) -> Optional[str]:
    """Extract text from a cell using multiple possible selectors"""
    for selector in selectors:
        try:
            element = row.locator(selector)
            if await element.count():
                text = await element.inner_text()
                return text.strip() if text else None
        except Exception:
            continue
    return None

async def _extract_document_url(row) -> Optional[str]:
    """Extract document URL if available"""
    link_selectors = [
        "a[href]",
        ".doc-link",
        "[ng-click*='view']",
        "[data-ng-click*='view']",
    ]
    
    for selector in link_selectors:
        try:
            element = row.locator(selector)
            if await element.count():
                href = await element.get_attribute("href")
                if href:
                    return href
                
                # Check for JavaScript click handlers
                onclick = await element.get_attribute("ng-click") or await element.get_attribute("data-ng-click")
                if onclick:
                    # This would need custom logic to extract document IDs from Angular click handlers
                    pass
        except Exception:
            continue
    
    return None

def _clean_record_data(record_data: dict) -> HillsboroughRecord:
    """Clean and standardize record data"""
    
    # Clean document number
    if record_data.get('document_number'):
        record_data['document_number'] = re.sub(r'[^\w\-]', '', record_data['document_number'])
    
    # Parse and standardize date
    if record_data.get('recorded_date'):
        record_data['recorded_date'] = _parse_date(record_data['recorded_date'])
    
    # Clean names
    for field in ['grantor', 'grantee']:
        if record_data.get(field):
            record_data[field] = record_data[field].upper().strip()
    
    # Clean consideration amount
    if record_data.get('consideration'):
        record_data['consideration'] = re.sub(r'[^\d\.]', '', record_data['consideration'])
    
    return record_data

def _parse_date(date_str: str) -> str:
    """Parse date string into standard format YYYY-MM-DD"""
    if not date_str:
        return ""
    
    # Common date formats
    date_patterns = [
        r'(\d{1,2})/(\d{1,2})/(\d{4})',  # MM/DD/YYYY
        r'(\d{1,2})-(\d{1,2})-(\d{4})',  # MM-DD-YYYY
        r'(\d{4})-(\d{1,2})-(\d{1,2})',  # YYYY-MM-DD
        r'(\d{4})/(\d{1,2})/(\d{1,2})',  # YYYY/MM/DD
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, date_str)
        if match:
            try:
                if len(match.group(1)) == 4:  # YYYY first
                    year, month, day = match.groups()
                else:  # MM/DD first
                    month, day, year = match.groups()
                
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                continue
    
    return date_str  # Return original if can't parse

def _remove_person_names_from_address(address: str) -> str:
    """Remove person names from addresses to clean them up"""
    if not address:
        return address
    
    # Common person name patterns to remove
    name_patterns = [
        # Specific names mentioned by user
        r'\b(Dennis\s+Hogan)\b',
        r'\b(DennisHogan)\b',
        r'\b(Register\s+of\s+Deeds\s+Hillsborough\s+County)\b',
        r'\b(RegisterofDeedsHillsboroughCounty)\b',
        
        # Pattern for concatenated first+last names (like DennisHogan)
        r'\b[A-Z][a-z]+[A-Z][a-z]+\b(?=\s|$)',  # CamelCase names
        
        # General pattern: Two consecutive capitalized words that look like names
        r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b(?=\s*$|(?=\s+[A-Z]{2,}))',  # First Last at end or before state
        
        # Pattern for names followed by common suffixes
        r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\s*(?:Jr\.?|Sr\.?|II|III|IV)\b',
        
        # Common first names + any last name pattern
        r'\b(Dennis|Daniel|Michael|David|John|Robert|James|William|Richard|Thomas|Christopher|Matthew|Anthony|Donald|Steven|Kenneth|Joshua|Kevin|Brian|George|Edward|Ronald|Timothy|Jason|Jeffrey|Ryan|Jacob|Gary|Nicholas|Eric|Stephen|Jonathan|Larry|Justin|Scott|Brandon|Benjamin|Samuel|Frank|Gregory|Raymond|Alexander|Patrick|Jack|Jerry|Tyler|Aaron)\s+[A-Z][a-z]+\b',
        
        # Female names
        r'\b(Mary|Patricia|Jennifer|Linda|Elizabeth|Barbara|Susan|Jessica|Sarah|Karen|Nancy|Lisa|Betty|Helen|Sandra|Donna|Carol|Ruth|Sharon|Michelle|Laura|Emily|Kimberly|Deborah|Dorothy|Amy|Angela|Ashley|Brenda|Emma|Olivia|Cynthia|Marie)\s+[A-Z][a-z]+\b',
    ]
    
    # Remove all matching name patterns
    for pattern in name_patterns:
        address = re.sub(pattern, '', address, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    address = re.sub(r'\s+', ' ', address)
    address = address.strip()
    
    # Remove leading/trailing commas or other punctuation
    address = re.sub(r'^[,\s]+|[,\s]+$', '', address)
    
    return address

# ─────────────────────────────────────────────────────────────────────────────
# OCR AND ADDRESS EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
async def _download_document_image(page: Page, document_number: str) -> Optional[str]:
    """
    Attempt to download the original document image by right-clicking and downloading
    This should provide better quality than screenshots for OCR
    """
    try:
        _log(f"🖼️ Attempting to download original document image for {document_number}")
        
        # Wait for document to load
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_timeout(3000)
        
        # Look for image elements in the document viewer
        image_selectors = [
            "img[src*='document']",     # Document images
            "img[src*='pdf']",          # PDF page images  
            "img[src*='image']",        # Generic images
            "img[src*='page']",         # Page images
            ".document-viewer img",     # Images in document viewer
            ".pdf-viewer img",          # Images in PDF viewer
            "#document-frame img",      # Images in document frame
            "iframe img",               # Images in iframes
            "embed + img",              # Images near embed elements
            ".page-image",              # Page image class
            ".document-image",          # Document image class
            "img[alt*='document']",     # Images with document in alt text
            "img[alt*='page']",         # Images with page in alt text
        ]
        
        downloaded_image_path = None
        
        for selector in image_selectors:
            try:
                image_count = await page.locator(selector).count()
                if image_count > 0:
                    _log(f"🎯 Found {image_count} images with selector: {selector}")
                    
                    # Try each image found
                    for i in range(image_count):
                        try:
                            image_element = page.locator(selector).nth(i)
                            
                            # Get image source URL
                            src = await image_element.get_attribute("src")
                            if src:
                                _log(f"🔗 Image {i+1} source: {src[:100]}...")
                                
                                # Check if it's a reasonable size (not tiny icons)
                                try:
                                    bounding_box = await image_element.bounding_box()
                                    if bounding_box and bounding_box['width'] > 200 and bounding_box['height'] > 200:
                                        _log(f"📏 Image {i+1} size: {bounding_box['width']}x{bounding_box['height']}")
                                        
                                        # Try to download via right-click context menu
                                        downloaded_path = await _try_download_image_via_context_menu(
                                            page, image_element, document_number, i
                                        )
                                        
                                        if downloaded_path:
                                            downloaded_image_path = downloaded_path
                                            _log(f"✅ Successfully downloaded image: {downloaded_path}")
                                            break
                                        
                                        # Alternative: Try direct URL download
                                        if src.startswith('http'):
                                            downloaded_path = await _try_download_image_via_url(
                                                page, src, document_number, i
                                            )
                                            if downloaded_path:
                                                downloaded_image_path = downloaded_path
                                                _log(f"✅ Successfully downloaded via URL: {downloaded_path}")
                                                break
                                                
                                except Exception as e:
                                    _log(f"Warning: Could not check image {i+1} properties: {e}")
                            
                        except Exception as e:
                            _log(f"Warning: Could not process image {i+1}: {e}")
                    
                    # If we found a good image, stop looking
                    if downloaded_image_path:
                        break
                        
            except Exception as e:
                _log(f"Warning: Could not use image selector {selector}: {e}")
        
        return downloaded_image_path
        
    except Exception as e:
        _log(f"❌ Error downloading document image for {document_number}: {e}")
        return None

async def _try_download_image_via_context_menu(page: Page, image_element, document_number: str, image_index: int) -> Optional[str]:
    """Try to download image via right-click context menu"""
    try:
        _log(f"🖱️ Trying right-click download for image {image_index}")
        
        # Set up download handling
        download_path = f"ocr_debug/document_{document_number}_original_{image_index}.png"
        
        # Right-click on the image to open context menu
        await image_element.click(button="right")
        await page.wait_for_timeout(1000)  # Wait for context menu to appear
        
        # Look for "Save image as" or similar options in context menu
        save_image_selectors = [
            "text=/save.*image/i",
            "text=/download.*image/i", 
            "text=/save.*as/i",
            "[data-action*='save']",
            "[data-action*='download']",
            ".context-menu-item:has-text('Save')",
            ".context-menu-item:has-text('Download')",
        ]
        
        for selector in save_image_selectors:
            try:
                if await page.locator(selector).count():
                    _log(f"🎯 Found save option: {selector}")
                    
                    # Set up download event listener
                    async with page.expect_download() as download_info:
                        await page.locator(selector).click()
                        download = await download_info.value
                    
                    # Save the download to our desired location
                    await download.save_as(download_path)
                    _log(f"💾 Saved downloaded image to: {download_path}")
                    return download_path
                    
            except Exception as e:
                _log(f"Warning: Could not use save selector {selector}: {e}")
        
        # If context menu approach doesn't work, dismiss the menu
        await page.keyboard.press("Escape")
        return None
        
    except Exception as e:
        _log(f"Warning: Context menu download failed: {e}")
        return None

async def _try_download_image_via_url(page: Page, image_url: str, document_number: str, image_index: int) -> Optional[str]:
    """Try to download image directly via URL"""
    try:
        _log(f"🌐 Trying direct URL download for image {image_index}")
        
        # Prepare download path
        download_path = f"ocr_debug/document_{document_number}_url_{image_index}.png"
        
        # Create a new page for downloading
        context = page.context
        download_page = await context.new_page()
        
        try:
            # Navigate to the image URL
            response = await download_page.goto(image_url, wait_until="networkidle")
            
            if response and response.status == 200:
                # Check if it's actually an image
                content_type = response.headers.get("content-type", "")
                if "image" in content_type.lower():
                    # Take a screenshot of the full image
                    await download_page.screenshot(path=download_path, full_page=True)
                    _log(f"💾 Downloaded image via URL to: {download_path}")
                    return download_path
                else:
                    _log(f"⚠️ URL does not return an image (content-type: {content_type})")
            else:
                _log(f"⚠️ Failed to load image URL (status: {response.status if response else 'No response'})")
                
        finally:
            await download_page.close()
        
        return None
        
    except Exception as e:
        _log(f"Warning: URL download failed: {e}")
        return None

async def _screenshot_full_iframe_content(page: Page, iframe_element, screenshot_path: str, document_number: str):
    """Screenshot iframe content - simplified for speed"""
    try:
        # Get the iframe frame
        frame = await iframe_element.content_frame()
        if frame:
            _log(f"🖼️ Taking simple iframe screenshot")
            
            # Wait briefly for iframe content to load
            await frame.wait_for_load_state("networkidle", timeout=3000)  # Reduced from 5000
            await frame.wait_for_timeout(500)  # Reduced from 1000
            
            # Take simple screenshot of iframe body with timeout
            await frame.screenshot(path=screenshot_path, timeout=8000)  # 8 second timeout
            _log(f"✅ Iframe screenshot captured")
        else:
            raise Exception("Could not access iframe content")
            
    except Exception as e:
        _log(f"❌ Failed to capture iframe content: {e}")
        raise

async def _screenshot_full_scrollable_content(page: Page, element, screenshot_path: str, document_number: str):
    """Screenshot the full scrollable content of an element by scrolling through it"""
    try:
        _log(f"📜 Capturing full scrollable content for document")
        
        # Get element dimensions
        scroll_height = await element.evaluate("el => el.scrollHeight")
        client_height = await element.evaluate("el => el.clientHeight")
        scroll_width = await element.evaluate("el => el.scrollWidth")
        client_width = await element.evaluate("el => el.clientWidth")
        
        _log(f"📏 Scroll dimensions: {scroll_width}x{scroll_height}, Viewport: {client_width}x{client_height}")
        
        # If content is much larger than viewport, use stitching approach
        if scroll_height > client_height * 1.5:  # More than 1.5x viewport height
            await _screenshot_with_stitching(page, element, screenshot_path, document_number)
        else:
            # Content is not much larger - try to scroll to show all content and screenshot
            # First scroll to top
            await element.evaluate("el => el.scrollTop = 0")
            await page.wait_for_timeout(300)  # Reduced from 500
            
            # Try to adjust element size to show full content if possible
            try:
                # Temporarily adjust the element's style to show full content
                await element.evaluate("""
                    el => {
                        el.style.height = 'auto';
                        el.style.maxHeight = 'none';
                        el.style.overflow = 'visible';
                    }
                """)
                await page.wait_for_timeout(500)  # Reduced from 1000
                
                # Take screenshot with timeout
                await element.screenshot(path=screenshot_path, timeout=8000)  # 8 second timeout
                _log(f"✅ Captured full content by adjusting element size")
                
            except Exception as e:
                _log(f"Warning: Could not adjust element size: {e}")
                # Fallback to regular screenshot with timeout
                await element.screenshot(path=screenshot_path, timeout=8000)  # 8 second timeout
                _log(f"✅ Captured content with regular screenshot")
                
    except Exception as e:
        _log(f"❌ Failed to capture scrollable content: {e}")
        raise

async def _screenshot_with_stitching(page: Page, element, screenshot_path: str, document_number: str):
    """Capture long documents by taking multiple screenshots and stitching them"""
    try:
        _log(f"🧩 Using screenshot stitching for long document")
        
        # For very long documents, we'll scroll through and take multiple screenshots
        # then combine them (or just take the first few sections for OCR)
        
        # Get dimensions
        scroll_height = await element.evaluate("el => el.scrollHeight")
        client_height = await element.evaluate("el => el.clientHeight")
        
        # Calculate number of sections needed
        sections_needed = min(5, max(1, int(scroll_height / client_height) + 1))  # Cap at 5 sections
        _log(f"📑 Taking {sections_needed} sections of the document")
        
        screenshot_sections = []
        section_height = client_height
        
        for i in range(sections_needed):
            try:
                # Scroll to the section
                scroll_position = i * section_height * 0.8  # 20% overlap
                await element.evaluate(f"el => el.scrollTop = {scroll_position}")
                await page.wait_for_timeout(500)  # Reduced from 1000
                
                # Take screenshot of this section with timeout
                section_path = screenshot_path.replace(".png", f"_section_{i}.png")
                await element.screenshot(path=section_path, timeout=6000)  # 6 second timeout for sections
                screenshot_sections.append(section_path)
                _log(f"📸 Captured section {i+1}/{sections_needed}")
                
            except Exception as e:
                _log(f"Warning: Could not capture section {i}: {e}")
        
        if screenshot_sections:
            # Use the first section as the main screenshot for now
            # In the future, we could stitch these together with CV2
            import shutil
            shutil.copy2(screenshot_sections[0], screenshot_path)
            _log(f"✅ Using first section as main screenshot: {screenshot_path}")
            
            # Optionally combine all sections for better OCR coverage
            await _combine_screenshot_sections(screenshot_sections, screenshot_path, document_number)
        else:
            raise Exception("No sections captured")
            
    except Exception as e:
        _log(f"❌ Screenshot stitching failed: {e}")
        raise

async def _combine_screenshot_sections(section_paths: list, output_path: str, document_number: str):
    """Combine multiple screenshot sections into one tall image"""
    try:
        import cv2
        import numpy as np
        
        _log(f"🔗 Combining {len(section_paths)} screenshot sections")
        
        # Load all images
        images = []
        total_height = 0
        max_width = 0
        
        for path in section_paths:
            img = cv2.imread(path)
            if img is not None:
                images.append(img)
                height, width = img.shape[:2]
                total_height += height
                max_width = max(max_width, width)
        
        if not images:
            _log("⚠️ No valid images to combine")
            return
        
        # Create combined image
        combined = np.zeros((total_height, max_width, 3), dtype=np.uint8)
        combined.fill(255)  # White background
        
        # Paste images vertically
        current_y = 0
        for img in images:
            height, width = img.shape[:2]
            combined[current_y:current_y + height, 0:width] = img
            current_y += height
        
        # Save combined image
        combined_path = output_path.replace(".png", "_combined.png")
        cv2.imwrite(combined_path, combined)
        _log(f"✅ Combined screenshot saved: {combined_path}")
        
        # Copy combined as main if it's reasonable size
        if total_height < 10000:  # Don't use extremely tall images
            import shutil
            shutil.copy2(combined_path, output_path)
            _log(f"✅ Using combined image as main screenshot")
        
    except Exception as e:
        _log(f"Warning: Could not combine screenshot sections: {e}")

async def _extract_property_address_from_document(page: Page, document_number: str) -> Optional[str]:
    """
    Extract property address from document using OCR
    1. Screenshot the document
    2. OCR the screenshot 
    3. Parse for address information
    """
    try:
        # Wait for document to load
        await page.wait_for_load_state("networkidle", timeout=10000)  # Reduced from 15000
        await page.wait_for_timeout(1500)  # Reduced from 3000
        
        _log(f"📄 Document page URL: {page.url}")
        
        # First, try to download the original document image (better quality) if enabled
        downloaded_image_path = None
        if DOWNLOAD_ORIGINAL_IMAGES:
            downloaded_image_path = await _download_document_image(page, document_number)
        
        if downloaded_image_path:
            # Use the downloaded original image for OCR
            _log(f"🎯 Using downloaded original image: {downloaded_image_path}")
            property_address = await _ocr_extract_address(downloaded_image_path)
            
            if property_address:
                _log(f"✅ Extracted address from downloaded image for {document_number}: {property_address}")
                return property_address
            else:
                _log(f"⚠️ No address found in downloaded image, falling back to screenshot method")
        else:
            _log(f"⚠️ Could not download original image, using screenshot method")
        
        # Fallback: Take screenshot of the document area
        screenshot_path = f"ocr_debug/document_{document_number}.png"
        
        # Enhanced selectors for document content
        document_selectors = [
            ".document-viewer",
            ".pdf-viewer", 
            ".document-content",
            "#document-frame",
            "iframe[src*='document']",  # Iframes that likely contain documents
            "iframe[src*='pdf']",       # PDF-containing iframes  
            "iframe[src*='image']",     # Image-containing iframes
            "iframe:nth-child(2)",      # Try second iframe if first doesn't work
            "iframe:nth-child(1)",      # First iframe (but we'll check size)
            ".document-container",
            "#documentContainer",
            ".pdf-container",
            "embed",
            ".viewer-content",
            "#viewer",
            ".content-area",            # Generic content area
            "#main-content",            # Main content div
            ".page-content",            # Page content area
        ]
        
        screenshot_taken = False
        used_selector = None
        
        for selector in document_selectors:
            try:
                element_count = await page.locator(selector).count()
                if element_count > 0:
                    _log(f"🎯 Found {element_count} elements with selector: {selector}")
                    
                    # Get the element for full document capture
                    element = page.locator(selector).first
                    
                    # For iframe elements, try to access the full content
                    if "iframe" in selector:
                        try:
                            # Skip scroll_into_view_if_needed for iframes (causes timeouts)
                            _log(f"⚡ Skipping scroll for iframe to avoid timeout - taking direct screenshot")
                            await _screenshot_full_iframe_content(page, element, screenshot_path, document_number)
                            screenshot_taken = True
                            used_selector = selector + " (iframe content)"
                            _log(f"📸 Iframe document screenshot saved: {screenshot_path}")
                        except Exception as e:
                            _log(f"Warning: Could not capture iframe content: {e}")
                            # Fall back to regular element screenshot
                    else:
                        # Only scroll for non-iframe elements with short timeout
                        try:
                            await element.scroll_into_view_if_needed(timeout=3000)  # Reduced from 5000
                            await page.wait_for_timeout(300)  # Reduced from 500
                        except Exception as e:
                            _log(f"Warning: Could not scroll element into view: {e}")
                    
                    if not screenshot_taken:
                        # Simple element screenshot with shorter timeout
                        try:
                            await element.screenshot(path=screenshot_path, timeout=10000)  # 10 second timeout instead of default 30
                            screenshot_taken = True
                            used_selector = selector
                            _log(f"📸 Document screenshot saved using {selector}: {screenshot_path}")
                                
                        except Exception as e:
                            _log(f"Warning: Could not take screenshot with {selector}: {e}")
                    
                    # Check if the screenshot is large enough to contain document content
                    if screenshot_taken:
                        try:
                            import os
                            file_size = os.path.getsize(screenshot_path)
                            if file_size < 5000:  # If less than 5KB, likely too small
                                _log(f"⚠️ Screenshot too small ({file_size} bytes), trying next selector...")
                                screenshot_taken = False
                                continue
                            
                            # Quick check of image dimensions
                            test_image = cv2.imread(screenshot_path)
                            if test_image is not None:
                                h, w = test_image.shape[:2]
                                if w < 300 or h < 200:  # Too small to contain document
                                    _log(f"⚠️ Screenshot dimensions too small ({w}x{h}), trying next selector...")
                                    screenshot_taken = False
                                    continue
                                else:
                                    _log(f"✅ Good screenshot dimensions: {w}x{h}")
                        except Exception as e:
                            _log(f"Warning: Could not check screenshot size: {e}")
                    
                    if screenshot_taken:
                        break
                        
            except Exception as e:
                _log(f"Warning: Could not screenshot with selector {selector}: {e}")
        
        if not screenshot_taken:
            # Fallback: take full page screenshot with timeout
            await page.screenshot(path=screenshot_path, timeout=10000)  # 10 second timeout
            _log(f"📸 Full page screenshot saved: {screenshot_path}")
            used_selector = "full page"
        
        # Additional approach: Try to capture a larger area if we used a small selector
        if used_selector and "iframe" in used_selector:
            # Take an additional expanded screenshot for better address capture
            expanded_path = screenshot_path.replace(".png", "_expanded.png")
            try:
                # Try to capture the parent container of the iframe for more context
                parent_selectors = [
                    f"{used_selector}",  # The iframe itself
                    ".document-area",    # Common document container
                    ".main-content",     # Main content area
                    "#content",          # Content div
                    "body",              # Full body as last resort
                ]
                
                for parent_sel in parent_selectors:
                    try:
                        if await page.locator(parent_sel).count():
                            await page.locator(parent_sel).screenshot(path=expanded_path, timeout=8000)  # Shorter timeout for expanded screenshots
                            _log(f"📸 Expanded screenshot saved using {parent_sel}: {expanded_path}")
                            
                            # Check if expanded screenshot is larger
                            import os
                            original_size = os.path.getsize(screenshot_path)
                            expanded_size = os.path.getsize(expanded_path)
                            
                            if expanded_size > original_size * 1.5:  # If significantly larger
                                _log(f"✅ Using expanded screenshot ({expanded_size} vs {original_size} bytes)")
                                screenshot_path = expanded_path  # Use the expanded version
                                break
                    except Exception as e:
                        _log(f"Warning: Could not take expanded screenshot with {parent_sel}: {e}")
                        
            except Exception as e:
                _log(f"Warning: Could not create expanded screenshot: {e}")
        
        # OCR the screenshot
        property_address = await _ocr_extract_address(screenshot_path)
        
        if property_address:
            _log(f"✅ Extracted address for {document_number}: {property_address}")
            return property_address
        else:
            _log(f"⚠️ No address found in document {document_number}")
            return ""
            
    except Exception as e:
        _log(f"❌ Error extracting address from document {document_number}: {e}")
        return ""

async def _ocr_extract_address(image_path: str) -> Optional[str]:
    """Extract address from image using OCR and address parsing"""
    try:
        # Set tesseract path for Windows (common installation locations)
        possible_tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
            'tesseract',  # If in PATH
        ]
        
        tesseract_found = False
        for tesseract_path in possible_tesseract_paths:
            try:
                if os.path.exists(tesseract_path) or tesseract_path == 'tesseract':
                    pytesseract.pytesseract.tesseract_cmd = tesseract_path
                    # Test if tesseract works
                    pytesseract.get_tesseract_version()
                    tesseract_found = True
                    _log(f"✅ Found Tesseract at: {tesseract_path}")
                    break
            except Exception:
                continue
        
        if not tesseract_found:
            _log("❌ Tesseract not found. Please install Tesseract OCR.")
            _log("   Download from: https://github.com/UB-Mannheim/tesseract/wiki")
            return None
        
        # Load and preprocess image
        image = cv2.imread(image_path)
        if image is None:
            _log(f"❌ Could not load image: {image_path}")
            return None
        
        # Log image dimensions for debugging
        height, width = image.shape[:2]
        _log(f"📏 Image dimensions: {width}x{height} pixels")
        
        # Check if image is too small to contain meaningful text
        if width < 100 or height < 100:
            _log(f"⚠️ Image too small for OCR: {width}x{height}")
            return None
        
        # Convert to grayscale only - no other preprocessing
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _log(f"🔧 Using simple grayscale conversion - no additional preprocessing")
        
        # Save grayscale version for debugging
        debug_path_grayscale = image_path.replace(".png", "_grayscale.png")
        cv2.imwrite(debug_path_grayscale, gray)
        _log(f"💾 Grayscale image saved: {debug_path_grayscale}")
        
        # OCR the grayscale image with basic configuration
        custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,#-/()'
        ocr_text = pytesseract.image_to_string(gray, config=custom_config)
        ocr_method_used = "grayscale"
        
        # Try original image as backup if grayscale fails
        if not ocr_text.strip():
            _log("🔄 Grayscale failed, trying original image...")
            ocr_text = pytesseract.image_to_string(image)
            ocr_method_used = "original_image"
        
        # Try different PSM modes with grayscale if still no text
        if not ocr_text.strip():
            _log("🔄 Trying different OCR PSM modes with grayscale...")
            for psm_mode in [3, 4, 6, 8, 11, 12]:
                try:
                    alt_config = f'--oem 3 --psm {psm_mode}'
                    alt_text = pytesseract.image_to_string(gray, config=alt_config)
                    if alt_text.strip():
                        ocr_text = alt_text
                        ocr_method_used = f"grayscale_psm_{psm_mode}"
                        _log(f"✅ Found text with grayscale + PSM mode {psm_mode}")
                        break
                except Exception:
                    continue
        
        if not ocr_text.strip():
            _log("⚠️ No text found in OCR after trying all methods and processing variations")
            _log(f"📊 Image stats - Size: {width}x{height}, File: {image_path}")
            return None
        
        _log(f"✅ OCR successful using method: {ocr_method_used}")
        
        # Save complete OCR text to debug file
        ocr_debug_file = image_path.replace(".png", "_ocr_text.txt")
        try:
            with open(ocr_debug_file, 'w', encoding='utf-8') as f:
                f.write(f"=== OCR DEBUG OUTPUT ===\n")
                f.write(f"Image: {image_path}\n")
                f.write(f"Image dimensions: {width}x{height}\n")
                f.write(f"OCR method used: {ocr_method_used}\n")
                f.write(f"OCR text length: {len(ocr_text)} characters\n")
                f.write(f"Timestamp: {datetime.now()}\n")
                f.write(f"=== FULL OCR TEXT ===\n\n")
                f.write(ocr_text)
                f.write(f"\n\n=== END OCR TEXT ===\n")
            _log(f"💾 Complete OCR text saved to: {ocr_debug_file}")
        except Exception as e:
            _log(f"⚠️ Could not save OCR text to file: {e}")
        
        # Print complete OCR text to console for debugging
        _log(f"📝 === COMPLETE OCR TEXT ({len(ocr_text)} chars) via {ocr_method_used} ===")
        _log(f"OCR Text Content:\n{ocr_text}")
        _log(f"📝 === END OCR TEXT ===")
        
        # Parse addresses from OCR text
        addresses = _parse_addresses_from_text(ocr_text)
        
        if addresses:
            # Return the most complete address found
            best_address = max(addresses, key=len)
            _log(f"✅ Best address found: {best_address}")
            return best_address
        
        return None
        
    except Exception as e:
        _log(f"❌ OCR extraction error: {e}")
        return None

def _parse_addresses_from_text(text: str) -> List[str]:
    """Parse addresses from OCR text using multiple methods - REGEX FIRST"""
    addresses = []
    
    try:
        # Method 1: PRIORITY REGEX - User specified patterns in priority order
        priority_patterns = [
            # Pattern 0: HIGHEST PRIORITY - Capture address between "being know and numbered as" and "and described as followed"
            r'(?i)being\s+know\s+and\s+numbered\s+as\s+([^.]*?)\s+and\s+described\s+as\s+followed',
            
            # Pattern 1: Capture text AFTER "residence" on the SAME line, include "manchester" line if present
            r'(?i)residence\s+([^\n]+)(?:\n([^\n]*manchester[^\n]*))?',
            
            # Pattern 3: If no "residence", capture line above "manchester" and the "manchester" line
            r'(?i)([^\n]*)\n(manchester[^\n]*)',
            
            # Pattern 3: If no "residence", capture line above "pelham" and the "pelham" line
            r'(?i)([^\n]*)\n(pelham[^\n]*)',
            
            # Pattern 4: If no "residence", capture line above "goffstown" and the "goffstown" line
            r'(?i)([^\n]*)\n(goffstown[^\n]*)',
            
            # Pattern 5: If no "residence", capture line above "nashua" and the "nashua" line
            r'(?i)([^\n]*)\n(nashua[^\n]*)',
            
            # Pattern 6: More flexible "residence" pattern - capture everything after residence on same line
            r'(?i)residence[^a-zA-Z]*([A-Z0-9][^\n]*)',

            # Pattern 2: Unit Number to Condominium Name - Capture address starting with Unit Number and ending with Name of Condominium
            r'(?i)(Unit\s+\w+[A-Z0-9]*\s+[^.]*?)\s+(?:\w+\s+)*(?:Condominium)',
            
            # Pattern 7: Capture address block that contains both street and manchester
            r'(?i)([A-Z0-9][^\n]*(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE)[^\n]*\n[^\n]*manchester[^\n]*)',
            
            # Pattern 8: Fallback - any line with residence followed by content on same line
            r'(?i)residence[^\n]*?([A-Z0-9][^\n]*)',
        ]
        
        for pattern in priority_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle tuple matches - combine all non-empty parts
                    clean_address = ' '.join(str(m).strip() for m in match if m.strip())
                else:
                    clean_address = str(match).strip()
                
                # Clean up the extracted text
                clean_address = re.sub(r'[\n\r]+', ' ', clean_address)  # Replace newlines with spaces
                clean_address = re.sub(r'\s+', ' ', clean_address)      # Normalize whitespace
                clean_address = clean_address.strip()
                
                if len(clean_address) > 10:  # Minimum length filter
                    addresses.append(clean_address)
                    _log(f"🎯 Priority regex address: {clean_address}")
        
        # Method 2: Enhanced regex patterns for NH tax lien documents
        address_patterns = [
            # NH Tax Lien Format: "14 LADYSLIPPER AVE PELHAM NH 03076-2959"
            # Street Number + Street Name + Street Type + City + State + ZIP
            r'\b\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?\b',
            
            # More flexible version with optional components
            r'\b\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)[,\s]+[A-Z\s]+[,\s]+NH[,\s]+\d{5}(?:-\d{4})?\b',
            
            # Unit/Apt Number, Street Number, Street Name, City, State
            r'(?:Unit|Apt|Apartment)\s*\d+[A-Z]?,?\s*\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Way|Circle|Cir|Court|Ct|Place|Pl)[,\s]+[A-Za-z\s]+[,\s]+(?:NH|New Hampshire)',
            
            # Standard format: Street Number, Street Name, City, State  
            r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Way|Circle|Cir|Court|Ct|Place|Pl)[,\s]+[A-Za-z\s]+[,\s]+(?:NH|New Hampshire)',
            
            # More flexible pattern
            r'\d+[A-Z]?\s+[A-Za-z\s]+(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Cir|Circle|Ct|Court|Pl|Place)\b[,\s]*[A-Za-z\s]+[,\s]*(?:NH|New Hampshire)',
            
            # Specifically for NH addresses with ZIP codes
            r'\b\d+[A-Z]?\s+[A-Z\s]+\s+(?:AVE|ST|RD|DR|LN|WAY|CT|CIR|PL)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?\b',
            
            # Pattern for addresses that might span multiple lines
            r'\b\d+[A-Z]?\s+[A-Z][A-Z\s]+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE)[\s\n]+[A-Z\s]+[\s\n]+NH[\s\n]+\d{5}(?:-\d{4})?\b',
        ]
        
        for pattern in address_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                clean_address = re.sub(r'\s+', ' ', match.strip())
                if len(clean_address) > 15:  # Filter reasonable length
                    addresses.append(clean_address)
        
        # Method 3: Look for specific New Hampshire patterns and cities
        nh_patterns = [
            r'[A-Za-z\s,]+(?:Nashua|Manchester|Concord|Derry|Rochester|Salem|Merrimack|Hudson|Londonderry|Keene|Pelham|Windham|Litchfield|Amherst|Milford|Bedford)[,\s]+(?:NH|New Hampshire)',
            r'[A-Za-z0-9\s,]+Hillsborough\s+County[,\s]+(?:NH|New Hampshire)',
        ]
        
        for pattern in nh_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                clean_address = re.sub(r'\s+', ' ', match.strip())
                if len(clean_address) > 10:
                    addresses.append(clean_address)
        
        # Method 4: Specific patterns for tax lien documents based on the format you showed
        tax_lien_patterns = [
            # Look for person name followed by address pattern
            r'[A-Z][A-Z\s]+\n(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)',
            
            # Multi-line pattern where address components are on separate lines
            r'(\d+[A-Z]?\s+[A-Z][A-Z\s]+)\s*(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)[\s\n]+([A-Z\s]+)\s+NH\s+(\d{5}(?:-\d{4})?)',
            
            # Complete address on single line after name
            r'[A-Z][A-Z\s,]+\s+(\d+\s+[A-Z][A-Z\s]+\s+(?:AVE|ST|RD|DR|LN|WAY|CT|CIR|PL)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)',
        ]
        
        for pattern in tax_lien_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    # Join tuple components for multi-group matches
                    clean_address = ' '.join(str(m).strip() for m in match if m)
                else:
                    clean_address = str(match).strip()
                
                clean_address = re.sub(r'\s+', ' ', clean_address)
                if len(clean_address) > 15:
                    addresses.append(clean_address)
        
        # Method 5: Extract addresses between specific text boundaries (user requested)
        boundary_patterns = [
            # Pattern: From "Certain unit known and numbered as" or "Residence" to "Which unit is created under a declaration" or zip code or "SSN"
            r'(?:Certain unit known and numbered as|Residence)[^a-zA-Z]*([A-Z0-9][^SSN]*?)(?:Which unit is created under a declaration|SSN|\d{5}(?:-\d{4})?)',
            
            # Alternative pattern: Extract address after "Residence" keyword 
            r'Residence[^a-zA-Z]*?([A-Z0-9][^\n]*?(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE)[^\n]*?NH[^\n]*?\d{5}(?:-\d{4})?)',
            
            # Pattern: Extract complete addresses found before SSN or zip codes
            r'([A-Z0-9][^\n]*?(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE)[^\n]*?NH[^\n]*?\d{5}(?:-\d{4})?)[\s\n]*(?:SSN|Which unit)',
            
            # Enhanced pattern for multi-line address blocks (like VICTOR RODRIGUEZ example)
            r'([A-Z][A-Z\s]+\s+\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)',
            
            # Pattern: Person name on one line, address components on subsequent lines
            r'([A-Z][A-Z\s]+)\s*\n\s*(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD))\s*\n\s*([A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)',
            
            # Capture address block between name and SSN (common tax lien format)
            r'[A-Z][A-Z\s]+\s*\n\s*(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s*\n\s*[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)\s*\n?\s*(?:SSN|$)',
            
            # More lenient pattern for OCR errors (SEWALL vs SEAWALL)
            r'(\d+[A-Z]?\s+[A-Z][A-Z\s]*?(?:WALL|SEWALL|SEAWALL)[A-Z\s]*?(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)',
        ]
        
        for pattern in boundary_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle multi-group matches - combine all parts
                    if len(match) == 3:  # Name, street, city/state/zip
                        clean_address = f"{match[1]} {match[2]}".strip()  # Skip name, use street + city/state/zip
                    else:
                        # Join all non-empty components
                        clean_address = ' '.join(str(m).strip() for m in match if m.strip())
                else:
                    clean_address = str(match).strip()
                
                # Clean up the extracted text
                clean_address = re.sub(r'[\n\r]+', ' ', clean_address)  # Replace newlines with spaces
                clean_address = re.sub(r'\s+', ' ', clean_address)      # Normalize whitespace
                clean_address = clean_address.strip()
                
                # Extract just the address portion if person name is included at the start
                address_match = re.search(r'(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:AVE|AVENUE|ST|STREET|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)', clean_address, re.IGNORECASE)
                if address_match:
                    clean_address = address_match.group(1)
                
                if len(clean_address) > 15 and 'NH' in clean_address.upper():
                    addresses.append(clean_address)
                    _log(f"🎯 Boundary-extracted address: {clean_address}")
                    
                    # Debug: Log surrounding OCR text to see what we might be missing
                    if len(clean_address) < 30:  # If address seems incomplete
                        _log(f"🔍 OCR context around address: {text[max(0, text.find(clean_address.replace(' ', ''))-100):text.find(clean_address.replace(' ', ''))+200]}")
        
        # Method 6: Enhanced patterns specifically for the format shown (VICTOR RODRIGUEZ style)
        enhanced_patterns = [
            # Direct match for "NUMBER STREET_NAME ST CITY NH ZIP" format
            r'\b(\d+[A-Z]?\s+[A-Z]+(?:\s+[A-Z]+)*\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z]+(?:\s+[A-Z]+)*\s+NH\s+\d{5}(?:-\d{4})?)\b',
            
            # Pattern for addresses that might have OCR errors in street names
            r'\b(\d+[A-Z]?\s+[A-Z][A-Z\s]*(?:WALL|SEWALL|SEAWALL|MAIN|CENTRAL|UNION|PARK|FIRST|SECOND|THIRD)[A-Z\s]*\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+NH\s+\d{5}(?:-\d{4})?)\b',
            
            # Match addresses even with extra whitespace or line breaks
            r'(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)[\s\n]+[A-Z\s]+[\s\n]+NH[\s\n]+\d{5}(?:-\d{4})?)',
            
            # Manchester-specific pattern (since user mentioned Manchester NH)
            r'(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+MANCHESTER\s+NH\s+\d{5}(?:-\d{4})?)',
            
            # Look for street address in proximity to "MANCHESTER NH" + zip pattern
            r'(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD))[^NH]*MANCHESTER\s+NH\s+(\d{5}(?:-\d{4})?)',
            
            # Capture addresses that span multiple lines with city/state/zip separate
            r'(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD))[\s\n]+MANCHESTER[\s\n]+NH[\s\n]+(\d{5}(?:-\d{4})?)',
        ]
        
        for pattern in enhanced_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    # Handle tuple matches - combine street address with city/state/zip
                    if len(match) == 2:  # Street address + zip code
                        clean_address = f"{match[0]} MANCHESTER NH {match[1]}".strip()
                    else:
                        # Join all components
                        clean_address = ' '.join(str(m).strip() for m in match if m.strip())
                else:
                    clean_address = str(match).strip()
                
                clean_address = re.sub(r'[\n\r]+', ' ', clean_address)  # Replace newlines with spaces
                clean_address = re.sub(r'\s+', ' ', clean_address)      # Normalize whitespace
                clean_address = clean_address.strip()
                
                if len(clean_address) > 20 and 'NH' in clean_address.upper():  # Slightly higher threshold for complete addresses
                    addresses.append(clean_address)
                    _log(f"🏠 Enhanced pattern address: {clean_address}")
        
        # Method 7: Additional pattern to find street addresses near "MANCHESTER NH" or zip codes
        proximity_patterns = [
            # Look for lines with street numbers and street types near Manchester
            r'(?:^|\n)([A-Z\s]*\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD))[A-Z\s\n]*MANCHESTER[A-Z\s\n]*NH[A-Z\s\n]*(\d{5}(?:-\d{4})?)',
            
            # Find any complete address pattern in the text
            r'(\d+[A-Z]?\s+[A-Z][A-Z\s]*(?:WALL|SEWALL|MAIN|UNION|PARK|CENTRAL|FIRST|SECOND|THIRD|BEECH|ELM|OAK|PINE)[A-Z\s]*\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD))\s+([A-Z\s]+)\s+(NH)\s+(\d{5}(?:-\d{4})?)',
        ]
        
        for pattern in proximity_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    if len(match) == 2:  # Street + zip
                        clean_address = f"{match[0]} MANCHESTER NH {match[1]}".strip()
                    elif len(match) == 4:  # Street + city + state + zip
                        clean_address = f"{match[0]} {match[1]} {match[2]} {match[3]}".strip()
                    else:
                        clean_address = ' '.join(str(m).strip() for m in match if m.strip())
                else:
                    clean_address = str(match).strip()
                
                clean_address = re.sub(r'[\n\r]+', ' ', clean_address)
                clean_address = re.sub(r'\s+', ' ', clean_address)
                clean_address = clean_address.strip()
                
                if len(clean_address) > 20 and 'NH' in clean_address.upper():
                    addresses.append(clean_address)
                    _log(f"📍 Proximity pattern address: {clean_address}")
        
        # Method 8: FALLBACK - Use pyap library for address parsing (last resort)
        if not addresses:  # Only use pyap if no regex patterns found anything
            _log("🔄 No addresses found with regex patterns, trying pyap library as fallback...")
            try:
                parsed_addresses = pyap.parse(text, country='US')
                for addr in parsed_addresses:
                    addr_str = str(addr).strip()
                    if len(addr_str) > 10:  # Filter out short/incomplete addresses
                        addresses.append(addr_str)
                        _log(f"📚 Pyap fallback address: {addr_str}")
            except Exception as e:
                _log(f"⚠️ Pyap library failed: {e}")
        
        # Remove duplicates and return
        unique_addresses = list(set(addresses))
        
        # Clean addresses: Remove person names like "Dennis Hogan"
        cleaned_addresses = []
        for address in unique_addresses:
            cleaned = _remove_person_names_from_address(address)
            if cleaned and len(cleaned.strip()) > 5:  # Only keep if meaningful content remains
                cleaned_addresses.append(cleaned)
                if cleaned != address:
                    _log(f"🧹 Cleaned address: '{address}' → '{cleaned}'")
        
        return cleaned_addresses
        
    except Exception as e:
        _log(f"❌ Address parsing error: {e}")
        return []

async def _click_and_extract_address(page: Page, row, document_number: str) -> tuple[str, str]:
    """
    Click a result row to expand details, then click document to extract address and URL
    Returns: (property_address, document_url)
    """
    try:
        _log(f"🔍 Extracting address and URL for document {document_number}")
        
        # Step 1: Click the row to expand details
        try:
            await row.click()
            _log(f"✅ Clicked row for document {document_number}")
            await page.wait_for_timeout(500)  # Reduced from 1000
        except Exception as e:
            _log(f"Warning: Could not click row: {e}")
        
        # Step 2: Look for and click the document number button
        document_button_selectors = [
            f"button:has-text('{document_number}')",
            f"[title='{document_number}']",
            ".resultRowDetail button",
            "button[ng-content*='c982831721']",  # Based on the HTML structure
            "div.resultRowDetail button",
        ]
        
        document_clicked = False
        for selector in document_button_selectors:
            try:
                if await page.locator(selector).count():
                    await page.locator(selector).click()
                    _log(f"✅ Clicked document button using {selector}")
                    document_clicked = True
                    break
            except Exception as e:
                _log(f"Warning: Could not click document button with {selector}: {e}")
        
        if not document_clicked:
            _log(f"❌ Could not find document button for {document_number}")
            return "", ""
        
        # Step 3: Wait for document to open (might be new tab/window)
        await page.wait_for_timeout(1500)  # Reduced from 3000
        
        # Check if a new page/tab opened
        context = page.context
        all_pages = context.pages
        
        if len(all_pages) > 1:
            # Document opened in new tab
            document_page = all_pages[-1]  # Get the newest page
            _log(f"✅ Document opened in new tab")
            
            # Capture the document URL
            document_url = document_page.url
            _log(f"📄 Captured document URL: {document_url}")
            
            # Extract address from the new page
            address = await _extract_property_address_from_document(document_page, document_number)
            
            # Close the document tab
            await document_page.close()
            
            return address or "", document_url
        else:
            # Document opened in same page
            _log(f"✅ Document opened in same page")
            
            # Capture the document URL
            document_url = page.url
            _log(f"📄 Captured document URL: {document_url}")
            
            # Extract address from the page
            address = await _extract_property_address_from_document(page, document_number)
            
            # Go back to results if needed
            try:
                await page.go_back()
                await page.wait_for_load_state("networkidle", timeout=3000)  # Reduced from 5000
            except:
                pass  # If go_back fails, continue
            
            return address or "", document_url
        
    except Exception as e:
        _log(f"❌ Error extracting address and URL for {document_number}: {e}")
        return "", ""

async def _ensure_back_to_results(page: Page, target_url: str, rows_selector: str) -> bool:
    """
    Ensure we're back on the search results page after address extraction
    Uses multiple strategies to return to results efficiently
    """
    try:
        _log("🔄 Ensuring we're back on search results page...")
        
        # Strategy 1: Check if we're already on a results page
        try:
            current_rows = await page.locator(rows_selector).count()
            if current_rows > 0:
                _log(f"✅ Already on results page with {current_rows} rows")
                return True
        except Exception:
            pass
        
        # Strategy 2: Try browser back button first (most efficient)
        try:
            _log("🔙 Trying browser back button...")
            await page.go_back()
            await page.wait_for_load_state("networkidle", timeout=5000)  # Reduced from 10000
            await page.wait_for_timeout(500)  # Reduced from 1000
            
            # Check if we have results now
            current_rows = await page.locator(rows_selector).count()
            if current_rows > 0:
                _log(f"✅ Back button worked - found {current_rows} rows")
                return True
        except Exception as e:
            _log(f"⚠️ Back button failed: {e}")
        
        # Strategy 3: Navigate to search page and re-execute search
        try:
            _log("🔍 Re-executing search to get back to results...")
            await page.goto(BASE_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            
            # Re-apply search filters and execute search
            if await _apply_search_filters(page):
                if await _execute_search(page):
                    await page.wait_for_timeout(1500)  # Reduced from 3000
                    
                    # Check if we have results now
                    current_rows = await page.locator(rows_selector).count()
                    if current_rows > 0:
                        _log(f"✅ Search re-execution worked - found {current_rows} rows")
                        return True
                    else:
                        _log("⚠️ Search re-execution completed but no rows found")
                else:
                    _log("❌ Failed to re-execute search")
            else:
                _log("❌ Failed to re-apply search filters")
        except Exception as e:
            _log(f"❌ Search re-execution failed: {e}")
        
        # Strategy 4: Last resort - try direct URL navigation if provided
        if target_url and target_url != BASE_URL:
            try:
                _log(f"🔗 Trying direct navigation to: {target_url}")
                await page.goto(target_url, wait_until="networkidle")
                await page.wait_for_timeout(1000)  # Reduced from 2000
                
                current_rows = await page.locator(rows_selector).count()
                if current_rows > 0:
                    _log(f"✅ Direct navigation worked - found {current_rows} rows")
                    return True
            except Exception as e:
                _log(f"⚠️ Direct navigation failed: {e}")
        
        _log("❌ All strategies failed to return to results page")
        return False
        
    except Exception as e:
        _log(f"❌ Error in _ensure_back_to_results: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────
async def get_existing_document_numbers() -> set:
    """Get existing document numbers from database to avoid duplicates"""
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                text("SELECT document_number FROM hillsborough_nh_filing WHERE county = :county"),
                {"county": COUNTY_NAME}
            )
            return {row[0] for row in result.fetchall()}
    except Exception as e:
        _log(f"Error getting existing document numbers: {e}")
        return set()

async def upsert_records(records: List[dict]):
    """Insert or update records in database"""
    if not records:
        return
    
    try:
        async with AsyncSession(engine) as session:
            for record in records:
                # Add metadata and additional fields required by the site
                current_time = datetime.now()
                
                # Convert recorded_date string to datetime object if present
                recorded_date_obj = None
                recorded_date_str = record.get('recorded_date', '')
                if recorded_date_str:
                    try:
                        # Parse date string YYYY-MM-DD into datetime object
                        recorded_date_obj = datetime.strptime(recorded_date_str, '%Y-%m-%d')
                    except Exception as e:
                        _log(f"Warning: Could not parse recorded_date '{recorded_date_str}': {e}")
                
                record.update({
                    'recorded_date': recorded_date_obj,  # Use datetime object
                    'county': COUNTY_NAME,
                    'state': 'NH',
                    'filing_date': recorded_date_str,  # Keep original string for filing_date
                    'amount': record.get('consideration', ''),  # Use consideration as amount
                    'parties': f"{record.get('grantor', '')} / {record.get('grantee', '')}".strip(' /'),  # Combined parties
                    'location': record.get('book_page', ''),  # Use book_page (legals) as location for now
                    'status': 'active',  # Default status
                    'created_at': current_time,
                    'updated_at': current_time,
                    'is_new': True,
                    'doc_type': 'lien',  # Since we're searching for liens
                    'userId': USER_ID,
                })
                
                await session.execute(text(INSERT_SQL), record)
            
            await session.commit()
            _log(f"Successfully upserted {len(records)} records to database")
            
    except Exception as e:
        _log(f"Error upserting records: {e}")
        raise

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def _export_csv(df: pd.DataFrame) -> Path:
    """Export records to CSV file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = EXPORT_DIR / f"hillsborough_nh_records_{timestamp}.csv"
    
    df.to_csv(csv_path, index=False)
    _log(f"✅ Exported {len(df)} records to {csv_path}")
    return csv_path

def _push_to_google_sheets(df: pd.DataFrame):
    """Push records to Google Sheets (optional)"""
    if not GOOGLE_CREDS_FILE or not GSHEET_NAME:
        _log("Google Sheets credentials not configured, skipping upload")
        return
    
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scope)
        client = gspread.authorize(creds)
        
        sheet = client.open(GSHEET_NAME)
        worksheet = sheet.worksheet(HILLSBOROUGH_TAB)
        
        # Clear existing data and add new data
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        
        _log(f"✅ Uploaded {len(df)} records to Google Sheets")
        
    except Exception as e:
        _log(f"Error uploading to Google Sheets: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
async def run(max_new_records: int = MAX_NEW_RECORDS, test_mode: bool = False):
    """Main execution function"""
    _log(f"🚀 Starting Hillsborough County NH scraper (max {max_new_records} records)")
    
    if test_mode:
        _log("🧪 Running in TEST MODE - no database operations")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Minimize browser after 3 seconds (reduced for speed)
        if not test_mode and not HEADLESS:  # Skip minimization in test mode and headless mode
            try:
                _log("[TIMER] Browser will minimize in 3 seconds - please click 'Agree' on any disclaimers if needed...")
                await page.wait_for_timeout(3000)  # Reduced from 5000
                
                # Minimize all Chromium windows using pygetwindow (same as other scripts)
                try:
                    for w in gw.getWindowsWithTitle('Chromium'):
                        w.minimize()
                    _log("[SUCCESS] Browser minimized using pygetwindow")
                except Exception as e:
                    _log(f"[WARNING] Could not minimize browser window: {e}")
                    _log("[NOTE] Browser will remain visible during scraping")
            except Exception as e:
                _log(f"[WARNING] Error in minimization timer: {e}")
        
        try:
            # Navigate to the search page
            _log(f"Navigating to {BASE_URL}")
            await page.goto(BASE_URL, wait_until="networkidle")
            
            # Accept disclaimer if present
            await _maybe_accept_disclaimer(page)
            
            # Wait for page to fully load
            if not await _wait_for_page_load(page):
                _log("Warning: Page may not have loaded completely")
            
            # Take screenshot for debugging
            try:
                await page.screenshot(path="debug_hillsborough_initial.png", timeout=10000)
                _log("Screenshot saved: debug_hillsborough_initial.png")
            except Exception as screenshot_error:
                _log(f"Warning: Could not take initial screenshot: {screenshot_error}")
            
            # Apply search filters
            if await _apply_search_filters(page):
                _log("✅ Search filters applied")
            else:
                _log("❌ Failed to apply search filters")
                return
            
            # Take screenshot after filling form
            try:
                await page.screenshot(path="debug_hillsborough_form_filled.png", timeout=10000)
                _log("Screenshot saved: debug_hillsborough_form_filled.png")
            except Exception as screenshot_error:
                _log(f"Warning: Could not take form screenshot: {screenshot_error}")
            
            # Execute search
            if await _execute_search(page):
                _log("✅ Search executed")
            else:
                _log("❌ Failed to execute search")
                return
            
            # Take screenshot of results
            try:
                await page.screenshot(path="debug_hillsborough_results.png", timeout=10000)
                _log("Screenshot saved: debug_hillsborough_results.png")
            except Exception as screenshot_error:
                _log(f"Warning: Could not take results screenshot: {screenshot_error}")
            
            # Extract records from results (already filters for new records only)
            new_records = await _extract_records_from_results(page, max_new_records)
            
            if not new_records:
                _log("No new records found")
                return
            
            _log(f"✅ Found {len(new_records)} new records (already filtered)")
            
            if not new_records:
                _log("No new records to process")
                return
            
            # Export to CSV (always do this)
            df = pd.DataFrame(new_records)
            await _export_csv(df)
            
            if test_mode:
                _log("🧪 TEST MODE: Skipping database and Google Sheets operations")
                _log(f"✅ TEST COMPLETED - Found {len(new_records)} records")
                
                # Show first few records for review
                _log("📋 Sample records found:")
                for i, record in enumerate(new_records[:3]):
                    _log(f"  {i+1}. Doc: {record.get('document_number', 'N/A')}, "
                         f"Date: {record.get('recorded_date', 'N/A')}, "
                         f"Type: {record.get('instrument_type', 'N/A')}")
                if len(new_records) > 3:
                    _log(f"  ... and {len(new_records) - 3} more records")
            else:
                # Save to database
                await upsert_records(new_records)
                
                # Optional: Push to Google Sheets
                _push_to_google_sheets(df)
                
                _log(f"✅ Successfully processed {len(new_records)} new records")
            
        except Exception as e:
            _log(f"❌ Error in main execution: {e}")
            # Take screenshot for debugging (with timeout protection)
            try:
                await page.screenshot(path="debug_hillsborough_error.png", timeout=10000)
                _log("Error screenshot saved: debug_hillsborough_error.png")
            except Exception as screenshot_error:
                _log(f"Warning: Could not take error screenshot: {screenshot_error}")
            raise
        
        finally:
            if test_mode:
                _log("🖥️  Browser will stay open for 5 seconds for inspection...")
                await page.wait_for_timeout(5000)  # Reduced from 10000
            await browser.close()

async def main():
    """Command line entry point"""
    parser = argparse.ArgumentParser(description="Hillsborough County NH Registry Scraper")
    parser.add_argument("--max-records", type=int, default=MAX_NEW_RECORDS,
                        help=f"Maximum number of new records to scrape (default: {MAX_NEW_RECORDS})")
    parser.add_argument("--user-id", type=str, 
                        help="User ID for database records (required unless using --test-mode)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode")
    parser.add_argument("--test-mode", action="store_true",
                        help="Run in test mode without database operations")
    parser.add_argument("--extract-addresses", action="store_true",
                        help="Extract property addresses using OCR (slower but more complete)")
    parser.add_argument("--no-extract-addresses", action="store_true",
                        help="Skip address extraction (faster)")
    parser.add_argument("--download-original-images", action="store_true",
                        help="Download original document images for better OCR quality")
    parser.add_argument("--no-download-original-images", action="store_true",
                        help="Use screenshots only (faster but lower quality)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.test_mode and not args.user_id:
        parser.error("--user-id is required unless using --test-mode")
    
    global USER_ID, HEADLESS, EXTRACT_ADDRESSES, DOWNLOAD_ORIGINAL_IMAGES
    USER_ID = args.user_id
    HEADLESS = args.headless
    
    # Set address extraction preference
    if args.no_extract_addresses:
        EXTRACT_ADDRESSES = False
    elif args.extract_addresses:
        EXTRACT_ADDRESSES = True
    # Otherwise keep default value
    
    # Set image download preference
    if args.no_download_original_images:
        DOWNLOAD_ORIGINAL_IMAGES = False
    elif args.download_original_images:
        DOWNLOAD_ORIGINAL_IMAGES = True
    # Otherwise keep default value
    
    # Override headless mode in test mode to show browser
    if args.test_mode:
        HEADLESS = False
        _log("🧪 TEST MODE: Browser will be visible")
    
    if EXTRACT_ADDRESSES:
        _log("🔍 Address extraction enabled - this will be slower but more complete")
        if DOWNLOAD_ORIGINAL_IMAGES:
            _log("🖼️ Original image download enabled - highest quality OCR")
        else:
            _log("📸 Using screenshots only - faster but lower quality OCR")
    else:
        _log("⚡ Address extraction disabled - faster scraping")
    
    await run(max_new_records=args.max_records, test_mode=args.test_mode)

if __name__ == "__main__":
    asyncio.run(main()) 
