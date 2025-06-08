"""
Brevard County Florida Official Records Scraper

This script scrapes recent official records from Brevard County, Florida's 
Acclaim-powered records system. It focuses on liens, lis pendens, foreclosures, 
and other relevant document types.

Website: https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeDocType

Features:
- Searches for recent records (last 14 days by default)
- Targets specific document types (liens, lis pendens, etc.)
- Extracts structured data including document numbers, dates, parties
- Prevents duplicate records via database checking
- Exports results to CSV and optionally Google Sheets
- Supports test mode for development/debugging

Dependencies:
- playwright (browser automation)
- pandas (data manipulation)
- sqlalchemy (database operations) 
- python-dotenv (environment variables)
- pytesseract, opencv (OCR capabilities)
- gspread (Google Sheets integration)

Author: Based on patterns from HillsboroughNH.py, LpH.py, and MdCaseSearch.py
"""

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
class BrevardRecord(TypedDict):
    case_number: str
    document_url: Optional[str]
    file_date: str
    case_type: str
    party_name: str
    property_address: str

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL = "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeDocType"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
HEADLESS = False
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
MAX_NEW_RECORDS = 5   # Maximum number of new records to scrape per run (default)
USER_ID = None  # Will be set from command line argument
COUNTY_NAME = "Brevard"

# Environment variables
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME = os.getenv("GSHEET_NAME")
BREVARD_TAB = os.getenv("BREVARD_TAB", "BrevardFL")
EXPORT_DIR = (Path(__file__).parent / "data").resolve()
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required for database connection")

# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: You need to create the brevard_fl_filing table first:
# 
# CREATE TABLE brevard_fl_filing (
#   id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
#   document_number TEXT UNIQUE NOT NULL,
#   document_url TEXT,
#   recorded_date TIMESTAMP,
#   document_type TEXT,
#   grantor TEXT,
#   grantee TEXT,
#   property_address TEXT,
#   book_page TEXT,
#   consideration TEXT,
#   legal_description TEXT,
#   county TEXT DEFAULT 'Brevard FL',
#   state TEXT DEFAULT 'FL',
#   filing_date TEXT,
#   amount TEXT,
#   parties TEXT,
#   location TEXT,
#   status TEXT DEFAULT 'active',
#   created_at TIMESTAMP DEFAULT NOW(),
#   updated_at TIMESTAMP DEFAULT NOW(),
#   is_new BOOLEAN DEFAULT TRUE,
#   doc_type TEXT,
#   "userId" TEXT
# );
# 
# CREATE INDEX idx_brevard_fl_document_number ON brevard_fl_filing(document_number);
# CREATE INDEX idx_brevard_fl_recorded_date ON brevard_fl_filing(recorded_date);
# CREATE INDEX idx_brevard_fl_user_id ON brevard_fl_filing("userId");

engine = create_async_engine(DB_URL, echo=False)
INSERT_SQL = """
INSERT INTO brevard_fl_filing
  (id,
   case_number,
   document_url,
   file_date,
   case_type,
   party_name,
   property_address,
   county,
   created_at,
   is_new,
   "userId")
VALUES
  (gen_random_uuid(),
   :case_number,
   :document_url,
   :file_date,
   :case_type,
   :party_name,
   :property_address,
   :county,
   :created_at,
   :is_new,
   :userId)
ON CONFLICT (case_number) DO UPDATE
SET
  document_url       = EXCLUDED.document_url,
  file_date          = EXCLUDED.file_date,
  case_type          = EXCLUDED.case_type,
  party_name         = EXCLUDED.party_name,
  property_address   = EXCLUDED.property_address,
  county             = EXCLUDED.county,
  created_at         = EXCLUDED.created_at,
  is_new             = EXCLUDED.is_new,
  "userId"           = EXCLUDED."userId";
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
    """Accept Brevard County's specific disclaimer with 'I accept the conditions above' button"""
    try:
        # Wait for page to load first
        await page.wait_for_timeout(3000)
        
        # Check for "You must enable Cookies" message first
        cookie_message = page.locator('text="You must enable Cookies"')
        if await cookie_message.count():
            _log("⚠️ Website requires cookies to be enabled")
        
        # Look for Brevard County's specific disclaimer form and submit button
        # Based on the HTML structure: <input type="submit" value="I accept the conditions above.">
        disclaimer_selectors = [
            "input[type='submit'][value='I accept the conditions above.']",
            "button[value='I accept the conditions above.']",
            "input[value='I accept the conditions above.']",
            "input[type='submit']:has-text('I accept the conditions above')",
            "button:has-text('I accept the conditions above')",
            # Fallback selectors
            "input[type='submit'][value*='accept']",
            "input[type='submit'][value*='Accept']",
            "button[value*='accept']",
            "input[value*='accept the conditions']",
            "input[type='submit']",  # Any submit button as last resort
        ]
        
        disclaimer_accepted = False
        for sel in disclaimer_selectors:
            try:
                element_count = await page.locator(sel).count()
                if element_count > 0:
                    _log(f"Found disclaimer element: {sel} (count: {element_count})")
                    
                    # Get the button text for logging
                    try:
                        button_text = await page.locator(sel).first.get_attribute("value")
                        if not button_text:
                            button_text = await page.locator(sel).first.inner_text()
                        _log(f"Button text: '{button_text}'")
                    except:
                        pass
                    
                    # Click the disclaimer acceptance button
                    await page.locator(sel).first.click()
                    _log(f"✅ Clicked disclaimer button via {sel}")
                    
                    # Wait for form submission and page navigation
                    await page.wait_for_load_state("networkidle", timeout=15000)
                    disclaimer_accepted = True
                    break
                    
            except Exception as e:
                _log(f"Warning: Could not use disclaimer selector {sel}: {e}")
        
        if not disclaimer_accepted:
            _log("⚠️ No disclaimer button found - checking if already past disclaimer")
            
            # Check if we're already on the main search page
            search_elements = page.locator('text="Official Records Search", text="Document Type", text="Record Date"')
            if await search_elements.count():
                _log("✅ Already on main search page - disclaimer may have been bypassed")
                disclaimer_accepted = True
            else:
                # Take a screenshot to help debug
                await page.screenshot(path="debug_brevard_disclaimer_not_found.png")
                _log("📸 Screenshot saved: debug_brevard_disclaimer_not_found.png")
                
                # Log page content for debugging
                page_text = await page.inner_text("body")
                _log(f"Page content preview: {page_text[:300]}...")
        
        # Wait a moment for any page transitions to complete
        await page.wait_for_timeout(2000)
        
        # Final check - see if we're on the search page now
        if disclaimer_accepted:
            search_page_indicators = [
                'text="Official Records Search"',
                'text="Document Type"', 
                'text="Record Date"',
                'text="Name"',
                'text="Book / Page"'
            ]
            
            for indicator in search_page_indicators:
                if await page.locator(indicator).count():
                    _log(f"✅ Confirmed on search page - found: {indicator}")
                    break
        
        return disclaimer_accepted
        
    except Exception as e:
        _log(f"❌ Error handling disclaimer: {e}")
        return False

