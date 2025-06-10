"""
Fulton County Georgia Lien Index Scraper

This script scrapes lien records for Fulton County, Georgia from the
Georgia Superior Court Clerks' Cooperative Authority (GSCCCA) system.

Website: https://search.gsccca.org/Lien/namesearch.asp

Features:
- Searches for recent Fulton County lien records by date range
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
class FultonRecord(TypedDict):
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
COUNTY_NAME = "Fulton GA"

# Environment variables
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME = os.getenv("GSHEET_NAME")
FULTON_TAB = os.getenv("FULTON_TAB", "FultonGA")
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required")

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
INSERT INTO fulton_ga_filing
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
# FULTON COUNTY SCRAPER CLASS
# ─────────────────────────────────────────────────────────────────────────────
class FultonScraper(SearchFormScraper):
    """Fulton County Georgia lien index scraper implementation"""
    
    async def navigate_to_search_results(self, task_params: Dict[str, Any]):
        """Navigate to search results page and execute search"""
        
        # Load saved cookies FIRST to maintain session state
        await self.load_cookies()
        
        # Navigate to search page
        await self.navigate_to_url(self.config.search_config.search_url)
        await self.page.wait_for_timeout(2000)
        
        # Click the search button to initiate search flow
        search_button = await self.find_search_button()
        await search_button.click()
        _log("✅ Clicked search button")
        
        # Wait 5 seconds for login form to appear
        await self.page.wait_for_timeout(5000)
        
        # Handle login if required
        await self.handle_login()
        
        _log(f"✅ Search initiated")
        
        # Handle Customer Communications page if it appears
        await self.handle_customer_communications()
        
        # Navigate through the search menu sequence
        await self.navigate_search_menu(task_params)
        
        _log("✅ Successfully navigated to search results")
    
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
        """Navigate through the search menu sequence: Search -> Lien Index -> Name Search"""
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
            
            # Step 2: Wait 2 seconds after redirection then click on "Lien Index"
            _log("⏳ Waiting 2 seconds after Search redirection...")
            await self.page.wait_for_timeout(2000)
            
            # Wait for page to load
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
                _log("✅ Page loaded after Search click")
            except Exception as e:
                _log(f"⚠️ Page load timeout after Search click: {e}")
            
            lien_index_selectors = [
                'span.box-nolink:has-text("Lien Index")',
                'span[class="box-nolink"]:has-text("Lien Index")',
                'a:has-text("Lien Index")',
                '*:has-text("Lien Index")'
            ]
            
            lien_index_clicked = False
            for selector in lien_index_selectors:
                try:
                    lien_element = self.page.locator(selector)
                    if await lien_element.count() > 0:
                        _log(f"🎯 Found Lien Index element using selector: {selector}")
                        
                        # If it's a span, try to find the parent clickable element
                        if 'span' in selector:
                            parent_element = lien_element.locator('xpath=..')
                            if await parent_element.count() > 0:
                                await parent_element.first.click()
                                _log("✅ Clicked Lien Index (parent element)")
                                lien_index_clicked = True
                                break
                        else:
                            await lien_element.first.click()
                            _log("✅ Clicked Lien Index")
                            lien_index_clicked = True
                            break
                except Exception as e:
                    _log(f"⚠️ Failed to click Lien Index with selector {selector}: {e}")
                    continue
            
            if not lien_index_clicked:
                _log("❌ Could not find or click Lien Index")
                return
            
            # Step 3: Click on "Name Search"
            _log("⏳ Looking for Name Search...")
            
            # Wait for page to load
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
                _log("✅ Page loaded after Lien Index click")
            except Exception as e:
                _log(f"⚠️ Page load timeout after Lien Index click: {e}")
            
            name_search_selectors = [
                
                'a[href="https://search.gsccca.org/Lien/namesearch.asp"]',           # Exact Lien name search link
                'a[href*="/Lien/namesearch"]',              # Lien-specific path
                'a[href*="Lien/namesearch.asp"]'           # Lien-specific fallback
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
    
    async def apply_search_filters(self, task_params: Dict[str, Any]):
        """Apply search filters on the name search page"""
        try:
            _log("🔧 Applying search filters on name search page...")
            
            # Wait for the search form to load
            await self.page.wait_for_timeout(3000)
            _log("⏳ Page loaded, checking for search form elements...")
            
            # Log current URL to verify we're on the correct page
            current_url = self.page.url
            _log(f"📄 Current URL: {current_url}")
            
            # Set date range FIRST - ensure we always have dates
            date_from = task_params.get('date_from')
            date_to = task_params.get('date_to')
            
            # Always set default dates if not provided
            if not date_from:
                from datetime import datetime, timedelta
                date_from = (datetime.now() - timedelta(days=30)).strftime('%m/%d/%Y')
                _log(f"📅 Using default from date: {date_from}")
            
            if not date_to:
                from datetime import datetime
                date_to = datetime.now().strftime('%m/%d/%Y')
                _log(f"📅 Using default to date: {date_to}")
            
            _log(f"📅 Date range: {date_from} to {date_to}")
            
            # Fill from date with enhanced error handling
            _log("📅 Setting FROM date...")
            from_date_input = self.page.locator('input[name="txtFromDate"]')
            if await from_date_input.count() > 0:
                _log(f"🎯 Found txtFromDate input field")
                # Click to focus first
                await from_date_input.click()
                await self.page.wait_for_timeout(500)
                # Clear using multiple methods
                await from_date_input.fill('')
                await from_date_input.clear()
                await self.page.wait_for_timeout(500)
                # Fill with date
                await from_date_input.fill(date_from)
                await self.page.wait_for_timeout(1000)
                # Press Tab to trigger any onchange events
                await from_date_input.press('Tab')
                await self.page.wait_for_timeout(500)
                # Verify the date was entered
                entered_value = await from_date_input.input_value()
                _log(f"✅ Set from date to {date_from} (verified: '{entered_value}')")
                if entered_value != date_from:
                    _log(f"⚠️ Date verification mismatch! Expected: '{date_from}', Got: '{entered_value}'")
            else:
                _log("❌ From date input (txtFromDate) not found!")
                # List all available input fields for debugging
                all_inputs = self.page.locator('input')
                input_count = await all_inputs.count()
                _log(f"🔍 Found {input_count} total input fields on page:")
                for i in range(min(input_count, 10)):  # Show first 10
                    try:
                        input_name = await all_inputs.nth(i).get_attribute('name')
                        input_type = await all_inputs.nth(i).get_attribute('type')
                        _log(f"   Input {i+1}: name='{input_name}', type='{input_type}'")
                    except:
                        pass
            
            # Fill to date with enhanced error handling
            _log("📅 Setting TO date...")
            to_date_input = self.page.locator('input[name="txtToDate"]')
            if await to_date_input.count() > 0:
                _log(f"🎯 Found txtToDate input field")
                # Click to focus first
                await to_date_input.click()
                await self.page.wait_for_timeout(500)
                # Clear using multiple methods
                await to_date_input.fill('')
                await to_date_input.clear()
                await self.page.wait_for_timeout(500)
                # Fill with date
                await to_date_input.fill(date_to)
                await self.page.wait_for_timeout(1000)
                # Press Tab to trigger any onchange events
                await to_date_input.press('Tab')
                await self.page.wait_for_timeout(500)
                # Verify the date was entered
                entered_value = await to_date_input.input_value()
                _log(f"✅ Set to date to {date_to} (verified: '{entered_value}')")
                if entered_value != date_to:
                    _log(f"⚠️ Date verification mismatch! Expected: '{date_to}', Got: '{entered_value}'")
            else:
                _log("❌ To date input (txtToDate) not found!")
            
            # Set search name
            search_name = task_params.get('search_name', 'A')
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
            
            # Set instrument type to Lis Pendens (value='9')
            _log("🔧 Setting instrument type to Lis Pendens...")
            instrument_select = self.page.locator('select[name="txtInstrCode"]')
            if await instrument_select.count() > 0:
                await instrument_select.select_option('9')  # Lis Pendens
                selected_value = await instrument_select.input_value()
                _log(f"✅ Set instrument type to Lis Pendens (value: 9, verified: '{selected_value}')")
            else:
                _log("⚠️ Instrument type selector not found")
            
            # Set county to FULTON (value='60')
            _log("🏛️ Setting county to FULTON...")
            county_select = self.page.locator('select[name="intCountyID"]')
            if await county_select.count() > 0:
                await county_select.select_option('60')  # FULTON
                selected_value = await county_select.input_value()
                _log(f"✅ Set county to FULTON (value: 60, verified: '{selected_value}')")
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
            
            # Final verification of all form fields before search
            _log("🔍 Final verification of form fields before search...")
            try:
                # Re-check all the critical fields
                from_date_final = await from_date_input.input_value() if await from_date_input.count() > 0 else "NOT FOUND"
                to_date_final = await to_date_input.input_value() if await to_date_input.count() > 0 else "NOT FOUND"
                search_name_final = await search_name_input.input_value() if await search_name_input.count() > 0 else "NOT FOUND"
                
                _log(f"📋 Final form state:")
                _log(f"   From Date: '{from_date_final}'")
                _log(f"   To Date: '{to_date_final}'")
                _log(f"   Search Name: '{search_name_final}'")
                
                # Check if dates are actually filled
                if from_date_final == "" or from_date_final == "NOT FOUND":
                    _log("❌ FROM DATE IS EMPTY! This will cause the search to fail.")
                if to_date_final == "" or to_date_final == "NOT FOUND":
                    _log("❌ TO DATE IS EMPTY! This will cause the search to fail.")
                    
            except Exception as verify_error:
                _log(f"⚠️ Error during final verification: {verify_error}")
            
            # Click the search button
            _log("🔍 Looking for and clicking search button...")
            try:
                search_button = await self.find_search_button()
                _log(f"✅ Found search button, preparing to click...")
                
                # Scroll to button if needed
                await search_button.scroll_into_view_if_needed()
                await self.page.wait_for_timeout(500)
                
                # Click the search button
                await search_button.click()
                _log("✅ Clicked search button - executing search")
                
                # Wait longer for search results
                _log("⏳ Waiting for search to complete...")
                await self.page.wait_for_timeout(8000)  # Increased wait time
                
                # Check if we're still on the search form or moved to results
                new_url = self.page.url
                _log(f"📄 URL after search click: {new_url}")
                
                # Look for search results or errors
                await self.verify_search_execution()
                
            except Exception as search_error:
                _log(f"❌ Failed to click search button: {search_error}")
                raise
            
            # Handle login if required (this might redirect us)
            await self.handle_login()
            
            # Final verification
            result_url = self.page.url
            _log(f"📄 Final search results URL: {result_url}")
            _log("✅ Search filters applied and search executed successfully")
            
        except Exception as e:
            _log(f"❌ Error applying search filters: {e}")
            raise
    
    async def verify_search_execution(self):
        """Verify that the search was actually executed"""
        try:
            _log("🔍 Verifying search execution...")
            
            # Wait a bit more for results to load
            await self.page.wait_for_timeout(3000)
            
            # Check for various indicators of search results
            result_indicators = [
                'table.name_results',          # Results table
                'table[class*="result"]',      # Alternative results table
                'div:has-text("Search Results")',  # Results heading
                'div:has-text("No records found")',  # No results message
                'tr:has(td)',                  # Any table rows with data
                'form:has-text("Display")'     # Results form
            ]
            
            found_results = False
            for indicator in result_indicators:
                try:
                    element = self.page.locator(indicator)
                    if await element.count() > 0:
                        _log(f"✅ Found search results indicator: {indicator}")
                        found_results = True
                        break
                except:
                    continue
            
            if not found_results:
                _log("⚠️ No clear search results indicators found")
                # Log page content for debugging
                page_text = await self.page.text_content('body')
                if page_text:
                    # Look for error messages or other clues
                    if 'error' in page_text.lower():
                        _log(f"❌ Error detected in page content")
                    if 'invalid' in page_text.lower():
                        _log(f"❌ Invalid input detected in page content")
                    if 'required' in page_text.lower():
                        _log(f"❌ Required field message detected")
                        
                    # Show first 500 characters of page content
                    preview = page_text[:500].replace('\n', ' ').replace('\r', ' ')
                    _log(f"📄 Page content preview: {preview}")
            else:
                _log("✅ Search execution verified - results found")
                
        except Exception as e:
            _log(f"⚠️ Error during search execution verification: {e}")
    
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
            {"name":"GSCCCASaved","value":"iLienInstType=9&iLienTableType=1&iLienMaxRows=50&iLienPartyType=2&intLienBKPGCountyID=60&intLienCountyID=60&sLienName=a","domain":"search.gsccca.org","path":"/"},
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
        
    def clean_record_data(self, record_data: dict) -> FultonRecord:
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
        
        return FultonRecord(
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
        _log("🔍 Starting custom table extraction for Fulton GA results")
        
        try:
            # Wait for results table to load
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
            
            # Get all table rows (excluding header if present)
            table_rows = results_table.locator('tbody tr, tr').filter(lambda row: row.locator('td').count() > 0)
            row_count = await table_rows.count()
            _log(f"📊 Found {row_count} data rows in results table")
            
            if row_count == 0:
                _log("⚠️ No data rows found in results table")
                return []
            
            records = []
            skipped_count = 0
            processed_names_this_session = set()  # Track names processed in this session
            
            # Process each row in order
            for row_index in range(row_count):
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
                    
                    # First, click on any data inputs in this row
                    data_inputs = current_row.locator('input[type="radio"], input[type="checkbox"], input[name*="data"], input[name*="select"]')
                    input_count = await data_inputs.count()
                    
                    if input_count > 0:
                        _log(f"   🎯 Found {input_count} data input(s) in row {row_index + 1}")
                        for input_index in range(input_count):
                            try:
                                data_input = data_inputs.nth(input_index)
                                input_name = await data_input.get_attribute('name')
                                input_type = await data_input.get_attribute('type')
                                _log(f"   ✅ Clicking data input: name='{input_name}', type='{input_type}'")
                                await data_input.click()
                                await self.page.wait_for_timeout(500)  # Brief pause between clicks
                            except Exception as input_error:
                                _log(f"   ⚠️ Failed to click data input {input_index + 1}: {input_error}")
                    else:
                        _log(f"   ℹ️ No data inputs found in row {row_index + 1}")
                    
                    # Extract basic row data before clicking Display Details
                    row_data = {}
                    for cell_index in range(cell_count):
                        try:
                            cell = row_cells.nth(cell_index)
                            cell_text = await cell.text_content()
                            if cell_text and cell_text.strip():
                                row_data[f'column_{cell_index}'] = cell_text.strip()
                        except Exception as cell_error:
                            _log(f"   ⚠️ Failed to extract cell {cell_index} text: {cell_error}")
                    
                    # Look for Display Details button in this row
                    display_details_selectors = [
                        'input[value*="Display Details"]',
                        'input[value*="Details"]', 
                        'button:has-text("Display Details")',
                        'input[type="submit"][value*="Display"]',
                        'input[onclick*="Display"]'
                    ]
                    
                    display_details_clicked = False
                    for selector in display_details_selectors:
                        try:
                            details_button = current_row.locator(selector)
                            if await details_button.count() > 0:
                                button_value = await details_button.get_attribute('value')
                                _log(f"   🎯 Found Display Details button: value='{button_value}'")
                                
                                # Click the Display Details button
                                await details_button.click()
                                _log(f"   ✅ Clicked Display Details button in row {row_index + 1}")
                                
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
            await self.page.wait_for_selector('table.name_results', timeout=10000)
            _log("   ✅ Successfully returned to results table")
            
        except Exception as e:
            _log(f"❌ Failed to navigate back to results: {e}")
            raise
    
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

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def get_existing_case_numbers() -> set:
    """Get existing case numbers from database to avoid duplicates"""
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                text("SELECT case_number FROM fulton_ga_filing WHERE case_number IS NOT NULL")
            )
            existing = {row[0] for row in result.fetchall()}
            _log(f"📊 Found {len(existing)} existing records in database")
            return existing
    except Exception as e:
        _log(f"⚠️ Database check failed: {e}")
        return set()

async def get_existing_names_for_user(user_id: str) -> set:
    """Get existing debtor names from database for a specific user to avoid duplicates"""
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                text("SELECT DISTINCT debtor_name FROM fulton_ga_filing WHERE userId = :user_id AND debtor_name IS NOT NULL AND debtor_name != ''"),
                {"user_id": user_id}
            )
            # Normalize names consistently (lowercase, remove extra spaces)
            existing = set()
            for row in result.fetchall():
                if row[0] and row[0].strip():
                    normalized = " ".join(row[0].strip().lower().split())
                    existing.add(normalized)
            
            _log(f"📊 Found {len(existing)} existing names in database for user {user_id}")
            return existing
    except Exception as e:
        _log(f"⚠️ Database check for existing names failed: {e}")
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
    csv_file = EXPORT_DIR / f"fulton_ga_{timestamp}.csv"
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
            worksheet = sheet.worksheet(FULTON_TAB)
        except:
            worksheet = sheet.add_worksheet(title=FULTON_TAB, rows=1000, cols=20)
        
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
    
    # Set default date range (last 30 days)
    if not from_date:
        from_date = (datetime.now() - timedelta(days=30)).strftime('%m/%d/%Y')
    if not to_date:
        to_date = datetime.now().strftime('%m/%d/%Y')
    
    # Set default instrument types (focus on lis pendens)
    if not instrument_types:
        instrument_types = ['Lis Pendens']  # Default to Lis Pendens (value=9)
    
    # Get existing case numbers
    existing_case_numbers = await get_existing_case_numbers()
    
    # Single search (letter-based looping disabled for now)
    all_records = []
    
    _log(f"Starting single search (letter-based search disabled)")
    
    # Prepare task parameters for single search
    task_params = {
        'max_records': max_new_records,
        'test_mode': test_mode,
        'date_from': from_date,
        'date_to': to_date,
        'instrument_types': instrument_types,
        'party_type': 'All Parties',
        'search_name': 'A'  # Just search for 'A' for now
    }
    
    try:
        # Run scraper once
        async with FultonScraper(config) as scraper:
            result = await scraper.scrape(task_params)
            
            if result.success and result.records:
                # Filter out existing records
                new_records = []
                for record in result.records:
                    clean_record = scraper.clean_record_data(record.data)
                    if clean_record['case_number'] not in existing_case_numbers:
                        new_records.append(clean_record)
                        existing_case_numbers.add(clean_record['case_number'])
                
                _log(f"📊 Found {len(new_records)} new records")
                all_records.extend(new_records)
            else:
                _log(f"⚠️ No records found")
        
        if all_records and not test_mode:
            # Save to database
            await upsert_records(all_records)
            
            # Export to files
            df = pd.DataFrame(all_records)
            await export_to_csv(df)
            export_to_google_sheets(df)
        
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