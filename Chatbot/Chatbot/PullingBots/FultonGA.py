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
    
    async def setup_search_parameters(self, task_params: Dict[str, Any]):
        """Setup Fulton County-specific search parameters"""
        
        # Load saved cookies FIRST to maintain session state
        await self.load_cookies()
        
        # Navigate to search page
        await self.navigate_to_url(self.config.search_config.search_url)
        await self.page.wait_for_timeout(2000)
        
        # Set instrument type to focus on lis pendens
        instrument_types = task_params.get('instrument_types', ['Lis Pendens'])
        if instrument_types and instrument_types != ['All Instruments']:
            # Map instrument type names to their values
            instrument_value_map = {
                'Lien': '8',
                'Lis Pendens': '9',
                'Federal Tax Lien': '3',
                'Assignment': '14',
                'Cancellation': '52',
                'FIFA': '2',
                'Levy': '54',
                'Notice': '10',
                'Order': '7',
                'Preliminary Notice of Lien': '11',
                'Personal Property Lien': '12',
                'Release': '4'
            }
            
            for instrument_type in instrument_types:
                instrument_value = instrument_value_map.get(instrument_type, '8')  # Default to Lien
                await self.page.select_option('select[name="txtInstrCode"]', instrument_value)
                _log(f"✅ Selected instrument type: {instrument_type} (value: {instrument_value})")
                break  # Select first one for now
        
        # Set party type if specified (commented out - PartyType field doesn't exist on this form)
        # party_type = task_params.get('party_type', 'All Parties')
        # await self.page.select_option('select[name="PartyType"]', party_type)
        _log("✅ Skipped party type selection (field not available on form)")
        
        # Always set county to FULTON for this scraper (value=60)
        await self.page.select_option('select[name="intCountyID"]', '60')
        _log(f"✅ Selected county: FULTON (value: 60)")
        
        # Set records per page to 25
        await self.page.select_option('select[name="MaxRows"]', '25')
        _log(f"✅ Set records per page: 25")
        
        # Set name search if provided (for letter-based searching)
        search_name = task_params.get('search_name')
        if search_name:
            await self.page.fill('input[name="txtSearchName"]', search_name)
            _log(f"✅ Set search name: {search_name}")
        
        # Set date range
        date_from = task_params.get('date_from')
        date_to = task_params.get('date_to')
        
        if date_from:
            await self.page.fill('input[name="txtFromDate"]', date_from)
        if date_to:
            await self.page.fill('input[name="txtToDate"]', date_to)
        
        # Set results per page to maximum
        await self.page.select_option('select[name="MaxRows"]', '50')
        
        # Click the search button (handle both active and inactive states)
        search_button = await self.find_search_button()
        await search_button.click()
        _log("✅ Clicked search button")
        
        # Wait 5 seconds for login form to appear
        await self.page.wait_for_timeout(5000)
        
        # Handle login if required
        await self.handle_login()
        
        _log(f"✅ Search parameters configured and search executed")
        
        # DEBUG: Check if snooze and continue elements are present on the page
        _log("🔍 DEBUG: Checking for Customer Communications elements on current page...")
        
        try:
            # Check for snooze dropdown
            snooze_count = await self.page.locator('select[name="Options"]').count()
            snooze_generic_count = await self.page.locator('select').count()
            _log(f"📊 Found {snooze_count} select[name='Options'] elements")
            _log(f"📊 Found {snooze_generic_count} total select elements")
            
            if snooze_generic_count > 0:
                # Get details about the select elements
                select_elements = self.page.locator('select')
                for i in range(min(3, snooze_generic_count)):  # Check first 3 select elements
                    try:
                        select_name = await select_elements.nth(i).get_attribute('name')
                        select_id = await select_elements.nth(i).get_attribute('id')
                        _log(f"  Select {i+1}: name='{select_name}', id='{select_id}'")
                        
                        # Check options in this select
                        options = select_elements.nth(i).locator('option')
                        option_count = await options.count()
                        _log(f"    Has {option_count} options")
                        
                        for j in range(min(5, option_count)):  # Check first 5 options
                            option_value = await options.nth(j).get_attribute('value')
                            option_text = await options.nth(j).text_content()
                            _log(f"      Option {j+1}: value='{option_value}', text='{option_text}'")
                    except Exception as e:
                        _log(f"  Error checking select element {i+1}: {e}")
            
            # Check for continue button
            continue_count = await self.page.locator('input[value="Continue"]').count()
            continue_submit_count = await self.page.locator('input[type="submit"]').count()
            _log(f"📊 Found {continue_count} input[value='Continue'] elements")
            _log(f"📊 Found {continue_submit_count} total submit input elements")
            
            if continue_submit_count > 0:
                # Get details about submit elements
                submit_elements = self.page.locator('input[type="submit"]')
                for i in range(min(3, continue_submit_count)):  # Check first 3 submit elements
                    try:
                        submit_name = await submit_elements.nth(i).get_attribute('name')
                        submit_value = await submit_elements.nth(i).get_attribute('value')
                        _log(f"  Submit {i+1}: name='{submit_name}', value='{submit_value}'")
                    except Exception as e:
                        _log(f"  Error checking submit element {i+1}: {e}")
            
            # Check current page URL and title
            current_url = self.page.url
            page_title = await self.page.title()
            _log(f"📄 Current page URL: {current_url}")
            _log(f"📄 Current page title: {page_title}")
            
            # Check if we're on Customer Communications page and handle it
            if "CustomerCommunicationApi" in current_url or "Announcement" in current_url:
                _log("🎯 We ARE on Customer Communications page - handling it now")
                
                # Take a debug screenshot
                await self.page.screenshot(path="debug_fulton_after_search.png")
                _log("📸 Debug screenshot saved: debug_fulton_after_search.png")
                
                # First, scroll down the page to make sure all elements are visible
                _log("📜 Scrolling down to reveal all page elements...")
                
                # Scroll to bottom of page first
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await self.page.wait_for_timeout(1000)
                
                # Then scroll back to top
                await self.page.evaluate("window.scrollTo(0, 0)")
                await self.page.wait_for_timeout(500)
                
                # Scroll down in increments to reveal content gradually
                page_height = await self.page.evaluate("document.body.scrollHeight")
                current_scroll = 0
                scroll_increment = 300  # Scroll 300px at a time
                
                while current_scroll < page_height:
                    await self.page.evaluate(f"window.scrollTo(0, {current_scroll})")
                    await self.page.wait_for_timeout(300)
                    current_scroll += scroll_increment
                    
                    # Check if snooze dropdown appears as we scroll
                    try:
                        if await self.page.locator('select').count() > 0:
                            _log(f"✅ Found select elements at scroll position {current_scroll}")
                            break
                    except:
                        continue
                
                _log("✅ Completed page scrolling - now looking for snooze elements")
                
                # Look for the snooze options dropdown/select (based on debug logs)
                snooze_selectors = [
                    'select[name="Options"]',    # Specific selector from debug logs
                    'select[id="Options"]',      # Alternative by ID
                    'select',                    # Generic fallback
                ]
                
                snooze_element = None
                for selector in snooze_selectors:
                    try:
                        elem = self.page.locator(selector)
                        if await elem.count() > 0:
                            snooze_element = elem.first
                            _log(f"✅ Found snooze dropdown using selector: {selector}")
                            break
                    except Exception as e:
                        _log(f"Warning: Could not use snooze selector {selector}: {e}")
                        continue
                
                if snooze_element:
                    # Select "Snooze 1 Day" option (value="snooze1d" based on debug logs)
                    try:
                        await snooze_element.select_option(value="snooze1d")
                        _log("✅ Selected 'Snooze 1 Day' option (value='snooze1d')")
                        await self.page.wait_for_timeout(1000)
                        
                        # Verify the selection was successful
                        selected_value = await snooze_element.input_value()
                        _log(f"📋 Snooze dropdown now shows selected value: '{selected_value}'")
                        
                    except Exception as e:
                        _log(f"❌ Failed to select snooze1d option: {e}")
                        # Try alternative selection methods
                        try:
                            await snooze_element.select_option(label="Snooze 1 Day")
                            _log("✅ Selected 'Snooze 1 Day' option by label")
                            await self.page.wait_for_timeout(1000)
                            
                            # Verify the alternative selection
                            selected_value = await snooze_element.input_value()
                            _log(f"📋 Snooze dropdown now shows selected value: '{selected_value}'")
                            
                        except Exception as e2:
                            _log(f"❌ Failed to select by label: {e2}")
                            _log("⚠️ Could not select snooze option, trying to continue anyway")
                else:
                    _log("⚠️ Could not find snooze dropdown, trying to continue anyway")
                
                # Scroll again to make sure Continue button is visible
                _log("📜 Scrolling to find Continue button...")
                
                # Try different scroll positions to find the Continue button
                scroll_positions = [0, 200, 400, 600, 800, page_height // 2, page_height]
                continue_found = False
                
                for scroll_pos in scroll_positions:
                    await self.page.evaluate(f"window.scrollTo(0, {scroll_pos})")
                    await self.page.wait_for_timeout(200)
                    
                    # Check if Continue button is visible at this scroll position
                    try:
                        if await self.page.locator('input[value="Continue"]').count() > 0:
                            _log(f"✅ Found Continue button at scroll position {scroll_pos}")
                            continue_found = True
                            break
                    except:
                        continue
                
                if not continue_found:
                    _log("⚠️ Continue button not found after scrolling - trying all selectors anyway")
                
                # Click the Continue button (based on debug logs)
                continue_selectors = [
                    'input[name="Continue"][value="Continue"]',  # Specific from debug logs
                    'input[value="Continue"]',                   # Generic by value
                    'input[type="submit"][value="Continue"]',    # By type and value
                    'button:has-text("Continue")'                # Button fallback
                ]
                
                continue_clicked = False
                for selector in continue_selectors:
                    try:
                        continue_button = self.page.locator(selector)
                        if await continue_button.count() > 0:
                            _log(f"🎯 Found Continue button using selector: {selector}")
                            
                            # Check if button is visible
                            is_visible = await continue_button.is_visible()
                            _log(f"📍 Continue button visible: {is_visible}")
                            
                            if is_visible:
                                await continue_button.click()
                                _log("✅ Clicked Continue button")
                                
                                # Log immediately after clicking
                                _log("⏳ Waiting for page response after clicking Continue...")
                                await self.page.wait_for_timeout(2000)  # Wait for initial response
                                
                                # Check if page is loading
                                loading_url = self.page.url
                                _log(f"📍 Current URL after Continue click: {loading_url}")
                                
                                continue_clicked = True
                                break
                            else:
                                # Try to scroll to make it visible
                                try:
                                    await continue_button.scroll_into_view_if_needed()
                                    await self.page.wait_for_timeout(500)
                                    await continue_button.click()
                                    _log("✅ Clicked Continue button after scrolling into view")
                                    
                                    # Log immediately after clicking
                                    _log("⏳ Waiting for page response after clicking Continue...")
                                    await self.page.wait_for_timeout(2000)  # Wait for initial response
                                    
                                    # Check if page is loading
                                    loading_url = self.page.url
                                    _log(f"📍 Current URL after Continue click: {loading_url}")
                                    
                                    continue_clicked = True
                                    break
                                except Exception as scroll_error:
                                    _log(f"⚠️ Failed to scroll and click: {scroll_error}")
                                    continue
                        else:
                            _log(f"⚠️ No Continue button found with selector: {selector}")
                    except Exception as e:
                        _log(f"⚠️ Failed to click continue with selector {selector}: {e}")
                        continue
                
                if not continue_clicked:
                    _log("❌ Could not find or click Continue button")
                    raise Exception("Failed to click Continue button on Customer Communications page")
                
                # Ensure browser is in standard view (not minimized)
                _log("🖥️ Ensuring browser is in standard view...")
                try:
                    await self.page.bring_to_front()
                    _log("✅ Brought browser window to front")
                except Exception as e:
                    _log(f"⚠️ Could not bring browser to front: {e}")
                
                # Wait for page to fully load after clicking Continue (staying on same browser)
                _log("⏳ Waiting for full page load after Continue click...")
                _log("🌐 Using same browser instance - no new browser will open")
                try:
                    # Wait for network to be idle (page fully loaded)
                    await self.page.wait_for_load_state("networkidle", timeout=15000)
                    _log("✅ Page load state: networkidle achieved on same browser")
                except Exception as e:
                    _log(f"⚠️ Network idle timeout (continuing anyway): {e}")
                
                # Additional wait for any JavaScript to complete
                await self.page.wait_for_timeout(3000)
                _log("✅ Additional wait completed for JavaScript execution")
                
                # Verify we're now on the correct search page (same browser instance)
                final_url = self.page.url
                page_title = await self.page.title()
                _log(f"📄 Final page URL (same browser): {final_url}")
                _log(f"📄 Final page title (same browser): {page_title}")
                _log("✅ Successfully stayed on same browser instance throughout process")
                
                # Take screenshot of final page for verification
                try:
                    await self.page.screenshot(path="debug_fulton_after_continue.png")
                    _log("📸 Final page screenshot saved: debug_fulton_after_continue.png")
                except Exception as screenshot_error:
                    _log(f"⚠️ Could not take final screenshot: {screenshot_error}")
                
                # Check if we're still on the announcement page
                if "CustomerCommunicationApi" in final_url or "Announcement" in final_url:
                    _log("⚠️ Still on announcement page after handling, may need manual intervention")
                else:
                    _log("✅ Successfully handled Customer Communications page and proceeded to search")
                    
                    # Now navigate through the search menu sequence
                    await self.navigate_search_menu()
                    
                    # Verify we can see search form elements
                    try:
                        search_form_count = await self.page.locator('form').count()
                        input_count = await self.page.locator('input').count()
                        select_count = await self.page.locator('select').count()
                        _log(f"📊 Search page verification - Forms: {search_form_count}, Inputs: {input_count}, Selects: {select_count}")
                        
                        if input_count > 0 and select_count > 0:
                            _log("✅ Search form elements detected - page appears to be ready")
                        else:
                            _log("⚠️ Limited form elements detected - page may still be loading")
                    except Exception as verify_error:
                        _log(f"⚠️ Could not verify search form elements: {verify_error}")
            else:
                _log("ℹ️ Not on Customer Communications page - continuing with normal flow")
                # Take a debug screenshot anyway
                await self.page.screenshot(path="debug_fulton_after_search.png")
                _log("📸 Debug screenshot saved: debug_fulton_after_search.png")
        
        except Exception as e:
            _log(f"❌ Error during Customer Communications page handling: {e}")
            # Fallback: require manual intervention
            _log("⚠️ MANUAL INTERVENTION REQUIRED:")
            _log("   - Customer Communications page could not be handled automatically")
            _log("   - Please manually handle the page (select snooze option and click Continue)")
            _log("   - Script will wait for 60 seconds for manual intervention...")
            _log("   - Press Ctrl+C to abort if needed")
            
            # Wait for manual intervention
            for i in range(60, 0, -5):
                _log(f"⏳ Waiting {i} seconds for manual intervention...")
                await self.page.wait_for_timeout(5000)
                
                # Check if we're still on the Customer Communications page
                current_url = self.page.url
                if "CustomerCommunicationApi" not in current_url and "Announcement" not in current_url:
                    _log("✅ Manual intervention successful - page has changed")
                    break
            else:
                _log("⚠️ Manual intervention timeout - continuing with current page state")
            
            # Final verification
            final_url = self.page.url
            _log(f"📄 Current page after manual intervention: {final_url}")
        
        _log("✅ Continuing with script execution...")
    
    async def navigate_search_menu(self):
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
            await self.apply_search_filters()
            
        except Exception as e:
            _log(f"❌ Error during search menu navigation: {e}")
            raise
    
    async def apply_search_filters(self):
        """Apply search filters on the name search page"""
        try:
            _log("🔧 Applying search filters on name search page...")
            
            # Wait for the search form to load
            await self.page.wait_for_timeout(2000)
            
            # Clear and set instrument type to Lis Pendens (value='9')
            instrument_select = self.page.locator('select[name="txtInstrCode"]')
            if await instrument_select.count() > 0:
                await instrument_select.select_option('9')  # Lis Pendens
                _log("✅ Set instrument type to Lis Pendens (value: 9)")
            else:
                _log("⚠️ Instrument type selector not found")
            
            # Clear and set county to FULTON (value='60')
            county_select = self.page.locator('select[name="intCountyID"]')
            if await county_select.count() > 0:
                await county_select.select_option('60')  # FULTON
                _log("✅ Set county to FULTON (value: 60)")
            else:
                _log("⚠️ County selector not found")
            
            # Clear and set records per page to maximum (50)
            maxrows_select = self.page.locator('select[name="MaxRows"]')
            if await maxrows_select.count() > 0:
                await maxrows_select.select_option('50')
                _log("✅ Set records per page to 50")
            else:
                _log("⚠️ MaxRows selector not found")
            
            # Clear and set search name (using 'A' for broad search)
            search_name_input = self.page.locator('input[name="txtSearchName"]')
            if await search_name_input.count() > 0:
                await search_name_input.clear()  # Clear existing text
                await search_name_input.fill('A')
                _log("✅ Set search name to 'A' (cleared previous input)")
            else:
                _log("⚠️ Search name input not found")
            
            # Clear and set date range (last 30 days)
            from datetime import datetime, timedelta
            from_date = (datetime.now() - timedelta(days=30)).strftime('%m/%d/%Y')
            to_date = datetime.now().strftime('%m/%d/%Y')
            
            from_date_input = self.page.locator('input[name="txtFromDate"]')
            if await from_date_input.count() > 0:
                await from_date_input.clear()  # Clear existing text
                await from_date_input.fill(from_date)
                _log(f"✅ Set from date to {from_date} (cleared previous input)")
            else:
                _log("⚠️ From date input not found")
            
            to_date_input = self.page.locator('input[name="txtToDate"]')
            if await to_date_input.count() > 0:
                await to_date_input.clear()  # Clear existing text
                await to_date_input.fill(to_date)
                _log(f"✅ Set to date to {to_date} (cleared previous input)")
            else:
                _log("⚠️ To date input not found")
            
            # Click the search button
            _log("🔍 Clicking search button...")
            search_button = await self.find_search_button()
            await search_button.click()
            _log("✅ Clicked search button - executing search")
            
            # Wait for search results
            _log("⏳ Waiting for search results...")
            await self.page.wait_for_timeout(5000)
            
            # Handle login if required
            await self.handle_login()
            
            # Final verification
            result_url = self.page.url
            _log(f"📄 Search results URL: {result_url}")
            _log("✅ Search filters applied and search executed successfully")
            
        except Exception as e:
            _log(f"❌ Error applying search filters: {e}")
            raise
    
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
            await scraper.setup_search_parameters(task_params)
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