async def _wait_for_page_load(page: Page, timeout: int = 30000):
    """Wait for the page to fully load"""
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout)
        
        # Look for key elements that indicate the search form is ready
        search_indicators = [
            "input[type='text']",  # Basic input fields
            "select",  # Dropdown selectors
            ".form-control",  # Bootstrap form controls
            "[name*='search']",  # Elements with search in name
        ]
        
        for indicator in search_indicators:
            try:
                await page.wait_for_selector(indicator, timeout=5000)
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

async def _set_custom_date_range(page: Page, from_date: str, to_date: str) -> bool:
    """Set custom date range using Record Date From and Record Date To input fields"""
    try:
        _log(f"📅 Setting custom date range: From {from_date} to {to_date}")
        
        # First, we need to select "Custom" from the date range dropdown to enable date inputs
        await _select_custom_date_option(page)
        
        # Wait for the date input fields to become visible
        await page.wait_for_timeout(2000)
        
        # STEP 1: Set "Record Date From" field
        from_date_selectors = [
            "input[name='RecordDateFrom']",              # Based on HTML structure from screenshot
            "input[id='RecordDateFrom']",                # Alternative ID format
            "input[name='RecordDateFrom-input']",        # Telerik input format
            "input[id='RecordDateFrom-input']",          # Telerik input ID format
            ".t-datepicker .t-input[name*='RecordDateFrom']",  # Telerik datepicker
            ".t-widget.t-datepicker .t-input:first",     # First datepicker widget
        ]
        
        from_date_set = False
        for selector in from_date_selectors:
            try:
                if await page.locator(selector).count():
                    _log(f"Found Record Date From field: {selector}")
                    
                    # Clear and set the from date
                    await page.locator(selector).first.clear()
                    await page.locator(selector).first.fill(from_date)
                    await page.keyboard.press("Tab")  # Trigger validation
                    _log(f"✅ Set Record Date From: {from_date}")
                    from_date_set = True
                    break
                    
            except Exception as e:
                _log(f"Warning: Could not use from date selector {selector}: {e}")
        
        if not from_date_set:
            _log("❌ Could not find or set Record Date From field")
            return False
        
        await page.wait_for_timeout(1000)
        
        # STEP 2: Set "Record Date To" field  
        to_date_selectors = [
            "input[name='RecordDateTo']",                # Based on HTML structure from screenshot
            "input[id='RecordDateTo']",                  # Alternative ID format
            "input[name='RecordDateTo-input']",          # Telerik input format
            "input[id='RecordDateTo-input']",            # Telerik input ID format
            ".t-datepicker .t-input[name*='RecordDateTo']",    # Telerik datepicker
            ".t-widget.t-datepicker .t-input:last",      # Last datepicker widget
        ]
        
        to_date_set = False
        for selector in to_date_selectors:
            try:
                if await page.locator(selector).count():
                    _log(f"Found Record Date To field: {selector}")
                    
                    # Clear and set the to date
                    await page.locator(selector).first.clear()
                    await page.locator(selector).first.fill(to_date)
                    await page.keyboard.press("Tab")  # Trigger validation
                    _log(f"✅ Set Record Date To: {to_date}")
                    to_date_set = True
                    break
                    
            except Exception as e:
                _log(f"Warning: Could not use to date selector {selector}: {e}")
        
        if not to_date_set:
            _log("❌ Could not find or set Record Date To field")
            return False
        
        await page.wait_for_timeout(1000)
        _log("✅ Custom date range set successfully")
        return True
        
    except Exception as e:
        _log(f"❌ Error setting custom date range: {e}")
        return False

async def _select_custom_date_option(page: Page) -> bool:
    """Select 'Custom' option from date range dropdown to enable manual date inputs"""
    try:
        _log("📅 Selecting 'Custom' from date range dropdown")
        
        # Target the specific DateRangeDropDown from the HTML structure
        date_range_selectors = [
            "#DateRangeDropDown .t-select",        # Specific ID + select element
            "#DateRangeDropDown .t-dropdown-wrap", # Specific ID + dropdown wrapper
            "#DateRangeDropDown",                  # Direct ID targeting
            ".t-widget.t-dropdown.t-header",       # Telerik widget classes
            "[id='DateRangeDropDown'] .t-input",   # ID with input element
        ]
        
        dropdown_opened = False
        for selector in date_range_selectors:
            try:
                element_count = await page.locator(selector).count()
                if element_count > 0:
                    _log(f"Found date range dropdown: {selector} (count: {element_count})")
                    
                    # Click to open the dropdown
                    await page.locator(selector).first.click()
                    _log(f"✅ Clicked date range dropdown: {selector}")
                    dropdown_opened = True
                    break
                    
            except Exception as e:
                _log(f"Warning: Could not use date range selector {selector}: {e}")
        
        if not dropdown_opened:
            _log("❌ Could not open date range dropdown")
            return False
        
        # Wait for dropdown options to appear
        await page.wait_for_timeout(1500)
        
        # Look for "Custom" option with more specific selectors
        custom_option_selectors = [
            "li:has-text('Custom')",           # List item
            ".t-item:has-text('Custom')",      # Telerik item
            ".t-state-default:has-text('Custom')", # Telerik state
            "[title='Custom']",                # Title attribute
            "text='Custom'",                   # Direct text match
            "span:has-text('Custom')",         # Span with text
            "[data-value='Custom']",           # Data value
        ]
        
        custom_selected = False
        for option_selector in custom_option_selectors:
            try:
                option_count = await page.locator(option_selector).count()
                if option_count > 0:
                    _log(f"Found 'Custom' option: {option_selector} (count: {option_count})")
                    await page.locator(option_selector).first.click()
                    _log("✅ Selected 'Custom' from dropdown")
                    custom_selected = True
                    break
            except Exception as e:
                _log(f"Warning: Could not click Custom option {option_selector}: {e}")
        
        if not custom_selected:
            _log("⚠️ Could not find 'Custom' option, date inputs may already be visible")
            # This might not be an error - some forms have date inputs always visible
        
        return True
        
    except Exception as e:
        _log(f"❌ Error selecting custom date option: {e}")
        return False

