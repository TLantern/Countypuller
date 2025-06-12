"""
Cobb County Georgia Real Estate Index Scraper

This script scrapes real estate records for Cobb County, Georgia from the
Georgia Superior Court Clerks' Cooperative Authority (GSCCCA) system.

Website: https://search.gsccca.org/RealEstate/namesearch.asp

Features:
- Searches for recent Cobb County real estate records by date range
- Filters by instrument type (deed foreclosures, etc.)
- Extracts structured data including case numbers, parties, dates
- Prevents duplicate records via database checking
- Exports results to CSV and optionally Google Sheets
- Supports test mode for development/debugging

Dependencies:
- Base scraper infrastructure (base_scrapers.py, config_schemas.py)
- playwright (browser automation)
- pandas (data manipulation)
- sqlalchemy (database operations)

Usage:
    python CobbGA.py --user-id your_user_id [--test] [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD]
    
Environment Variables Required:
    - DB_URL: Database connection string
    - GSCCCA_USERNAME: Login username for GSCCCA
    - GSCCCA_PASSWORD: Login password for GSCCCA
    - COBB_TAB: Google Sheets tab name (optional)
"""

import asyncio
import os
import pandas as pd
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import urljoin, parse_qs, urlparse
import argparse
import json
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

# Third-party imports
from playwright.async_api import Browser, BrowserContext, Page
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# OCR imports
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import numpy as np

# Configure Tesseract path for Windows
if os.name == 'nt':  # Windows
    # Check for custom path from environment variable first
    custom_tesseract_path = os.getenv('TESSERACT_PATH')
    if custom_tesseract_path and os.path.exists(custom_tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = custom_tesseract_path
        print(f"✅ Using custom Tesseract path: {custom_tesseract_path}")
    else:
        # Common Tesseract installation paths on Windows
        tesseract_paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\%USERNAME%\AppData\Local\Programs\Tesseract-OCR\tesseract.exe',
        ]
        
        # Try to find Tesseract executable
        for path in tesseract_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                pytesseract.pytesseract.tesseract_cmd = expanded_path
                print(f"✅ Found Tesseract at: {expanded_path}")
                break
        else:
            # If not found in common paths, provide instructions
            print("⚠️ Tesseract not found in common installation paths.")
            print("📥 Please install Tesseract OCR:")
            print("   1. Download from: https://github.com/UB-Mannheim/tesseract/wiki") 
            print("   2. Install to default location")
            print("   3. Or set TESSERACT_PATH environment variable to tesseract.exe path")

# Local imports
from base_scrapers import SearchFormScraper, ScrapingRecord, ScrapingResult
from config_schemas import CountyConfig

# Constants - Updated for Cobb County
BASE_URL = "https://search.gsccca.org/RealEstate/namesearch.asp"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
MAX_NEW_RECORDS = 200
GSCCCA_TIMEOUT = 30000  # 30 seconds timeout

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
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
OCR_TEXT_DIR = Path("ocr_text_outputs"); OCR_TEXT_DIR.mkdir(exist_ok=True)
USER_ID = None  # Will be set from command line argument
COUNTY_NAME = "Cobb GA"

# Environment variables
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME = os.getenv("GSHEET_NAME")
COBB_TAB = os.getenv("COBB_TAB", "CobbGA")
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise Exception("DB_URL environment variable is required")

# Database configuration
engine = create_async_engine(DB_URL, echo=False)

# You'll need to create this table first:
# CREATE TABLE fulton_ga_filing (
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
   county, book_page, document_link, state, created_at, updated_at, is_new, 
   "userId", parsed_address, ocr_text_file, screenshot_path, source_url)