async def _set_preset_date_range(page: Page) -> bool:
    """Set preset date range to 'Last 7 Days' using dropdown"""
    try:
        # Target the specific DateRangeDropDown from the HTML structure
        date_range_selectors = [
            "#DateRangeDropDown .t-select",        # Specific ID + select element
            "#DateRangeDropDown .t-dropdown-wrap", # Specific ID + dropdown wrapper
            "#DateRangeDropDown",                  # Direct ID targeting
            ".t-widget.t-dropdown.t-header",       # Telerik widget classes
            "[id='DateRangeDropDown'] .t-input",   # ID with input element
        ]
        
        date_range_set = False
        for selector in date_range_selectors:
            try:
                element_count = await page.locator(selector).count()
                if element_count > 0:
                    _log(f"Found date range dropdown: {selector} (count: {element_count})")
                    
                    # Click to open the dropdown
                    await page.locator(selector).first.click()
                    _log(f"✅ Clicked date range dropdown: {selector}")
                    
                    # Wait for dropdown options to appear
                    await page.wait_for_timeout(1500)
                    
                    # Look for "Last 7 Days" option with more specific selectors
                    last_7_days_selectors = [
                        "li:has-text('Last 7 Days')",           # List item
                        ".t-item:has-text('Last 7 Days')",      # Telerik item
                        ".t-state-default:has-text('Last 7 Days')", # Telerik state
                        "[title='Last 7 Days']",                # Title attribute
                        "text='Last 7 Days'",                   # Direct text match
                        "span:has-text('Last 7 Days')",         # Span with text
                        "[data-value*='7']",                     # Data value with 7
                    ]
                    
                    option_found = False
                    for option_selector in last_7_days_selectors:
                        try:
                            option_count = await page.locator(option_selector).count()
                            if option_count > 0:
                                _log(f"Found 'Last 7 Days' option: {option_selector} (count: {option_count})")
                                await page.locator(option_selector).first.click()
                                _log("✅ Selected 'Last 7 Days' from dropdown")
                                date_range_set = True
                                option_found = True
                                break
                        except Exception as e:
                            _log(f"Warning: Could not click Last 7 Days option {option_selector}: {e}")
                    
                    if option_found:
                        break
                    else:
                        _log("⚠️ Dropdown opened but 'Last 7 Days' option not found")
                        # Take screenshot to debug dropdown contents
                        await page.screenshot(path="debug_brevard_dropdown_opened.png")
                        _log("📸 Screenshot saved: debug_brevard_dropdown_opened.png")
                        
            except Exception as e:
                _log(f"Warning: Could not use date range selector {selector}: {e}")
        
        # Alternative approach if direct targeting fails
        if not date_range_set:
            _log("🔄 Trying alternative date range selection approach...")
            try:
                # Look for any dropdown that might contain date options
                all_dropdowns = await page.locator(".t-dropdown, .t-widget").count()
                _log(f"Found {all_dropdowns} potential dropdown elements")
                
                # Try clicking any element that shows current date range
                current_range_selectors = [
                    ":has-text('Last')",
                    ":has-text('Days')", 
                    ":has-text('Custom')",
                    ".t-input:visible",
                ]
                
                for selector in current_range_selectors:
                    try:
                        if await page.locator(selector).count():
                            await page.locator(selector).first.click()
                            await page.wait_for_timeout(1000)
                            
                            # Try to find Last 7 Days in any visible list
                            if await page.locator("text='Last 7 Days'").count():
                                await page.locator("text='Last 7 Days'").first.click()
                                _log("✅ Selected 'Last 7 Days' via alternative method")
                                date_range_set = True
                                break
                    except Exception as e:
                        continue
                        
            except Exception as e:
                _log(f"Alternative approach also failed: {e}")
        
        if not date_range_set:
            _log("⚠️ Could not set date range to 'Last 7 Days' - continuing with default range")
        
        return date_range_set
        
    except Exception as e:
        _log(f"❌ Error setting preset date range: {e}")
        return False
async def _apply_search_filters(page: Page, from_date: str = None, to_date: str = None) -> bool:
    """Apply search filters: set date range and enter 'LIS PENDENS' document type
    
    Args:
        page: Playwright page object
        from_date: Start date in MM/DD/YYYY format (optional)
        to_date: End date in MM/DD/YYYY format (optional)
    """
    try:
        _log("🔍 Setting up search filters for Brevard County")
        
        # Wait for the form elements to be ready
        await page.wait_for_timeout(3000)
        
        # STEP 1: Set Date Range - either custom dates or "Last 7 Days"
        if from_date and to_date:
            _log(f"📅 Setting custom date range: {from_date} to {to_date}")
            custom_dates_set = await _set_custom_date_range(page, from_date, to_date)
            if not custom_dates_set:
                _log("⚠️ Failed to set custom dates, falling back to 'Last 7 Days'")
                await _set_preset_date_range(page)
        else:
            _log("📅 Setting date range to 'Last 7 Days'")
            await _set_preset_date_range(page)
        
        await page.wait_for_timeout(1000)
        
        # STEP 2: Enter "LIS PENDENS (LP)" in Document Type field
        _log("📋 Setting document type to 'LIS PENDENS (LP)'")
        
        # Based on the HTML, look for the document type input field
        doc_type_selectors = [
            "input[name='DocTypesDisplay-input']",  # From the HTML structure
            "input[id='DocTypesDisplay-input']",
            "textarea[name='DocTypes']",            # The hidden textarea
            "input[class*='t-input'][name*='DocTypes']",
            "input[autocomplete='off'][title*='LIS PENDENS']",
            "input[type='text'][name*='Doc']",      # Generic document input
        ]
        
        doc_type_set = False
        for selector in doc_type_selectors:
            try:
                if await page.locator(selector).count():
                    _log(f"Found document type input: {selector}")
                    
                    # Clear the field and enter "LIS PENDENS (LP)"
                    await page.locator(selector).first.clear()
                    await page.locator(selector).first.fill("LIS PENDENS (LP)")
                    _log("✅ Entered 'LIS PENDENS (LP)' in document type field")
                    
                    # Press Tab or Enter to trigger autocomplete/selection
                    await page.keyboard.press("Tab")
                    await page.wait_for_timeout(1000)
                    
                    doc_type_set = True
                    break
                    
            except Exception as e:
                _log(f"Warning: Could not use document type selector {selector}: {e}")
        
        # Alternative approach: Try to find and select from document type dropdown/autocomplete
        if not doc_type_set:
            _log("🔄 Trying alternative document type selection method")
            
            # Look for document type dropdown or autocomplete
            doc_dropdown_selectors = [
                ".t-widget.t-combobox .t-input",
                ".t-combobox .t-input", 
                "[class*='combobox'] input",
                ".t-dropdown .t-input",
            ]
            
            for selector in doc_dropdown_selectors:
                try:
                    if await page.locator(selector).count():
                        _log(f"Found document type dropdown: {selector}")
                        
                        # Click to open dropdown
                        await page.locator(selector).first.click()
                        await page.wait_for_timeout(500)
                        
                        # Type "LIS PENDENS" to filter options (partial to trigger autocomplete)
                        await page.locator(selector).first.fill("LIS PENDENS")
                        await page.wait_for_timeout(1000)
                        
                        # Look for LIS PENDENS (LP) option in dropdown - prioritize the (LP) version
                        lis_pendens_options = [
                            "text='LIS PENDENS (LP)'",              # Exact match with (LP)
                            ".t-item:has-text('LIS PENDENS (LP)')", # Telerik item with (LP)
                            "li:has-text('LIS PENDENS (LP)')",      # List item with (LP)
                            "[data-value='LIS PENDENS (LP)']",      # Data value with (LP)
                            ":has-text('LIS PENDENS (LP)')",        # Any element with (LP)
                            "text='LIS PENDENS'",                   # Fallback without (LP)
                            ".t-item:has-text('LIS PENDENS')",      # Fallback Telerik item
                            "li:has-text('LIS PENDENS')",           # Fallback list item
                            "[data-value*='LIS PENDENS']",          # Fallback data value
                        ]
                        
                        for option in lis_pendens_options:
                            try:
                                if await page.locator(option).count():
                                    option_text = await page.locator(option).first.inner_text()
                                    await page.locator(option).first.click()
                                    _log(f"✅ Selected LIS PENDENS option: '{option_text}' using {option}")
                                    doc_type_set = True
                                    break
                            except Exception as e:
                                _log(f"Warning: Could not select LIS PENDENS option {option}: {e}")
                        
                        if doc_type_set:
                            break
                            
                except Exception as e:
                    _log(f"Warning: Could not use document dropdown selector {selector}: {e}")
        
        if not doc_type_set:
            _log("⚠️ Could not set document type to 'LIS PENDENS (LP)' - search may return all document types")
        
        # Wait for any UI updates
        await page.wait_for_timeout(2000)
        
        # Take a screenshot after setting filters
        await page.screenshot(path="debug_brevard_filters_applied.png")
        _log("📸 Screenshot saved: debug_brevard_filters_applied.png")
        
        _log("✅ Search filters configuration completed")
        return True
        
    except Exception as e:
        _log(f"❌ Error applying search filters: {e}")
        return False

async def _execute_search(page: Page) -> bool:
    """Execute the search by clicking submit button and waiting for SearchGridContainer"""
    try:
        _log("🔍 Executing search by clicking submit button...")
        
        # Target the specific submit button from the HTML structure
        search_button_selectors = [
            "input[id='btnSearch'][value='Search']",  # Exact match from HTML
            "input[type='submit'][value='Search']",   # Generic submit with Search value
            "#btnSearch",                             # ID selector
            "input[onclick*='Asyncform.handleSubmit']", # Based on onclick handler
            "form#schfrm input[type='submit']",       # Submit button in the search form
        ]
        
        search_clicked = False
        for selector in search_button_selectors:
            try:
                if await page.locator(selector).count():
                    _log(f"Found search button: {selector}")
                    await page.locator(selector).first.click()
                    _log(f"✅ Clicked search button using {selector}")
                    search_clicked = True
                    break
            except Exception as e:
                _log(f"Warning: Could not click search button with {selector}: {e}")
        
        if not search_clicked:
            _log("❌ Could not find or click search button")
            return False
        
        # Wait for the SearchGridContainer to appear (indicates results are loading/loaded)
        _log("⏳ Waiting for SearchGridContainer to appear...")
        
        try:
            # Wait for the SearchGridContainer to be visible
            await page.wait_for_selector("#SearchGridContainer", timeout=30000)
            _log("✅ SearchGridContainer appeared - results container is ready")
            
            # Drill down into the SearchGridContainer structure
            # Based on HTML: SearchGridContainer > gridDiv > searchGridDiv > t-widget t-grid
            search_grid_selectors = [
                "#SearchGridContainer .gridDiv",                    # Grid div within container
                "#SearchGridContainer .searchGridDiv",              # Search grid div
                "#SearchGridContainer .t-widget.t-grid",            # Telerik grid widget
                "#SearchGridContainer #RsltsGrid",                  # Results grid by ID
                "#SearchGridContainer [class*='grid']",             # Any grid class within container
            ]
            
            grid_found = False
            for selector in search_grid_selectors:
                try:
                    element_count = await page.locator(selector).count()
                    if element_count > 0:
                        _log(f"Found grid element: {selector} (count: {element_count})")
                        await page.wait_for_selector(selector, timeout=15000)
                        grid_found = True
                        break
                except Exception as e:
                    _log(f"Warning: Could not find grid element {selector}: {e}")
            
            if not grid_found:
                _log("⚠️ Could not find specific grid elements within SearchGridContainer")
            
            # Wait for the actual results grid and data to be populated
            results_ready_selectors = [
                "#RsltsGrid",                                       # Primary results grid
                "#SearchGridContainer .t-grid-content",             # Telerik grid content
                "#SearchGridContainer tbody",                       # Table body with data
                "#SearchGridContainer .t-grid-header",              # Grid header (indicates structure loaded)
            ]
            
            results_loaded = False
            for selector in results_ready_selectors:
                try:
                    element_count = await page.locator(selector).count()
                    if element_count > 0:
                        _log(f"Found results element: {selector} (count: {element_count})")
                        await page.wait_for_selector(selector, timeout=15000)
                        results_loaded = True
                        break
                except Exception as e:
                    _log(f"Warning: Could not find results element {selector}: {e}")
            
            if results_loaded:
                _log("✅ Results grid structure is ready")
            else:
                _log("⚠️ Results grid structure not detected")
            
            # Wait for the grid to be fully populated with data
            await page.wait_for_timeout(3000)
            
            # Check for actual data rows with multiple targeting strategies
            result_row_selectors = [
                "#RsltsGrid tbody tr",                              # Primary table rows
                "#SearchGridContainer tbody tr",                    # Rows within container
                "#SearchGridContainer .t-grid-content tr",          # Telerik content rows
                "#SearchGridContainer [role='row']",                # ARIA role rows
                "#SearchGridContainer .t-master-row",               # Telerik master rows
            ]
            
            row_count = 0
            for selector in result_row_selectors:
                try:
                    count = await page.locator(selector).count()
                    if count > 0:
                        row_count = count
                        _log(f"📊 Found {row_count} rows using selector: {selector}")
                        break
                except Exception as e:
                    _log(f"Warning: Could not count rows with {selector}: {e}")
            
            # Additional check for "no results" message
            no_results_selectors = [
                "#SearchGridContainer:has-text('No records')",
                "#SearchGridContainer:has-text('No results')",
                "#SearchGridContainer .t-grid-norecords",
                "#SearchGridContainer:has-text('0 items')",
            ]
            
            for selector in no_results_selectors:
                try:
                    if await page.locator(selector).count():
                        _log("ℹ️ 'No results' message detected")
                        row_count = 0
                        break
                except Exception:
                    continue
            
            if row_count == 0:
                _log("⚠️ No results found in the grid")
                return True  # Return True but with no results to process
            else:
                _log(f"✅ Search completed successfully with {row_count} potential results")
                
                # STEP 1: Change page size to 25 via dropdown
                await _set_page_size_to_25(page)
                
                # STEP 2: Click Export to CSV button and get the downloaded file
                csv_file_path = await _click_export_csv(page)
                if csv_file_path:
                    _log(f"✅ CSV export successful: {csv_file_path}")
                    return csv_file_path  # Return the path to the downloaded CSV
                else:
                    _log("❌ CSV export failed")
                    return False
            
            return True
            
        except Exception as e:
            _log(f"❌ Timeout waiting for search results: {e}")
            
            # Take a screenshot to debug what happened
            try:
                await page.screenshot(path="debug_brevard_search_timeout.png", timeout=5000)
                _log("📸 Screenshot saved: debug_brevard_search_timeout.png")
            except Exception as screenshot_error:
                _log(f"⚠️ Could not take timeout screenshot: {screenshot_error}")
            
            # Check if we're still on the same page or if there's an error
            page_content = await page.inner_text("body")
            if "error" in page_content.lower() or "exception" in page_content.lower():
                _log("❌ Page shows an error after search")
            else:
                _log("⚠️ Search may have completed but grid container not found")
            
            return False
        
    except Exception as e:
        _log(f"❌ Error executing search: {e}")
        try:
            await page.screenshot(path="debug_brevard_search_error.png", timeout=5000)
            _log("📸 Error screenshot saved: debug_brevard_search_error.png")
        except Exception as screenshot_error:
            _log(f"⚠️ Could not take search error screenshot: {screenshot_error}")
        return False