VALUES
  (:case_number, :document_type, :filing_date, :debtor_name, :claimant_name,
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

# ─────────────────────────────────────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────────────────────────────────────
def _log(msg: str):
    """Enhanced logging with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")

async def _safe(desc: str, coro):
    """Safety wrapper for async operations"""
    try:
        return await coro
    except Exception as e:
        _log(f"❌ {desc}: {e}")
        return None

# ─────────────────────────────────────────────────────────────────────────────
# FULTON COUNTY SCRAPER CLASS
# ─────────────────────────────────────────────────────────────────────────────
class CobbScraper(SearchFormScraper):
    """Cobb County Georgia lien index scraper implementation"""
    
    async def navigate_to_search_results(self, task_params: Dict[str, Any]):
        """Navigate to search results page and execute search"""
        
        # Clear browser data first to prevent redirects
        await self.clear_browser_data()
        
        # Navigate directly to GSCCCA (don't load old cookies that might redirect)
        gsccca_url = BASE_URL  # Use the constant defined at the top
        _log(f"🌐 Navigating to GSCCCA Real Estate search: {gsccca_url}")
        
        await self.navigate_to_url(gsccca_url)
        await self.page.wait_for_timeout(3000)
        
        # Load saved cookies AFTER confirming we're on the right site
        await self.load_cookies()
        
        # Navigate through the search menu sequence
        await self.navigate_search_menu(task_params)
        
        # Navigation complete - search filters will be applied separately
    
    async def detect_customer_communications_page(self) -> bool:
        """Detect if we're on a Customer Communications page by looking for snooze element"""
        try:
            # Primary detection: Look for the snooze dropdown element
            snooze_element = self.page.locator('select[name="Options"]')
            snooze_count = await snooze_element.count()
            
            if snooze_count > 0:
                # Verify it's actually a snooze dropdown by checking its options
                options = snooze_element.locator('option')
                option_count = await options.count()
                
                if option_count > 0:
                    # Check if any option contains "snooze" text
                    for i in range(min(option_count, 5)):  # Check first 5 options
                        try:
                            option_text = await options.nth(i).text_content()
                            option_value = await options.nth(i).get_attribute('value')
                            if option_text and ('snooze' in option_text.lower() or 
                                              (option_value and 'snooze' in option_value.lower())):
                                _log(f"🎯 Customer Communications page detected via snooze element")
                                _log(f"   Found snooze option: '{option_text}' (value: '{option_value}')")
                                return True
                        except Exception:
                            continue
            
            # Secondary detection: URL-based check
            current_url = self.page.url
            if "CustomerCommunicationApi" in current_url or "Announcement" in current_url:
                _log(f"🎯 Customer Communications page detected via URL: {current_url}")
                return True
            
            # Tertiary detection: Look for Continue button with specific characteristics
            continue_button = self.page.locator('input[value="Continue"]')
            continue_count = await continue_button.count()
            
            if continue_count > 0 and snooze_count > 0:
                _log(f"🎯 Customer Communications page detected via Continue button + select element")
                return True
            
            return False
            
        except Exception as e:
            _log(f"⚠️ Error detecting Customer Communications page: {e}")
            return False
    
    async def handle_customer_communications(self):
        """Handle the Customer Communications page that appears after login"""
        try:
            # Use the detection function to check if we're on the page
            is_customer_comm_page = await self.detect_customer_communications_page()
            
            if not is_customer_comm_page:
                _log("ℹ️ Not on Customer Communications page")
                return False
            
            _log("🎯 Handling Customer Communications page...")
            
            # Log current page details
            current_url = self.page.url
            page_title = await self.page.title()
            _log(f"📄 Current page URL: {current_url}")
            _log(f"📄 Current page title: {page_title}")
            
            # Scroll to reveal all elements
            _log("📜 Scrolling to reveal page elements...")
            await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await self.page.wait_for_timeout(1000)
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self.page.wait_for_timeout(500)
            
            # Handle snooze selection
            await self.select_snooze_option()
            
            # Handle continue button
            success = await self.click_continue_button()
            
            if success:
                _log("✅ Customer Communications page handled successfully")
                return True
            else:
                _log("❌ Failed to handle Customer Communications page")
                return False
                
        except Exception as e:
            _log(f"❌ Error handling Customer Communications page: {e}")
            raise
    
    async def select_snooze_option(self, snooze_option: str = "snooze1d"):
        """Select a snooze option from the dropdown"""
        try:
            _log(f"🔧 Selecting snooze option: {snooze_option}")
            
            # Find the snooze dropdown
            snooze_element = self.page.locator('select[name="Options"]')
            
            if await snooze_element.count() > 0:
                # List available options first
                options = snooze_element.locator('option')
                option_count = await options.count()
                _log(f"📋 Found {option_count} snooze options:")
                
                available_options = []
                for i in range(option_count):
                    try:
                        option_value = await options.nth(i).get_attribute('value')
                        option_text = await options.nth(i).text_content()
                        available_options.append((option_value, option_text))
                        _log(f"   Option {i+1}: value='{option_value}', text='{option_text}'")
                    except Exception:
                        continue
                
                # Try to select the requested option
                try:
                    await snooze_element.select_option(value=snooze_option)
                    _log(f"✅ Selected snooze option: {snooze_option}")
                    await self.page.wait_for_timeout(1000)
                    
                    # Verify selection
                    selected_value = await snooze_element.input_value()
                    _log(f"📋 Confirmed selection: {selected_value}")
                    return True
                    
                except Exception as select_error:
                    _log(f"⚠️ Failed to select '{snooze_option}': {select_error}")
                    
                    # Try to select first available snooze option as fallback
                    for option_value, option_text in available_options:
                        if option_value and 'snooze' in option_value.lower():
                            try:
                                await snooze_element.select_option(value=option_value)
                                _log(f"✅ Selected fallback snooze option: {option_value}")
                                await self.page.wait_for_timeout(1000)
                                return True
                            except Exception:
                                continue
                    
                    _log("❌ Could not select any snooze option")
                    return False
            else:
                _log("⚠️ Snooze dropdown not found")
                return False
                
        except Exception as e:
            _log(f"❌ Error selecting snooze option: {e}")
            return False
    
    async def click_continue_button(self):
        """Click the Continue button on Customer Communications page"""
        try:
            _log("🔧 Looking for Continue button...")
            
            # Try different selectors for the Continue button
            continue_selectors = [
                'input[name="Continue"][value="Continue"]',
                'input[value="Continue"]',
                'input[type="submit"][value="Continue"]',
                'button:has-text("Continue")'
            ]
            
            for selector in continue_selectors:
                try:
                    continue_button = self.page.locator(selector)
                    if await continue_button.count() > 0:
                        _log(f"🎯 Found Continue button with selector: {selector}")
                        
                        # Check if button is visible and enabled
                        is_visible = await continue_button.is_visible()
                        is_enabled = await continue_button.is_enabled()
                        _log(f"   Button status - Visible: {is_visible}, Enabled: {is_enabled}")
                        
                        if is_visible and is_enabled:
                            await continue_button.click()
                            _log("✅ Clicked Continue button")
                            
                            # Wait for page transition
                            _log("⏳ Waiting for page transition...")
                            await self.page.wait_for_timeout(3000)
                            
                            try:
                                await self.page.wait_for_load_state("networkidle", timeout=15000)
                                _log("✅ Page transition completed")
                            except Exception as load_error:
                                _log(f"⚠️ Page load timeout: {load_error}")
                            
                            # Verify we left the Customer Communications page
                            new_url = self.page.url
                            _log(f"📄 New URL after Continue: {new_url}")
                            
                            # Check if we're still on Customer Communications page
                            still_on_comm_page = await self.detect_customer_communications_page()
                            if not still_on_comm_page:
                                _log("✅ Successfully left Customer Communications page")
                                return True
                            else:
                                _log("⚠️ Still on Customer Communications page after clicking Continue")
                                return False
                        else:
                            _log(f"   Button not ready - Visible: {is_visible}, Enabled: {is_enabled}")
                            
                            # Try scrolling to button and clicking
                            try:
                                await continue_button.scroll_into_view_if_needed()
                                await self.page.wait_for_timeout(500)
                                await continue_button.click()
                                _log("✅ Clicked Continue button after scrolling")
                                
                                await self.page.wait_for_timeout(3000)
                                await self.page.wait_for_load_state("networkidle", timeout=15000)
                                return True
                                
                            except Exception as scroll_error:
                                _log(f"⚠️ Scroll and click failed: {scroll_error}")
                                continue
                except Exception as selector_error:
                    _log(f"⚠️ Failed with selector {selector}: {selector_error}")
                    continue
            
            _log("❌ Could not find or click Continue button")
            return False
            
        except Exception as e:
            _log(f"❌ Error clicking Continue button: {e}")
            return False
    
    async def navigate_search_menu(self, task_params: Dict[str, Any]):
        """Navigate through the search menu sequence: Search -> Real Estate Index -> Name Search"""
        try:
            _log("🔄 Starting search menu navigation sequence...")
            
            # Step 1: Wait 2 seconds then click on "Search"
            _log("⏳ Waiting 2 seconds before clicking Search...")
            await self.page.wait_for_timeout(2000)
            
            search_selectors = [
                'a.search',
                'a[class="search"]',
                'a[href*="search"]',
                'a:has-text("Search")'
            ]
            
            search_clicked = False
            for selector in search_selectors:
                try:
                    search_element = self.page.locator(selector)
                    if await search_element.count() > 0:
                        _log(f"🎯 Found Search element using selector: {selector}")
                        await search_element.first.click()
                        _log("✅ Clicked Search button")
                        search_clicked = True
                        break
                except Exception as e:
                    _log(f"⚠️ Failed to click search with selector {selector}: {e}")
                    continue
            
            if not search_clicked:
                _log("❌ Could not find or click Search button")
                return
            
            # Step 2: Wait 2 seconds after redirection then click on "Real Estate Index"
            _log("⏳ Waiting 2 seconds after Search redirection...")
            await self.page.wait_for_timeout(2000)
            
            # Wait for page to load
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
                _log("✅ Page loaded after Search click")
            except Exception as e:
                _log(f"⚠️ Page load timeout after Search click: {e}")
            
            real_estate_index_selectors = [
                'span.box-nolink:has-text("Real Estate Index")',
                'span[class="box-nolink"]:has-text("Real Estate Index")',
                'a:has-text("Real Estate Index")',
                '*:has-text("Real Estate Index")'
            ]
            
            real_estate_index_clicked = False
            for selector in real_estate_index_selectors:
                try:
                    real_estate_element = self.page.locator(selector)
                    if await real_estate_element.count() > 0:
                        _log(f"🎯 Found Real Estate Index element using selector: {selector}")
                        
                        # If it's a span, try to find the parent clickable element
                        if 'span' in selector:
                            parent_element = real_estate_element.locator('xpath=..')
                            if await parent_element.count() > 0:
                                await parent_element.first.click()
                                _log("✅ Clicked Real Estate Index (parent element)")
                                real_estate_index_clicked = True
                                break
                        else:
                            await real_estate_element.first.click()
                            _log("✅ Clicked Real Estate Index")
                            real_estate_index_clicked = True
                            break
                except Exception as e:
                    _log(f"⚠️ Failed to click Real Estate Index with selector {selector}: {e}")
                    continue
            
            if not real_estate_index_clicked:
                _log("❌ Could not find or click Real Estate Index")
                return
            
            # Step 3: Click on "Name Search" under Real Estate Index
            _log("⏳ Looking for Name Search under Real Estate Index...")
            
            # Wait for page to load
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
                _log("✅ Page loaded after Real Estate Index click")
            except Exception as e:
                _log(f"⚠️ Page load timeout after Real Estate Index click: {e}")
            
            name_search_selectors = [
                'a[href="https://search.gsccca.org/RealEstate/namesearch.asp"]',           # Exact Real Estate name search link
                'a[href*="/RealEstate/namesearch"]',              # Real Estate-specific path
                'a[href*="RealEstate/namesearch.asp"]'           # Real Estate-specific fallback
            ]
            
            name_search_clicked = False
            for selector in name_search_selectors:
                try:
                    name_element = self.page.locator(selector)
                    if await name_element.count() > 0:
                        _log(f"🎯 Found Name Search link using selector: {selector}")
                        await name_element.first.click()
                        _log("✅ Clicked Name Search link directly")
                        name_search_clicked = True
                        break
                except Exception as e:
                    _log(f"⚠️ Failed to click Name Search with selector {selector}: {e}")
                    continue
            
            if not name_search_clicked:
                _log("❌ Could not find or click Name Search")
                return
            
            # Final wait and verification
            _log("⏳ Waiting for final page load...")
            await self.page.wait_for_timeout(2000)
            
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
                _log("✅ Final page loaded after Name Search click")
            except Exception as e:
                _log(f"⚠️ Final page load timeout: {e}")
            
            final_url = self.page.url
            _log(f"📄 Final URL after navigation sequence: {final_url}")
            _log("✅ Search menu navigation sequence completed successfully")
            
            # Now apply search filters on the name search page
            await self.apply_search_filters(task_params)
            
        except Exception as e:
            _log(f"❌ Error during search menu navigation: {e}")
            raise
    
    async def navigate_to_search_results_after_comm(self, task_params: Dict[str, Any]):
        """Navigate back to search results after handling Customer Communications"""
        try:
            _log("🔄 Starting navigation sequence after Customer Communications...")
            
            # Wait a moment for page to settle
            await self.page.wait_for_timeout(2000)
            
            # Step 1: Click on "Search"
            _log("🔍 Step 1: Clicking Search...")
            search_selectors = [
                'a.search',
                'a[class="search"]',
                'a[href*="search"]',
                'a:has-text("Search")'
            ]
            
            search_clicked = False
            for selector in search_selectors:
                try:
                    search_element = self.page.locator(selector)
                    if await search_element.count() > 0:
                        _log(f"🎯 Found Search element using selector: {selector}")
                        await search_element.first.click()
                        _log("✅ Clicked Search button")
                        search_clicked = True
                        break
                except Exception as e:
                    _log(f"⚠️ Failed to click search with selector {selector}: {e}")
                    continue
            
            if not search_clicked:
                _log("❌ Could not find or click Search button")
                return False
            
            # Wait for page to load
            await self.page.wait_for_timeout(2000)
            
            # Step 2: Click on "Real Estate Index"
            _log("🏠 Step 2: Clicking Real Estate Index...")
            real_estate_index_selectors = [
                'span.box-nolink:has-text("Real Estate Index")',
                'span[class="box-nolink"]:has-text("Real Estate Index")',
                'a:has-text("Real Estate Index")',
                '*:has-text("Real Estate Index")'
            ]
            
            real_estate_index_clicked = False
            for selector in real_estate_index_selectors:
                try:
                    real_estate_element = self.page.locator(selector)
                    if await real_estate_element.count() > 0:
                        _log(f"🎯 Found Real Estate Index element using selector: {selector}")
                        
                        # If it's a span, try to find the parent clickable element
                        if 'span' in selector:
                            parent_element = real_estate_element.locator('xpath=..')
                            if await parent_element.count() > 0:
                                await parent_element.first.click()
                                _log("✅ Clicked Real Estate Index (parent element)")
                                real_estate_index_clicked = True
                                break
                        else:
                            await real_estate_element.first.click()
                            _log("✅ Clicked Real Estate Index")
                            real_estate_index_clicked = True
                            break
                except Exception as e:
                    _log(f"⚠️ Failed to click Real Estate Index with selector {selector}: {e}")
                    continue
            
            if not real_estate_index_clicked:
                _log("❌ Could not find or click Real Estate Index")
                return False
            
            # Wait for page to load
            await self.page.wait_for_timeout(2000)
            
            # Step 3: Click on "Name Search" under Real Estate Index
            _log("📝 Step 3: Clicking Name Search...")
            name_search_selectors = [
                'a[href="https://search.gsccca.org/RealEstate/namesearch.asp"]',
                'a[href*="/RealEstate/namesearch"]',
                'a[href*="RealEstate/namesearch.asp"]'
            ]
            
            name_search_clicked = False
            for selector in name_search_selectors:
                try:
                    name_element = self.page.locator(selector)
                    if await name_element.count() > 0:
                        _log(f"🎯 Found Name Search link using selector: {selector}")
                        await name_element.first.click()
                        _log("✅ Clicked Name Search link")
                        name_search_clicked = True
                        break
                except Exception as e:
                    _log(f"⚠️ Failed to click Name Search with selector {selector}: {e}")
                    continue
            
            if not name_search_clicked:
                _log("❌ Could not find or click Name Search")
                return False
            
            # Wait for final page to load
            await self.page.wait_for_timeout(3000)
            
            final_url = self.page.url
            _log(f"📄 Final URL after navigation: {final_url}")
            _log("✅ Successfully navigated back to Name Search form")
            
            # Now apply search filters on the name search page
            await self.apply_search_filters(task_params)
            
            return True
            
        except Exception as e:
            _log(f"❌ Error navigating back to search results after Customer Communications: {e}")
            return False
    
    async def apply_search_filters(self, task_params: Dict[str, Any]):
        """Apply search form filters for Cobb County foreclosure deeds"""
        try:
            _log("🔧 Applying Cobb County search filters...")
            
            # Wait for form to load
            await self.page.wait_for_timeout(3000)
            _log("⏳ Search form loaded, applying filters...")
            
            # Get search parameters
            date_from = task_params.get('date_from')
            date_to = task_params.get('date_to')
            search_name = task_params.get('search_name', 'A')
            
            _log(f"📅 Date range: {date_from} to {date_to}")
            _log(f"🔤 Search name: '{search_name}'")
            
            # Set FROM date
            _log("📅 Setting FROM date...")
            from_date_input = self.page.locator('input[name="txtFromDate"]')
            if await from_date_input.count() > 0:
                await from_date_input.click()
                await self.page.wait_for_timeout(500)
                await from_date_input.fill('')
                await from_date_input.clear()
                await self.page.wait_for_timeout(500)
                await from_date_input.fill(date_from)
                _log(f"✅ Set FROM date: {date_from}")
            else:
                _log("⚠️ FROM date field not found")
            
            # Set TO date
            _log("📅 Setting TO date...")
            to_date_input = self.page.locator('input[name="txtToDate"]')
            if await to_date_input.count() > 0:
                await to_date_input.click()
                await self.page.wait_for_timeout(500)
                await to_date_input.fill('')
                await to_date_input.clear()
                await self.page.wait_for_timeout(500)
                await to_date_input.fill(date_to)
                _log(f"✅ Set TO date: {date_to}")
            else:
                _log("⚠️ TO date field not found")
            
            # Set search name
            _log(f"🔤 Setting search name to '{search_name}'...")
            search_name_input = self.page.locator('input[name="txtSearchName"]')
            if await search_name_input.count() > 0:
                await search_name_input.click()
                await search_name_input.clear()
                await search_name_input.fill(search_name)
                await self.page.wait_for_timeout(500)
                entered_name = await search_name_input.input_value()
                _log(f"✅ Set search name to '{search_name}' (verified: '{entered_name}')")
            else:
                _log("⚠️ Search name input not found")
            
            # Set instrument type to DEED - FORECLOSURE (value='28')
            _log("🔧 Setting instrument type to DEED - FORECLOSURE...")
            instrument_select = self.page.locator('select[name="txtInstrCode"]')
            if await instrument_select.count() > 0:
                await instrument_select.select_option('28')  # DEED - FORECLOSURE
                selected_value = await instrument_select.input_value()
                _log(f"✅ Set instrument type to DEED - FORECLOSURE (value: 28, verified: '{selected_value}')")
            else:
                _log("⚠️ Instrument type selector not found")
            
            # Set county to COBB (need to find the correct value for Cobb County)
            _log("🏛️ Setting county to COBB...")
            county_select = self.page.locator('select[name="intCountyID"]')
            if await county_select.count() > 0:
                # Find the correct value for Cobb County
                options = county_select.locator('option')
                option_count = await options.count()
                cobb_value = None
                
                for i in range(option_count):
                    try:
                        option_text = await options.nth(i).text_content()
                        option_value = await options.nth(i).get_attribute('value')
                        if option_text and 'COBB' in option_text.upper():
                            cobb_value = option_value
                            _log(f"🎯 Found COBB county option: text='{option_text}', value='{option_value}'")
                            break
                    except:
                        continue
                
                if cobb_value:
                    await county_select.select_option(cobb_value)
                    selected_value = await county_select.input_value()
                    _log(f"✅ Set county to COBB (value: {cobb_value}, verified: '{selected_value}')")
                else:
                    _log("❌ Could not find COBB county in options")
            else:
                _log("⚠️ County selector not found")
            
            # Set records per page to maximum (50)
            _log("📊 Setting max rows to 50...")
            maxrows_select = self.page.locator('select[name="MaxRows"]')
            if await maxrows_select.count() > 0:
                await maxrows_select.select_option('50')
                selected_value = await maxrows_select.input_value()
                _log(f"✅ Set records per page to 50 (verified: '{selected_value}')")
            else:
                _log("⚠️ MaxRows selector not found")
            
            # Set table display type to "1 Line" (value = 2)
            _log("📋 Setting table display type to 1 Line...")
            try:
                table_type_select = self.page.locator('select[name="TableType"]')
                if await table_type_select.count() > 0:
                    await table_type_select.select_option('2')
                    selected_value = await table_type_select.input_value()
                    _log(f"✅ Set table display type: 1 Line (value: 2, verified: '{selected_value}')")
                else:
                    _log("⚠️ Table type selector not found")
            except Exception as table_type_error:
                _log(f"⚠️ Could not set table display type: {table_type_error}")
            
            _log("🎯 All search filters applied successfully")
            
            # Add a small delay before clicking search
            await self.page.wait_for_timeout(1000)
            
            # Find and click the search button
            search_button = await self.find_search_button()
            if search_button:
                try:
                    # Click the search button
                    await search_button.click()
                    _log("✅ Clicked search button - executing search")
                    
                    # Wait longer for search results
                    _log("⏳ Waiting for search to complete...")
                    await self.page.wait_for_timeout(8000)  # Increased wait time
                    
                    # Check if we're still on the search form or moved to results
                    new_url = self.page.url
                    _log(f"📄 URL after search click: {new_url}")
                    
                    # Handle login if required (this might redirect us)
                    await self.handle_login()
                    
                    # Handle Customer Communications page if it appears after login
                    customer_comm_handled = await self.handle_customer_communications()
                    
                    # If Customer Communications was handled, we need to navigate back to search results
                    if customer_comm_handled:
                        _log("🔄 Customer Communications handled, navigating back to search results...")
                        await self.navigate_to_search_results_after_comm(task_params)
                        return "results_found"  # Return successful execution since we navigated successfully
                    
                    # Look for search results or errors
                    search_result = await self.verify_search_execution()
                    
                    # Return the search result status for the caller to handle
                    return search_result
                    
                except Exception as search_error:
                    _log(f"❌ Failed to click search button: {search_error}")
                    raise
            
        except Exception as e:
            _log(f"❌ Error applying search filters: {e}")
            raise
    
    async def verify_search_execution(self):
        """Verify search execution and handle results immediately"""
        try:
            _log("🔍 Verifying search execution...")
            
            # Wait a bit more for results to load
            await self.page.wait_for_timeout(3000)
            
            # Check specifically for the results table first
            try:
                results_table = self.page.locator('table.name_results')
                if await results_table.count() > 0:
                    _log("✅ Found results table - processing results...")
                    
                    # Results found! Click on first selection and display details
                    await self.handle_results_found()
                    return "results_found"
                    
            except Exception:
                pass
            
            # If no results table found, check for "No records found" message
            no_results_selectors = [
                'text="No records were found matching your search criteria."',
                '*:has-text("No records were found")',
                '*:has-text("No records found")',
                '*:has-text("no records found")',
                '*:has-text("No matching records")'
            ]
            
            for selector in no_results_selectors:
                try:
                    no_results_element = self.page.locator(selector)
                    if await no_results_element.count() > 0:
                        _log("📭 No records found - clicking Return to Search and moving to next letter")
                        
                        # No results found! Click return to search immediately
                        await self.click_return_to_search()
                        await self.page.wait_for_timeout(3000)  # Wait 3 seconds as requested
                        return "no_results"
                except:
                    continue
            
            # If we can't find either results table or no results message, assume no results
            _log("⚠️ No results table found - assuming no results")
            await self.click_return_to_search()
            await self.page.wait_for_timeout(3000)  # Wait 3 seconds as requested
            return "no_results"
                
        except Exception as e:
            _log(f"⚠️ Error during search execution verification: {e}")
            return "error"

    async def handle_results_found(self):
        """Handle when results are found - click on first selection and display details"""
        try:
            _log("📋 Handling results found - selecting first result and displaying details...")
            
            # Wait for results table to be fully loaded
            await self.page.wait_for_timeout(2000)
            
            # Find the first radio button or checkbox to select a result
            selection_selectors = [
                'input[type="radio"][name*="radio"]',
                'input[type="checkbox"]',
                'input[name*="rdoEntityName"]',
                'input[type="radio"]'
            ]
            
            for selector in selection_selectors:
                try:
                    selection_element = self.page.locator(selector).first
                    if await selection_element.count() > 0:
                        _log(f"🎯 Found selection element: {selector}")
                        await selection_element.click()
                        _log("✅ Selected first result")
                        break
                except Exception:
                    continue
            
            # Now click "Display Details" button
            display_details_selectors = [
                'input#btnDisplayDetails',  # Specific ID from the HTML
                'input[id="btnDisplayDetails"]',  # Alternative ID selector
                'input[value="Display Details"]',  # Exact value match
                'input[value*="Display Details"]',
                'input[id*="btnDisplayDetails"]',
                'input[type="button"][value*="Details"]',
                'button:has-text("Display Details")',
                'input[type="submit"][value*="Display"]'
            ]
            
            for selector in display_details_selectors:
                try:
                    details_button = self.page.locator(selector)
                    if await details_button.count() > 0:
                        _log(f"🎯 Found Display Details button: {selector}")
                        await details_button.click()
                        _log("✅ Clicked Display Details button")
                        
                        # Wait for details page to load
                        await self.page.wait_for_timeout(3000)
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        
                        return True
                except Exception:
                    continue
            
            _log("⚠️ Could not find Display Details button")
            return False
            
        except Exception as e:
            _log(f"❌ Error handling results found: {e}")
            return False

    async def click_return_to_search(self):
        """Click the 'Return to Search' button when no results are found"""
        try:
            _log("🔙 Looking for 'Return to Search' button...")
            
            # Try different selectors for the return to search button
            return_selectors = [
                'input[value*="Return to Search"]',
                'input[value*="Return"]',
                'button:has-text("Return to Search")',
                'button:has-text("Return")',
                'a:has-text("Return to Search")',
                'input[type="submit"][value*="Return"]'
            ]
            
            for selector in return_selectors:
                try:
                    return_button = self.page.locator(selector)
                    if await return_button.count() > 0:
                        _log(f"🎯 Found Return to Search button with selector: {selector}")
                        
                        # Scroll to button and click
                        await return_button.scroll_into_view_if_needed()
                        await self.page.wait_for_timeout(500)
                        await return_button.click()
                        _log("✅ Clicked Return to Search button")
                        
                        # Wait for search form to load
                        await self.page.wait_for_timeout(3000)
                        await self.page.wait_for_load_state("networkidle", timeout=10000)
                        
                        return True
                        
                except Exception as button_error:
                    _log(f"⚠️ Failed to click Return to Search with selector {selector}: {button_error}")
                    continue
            
            _log("❌ Could not find or click Return to Search button")
            return False
            
        except Exception as e:
            _log(f"❌ Error clicking Return to Search button: {e}")
            return False

    async def clear_browser_data(self):
        """Clear browser data to prevent redirects to old sites"""
        try:
            # Clear cookies, cache, and local storage
            await self.page.context.clear_cookies()
            await self.page.evaluate("localStorage.clear()")
            await self.page.evaluate("sessionStorage.clear()")
            _log("✅ Cleared browser data to prevent redirects")
        except Exception as e:
            _log(f"⚠️ Failed to clear browser data: {e}")
    
    async def load_cookies(self):
        """Load saved cookies to maintain session state"""
        cookies = [
            {"name":"ASPSESSIONIDACRCSSDR","value":"EGJICHEAMHKCCAOIKLPLKPMI","domain":"search.gsccca.org","path":"/"},
            {"name":"ASPSESSIONIDSCSATQCQ","value":"APDENIEAJEDEEBEHMFJPNMFO","domain":"search.gsccca.org","path":"/"},
            {"name":"ASPSESSIONIDQCRARSBQ","value":"HIBEGIEANGJJOICLHFENPDIA","domain":"search.gsccca.org","path":"/"},
            {"name":"_gid","value":"GA1.2.373521197.1749395529","domain":"gsccca.org","path":"/"},
            {"name":"ASPSESSIONIDQCTDTTAQ","value":"HHCNIMKCDAFEEAHKLIKJDCBC","domain":"search.gsccca.org","path":"/"},
            {"name":"ASPSESSIONIDCAQARQAS","value":"EGIAOKKCAFBKBOINJMGAIJLH","domain":"search.gsccca.org","path":"/"},
            {"name":"ASPSESSIONIDSCSDTRAQ","value":"GBALBMKCCHAAHJMDEFOBDNAG","domain":"search.gsccca.org","path":"/"},
            {"name":"CustomerCommunicationApi","value":"LastVisit=6%2F9%2F2025+2%3A36%3A50+AM&Snooze=6%2F10%2F2025+2%3A15%3A43+AM","domain":"gsccca.org","path":"/"},
            {"name":"GUID","value":"%7Bcde59db8%2D20e9%2D4019%2D8503%2Dba2d750e50fd%7D","domain":"gsccca.org","path":"/"},
            {"name":"GSCCCASaved","value":"iRealEstateInstType=28&iRealEstateTableType=1&iRealEstateMaxRows=50&iRealEstatePartyType=2&intRealEstateBKPGCountyID=31&intRealEstateCountyID=31&sRealEstateName=a","domain":"search.gsccca.org","path":"/"},
            {"name":"_ga_SV1BEGDXWV","value":"GS2.1.s1749448192$o5$g1$t1749451034$j29$l0$h0","domain":"gsccca.org","path":"/"},
            {"name":"_ga","value":"GA1.2.1927429005.1749094656","domain":"gsccca.org","path":"/"}
        ]
        
        try:
            await self.page.context.add_cookies(cookies)
            _log("✅ Loaded saved cookies for session maintenance")
        except Exception as e:
            _log(f"⚠️ Failed to load cookies: {e}")
    
    async def find_search_button(self):
        """Find the search button regardless of its active/inactive state"""
        # Try different selectors for the search button
        selectors = [
            'input[type="button"][value="Search"]',
            'input[value="Search"]',
            '.button[value="Search"]',
            'input[type="submit"][value="Search"]',
            'button:contains("Search")',
            '*[value="Search"]'
        ]
        
        for selector in selectors:
            try:
                button = self.page.locator(selector).first
                if await button.is_visible():
                    _log(f"✅ Found search button with selector: {selector}")
                    return button
            except:
                continue
        
        # If no button found, try a more general approach
        all_buttons = self.page.locator('input[type="button"], input[type="submit"], button')
        button_count = await all_buttons.count()
        
        for i in range(button_count):
            button = all_buttons.nth(i)
            try:
                value = await button.get_attribute('value')
                text = await button.text_content()
                if (value and 'search' in value.lower()) or (text and 'search' in text.lower()):
                    _log(f"✅ Found search button by content matching")
                    return button
            except:
                continue
        
        raise Exception("❌ Could not find search button with any selector")
    
    async def handle_login(self):
        """Handle login if login form is present"""
        try:
            # Check if login form is present
            username_field = self.page.locator('input[name="txtUserID"]')
            password_field = self.page.locator('input[name="txtPassword"]')
            
            # Check if login fields are visible
            if await username_field.is_visible():
                _log("🔐 Login form detected, attempting to login...")
                
                # Get credentials from environment variables
                username = os.getenv("GSCCCA_USERNAME")
                password = os.getenv("GSCCCA_PASSWORD")
                
                if not username or not password:
                    raise Exception("GSCCCA_USERNAME and GSCCCA_PASSWORD environment variables are required for login")
                
                # Fill in credentials
                await username_field.fill(username)
                await password_field.fill(password)
                _log("✅ Filled login credentials")
                
                #Remember me checkbox
                remember_me_checkbox = self.page.locator('input[name="permanent"]')
                await remember_me_checkbox.click()
                _log("✅ Clicked remember me checkbox")
                
                # Click login button
                login_button = self.page.locator('img[name="logon"]')
                await login_button.click()
                _log("✅ Clicked login button")
                
                # Wait for login to complete
                await self.page.wait_for_timeout(3000)
                _log("✅ Login completed")
            else:
                _log("ℹ️ No login form detected, proceeding...")
                
        except Exception as e:
            _log(f"❌ Login failed: {e}")
            raise
        
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

    async def extract_search_results(self) -> List[Dict[str, Any]]:
        """Extract records from search results table by scanning row by row and clicking on data inputs and Display Details"""
        _log("🔍 Starting custom table extraction for Cobb GA results")
        
        try:
            # STEP 0: Check for "No records found" message first
            await self.page.wait_for_timeout(2000)  # Wait for page to fully load
            
            # Check for "No records found" message
            no_results_selectors = [
                '*:has-text("No records were found matching your search criteria")',
                '*:has-text("No records were found")',
                '*:has-text("No records found")',
                '*:has-text("no records found")',
                '*:has-text("No matching records")',
                'font:has-text("No records were found")'  # Based on your screenshot
            ]
            
            for selector in no_results_selectors:
                try:
                    no_results_element = self.page.locator(selector)
                    if await no_results_element.count() > 0:
                        _log("📭 No records found message detected - will click Return to Search and try next letter")
                        
                        # Click Return to Search
                        await self.click_return_to_search()
                        await self.page.wait_for_timeout(3000)
                        
                        # Get next search letter and try again
                        # This will be handled by the calling function - just return empty for now
                        return []
                except Exception:
                    continue
            
            # Wait for results table to load (only if no "no results" message found)
            await self.page.wait_for_selector('table.name_results', timeout=10000)
            _log("✅ Found results table with class 'name_results'")
            
            # Get existing names for this user to avoid duplicates
            existing_names = await get_existing_names_for_user(USER_ID)
            _log(f"📋 Loaded {len(existing_names)} existing names for user {USER_ID}")
            
            # Log some example existing names for debugging (first 5)
            if existing_names:
                example_names = list(existing_names)[:5]
                _log(f"📝 Example existing names: {example_names}")
            
            # Get the results table
            results_table = self.page.locator('table.name_results')
            
            # Get all table rows (excluding header row - start from second tr)
            all_table_rows = results_table.locator('tbody tr, tr:has(td)')
            total_rows = await all_table_rows.count()
            _log(f"📊 Found {total_rows} total rows (including header)")
            
            # Skip the first row (header) and get data rows starting from index 1
            if total_rows <= 1:
                _log("⚠️ No data rows found (only header row present)")
                return []
            
            table_rows = all_table_rows  # We'll handle skipping the header in the loop
            row_count = await table_rows.count()
            _log(f"📊 Found {row_count} data rows in results table")
            
            if row_count == 0:
                _log("⚠️ No data rows found in results table")
                return []
            
            records = []
            skipped_count = 0
            processed_names_this_session = set()  # Track names processed in this session
            
            # Process each row in order (starting from index 1 to skip header row)
            for row_index in range(1, row_count):
                try:
                    _log(f"🔄 Processing row {row_index + 1} of {row_count}")
                    
                    # Get the current row
                    current_row = table_rows.nth(row_index)
                    
                    # Get all cells in this row
                    row_cells = current_row.locator('td')
                    cell_count = await row_cells.count()
                    _log(f"   📋 Row has {cell_count} cells")
                    
                    # Extract the name from the last td (cell) in this row
                    if cell_count > 0:
                        last_cell = row_cells.nth(cell_count - 1)
                        row_name = await last_cell.text_content()
                        row_name = row_name.strip() if row_name else ""
                        _log(f"   👤 Row name: '{row_name}'")
                        
                        # Normalize the name for comparison (lowercase, remove extra spaces)
                        normalized_name = " ".join(row_name.lower().split()) if row_name else ""
                        
                        # Check if this name already exists in the database for this user
                        if normalized_name and normalized_name in existing_names:
                            _log(f"   ⏭️ SKIPPING row {row_index + 1} - Name '{row_name}' already exists in database for user {USER_ID}")
                            skipped_count += 1
                            continue
                        # Also check if we've already processed this name in this session
                        elif normalized_name and normalized_name in processed_names_this_session:
                            _log(f"   ⏭️ SKIPPING row {row_index + 1} - Name '{row_name}' already processed in this session")
                            skipped_count += 1
                            continue
                        elif row_name:
                            _log(f"   ✅ Name '{row_name}' is new, proceeding with extraction")
                            # Add to processed names for this session
                            processed_names_this_session.add(normalized_name)
                        else:
                            _log(f"   ⚠️ Row {row_index + 1} has empty name, proceeding anyway")
                    else:
                        _log(f"   ⚠️ Row {row_index + 1} has no cells, skipping")
                        continue
                    
                    # Extract row data from all cells AND click radio button in first cell
                    row_data = {}
                    radio_button_clicked = False
                    
                    for cell_index in range(cell_count):
                        try:
                            cell = row_cells.nth(cell_index)
                            cell_text = await cell.text_content()
                            if cell_text and cell_text.strip():
                                row_data[f'column_{cell_index}'] = cell_text.strip()
                            
                            # For the first cell (index 0), look for and click the radio button
                            if cell_index == 0 and not radio_button_clicked:
                                # Try multiple selectors to find the radio button
                                radio_selectors = [
                                    'input[name="rdoEntityName"]',
                                    'input[type="radio"]',
                                    'input[type="radio"][name="rdoEntityName"]',
                                    'input',  # Fallback to any input in first cell
                                ]
                                
                                for radio_selector in radio_selectors:
                                    try:
                                        radio_button = cell.locator(radio_selector)
                                        radio_count = await radio_button.count()
                                        
                                        if radio_count > 0:
                                            # Get attributes for debugging
                                            radio_name = await radio_button.get_attribute('name')
                                            radio_type = await radio_button.get_attribute('type')
                                            radio_value = await radio_button.get_attribute('value')
                                            
                                            _log(f"   🎯 Found radio button with selector '{radio_selector}': name='{radio_name}', type='{radio_type}', value='{radio_value}'")
                                            
                                            # Click the radio button
                                            await radio_button.click()
                                            _log(f"   ✅ Clicked radio button to select row {row_index + 1}")
                                            radio_button_clicked = True
                                            await self.page.wait_for_timeout(500)  # Brief pause after selection
                                            break
                                            
                                    except Exception as radio_error:
                                        _log(f"   ⚠️ Failed to click radio button with selector '{radio_selector}': {radio_error}")
                                        continue
                                
                                # If still no radio button found, debug the first cell content
                                if not radio_button_clicked:
                                    try:
                                        cell_html = await cell.inner_html()
                                        _log(f"   🔍 DEBUG - First cell HTML: {cell_html}")
                                        
                                        # Try to find ANY input elements in the cell
                                        all_inputs = cell.locator('input')
                                        input_count = await all_inputs.count()
                                        _log(f"   🔍 DEBUG - Found {input_count} input elements in first cell")
                                        
                                        if input_count > 0:
                                            for i in range(input_count):
                                                input_elem = all_inputs.nth(i)
                                                input_name = await input_elem.get_attribute('name')
                                                input_type = await input_elem.get_attribute('type')
                                                input_value = await input_elem.get_attribute('value')
                                                _log(f"   🔍 DEBUG - Input {i}: name='{input_name}', type='{input_type}', value='{input_value}'")
                                    except Exception as debug_error:
                                        _log(f"   ⚠️ DEBUG failed: {debug_error}")
                                        
                        except Exception as cell_error:
                            _log(f"   ⚠️ Failed to extract cell {cell_index} text: {cell_error}")
                    
                    if not radio_button_clicked:
                        _log(f"   ⚠️ No radio button found in first cell of row {row_index + 1}")
                    
                    # After clicking radio button, we need to look for Display Details button on the entire page
                    # (not just in this row, as it might be at the bottom of the page)
                    display_details_selectors = [
                        'input#btnDisplayDetails',  # Specific ID from the HTML
                        'input[id="btnDisplayDetails"]',  # Alternative ID selector
                        'input[value="Display Details"]',  # Exact value match
                        'input[value*="Display Details"]',
                        'input[value*="Details"]', 
                        'button:has-text("Display Details")',
                        'input[type="submit"][value*="Display"]',
                        'input[onclick*="Display"]'
                    ]
                    
                    display_details_clicked = False
                    for selector in display_details_selectors:
                        try:
                            # Look for Display Details button on the entire page, not just in the row
                            details_button = self.page.locator(selector)
                            if await details_button.count() > 0:
                                button_value = await details_button.get_attribute('value')
                                _log(f"   🎯 Found Display Details button: value='{button_value}'")
                                
                                # Click the Display Details button
                                await details_button.click()
                                _log(f"   ✅ Clicked Display Details button for row {row_index + 1}")
                                
                                # Wait for details page to load
                                await self.page.wait_for_timeout(2000)
                                await self.page.wait_for_load_state('networkidle', timeout=10000)
                                
                                # Extract detailed record information from the details page
                                detailed_data = await self.extract_record_details()
                                
                                # Combine row data with detailed data
                                record_data = {**row_data, **detailed_data}
                                record_data['source_url'] = self.page.url
                                
                                records.append(record_data)
                                _log(f"   ✅ Extracted detailed record data for row {row_index + 1}")
                                
                                # Navigate back to results table
                                await self.navigate_back_to_results()
                                
                                display_details_clicked = True
                                break
                                
                        except Exception as details_error:
                            _log(f"   ⚠️ Failed to click Display Details with selector {selector}: {details_error}")
                            continue
                    
                    if not display_details_clicked:
                        _log(f"   ⚠️ No Display Details button found in row {row_index + 1}, using basic row data")
                        # Still add the basic row data as a record
                        row_data['source_url'] = self.page.url
                        records.append(row_data)
                    
                except Exception as row_error:
                    _log(f"❌ Failed to process row {row_index + 1}: {row_error}")
                    continue
            
            _log(f"✅ Completed table extraction, found {len(records)} new records, skipped {skipped_count} existing records")
            
            # After processing all records for this letter, navigate back to search form
            if len(records) > 0:
                _log(f"📋 Processed {len(records)} records for this letter, navigating back to search form...")
                back_success = await self.navigate_back_to_search_form()
                if not back_success:
                    _log("⚠️ Failed to navigate back to search form, may affect next letter search")
            
            return records
            
        except Exception as e:
            _log(f"❌ Table extraction failed: {e}")
            # Fallback to base class implementation
            return await super().extract_search_results()
    
    async def extract_record_details(self) -> Dict[str, Any]:
        """Extract detailed record information from the record details page"""
        _log("🔍 Extracting detailed record information")
        
        try:
            record_data = {}
            
            # Common selectors for record details
            detail_selectors = {
                'case_number': ['td:has-text("Case Number")', 'td:has-text("Case #")', '*:has-text("Case Number")'],
                'document_type': ['td:has-text("Document Type")', 'td:has-text("Type")', '*:has-text("Document Type")'],
                'filing_date': ['td:has-text("Filing Date")', 'td:has-text("Date Filed")', '*:has-text("Filing Date")'],
                'debtor_name': ['td:has-text("Debtor")', 'td:has-text("Defendant")', '*:has-text("Debtor")'],
                'claimant_name': ['td:has-text("Claimant")', 'td:has-text("Plaintiff")', '*:has-text("Claimant")'],
                'book_page': ['td:has-text("Book/Page")', 'td:has-text("Book")', '*:has-text("Book")'],
                'county': ['td:has-text("County")', '*:has-text("County")']
            }
            
            # Extract each field using multiple selector strategies
            for field_name, selectors in detail_selectors.items():
                for selector in selectors:
                    try:
                        # Find the label element
                        label_element = self.page.locator(selector).first
                        if await label_element.count() > 0:
                            # Try to find the value in the next cell or sibling
                            value_element = label_element.locator('.. >> td').nth(1)
                            if await value_element.count() == 0:
                                # Try next sibling approach
                                value_element = label_element.locator('xpath=following-sibling::td[1]')
                            
                            if await value_element.count() > 0:
                                value = await value_element.text_content()
                                if value and value.strip():
                                    record_data[field_name] = value.strip()
                                    _log(f"   ✅ {field_name}: {value.strip()}")
                                    break
                    except Exception as field_error:
                        continue
            
                            # Navigate to document and capture screenshot
                screenshot_path = await self.capture_document_screenshot(record_data)
                if screenshot_path:
                    record_data['screenshot_path'] = screenshot_path
                    
                    # OCR is automatically triggered in capture_document_screenshot
                    # Check if OCR text file was created and add to record
                    if record_data.get('parsed_address'):
                        _log(f"   📍 Address parsed from OCR: {record_data['parsed_address']}")
                    
                    # Add OCR text file path if available
                    ocr_text_file = screenshot_path.replace('.png', '.txt').replace('screenshots/', 'ocr_text_outputs/')
                    if Path(ocr_text_file).exists():
                        record_data['ocr_text_file'] = ocr_text_file
            
            # Also extract any document links
            try:
                link_elements = self.page.locator('a[href*=".pdf"], a[href*="document"], a[href*="view"]')
                if await link_elements.count() > 0:
                    first_link = await link_elements.first.get_attribute('href')
                    if first_link:
                        # Convert relative URL to absolute if needed
                        if first_link.startswith('/'):
                            base_url = f"{self.page.url.split('/')[0]}//{self.page.url.split('/')[2]}"
                            first_link = base_url + first_link
                        record_data['document_link'] = first_link
                        _log(f"   ✅ document_link: {first_link}")
            except Exception as link_error:
                _log(f"   ⚠️ Failed to extract document link: {link_error}")
            
            return record_data
            
        except Exception as e:
            _log(f"❌ Failed to extract record details: {e}")
            return {}
    
    async def capture_document_screenshot(self, record_data: Dict[str, Any]) -> Optional[str]:
        """Navigate to document link in table and capture screenshot for OCR"""
        try:
            _log("📸 Looking for document link to capture screenshot")
            
            # Very specific targeting: td.reg_property_cell_borders containing <a> with text starting with "PT"
            specific_document_selectors = [
                'td.reg_property_cell_borders:has(a:text-matches("^PT", "i"))',  # Most specific - td with reg_property_cell_borders class containing <a> with text starting with "PT"
                'td.reg_property_cell_borders a:text-matches("^PT", "i")'        # Alternative - directly target the <a> with PT text inside reg_property_cell_borders td
            ]
            
            for selector in specific_document_selectors:
                try:
                    _log(f"🔍 Looking for document link with specific selector: '{selector}'")
                    
                    if 'td.reg_property_cell_borders:has' in selector:
                        # First selector finds the td, then we get the <a> inside it
                        target_td = self.page.locator(selector)
                        td_count = await target_td.count()
                        _log(f"   📊 Found {td_count} matching td elements")
                        
                        if td_count > 0:
                            # Get the <a> link inside the first matching td
                            document_link = target_td.first.locator('a:text-matches("^PT", "i")')
                            
                    else:
                        # Second selector directly targets the <a> link
                        document_link = self.page.locator(selector)
                    
                    link_count = await document_link.count()
                    _log(f"   🔗 Found {link_count} matching document links")
                    
                    if link_count > 0:
                        link_href = await document_link.first.get_attribute('href')
                        link_text = await document_link.first.text_content()
                        
                        _log(f"   🎯 Found specific document link:")
                        _log(f"      📎 Link text: '{link_text}'")
                        _log(f"      🔗 Link href: '{link_href}'")
                        _log(f"      🎯 Using selector: '{selector}'")
                        
                        # Verify it's the right type of link (PT text and javascript:show)
                        if link_text and link_text.strip().upper().startswith('PT') and link_href and 'javascript:show' in link_href:
                            _log(f"   ✅ Confirmed: Link has PT text and javascript:show href")
                            
                            # Click the link and handle potential new tab
                            return await self.click_document_link_and_screenshot(document_link.first, record_data)
                        else:
                            _log(f"   ⚠️ Link found but doesn't match expected pattern (PT text + javascript:show)")
                            
                except Exception as selector_error:
                    _log(f"❌ Error with specific selector '{selector}': {selector_error}")
                    continue
            
            _log("📭 No document link found with reg_property_cell_borders class and PT text")
            return None
            
        except Exception as e:
            _log(f"❌ Error capturing document screenshot: {e}")
            return None
    
    async def click_document_link_and_screenshot(self, document_link, record_data: Dict[str, Any]) -> Optional[str]:
        """Click document link and capture screenshot of the opened document"""
        try:
            _log("🖱️ Clicking document link...")
            
            # Create screenshots directory if it doesn't exist
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            
            # Generate filename based on record data
            case_number = record_data.get('case_number', 'unknown')
            debtor_name = record_data.get('debtor_name', 'unknown')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Clean filename - remove special characters
            safe_case_number = re.sub(r'[^a-zA-Z0-9_-]', '_', case_number)
            safe_debtor_name = re.sub(r'[^a-zA-Z0-9_-]', '_', debtor_name)[:20]  # Limit length
            
            screenshot_filename = f"cobb_ga_{safe_case_number}_{safe_debtor_name}_{timestamp}.png"
            screenshot_path = screenshots_dir / screenshot_filename
            
            # Get current number of pages before clicking
            initial_pages = self.page.context.pages
            initial_page_count = len(initial_pages)
            _log(f"📊 Initial page count: {initial_page_count}")
            
            try:
                # Click the document link
                await document_link.click()
                _log("✅ Clicked document link")
                
                # Wait for potential new tab to open
                await asyncio.sleep(3)
                _log("⏳ Waiting for new tab to potentially open...")
                
                # Get all pages after clicking
                all_pages = self.page.context.pages
                current_page_count = len(all_pages)
                _log(f"📊 Current page count: {current_page_count}")
                
                # Check if a new page opened
                if current_page_count > initial_page_count:
                    # New tab opened - use the latest page
                    new_page = all_pages[-1]
                    _log("📄 New tab detected, taking screenshot of new page...")
                    
                    # Wait for the new page to load completely
                    await new_page.wait_for_load_state('networkidle', timeout=15000)
                    await new_page.wait_for_timeout(2000)  # Additional wait for document rendering
                    
                    # Take screenshot of the new page
                    await new_page.screenshot(path=str(screenshot_path), full_page=True)
                    _log(f"📸 Screenshot saved from new tab: {screenshot_path}")
                    
                    # Close the new page/tab
                    await new_page.close()
                    _log("🔐 Closed new document tab")
                    
                else:
                    # No new tab opened - screenshot current page
                    _log("📸 No new tab detected, taking screenshot of current page...")
                    await self.page.wait_for_timeout(3000)  # Wait for any changes on current page
                    await self.page.screenshot(path=str(screenshot_path), full_page=True)
                    _log(f"📸 Current page screenshot saved: {screenshot_path}")
                
                # Verify screenshot was created successfully
                if screenshot_path.exists():
                    file_size = screenshot_path.stat().st_size
                    _log(f"✅ Document screenshot captured successfully: {screenshot_path} ({file_size} bytes)")
                    
                    # Extract text from the screenshot using OCR
                    _log("🔍 Starting OCR text extraction from screenshot...")
                    ocr_text_file = extract_text_from_screenshot(str(screenshot_path), record_data)
                    if ocr_text_file:
                        _log(f"✅ OCR text extraction completed: {ocr_text_file}")
                    else:
                        _log("⚠️ OCR text extraction failed")
                    
                    return str(screenshot_path)
                else:
                    _log("❌ Screenshot file was not created")
                    return None
                    
            except Exception as click_error:
                _log(f"❌ Error clicking document link or taking screenshot: {click_error}")
                return None
            
        except Exception as e:
            _log(f"❌ Error in click_document_link_and_screenshot: {e}")
            return None
    
    async def navigate_back_to_results(self):
        """Navigate back to the search results table"""
        try:
            _log("🔙 Navigating back to search results")
            
            # Try different methods to go back
            back_selectors = [
                'input[value*="Back"]',
                'button:has-text("Back")',
                'a:has-text("Back")',
                'input[type="submit"][value*="Return"]',
                'a:has-text("Return to Results")'
            ]
            
            back_clicked = False
            for selector in back_selectors:
                try:
                    back_button = self.page.locator(selector)
                    if await back_button.count() > 0:
                        _log(f"   ✅ Found back button: {selector}")
                        await back_button.click()
                        back_clicked = True
                        break
                except Exception as back_error:
                    continue
            
            if not back_clicked:
                # Fallback: use browser back button
                _log("   ⚠️ No back button found, using browser back")
                await self.page.go_back()
            
            # Wait for results table to load again
            await self.page.wait_for_timeout(2000)
            await self.page.wait_for_selector('table.name_results', timeout=5000)
            _log("   ✅ Successfully returned to results table")
            
        except Exception as e:
            _log(f"❌ Failed to navigate back to results: {e}")
            raise
    
    async def navigate_back_to_search_form(self):
        """Navigate back to the search form after processing all records for a letter"""
        try:
            _log("🔙 Navigating back to search form for next letter search...")
            
            # Try different selectors for the Back button that returns to search form
            back_to_search_selectors = [
                'input[name="bBack"][value="Back"]',  # Specific back button from screenshot
                'input[type="button"][value="Back"]',
                'input[value="Back"]',
                'button:has-text("Back")',
                'a:has-text("Back")',
                'input[onclick*="history.go(-1)"]',
                'input[onclick*="back"]'
            ]
            
            back_clicked = False
            for selector in back_to_search_selectors:
                try:
                    back_button = self.page.locator(selector)
                    if await back_button.count() > 0:
                        _log(f"   🎯 Found back to search button: {selector}")
                        await back_button.click()
                        _log("   ✅ Clicked back button")
                        back_clicked = True
                        break
                except Exception as back_error:
                    _log(f"   ⚠️ Failed to click back button with selector {selector}: {back_error}")
                    continue
            
            if not back_clicked:
                # Fallback: use browser back button
                _log("   ⚠️ No back button found, using browser back")
                await self.page.go_back()
            
            # Wait for search form to load
            await self.page.wait_for_timeout(3000)
            
            # Verify we're back on the search form by looking for search name input
            try:
                await self.page.wait_for_selector('input[name="txtSearchName"]', timeout=10000)
                _log("   ✅ Successfully returned to search form")
                return True
            except Exception as form_error:
                _log(f"   ⚠️ Search form not detected after back navigation: {form_error}")
                return False
            
        except Exception as e:
            _log(f"❌ Failed to navigate back to search form: {e}")
            return False
    
    async def scrape(self, task_params: Dict[str, Any]) -> ScrapingResult:
        """Override base class scrape method to use custom flow"""
        try:
            _log(f"🚀 Starting Fulton GA custom scraping flow")
            
            # Navigate to search results using our custom method
            await self.navigate_to_search_results(task_params)
            
            # Extract search results using our custom method
            records_data = await self.extract_search_results()
            
            # Convert to ScrapingRecord objects
            records = []
            for record_data in records_data:
                clean_record = self.clean_record_data(record_data)
                records.append(ScrapingRecord(
                    data=clean_record,
                    source_url=record_data.get('source_url', self.page.url)
                ))
            
            _log(f"✅ Fulton GA scraping completed successfully, found {len(records)} records")
            
            return ScrapingResult(
                success=True,
                records=records,
                error_message=None
            )
            
        except Exception as e:
            _log(f"❌ Fulton GA scraping failed: {e}")
            return ScrapingResult(
                success=False,
                records=[],
                error_message=str(e)
            )
    
    async def search_next_letter(self, task_params: Dict[str, Any]) -> ScrapingResult:
        """Search for the next letter without full navigation (assumes we're already on the search form)"""
        try:
            search_letter = task_params.get('search_name', 'A')
            _log(f"🔤 Searching for next letter: '{search_letter}'")
            
            # Update the search name field with the new letter
            search_name_input = self.page.locator('input[name="txtSearchName"]')
            if await search_name_input.count() > 0:
                await search_name_input.click()
                await search_name_input.clear()
                await search_name_input.fill(search_letter)
                await self.page.wait_for_timeout(500)
                _log(f"✅ Updated search name to '{search_letter}'")
            else:
                _log("❌ Could not find search name input field")
                return ScrapingResult(success=False, records=[], error_message="Search name input not found")
            
            # Click the search button
            search_button = await self.find_search_button()
            if search_button:
                await search_button.click()
                _log("✅ Clicked search button for next letter")
                
                # Wait for search results
                await self.page.wait_for_timeout(5000)
                
                # Extract search results
                records_data = await self.extract_search_results()
                
                # Convert to ScrapingRecord objects
                records = []
                for record_data in records_data:
                    clean_record = self.clean_record_data(record_data)
                    records.append(ScrapingRecord(
                        data=clean_record,
                        source_url=record_data.get('source_url', self.page.url)
                    ))
                
                _log(f"✅ Letter '{search_letter}' search completed, found {len(records)} records")
                
                return ScrapingResult(
                    success=True,
                    records=records,
                    error_message=None
                )
            else:
                _log("❌ Could not find search button")
                return ScrapingResult(success=False, records=[], error_message="Search button not found")
                
        except Exception as e:
            _log(f"❌ Letter '{search_letter}' search failed: {e}")
            return ScrapingResult(
                success=False,
                records=[],
                error_message=str(e)
            )

# ─────────────────────────────────────────────────────────────────────────────
# OCR FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
def ocr_extract_text_from_image(image_path: str) -> Optional[str]:
    """Extract text from image using OCR - optimized for Cobb County documents"""
    try:
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
        
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _log(f"🔧 Using optimized OCR for Cobb County documents")
        
        # Try multiple approaches and combine results
        all_text = []
        
        # Method 1: Full document with basic OCR
        try:
            config1 = r'--oem 3 --psm 6'
            text1 = pytesseract.image_to_string(gray, config=config1)
            if text1.strip():
                all_text.append(("full_document", text1))
                _log(f"✅ Full document OCR: {len(text1)} chars")
        except Exception as e:
            _log(f"⚠️ Full document OCR failed: {e}")
        
        # Method 2: Property information region (where addresses are typically found)
        try:
            # Extract property region (middle-lower section where property info appears)
            property_region = gray[int(height*0.45):int(height*0.85), int(width*0.05):int(width*0.95)]
            config2 = r'--oem 3 --psm 6'
            text2 = pytesseract.image_to_string(property_region, config=config2)
            if text2.strip():
                all_text.append(("property_region", text2))
                _log(f"✅ Property region OCR: {len(text2)} chars")
        except Exception as e:
            _log(f"⚠️ Property region OCR failed: {e}")
        
        # Method 3: Seller information region (upper section)
        try:
            # Extract seller region (upper section where seller address appears)
            seller_region = gray[int(height*0.15):int(height*0.45), int(width*0.05):int(width*0.65)]
            config3 = r'--oem 3 --psm 6'
            text3 = pytesseract.image_to_string(seller_region, config=config3)
            if text3.strip():
                all_text.append(("seller_region", text3))
                _log(f"✅ Seller region OCR: {len(text3)} chars")
        except Exception as e:
            _log(f"⚠️ Seller region OCR failed: {e}")
        
        # Combine all extracted text
        if all_text:
            # Find the method that extracted the most text
            best_method = max(all_text, key=lambda x: len(x[1]))
            ocr_text = best_method[1]
            ocr_method_used = f"cobb_optimized_{best_method[0]}"
            
            # Also combine all text for comprehensive parsing
            combined_text = "\n".join([f"=== {method} ===\n{text}" for method, text in all_text])
            
            _log(f"✅ OCR successful using method: {ocr_method_used}")
            return combined_text, ocr_method_used
        else:
            # Fallback to basic OCR
            _log("🔄 All optimized methods failed, trying basic fallback...")
            ocr_text = pytesseract.image_to_string(gray)
            if ocr_text.strip():
                return ocr_text, "basic_fallback"
            else:
                _log("⚠️ No text found in OCR after trying all methods")
                return None
        
    except Exception as e:
        _log(f"❌ OCR extraction error: {e}")
        return None

def extract_text_from_screenshot(screenshot_path: str, record_data: Dict[str, Any]) -> Optional[str]:
    """Extract text from screenshot using OCR and save to txt file"""
    try:
        screenshot_file = Path(screenshot_path)
        if not screenshot_file.exists():
            _log(f"❌ Screenshot file not found: {screenshot_path}")
            return None
        
        _log(f"📖 Starting OCR text extraction from: {screenshot_file.name}")
        
        # Extract text using the proven HillsboroughNH approach
        _log("🔍 Running OCR text extraction...")
        
        # Use the proven OCR function
        ocr_result = ocr_extract_text_from_image(str(screenshot_file))
        
        if ocr_result:
            extracted_text, ocr_method_used = ocr_result
        else:
            extracted_text = ""
            ocr_method_used = "failed"
        
        # Generate output filename based on screenshot filename
        txt_filename = screenshot_file.stem + ".txt"  # Remove .png and add .txt
        txt_file_path = OCR_TEXT_DIR / txt_filename
        
        # Save extracted text to file with metadata - similar to HillsboroughNH format
        with open(txt_file_path, 'w', encoding='utf-8') as f:
            f.write(f"=== OCR DEBUG OUTPUT ===\n")
            f.write(f"Image: {screenshot_file.name}\n")
            f.write(f"Image path: {screenshot_path}\n")
            f.write(f"OCR method used: {ocr_method_used}\n")
            f.write(f"OCR text length: {len(extracted_text)} characters\n")
            f.write(f"Timestamp: {datetime.now()}\n")
            f.write(f"Case Number: {record_data.get('case_number', 'unknown')}\n")
            f.write(f"Document Type: {record_data.get('document_type', 'unknown')}\n")
            f.write(f"Filing Date: {record_data.get('filing_date', 'unknown')}\n")
            f.write(f"Debtor Name: {record_data.get('debtor_name', 'unknown')}\n")
            f.write(f"Claimant Name: {record_data.get('claimant_name', 'unknown')}\n")
            f.write(f"=== FULL OCR TEXT ===\n\n")
            f.write(extracted_text)
            f.write(f"\n\n=== END OCR TEXT ===\n")
        
        _log(f"✅ OCR text extracted and saved to: {txt_file_path}")
        _log(f"📊 Text length: {len(extracted_text)} characters (method: {ocr_method_used})")
        
        # Log first few lines of extracted text for debugging
        text_lines = extracted_text.split('\n')[:10]  # First 10 lines
        _log("📝 First few lines of extracted text:")
        for i, line in enumerate(text_lines, 1):
            if line.strip():  # Only log non-empty lines
                _log(f"   {i:2d}: {line.strip()}")
        
        # Try to parse addresses from the OCR text
        addresses = parse_addresses_from_ocr_text(extracted_text)
        if addresses:
            _log(f"🏠 Found {len(addresses)} potential addresses in OCR text:")
            for addr in addresses[:3]:  # Show first 3
                _log(f"   📍 {addr}")
            
            # Save the best address to the record data for database storage
            best_address = max(addresses, key=len) if addresses else ""
            record_data['parsed_address'] = best_address
            _log(f"✅ Best address selected: {best_address}")
        
        return str(txt_file_path)
        
    except Exception as e:
        _log(f"❌ OCR text extraction failed for {screenshot_path}: {e}")
        return None

def parse_addresses_from_ocr_text(text: str) -> List[str]:
    """Parse addresses from OCR text using patterns optimized for Cobb County documents"""
    addresses = []
    
    if not text or not text.strip():
        return addresses
    
    try:
        # Cobb County specific address patterns based on testing
        address_patterns = [
            # Pattern 1: Street address with number and road type (like "3043 TOWNSGATE ROAD")
            r'\b(\d+[A-Z]?\s+[A-Z][A-Z\s]*(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD|GATE))\b',
            
            # Pattern 2: Complete address with city, state, zip
            r'\b(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+GA\s+\d{5}(?:-\d{4})?)\b',
            
            # Pattern 3: Cobb County cities with addresses
            r'\b(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+(?:MARIETTA|KENNESAW|SMYRNA|ACWORTH|POWDER SPRINGS|AUSTELL|MABLETON)\s+(?:GA|GEORGIA)\s+\d{5}(?:-\d{4})?)\b',
            
            # Pattern 4: Address lines with Georgia cities (more flexible)
            r'([A-Za-z0-9\s,]+(?:MARIETTA|KENNESAW|SMYRNA|ACWORTH|POWDER SPRINGS|AUSTELL|MABLETON)[,\s]+(?:GA|GEORGIA)[,\s]*\d{5}(?:-\d{4})?)',
            
            # Pattern 5: Mailing address sections
            r'(?:MAILING ADDRESS|ADDRESS|STREET)[^:]*:?\s*([^\n]+)',
            
            # Pattern 6: Property location patterns
            r'(?:Property|Land|Lot|Located at|Situated at|Being)\s+([^.]*?(?:MARIETTA|KENNESAW|SMYRNA|ACWORTH|POWDER SPRINGS|AUSTELL|MABLETON|GA|GEORGIA)[^.]*)',
            
            # Pattern 7: Lines containing both street numbers and common Cobb County road names
            r'([^\n]*\d+[^\n]*(?:TOWNSGATE|MILL|MAIN|CHURCH|SCHOOL|PARK|SPRING|CREEK|RIDGE|HILL|VALLEY|FOREST|LAKE|RIVER|BRIDGE)[^\n]*)',
            
            # Pattern 8: Any line with a number followed by road-like words
            r'([^\n]*\d+[^\n]*(?:ROAD|RD|STREET|ST|AVENUE|AVE|DRIVE|DR|LANE|LN|WAY|COURT|CT|CIRCLE|CIR|PLACE|PL|BOULEVARD|BLVD)[^\n]*)',
        ]
        
        for pattern in address_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                if isinstance(match, tuple):
                    clean_address = ' '.join(str(m).strip() for m in match if m.strip())
                else:
                    clean_address = str(match).strip()
                
                # Clean up the address
                clean_address = re.sub(r'\s+', ' ', clean_address)
                clean_address = clean_address.strip()
                
                # Remove common OCR artifacts and prefixes
                clean_address = re.sub(r'^[^A-Za-z0-9]*', '', clean_address)  # Remove leading non-alphanumeric
                clean_address = re.sub(r'[^A-Za-z0-9\s,.-]*$', '', clean_address)  # Remove trailing artifacts
                
                # Remove obvious OCR noise patterns
                clean_address = re.sub(r'\b[A-Z]{1}\b', '', clean_address)  # Remove single capital letters
                clean_address = re.sub(r'\s+', ' ', clean_address).strip()  # Normalize whitespace
                
                # Clean up common OCR artifacts at the end of addresses
                clean_address = re.sub(r'\s*["\(][^"]*$', '', clean_address)  # Remove trailing quotes and parentheses with content
                clean_address = re.sub(r'\s*\$\d+\.\d+.*$', '', clean_address)  # Remove dollar amounts and everything after
                clean_address = re.sub(r'["\(\)\s]+$', '', clean_address)  # Remove trailing quotes, parentheses, and spaces
                clean_address = clean_address.strip()
                
                # Filter reasonable addresses
                if (len(clean_address) > 8 and 
                    re.search(r'\d', clean_address) and  # Must contain a number
                    re.search(r'[A-Za-z]', clean_address) and  # Must contain letters
                    not re.search(r'PT-\d+|033-2025|Report|Image|Need|Heln|Cuerks', clean_address, re.IGNORECASE) and  # Exclude document artifacts
                    re.search(r'\b(?:ROAD|RD|STREET|ST|AVENUE|AVE|DRIVE|DR|LANE|LN|WAY|COURT|CT|CIRCLE|CIR|PLACE|PL|BOULEVARD|BLVD|GATE)\b', clean_address, re.IGNORECASE)):  # Must contain street type
                    addresses.append(clean_address)
        
        # Remove duplicates and sort by length (longer addresses first)
        unique_addresses = list(set(addresses))
        unique_addresses.sort(key=len, reverse=True)
        
        # Log found addresses for debugging
        if unique_addresses:
            _log(f"🏠 Found {len(unique_addresses)} potential addresses:")
            for i, addr in enumerate(unique_addresses[:5], 1):  # Show first 5
                _log(f"   {i}. {addr}")
        
        return unique_addresses
        
    except Exception as e:
        _log(f"❌ Error parsing addresses from OCR text: {e}")
        return []

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def get_existing_case_numbers_for_user(user_id: str) -> set:
    """Get existing case numbers from the database for specific user to avoid duplicates"""
    try:
        if not user_id:
            _log("⚠️ No user_id provided - treating all records as new")
            return set()
            
        async with create_async_engine(DB_URL).begin() as conn:
            result = await conn.execute(
                text("SELECT DISTINCT case_number FROM cobb_ga_filing WHERE \"userId\" = :user_id AND case_number IS NOT NULL AND case_number != ''"),
                {"user_id": user_id}
            )
            case_numbers = {row[0] for row in result.fetchall()}
            _log(f"📊 Found {len(case_numbers)} existing case numbers for user {user_id}")
            return case_numbers
    except Exception as e:
        _log(f"❌ Error getting existing case numbers: {e}")
        return set()

async def get_existing_names_for_user(user_id: str) -> set:
    """Get existing debtor names for user to avoid duplicates"""
    try:
        if not user_id:
            return set()
            
        async with create_async_engine(DB_URL).begin() as conn:
            result = await conn.execute(
                text("SELECT DISTINCT LOWER(TRIM(debtor_name)) FROM cobb_ga_filing WHERE \"userId\" = :user_id AND debtor_name IS NOT NULL AND debtor_name != ''"),
                {"user_id": user_id}
            )
            names = {row[0] for row in result.fetchall() if row[0]}
            _log(f"📊 Found {len(names)} existing debtor names for user {user_id}")
            return names
    except Exception as e:
        _log(f"❌ Error getting existing names: {e}")
        return set()

async def upsert_records(records: List[dict], user_id: str = None):
    """Insert/update records in the database with enhanced fields"""
    if not records:
        _log("⚠️ No records to upsert")
        return 0
    
    try:
        # Map field names to match database schema
        mapped_records = []
        current_time = datetime.now()
        
        for record in records:
            mapped_record = {
                'case_number': record.get('case_number', ''),
                'document_type': record.get('document_type', ''),
                'filing_date': record.get('filing_date', ''),
                'debtor_name': record.get('debtor_name', ''),
                'claimant_name': record.get('claimant_name', ''),
                'county': 'Cobb GA',
                'book_page': record.get('book_page', ''),
                'document_link': record.get('document_link', ''),
                'state': 'GA',
                'created_at': current_time,
                'updated_at': current_time,
                'is_new': True,
                'userId': user_id or 'unknown',
                'parsed_address': record.get('parsed_address', ''),
                'ocr_text_file': record.get('ocr_text_file', ''),
                'screenshot_path': record.get('screenshot_path', ''),
                'source_url': record.get('source_url', '')
            }
            mapped_records.append(mapped_record)
        
        async with create_async_engine(DB_URL).begin() as conn:
            await conn.execute(text(INSERT_SQL), mapped_records)
        
        _log(f"✅ Successfully upserted {len(mapped_records)} records to database")
        return len(mapped_records)
        
    except Exception as e:
        _log(f"❌ Error upserting records to database: {e}")
        raise

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def export_to_csv(records: List[dict], user_id: str = None) -> Path:
    """Export records to CSV file with comprehensive data"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        user_suffix = f"_{user_id}" if user_id else ""
        csv_file = EXPORT_DIR / f"cobb_ga_records{user_suffix}_{timestamp}.csv"
        
        if not records:
            _log("⚠️ No records to export")
            return csv_file
        
        # Create DataFrame with all fields
        df = pd.DataFrame(records)
        
        # Ensure all expected columns exist
        expected_columns = [
            'case_number',
            'document_type', 
            'filing_date',
            'debtor_name',
            'claimant_name',
            'county',
            'book_page',
            'document_link',
            'parsed_address',
            'ocr_text_file',
            'screenshot_path',
            'source_url',
            'extraction_timestamp',
            'user_id'
        ]
        
        for col in expected_columns:
            if col not in df.columns:
                df[col] = ''
        
        # Add metadata columns
        df['extraction_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df['user_id'] = user_id or 'unknown'
        df['county'] = 'Cobb GA'
        df['state'] = 'GA'
        
        # Reorder columns for better readability
        column_order = [
            'case_number',
            'document_type',
            'filing_date', 
            'debtor_name',
            'claimant_name',
            'parsed_address',
            'book_page',
            'county',
            'state',
            'document_link',
            'ocr_text_file',
            'screenshot_path',
            'source_url',
            'extraction_timestamp',
            'user_id'
        ]
        
        # Keep only columns that exist in the DataFrame
        available_columns = [col for col in column_order if col in df.columns]
        df = df[available_columns]
        
        # Export to CSV
        df.to_csv(csv_file, index=False, encoding='utf-8')
        
        _log(f"📊 Exported {len(df)} records to {csv_file}")
        _log(f"📋 CSV columns: {', '.join(df.columns)}")
        
        # Log sample of exported data
        if len(df) > 0:
            _log("📝 Sample exported data:")
            for i, row in df.head(3).iterrows():
                _log(f"   Record {i+1}: Case#{row.get('case_number', 'N/A')}, "
                     f"Type: {row.get('document_type', 'N/A')}, "
                     f"Date: {row.get('filing_date', 'N/A')}")
        
        return csv_file
        
    except Exception as e:
        _log(f"❌ Error exporting to CSV: {e}")
        # Create empty CSV file as fallback
        csv_file = EXPORT_DIR / f"cobb_ga_records_error_{timestamp}.csv"
        pd.DataFrame().to_csv(csv_file, index=False)
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
    
    _log(f"🚀 Starting Fulton County GA Lien Index scraper")
    _log(f"📊 Max records: {max_new_records}, Test mode: {test_mode}")
    
    # Load configuration
    config = CountyConfig.from_json_file("configs/fulton_ga.json")
    config.headless = not test_mode  # Show browser in test mode
    
    # Set default date range (31st of previous month to today)
    if not from_date:
        # Get 31st of previous month
        today = datetime.now()
        # Go to first day of current month, then subtract 1 day to get last day of previous month
        first_of_current_month = today.replace(day=1)
        last_day_of_previous_month = first_of_current_month - timedelta(days=1)
        # Set to 31st (or last day if month has fewer than 31 days)
        try:
            from_date_obj = last_day_of_previous_month.replace(day=31)
        except ValueError:
            # Month doesn't have 31 days, use the last day of that month
            from_date_obj = last_day_of_previous_month
        from_date = from_date_obj.strftime('%m/%d/%Y')
    if not to_date:
        to_date = datetime.now().strftime('%m/%d/%Y')
    
    # Set default instrument types (focus on lis pendens)
    if not instrument_types:
        instrument_types = ['Lis Pendens']  # Default to Lis Pendens (value=9)
    
    # Get existing case numbers for this user
    existing_case_numbers = await get_existing_case_numbers_for_user(USER_ID)
    
    # Letter-based search implementation
    all_records = []
    search_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 
                     'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
    
    _log(f"Starting letter-based search through {len(search_letters)} letters")
    
    try:
        async with CobbScraper(config) as scraper:
            for letter_index, search_letter in enumerate(search_letters):
                if len(all_records) >= max_new_records:
                    _log(f"🛑 Reached maximum records limit ({max_new_records}), stopping search")
                    break
                
                _log(f"🔤 Searching for letter '{search_letter}' ({letter_index + 1}/{len(search_letters)})")
                
                # Prepare task parameters for this letter
                task_params = {
                    'max_records': max_new_records,
                    'test_mode': test_mode,
                    'date_from': from_date,
                    'date_to': to_date,
                    'instrument_types': instrument_types,
                    'party_type': 'All Parties',
                    'search_name': search_letter
                }
                
                # For the first letter, do full navigation
                if letter_index == 0:
                    _log(f"🚀 First search - doing full navigation for letter '{search_letter}'")
                    result = await scraper.scrape(task_params)
                else:
                    _log(f"🔄 Subsequent search - updating search name to '{search_letter}' and searching")
                    # For subsequent letters, just update the search name and search
                    result = await scraper.search_next_letter(task_params)
                
                if result.success and result.records:
                    # Filter out existing records
                    new_records = []
                    for record in result.records:
                        clean_record = scraper.clean_record_data(record.data)
                        if clean_record['case_number'] not in existing_case_numbers:
                            new_records.append(clean_record)
                            existing_case_numbers.add(clean_record['case_number'])
                    
                    _log(f"📊 Letter '{search_letter}': Found {len(new_records)} new records")
                    all_records.extend(new_records)
                else:
                    _log(f"📭 Letter '{search_letter}': No new records found")
                
                # Small delay between searches
                await asyncio.sleep(1)
        
        # Always export to CSV (even in test mode)
        _log(f"📊 Exporting {len(all_records)} records to CSV...")
        csv_file = await export_to_csv(all_records, USER_ID)
        
        if not test_mode and all_records:
            # Save to database
            _log(f"💾 Saving {len(all_records)} records to database...")
            await upsert_records(all_records, USER_ID)
            
            # Export to Google Sheets
            _log(f"📈 Exporting to Google Sheets...")
            df = pd.DataFrame(all_records)
            export_to_google_sheets(df)
        elif test_mode:
            _log(f"🧪 Test mode - skipping database and Google Sheets export")
        
        _log(f"✅ Scraping completed successfully!")
        _log(f"📁 CSV file: {csv_file}")
        _log(f"📝 OCR text files: {OCR_TEXT_DIR}")
        _log(f"📸 Screenshots: screenshots/")
        
        return all_records
                
    except Exception as e:
        _log(f"❌ Scraping failed: {e}")
        raise

# ─────────────────────────────────────────────────────────────────────────────
# COMMAND LINE INTERFACE
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description="Fulton County GA Lien Index Scraper")
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