async def _set_page_size_to_25(page: Page) -> bool:
    """Change the page size dropdown from 50 to 25 to show 25 records per page"""
    try:
        _log("📄 Setting page size to 25...")
        
        # Look for the page size dropdown - using correct HTML structure
        page_size_selectors = [
            ".t-page-size .t-select",                    # Exact page size select element
            ".t-page-size .t-dropdown-wrap .t-select",   # Page size dropdown wrapper + select
            ".t-page-size .t-dropdown .t-select",        # Page size dropdown + select
            ".t-page-size .t-dropdown-wrap",             # Page size dropdown wrapper
            ".t-page-size",                              # Page size container
        ]
        
        dropdown_clicked = False
        for selector in page_size_selectors:
            try:
                if await page.locator(selector).count():
                    _log(f"Found page size dropdown: {selector}")
                    await page.locator(selector).first.click()
                    _log("✅ Clicked page size dropdown")
                    dropdown_clicked = True
                    break
            except Exception as e:
                _log(f"Warning: Could not click dropdown with {selector}: {e}")
        
        if not dropdown_clicked:
            _log("⚠️ Could not find or click page size dropdown")
            return False
        
        # Wait for dropdown options to appear
        await page.wait_for_timeout(1000)
        
        # Look for the "25" option in the dropdown
        option_25_selectors = [
            "text='25'",                       # Direct text match
            ".t-item:has-text('25')",         # Telerik item with text 25
            "li:has-text('25')",              # List item with 25
            "[data-value='25']",              # Data value attribute
            ".t-state-default:has-text('25')", # Telerik state with 25
        ]
        
        option_selected = False
        for selector in option_25_selectors:
            try:
                if await page.locator(selector).count():
                    await page.locator(selector).first.click()
                    _log(f"✅ Selected '25' option using {selector}")
                    option_selected = True
                    break
            except Exception as e:
                _log(f"Warning: Could not select 25 option with {selector}: {e}")
        
        if not option_selected:
            _log("⚠️ Could not find or select '25' option")
            return False
        
        # Wait for the page to update with new page size
        await page.wait_for_timeout(2000)
        
        # Verify the change took effect
        try:
            current_page_size = await page.locator(".t-dropdown .t-input").inner_text()
            if "25" in current_page_size:
                _log("✅ Page size successfully changed to 25")
            else:
                _log(f"⚠️ Page size may not have changed (shows: {current_page_size})")
        except:
            _log("⚠️ Could not verify page size change")
        
        return True
        
    except Exception as e:
        _log(f"❌ Error setting page size to 25: {e}")
        return False

async def _click_export_csv(page: Page) -> Optional[str]:
    """Click the Export to CSV button to download the results and return the downloaded file path"""
    try:
        _log("📥 Clicking Export to CSV button...")
        
        # Set up download handling
        download_path = EXPORT_DIR / f"brevard_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        # Look for the Export to CSV button - using correct HTML structure
        export_csv_selectors = [
            "a[id='btnCsv']",                        # Exact anchor tag with ID from HTML
            "#btnCsv",                               # ID selector
            "a.csvButton",                           # Anchor with csvButton class
            ".csvButton",                            # csvButton class selector
            "a[href*='ExportCsv']",                  # Anchor with ExportCsv in href
            "a:has-text('Export to CSV')",           # Anchor with Export to CSV text
        ]
        
        export_clicked = False
        for selector in export_csv_selectors:
            try:
                if await page.locator(selector).count():
                    _log(f"Found Export to CSV button: {selector}")
                    
                    # Start waiting for download before clicking
                    async with page.expect_download() as download_info:
                        await page.locator(selector).first.click()
                        _log("✅ Clicked Export to CSV button")
                    
                    # Get the download and save it
                    download = await download_info.value
                    await download.save_as(download_path)
                    _log(f"✅ CSV downloaded and saved to: {download_path}")
                    export_clicked = True
                    break
                    
            except Exception as e:
                _log(f"Warning: Could not click export button with {selector}: {e}")
        
        if not export_clicked:
            _log("❌ Could not find or click Export to CSV button")
            return None
        
        # Verify the file was downloaded and has content
        if download_path.exists() and download_path.stat().st_size > 0:
            _log(f"✅ CSV file successfully downloaded: {download_path} ({download_path.stat().st_size} bytes)")
            return str(download_path)
        else:
            _log("❌ CSV download failed or file is empty")
            return None
        
    except Exception as e:
        _log(f"❌ Error downloading CSV: {e}")
        return None

async def _process_downloaded_csv(csv_file_path: str) -> List[dict]:
    """Process the downloaded CSV file and convert it to database records"""
    try:
        _log(f"📊 Processing downloaded CSV: {csv_file_path}")
        
        # Read the CSV file
        df = pd.read_csv(csv_file_path)
        _log(f"✅ CSV loaded successfully with {len(df)} rows and {len(df.columns)} columns")
        
        # Log the column names to understand the structure
        _log(f"CSV columns: {list(df.columns)}")
        
        # Preview first few rows for debugging
        if len(df) > 0:
            _log(f"Sample data (first row): {df.iloc[0].to_dict()}")
        
        records = []
        existing_case_numbers = await get_existing_case_numbers()
        _log(f"Found {len(existing_case_numbers)} existing records in database")
        
        for index, row in df.iterrows():
            try:
                # Map CSV columns to our database fields
                # Note: Column names will depend on Brevard County's CSV export format
                # Common possible column names in official records systems:
                record_data = {}
                
                # Try to map common CSV column variations to our fields
                column_mapping = {
                    # Document identification
                    'case_number': ['Case Number', 'Case #', 'Document Number', 'Doc Number', 'Document#', 'Doc#', 'Record Number', 'Instrument Number'],
                    'case_type': ['Case Type', 'Document Type', 'Doc Type', 'Type', 'Instrument Type'],
                    'file_date': ['File Date', 'Record Date', 'Recorded Date', 'Date Recorded', 'Filing Date', 'Date'],
                    'party_name': ['Party Name', 'First Indirect Name', 'Grantor', 'Grantor Name', 'From Party', 'First Party'],
                    'property_address': ['Property Address', 'First Legal Description', 'Legal Description', 'Address', 'Property Location'],
                }
                
                # Map the CSV data to our fields
                for field, possible_columns in column_mapping.items():
                    value = ""
                    for col_name in possible_columns:
                        if col_name in df.columns and pd.notna(row[col_name]):
                            value = str(row[col_name]).strip()
                            break
                    record_data[field] = value
                
                # If we can't find standard columns, use positional mapping as fallback
                if not record_data.get('case_number') and len(df.columns) > 0:
                    # Try to find case number in any column that looks like a number/ID
                    for col in df.columns:
                        cell_value = str(row[col]).strip()
                        # Look for patterns that might be case numbers
                        if re.search(r'\d{6,}', cell_value) or 'OR' in cell_value or 'DOC' in cell_value.upper():
                            record_data['case_number'] = cell_value
                            break
                
                # Generate a case number if still empty
                if not record_data.get('case_number'):
                    record_data['case_number'] = f"BREVARD_{datetime.now().strftime('%Y%m%d')}_{index+1:04d}"
                
                # Skip if this record already exists in database
                if record_data['case_number'] in existing_case_numbers:
                    _log(f"Skipping existing record: {record_data['case_number']}")
                    continue
                
                # Add metadata fields
                current_time = datetime.now()
                record_data.update({
                    'document_url': "",  # CSV export doesn't include URLs
                    'county': COUNTY_NAME,
                    'created_at': current_time,
                    'is_new': True,
                    'userId': USER_ID,
                })
                
                records.append(record_data)
                _log(f"✅ Processed record {len(records)}: {record_data['case_number']}")
                
            except Exception as e:
                _log(f"❌ Error processing CSV row {index+1}: {e}")
                continue
        
        _log(f"✅ Successfully processed {len(records)} new records from CSV")
        return records
        
    except Exception as e:
        _log(f"❌ Error processing CSV file: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────────────
# DATA EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────
async def _extract_records_from_results(page: Page, max_records: int = 100) -> List[BrevardRecord]:
    """Extract record data from search results - handles Acclaim system format"""
    records = []
    seen_document_numbers = set()  # Track document numbers to avoid duplicates
    
    try:
        # Take a screenshot for debugging
        try:
            await page.screenshot(path="debug_brevard_results.png", timeout=5000)
            _log("📸 Screenshot saved: debug_brevard_results.png")
        except Exception as e:
            _log(f"⚠️ Could not take results screenshot: {e}")
        
        # Get existing case numbers to check against
        try:
            existing_case_numbers = await get_existing_case_numbers()
            _log(f"📊 Found {len(existing_case_numbers)} existing records in database")
        except Exception as e:
            _log(f"⚠️ Could not fetch existing records: {e}")
            existing_case_numbers = set()
        
        # Look for results in Acclaim system format
        results_selectors = [
            "table[class*='results']",
            "table[id*='results']", 
            ".searchResultsTable",
            "table[class*='grid']",
            "table[class*='data']",
            "tbody tr",  # More generic table rows
            "table",
        ]
        
        results_found = False
        for selector in results_selectors:
            try:
                elements = await page.locator(selector).count()
                if elements > 0:
                    _log(f"✅ Found {elements} elements using '{selector}'")
                    
                    # Try to extract data from this element type
                    if "tr" in selector or "table" in selector:
                        # Handle table rows
                        if "tr" in selector:
                            rows = page.locator(selector)
                        else:
                            rows = page.locator(selector).locator("tr")
                        
                        row_count = await rows.count()
                        _log(f"Found {row_count} rows in results")
                        
                        # Skip header row (usually first row)
                        start_row = 1 if row_count > 1 else 0
                        
                        for i in range(start_row, min(row_count, max_records + start_row)):
                            try:
                                row = rows.nth(i)
                                cells = row.locator("td, th")
                                cell_count = await cells.count()
                                
                                if cell_count < 3:  # Skip rows with too few cells
                                    continue
                                
                                # Extract cell data
                                cell_texts = []
                                cell_links = []
                                for j in range(cell_count):
                                    try:
                                        cell = cells.nth(j)
                                        cell_text = await cell.inner_text()
                                        cell_texts.append(cell_text.strip())
                                        
                                        # Also check for links in this cell
                                        link = cell.locator("a")
                                        if await link.count():
                                            href = await link.first.get_attribute("href")
                                            if href:
                                                cell_links.append(href)
                                    except:
                                        cell_texts.append("")
                                
                                # Map to record structure - Acclaim systems typically have:
                                # [Document#, Date, Doc Type, Grantor, Grantee, Book/Page, Consideration, etc.]
                                document_number = ""
                                
                                # Look for document number in various cells
                                for cell_text in cell_texts:
                                    # Look for patterns like clerk file numbers or document numbers
                                    doc_patterns = [
                                        r'(\d{8,})',        # 8+ digit numbers
                                        r'(\d{4,}-\d+)',    # Pattern like 2024-123456
                                        r'(OR\d+)',         # Official Records pattern
                                        r'(\d{6,})',        # 6+ digit numbers
                                    ]
                                    
                                    for pattern in doc_patterns:
                                        match = re.search(pattern, cell_text)
                                        if match:
                                            document_number = match.group(1)
                                            break
                                    if document_number:
                                        break
                                
                                if not document_number:
                                    _log(f"Skipping row {i+1} - no document number found")
                                    continue
                                
                                # Check for duplicates
                                if document_number in seen_document_numbers:
                                    _log(f"Skipping duplicate document number: {document_number}")
                                    continue
                                seen_document_numbers.add(document_number)
                                
                                # Check if this record already exists in database
                                if document_number in existing_case_numbers:
                                    _log(f"Skipping existing record: {document_number}")
                                    continue
                                
                                # Extract other fields based on typical Acclaim layout
                                recorded_date = ""
                                document_type = ""
                                grantor = ""
                                grantee = ""
                                book_page = ""
                                consideration = ""
                                
                                # Parse cell contents for specific field types
                                for cell_text in cell_texts:
                                    # Look for date patterns
                                    if not recorded_date and re.search(r'\d{1,2}/\d{1,2}/\d{4}', cell_text):
                                        recorded_date = cell_text
                                    
                                    # Look for document types
                                    doc_types = ["LIS PENDENS", "LIEN", "MORTGAGE", "DEED", "FORECLOSURE", "NOTICE"]
                                    if not document_type and any(dt in cell_text.upper() for dt in doc_types):
                                        document_type = cell_text
                                    
                                    # Look for dollar amounts (consideration)
                                    if not consideration and re.search(r'\$[\d,]+', cell_text):
                                        consideration = cell_text
                                    
                                    # Look for book/page patterns
                                    if not book_page and re.search(r'(Book|Bk)\s*\d+.*Page\s*\d+', cell_text, re.IGNORECASE):
                                        book_page = cell_text
                                
                                # If we don't have enough specific data, use positional mapping
                                if len(cell_texts) >= 5:
                                    if not recorded_date:
                                        recorded_date = cell_texts[1] if len(cell_texts) > 1 else ""
                                    if not document_type:
                                        document_type = cell_texts[2] if len(cell_texts) > 2 else ""
                                    if not grantor:
                                        grantor = cell_texts[3] if len(cell_texts) > 3 else ""
                                    if not grantee:
                                        grantee = cell_texts[4] if len(cell_texts) > 4 else ""
                                    if not book_page:
                                        book_page = cell_texts[5] if len(cell_texts) > 5 else ""
                                    if not consideration:
                                        consideration = cell_texts[6] if len(cell_texts) > 6 else ""
                                
                                # Create document URL if we found links
                                document_url = None
                                if cell_links:
                                    document_url = cell_links[0]
                                    if not document_url.startswith(('http://', 'https://')):
                                        document_url = urljoin(BASE_URL, document_url)
                                
                                record_data = {
                                    'document_number': document_number,
                                    'document_type': document_type,
                                    'recorded_date': recorded_date,
                                    'grantor': grantor,
                                    'grantee': grantee,
                                    'book_page': book_page,
                                    'consideration': consideration,
                                    'legal_description': "",
                                    'property_address': "",
                                    'document_url': document_url,
                                }
                                
                                # Clean and format the data
                                record_data = _clean_record_data(record_data)
                                records.append(record_data)
                                
                                _log(f"✅ Extracted record {len(records)}: Doc#{record_data['document_number']}, "
                                     f"Type: {record_data['document_type']}, "
                                     f"Date: {record_data['recorded_date']}")
                                
                                # Stop when we reach max records
                                if len(records) >= max_records:
                                    _log(f"✅ Reached maximum of {max_records} records")
                                    break
                                
                            except Exception as e:
                                _log(f"❌ Error extracting record {i+1}: {e}")
                                continue
                        
                        if records:
                            results_found = True
                            break
                    
            except Exception as e:
                _log(f"Warning: Could not use results selector '{selector}': {e}")
        
        if not results_found:
            _log("❌ Could not find any results in expected format")
            
            # Try a more generic approach - look for any text that looks like results
            page_text = await page.inner_text("body")
            if "no results" in page_text.lower() or "no records" in page_text.lower():
                _log("🔍 Page indicates no results found")
            else:
                _log("🔍 Page may have results but couldn't parse them")
                _log(f"Page content preview: {page_text[:500]}...")
        
        _log(f"✅ Successfully extracted {len(records)} unique records")
        return records
        
    except Exception as e:
        _log(f"❌ Error extracting records from results: {e}")
        return records

async def _extract_document_url(row) -> Optional[str]:
    """Extract document URL if available"""
    link_selectors = [
        "a[href]",
        ".doc-link",
        "[onclick*='view']",
        "[onclick*='open']",
    ]
    
    for selector in link_selectors:
        try:
            element = row.locator(selector)
            if await element.count():
                href = await element.first.get_attribute("href")
                if href:
                    if not href.startswith(('http://', 'https://')):
                        return urljoin(BASE_URL, href)
                    return href
        except Exception:
            continue
    
    return None

def _clean_record_data(record_data: dict) -> BrevardRecord:
    """Clean and standardize record data"""
    
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

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────
async def get_existing_case_numbers() -> set:
    """Get existing case numbers from database to avoid duplicates"""
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                text("SELECT case_number FROM brevard_fl_filing WHERE county = :county"),
                {"county": COUNTY_NAME}
            )
            return {row[0] for row in result.fetchall()}
    except Exception as e:
        _log(f"Error getting existing case numbers: {e}")
        return set()

async def upsert_records(records: List[dict]):
    """Insert or update records in database"""
    if not records:
        return
    
    try:
        async with AsyncSession(engine) as session:
            for record in records:
                # Convert file_date string to datetime object if present
                file_date_obj = None
                file_date_str = record.get('file_date', '')
                if file_date_str:
                    try:
                        file_date_obj = datetime.strptime(file_date_str, '%Y-%m-%d')
                    except Exception as e:
                        _log(f"Warning: Could not parse file_date '{file_date_str}': {e}")
                
                # Update the record with the parsed date
                record['file_date'] = file_date_obj
                
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
    csv_path = EXPORT_DIR / f"brevard_fl_records_{timestamp}.csv"
    
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
        worksheet = sheet.worksheet(BREVARD_TAB)
        
        # Clear existing data and add new data
        worksheet.clear()
        worksheet.update([df.columns.values.tolist()] + df.values.tolist())
        
        _log(f"✅ Uploaded {len(df)} records to Google Sheets")
        
    except Exception as e:
        _log(f"Error uploading to Google Sheets: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN EXECUTION
# ─────────────────────────────────────────────────────────────────────────────
async def run(max_new_records: int = MAX_NEW_RECORDS, test_mode: bool = False, from_date: str = None, to_date: str = None):
    """Main execution function
    
    Args:
        max_new_records: Maximum number of new records to scrape
        test_mode: Run in test mode without database operations
        from_date: Start date in MM/DD/YYYY format (optional)
        to_date: End date in MM/DD/YYYY format (optional)
    """
    _log(f"🚀 Starting Brevard County FL scraper (max {max_new_records} records)")
    
    if from_date and to_date:
        _log(f"📅 Using custom date range: {from_date} to {to_date}")
    else:
        _log("📅 Using default date range: Last 7 Days")
    
    if test_mode:
        _log("🧪 Running in TEST MODE - no database operations")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Minimize browser after 5 seconds
        if not test_mode and not HEADLESS:
            try:
                _log("[TIMER] Browser will minimize in 5 seconds - please click 'Agree' on any disclaimers if needed...")
                await page.wait_for_timeout(5000)
                
                try:
                    for w in gw.getWindowsWithTitle('Chromium'):
                        w.minimize()
                    _log("[SUCCESS] Browser minimized using pygetwindow")
                except Exception as e:
                    _log(f"[WARNING] Could not minimize browser window: {e}")
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
                await page.screenshot(path="debug_brevard_initial.png", timeout=5000)
                _log("Screenshot saved: debug_brevard_initial.png")
            except Exception as e:
                _log(f"⚠️ Could not take initial screenshot: {e}")
            
            # Apply search filters
            if await _apply_search_filters(page, from_date, to_date):
                _log("✅ Search filters applied")
            else:
                _log("❌ Failed to apply search filters")
                return
            
            # Execute search and get CSV file path
            search_result = await _execute_search(page)
            if search_result == False:
                _log("❌ Failed to execute search")
                return
            elif search_result == True:
                _log("ℹ️ Search completed but no results to process")
                return
            elif isinstance(search_result, str):
                # We got a CSV file path
                csv_file_path = search_result
                _log(f"✅ Search executed and CSV exported: {csv_file_path}")
                
                # Process the downloaded CSV file
                new_records = await _process_downloaded_csv(csv_file_path)
                
                if not new_records:
                    _log("No new records found in CSV")
                    return
                
                _log(f"✅ Found {len(new_records)} new records in CSV")
            else:
                _log("❌ Unexpected search result")
                return
            
            # Create DataFrame for additional processing
            df = pd.DataFrame(new_records)
            
            # The original CSV from the website is already saved
            # Create an additional processed CSV with our standardized data
            processed_csv_path = await _export_csv(df)
            _log(f"✅ Created processed CSV: {processed_csv_path}")
            _log(f"📄 Original CSV from website: {csv_file_path}")
            
            if test_mode:
                _log("🧪 TEST MODE: Skipping database and Google Sheets operations")
                _log(f"✅ TEST COMPLETED - Found {len(new_records)} records")
                
                # Show first few records for review
                _log("📋 Sample records found:")
                for i, record in enumerate(new_records[:3]):
                    _log(f"  {i+1}. Doc: {record.get('document_number', 'N/A')}, "
                         f"Date: {record.get('recorded_date', 'N/A')}, "
                         f"Type: {record.get('document_type', 'N/A')}")
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
            try:
                await page.screenshot(path="debug_brevard_error.png", timeout=5000)
                _log("Error screenshot saved: debug_brevard_error.png")
            except Exception as screenshot_error:
                _log(f"⚠️ Could not take error screenshot: {screenshot_error}")
            raise
        
        finally:
            if test_mode:
                _log("🖥️  Browser will stay open for 10 seconds for inspection...")
                await page.wait_for_timeout(10000)
            await browser.close()

async def main():
    """Command line entry point"""
    parser = argparse.ArgumentParser(description="Brevard County FL Registry Scraper")
    parser.add_argument("--max-records", type=int, default=MAX_NEW_RECORDS,
                        help=f"Maximum number of new records to scrape (default: {MAX_NEW_RECORDS})")
    parser.add_argument("--user-id", type=str, 
                        help="User ID for database records (required unless using --test-mode)")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser in headless mode")
    parser.add_argument("--test-mode", action="store_true",
                        help="Run in test mode without database operations")
    parser.add_argument("--from-date", type=str, 
                        help="Start date for search in MM/DD/YYYY format (e.g., 01/15/2024)")
    parser.add_argument("--to-date", type=str,
                        help="End date for search in MM/DD/YYYY format (e.g., 01/22/2024)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.test_mode and not args.user_id:
        parser.error("--user-id is required unless using --test-mode")
    
    # Validate date arguments
    if (args.from_date and not args.to_date) or (args.to_date and not args.from_date):
        parser.error("Both --from-date and --to-date must be provided together")
    
    if args.from_date and args.to_date:
        # Validate date format
        import re
        date_pattern = r'^\d{1,2}/\d{1,2}/\d{4}$'
        if not re.match(date_pattern, args.from_date):
            parser.error("--from-date must be in MM/DD/YYYY format (e.g., 01/15/2024)")
        if not re.match(date_pattern, args.to_date):
            parser.error("--to-date must be in MM/DD/YYYY format (e.g., 01/22/2024)")
        
        # Validate date order
        try:
            from datetime import datetime
            from_dt = datetime.strptime(args.from_date, '%m/%d/%Y')
            to_dt = datetime.strptime(args.to_date, '%m/%d/%Y')
            if from_dt > to_dt:
                parser.error("--from-date must be earlier than or equal to --to-date")
        except ValueError as e:
            parser.error(f"Invalid date format: {e}")
    
    global USER_ID, HEADLESS
    USER_ID = args.user_id
    HEADLESS = args.headless
    
    # Override headless mode in test mode to show browser
    if args.test_mode:
        HEADLESS = False
        _log("🧪 TEST MODE: Browser will be visible")
    
    await run(
        max_new_records=args.max_records, 
        test_mode=args.test_mode,
        from_date=args.from_date,
        to_date=args.to_date
    )

if __name__ == "__main__":
    # Example usage:
    # python BrevardFL.py --user-id "user123" --max-records 10
    # python BrevardFL.py --test-mode --max-records 5
    # python BrevardFL.py --user-id "user123" --from-date "01/15/2024" --to-date "01/22/2024"
    # python BrevardFL.py --test-mode --from-date "12/01/2023" --to-date "12/31/2023" --max-records 15
    asyncio.run(main()) 