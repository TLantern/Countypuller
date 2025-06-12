"""
Cobb County Georgia Public Notice Scraper

This script scrapes public notice records for Cobb County, Georgia from the
Georgia Public Notice website.

Website: https://www.georgiapublicnotice.com/

Features:
- Searches for recent Cobb County public notice records
- Filters by notice type (foreclosures, etc.)
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
BASE_URL = "https://www.georgiapublicnotice.com/(S(tv0ve0wmyued4k422mekjrk1))/Search.aspx#searchResults"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
MAX_NEW_RECORDS = 100  # Maximum number of new records to scrape per run
USER_ID = None  # Will be set from command line argument
COUNTY_NAME = "Cobb GA"

# Environment variables
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME = os.getenv("GSHEET_NAME")
COBB_TAB = os.getenv("COBB_TAB", "CobbGA")
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required")

# Database configuration
engine = create_async_engine(DB_URL, echo=False)

INSERT_SQL = """
INSERT INTO cobb_ga_filing
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
# COBB COUNTY SCRAPER CLASS
# ─────────────────────────────────────────────────────────────────────────────
class CobbScraper(SearchFormScraper):
    """Cobb County Georgia public notice scraper implementation"""
    
    async def start_browser(self):
        """Initialize browser with maximum stealth configuration"""
        _log("🛡️ Starting ultra-stealth browser...")
        
        from playwright.async_api import async_playwright
        import random
        
        # More realistic user agents
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        ]
        
        # Optimized stealth browser arguments (proven to work)
        stealth_args = [
            "--disable-blink-features=AutomationControlled",
            "--exclude-switches=enable-automation",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-translate",
            "--disable-background-timer-throttling",
            "--disable-renderer-backgrounding",
            "--disable-backgrounding-occluded-windows",
            "--disable-client-side-phishing-detection",
            "--disable-crash-reporter",
            "--no-crash-upload",
            "--disable-dev-shm-usage",
            "--disable-features=VizDisplayCompositor,TranslateUI",
            "--no-sandbox",
            "--disable-infobars",
            "--disable-notifications",
            "--disable-popup-blocking"
        ]
        
        playwright = await async_playwright().start()
        
        # Launch with optimized stealth (no slow_mo to avoid timeout)
        self.browser = await playwright.chromium.launch(
            headless=self.config.headless,
            args=stealth_args
        )
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            user_agent=random.choice(user_agents),
            viewport={'width': 1366, 'height': 768},
            locale='en-US',
            timezone_id='America/New_York',
            permissions=[],
            geolocation=None,
            color_scheme='light',
            extra_http_headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br, zstd',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Sec-Ch-Ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Ch-Ua-Platform-Version': '"15.0.0"',
                'Cache-Control': 'max-age=0',
                'DNT': '1'
            }
        )
        
        # Create page
        self.page = await self.context.new_page()
        
        # Set timeout
        self.page.set_default_timeout(self.config.timeout * 1000)
        
        # Apply advanced stealth patches
        await self._apply_stealth_patches()
        
        _log("✅ Ultra-stealth browser initialized successfully")
    
    async def _apply_stealth_patches(self):
        """Apply comprehensive stealth patches to avoid detection"""
        try:
            # Comprehensive stealth script covering all detection vectors
            await self.page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // Override plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }
                    ]
                });
                
                // Override languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                
                // Remove automation indicators
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_JSON;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Function;
                
                // Canvas fingerprint protection
                const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
                HTMLCanvasElement.prototype.toDataURL = function(...args) {
                    const context = this.getContext('2d');
                    if (context) {
                        const imageData = context.getImageData(0, 0, this.width, this.height);
                        for (let i = 0; i < imageData.data.length; i += 100) {
                            imageData.data[i] = Math.max(0, Math.min(255, imageData.data[i] + (Math.random() - 0.5)));
                        }
                        context.putImageData(imageData, 0, 0);
                    }
                    return originalToDataURL.apply(this, args);
                };
            """)
            
            _log("✅ Advanced stealth patches applied")
            
        except Exception as e:
            _log(f"⚠️ Stealth patches failed: {e}")
    
    async def _simulate_human_behavior(self):
        """Simulate human-like browsing behavior"""
        import random
        try:
            _log("👤 Simulating human-like behavior...")
            
            # Random mouse movements with more realistic patterns
            for i in range(random.randint(2, 5)):
                x = random.randint(100, 1200)
                y = random.randint(100, 600)
                await self.page.mouse.move(x, y)
                await self.page.wait_for_timeout(random.randint(100, 400))
            
            # Random scrolling
            scroll_delta = random.randint(50, 200)
            await self.page.mouse.wheel(0, scroll_delta)
            await self.page.wait_for_timeout(random.randint(500, 1200))
            
            # Scroll back up a bit
            await self.page.mouse.wheel(0, -random.randint(20, 80))
            await self.page.wait_for_timeout(random.randint(300, 800))
            
            # Focus on page and add some keyboard activity
            await self.page.focus('body')
            await self.page.wait_for_timeout(random.randint(200, 500))
            
            # Random click on non-interactive element (like body)
            await self.page.click('body', button='left')
            await self.page.wait_for_timeout(random.randint(100, 300))
            
            _log("✅ Human behavior simulation complete")
            
        except Exception as behavior_error:
            _log(f"⚠️ Human behavior simulation failed: {behavior_error}")

    async def navigate_to_search_results(self, task_params: Dict[str, Any]):
        """Navigate to Georgia Public Notice search page and execute search with maximum stealth"""
        
        _log("🌐 Navigating to Georgia Public Notice website with stealth mode...")
        
        # Navigate to the Georgia Public Notice search page
        await self.navigate_to_url(BASE_URL)
        await self.page.wait_for_timeout(8000)  # Longer initial wait to appear human
        
        _log("✅ Successfully navigated to Georgia Public Notice search page")
        _log(f"📄 Current URL: {self.page.url}")
        
        # Wait for the page to fully load with human-like behavior
        try:
            await self.page.wait_for_load_state("domcontentloaded", timeout=45000)
            await self.page.wait_for_load_state("networkidle", timeout=45000)
            _log("✅ Page loaded successfully")
        except Exception as load_error:
            _log(f"⚠️ Page load timeout (continuing anyway): {load_error}")
        
        # Simulate human-like behavior
        await self._simulate_human_behavior()
        
        # Now apply search filters
        await self.apply_search_filters(task_params)

    async def apply_search_filters(self, task_params: Dict[str, Any]):
        """Apply search filters using multiple interaction methods"""
        try:
            _log("🔧 Applying search filters...")
            
            # Wait for all form elements to load
            await self.page.wait_for_timeout(3000)
            
            # Step 1: Select "Foreclosures" from Popular Searches dropdown FIRST
            _log("🏛️ Selecting Foreclosures from Popular Searches dropdown...")
            try:
                foreclosure_select_js = """
                (() => {
                    // Look for the Popular Searches dropdown
                    const popularSearchesDropdown = document.querySelector('select[id*="ddlPopularSearches"]') || 
                                                   document.querySelector('select[name*="ddlPopularSearches"]');
                    
                    if (popularSearchesDropdown) {
                        console.log('Found Popular Searches dropdown:', popularSearchesDropdown.id);
                        
                        // Set the value to 16 (Foreclosures)
                        popularSearchesDropdown.value = '16';
                        
                        // Trigger change events to ensure the page updates
                        popularSearchesDropdown.dispatchEvent(new Event('change', { bubbles: true }));
                        popularSearchesDropdown.dispatchEvent(new Event('input', { bubbles: true }));
                        
                        // Also trigger the onchange event if it exists
                        if (popularSearchesDropdown.onchange) {
                            popularSearchesDropdown.onchange();
                        }
                        
                        return `foreclosures_selected_${popularSearchesDropdown.value}`;
                    }
                    
                    return 'dropdown_not_found';
                })()
                """
                
                foreclosure_result = await self.page.evaluate(foreclosure_select_js)
                _log(f"🔧 Foreclosures selection result: {foreclosure_result}")
                
                if 'foreclosures_selected' in foreclosure_result:
                    _log("✅ Selected Foreclosures from Popular Searches dropdown")
                    
                    # Wait 10 seconds for page to update as requested
                    _log("⏳ Waiting 10 seconds for page to update after selecting Foreclosures...")
                    await self.page.wait_for_timeout(10000)
                    
                else:
                    _log("❌ Could not find or select Popular Searches dropdown")
                    
            except Exception as dropdown_error:
                _log(f"⚠️ Foreclosures dropdown selection failed: {dropdown_error}")
            
            # Step 2: Expand County section
            _log("📂 Expanding County section...")
            try:
                county_js = """
                (() => {
                    const countyHeader = document.querySelector('label.header');
                    if (countyHeader && countyHeader.textContent.includes('County')) {
                        console.log('Found county header:', countyHeader);
                        countyHeader.click();
                        return 'county_clicked';
                    }
                    return 'county_not_found';
                })()
                """
                
                county_result = await self.page.evaluate(county_js)
                _log(f"🔧 County header JavaScript result: {county_result}")
                
                if county_result == 'county_clicked':
                    _log("✅ Expanded County section via JavaScript")
                    await self.page.wait_for_timeout(2000)
                else:
                    _log("❌ Could not expand County section")
                    
            except Exception as js_error:
                _log(f"⚠️ JavaScript County expansion failed: {js_error}")
            
            # Step 3: Select Cobb County
            _log("🏛️ Selecting Cobb County...")
            try:
                county_select_js = """
                (() => {
                    // Look for all checkbox inputs in the county section
                    const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                    
                    for (let checkbox of checkboxes) {
                        // Find the associated label
                        const label = document.querySelector(`label[for="${checkbox.id}"]`);
                        if (label && label.textContent.toLowerCase().includes('cobb')) {
                            console.log('Found Cobb checkbox:', checkbox.id, 'Label:', label.textContent);
                            // Click the checkbox directly
                            checkbox.click();
                            // Also trigger change event
                            checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                            return `cobb_selected_checkbox_${checkbox.id}`;
                        }
                    }
                    
                    // Fallback: Look for labels containing "cobb" and find their checkboxes
                    const labels = document.querySelectorAll('label');
                    for (let label of labels) {
                        if (label.textContent.toLowerCase().includes('cobb')) {
                            const forAttr = label.getAttribute('for');
                            if (forAttr) {
                                const checkbox = document.getElementById(forAttr);
                                if (checkbox && checkbox.type === 'checkbox') {
                                    console.log('Found Cobb via label:', forAttr, 'Text:', label.textContent);
                                    checkbox.click();
                                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                                    return `cobb_selected_via_label_${forAttr}`;
                                }
                            }
                        }
                    }
                    
                    return `cobb_not_found_total_checkboxes_${checkboxes.length}`;
                })()
                """
                
                county_select_result = await self.page.evaluate(county_select_js)
                _log(f"🔧 County selection JavaScript result: {county_select_result}")
                
                if 'cobb_selected' in county_select_result:
                    _log("✅ Selected Cobb County checkbox via JavaScript")
                else:
                    _log("❌ Could not find Cobb County checkbox")
                    
            except Exception as js_error:
                _log(f"⚠️ JavaScript County selection failed: {js_error}")
                
            # Step 4: Set date range using "Last N Days" input to go back to first of current month
            from datetime import datetime, date
            
            # Calculate days back to first of current month
            today = date.today()
            first_of_month = today.replace(day=1)
            days_back = (today - first_of_month).days + 1  # +1 to include first day
            
            _log(f"📅 Setting date range to last {days_back} days (back to first of month: {first_of_month})")
            
            try:
                last_days_js = f"""
                (() => {{
                    // Look for txtLastNumDays input field
                    const lastDaysSelectors = [
                        '[id*="txtLastNumDays"]',
                        '[name*="txtLastNumDays"]',
                        '[id*="LastNumDays"]',
                        '[name*="LastNumDays"]',
                        'input[id*="txtLast"]',
                        'input[name*="txtLast"]'
                    ];
                    
                    for (let selector of lastDaysSelectors) {{
                        const input = document.querySelector(selector);
                        
                        if (input && input.type === 'text') {{
                            console.log('Found last days input:', input.id || input.name);
                            
                            // Clear existing value first
                            input.value = '';
                            input.focus();
                            
                            // Set new value (days back to first of month)
                            input.value = '{days_back}';
                            
                            // Trigger multiple events to ensure ASP.NET viewstate updates
                            input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                            
                            return {{
                                found: true,
                                fieldId: input.id || input.name,
                                value: input.value
                            }};
                        }}
                    }}
                    
                    return {{
                        found: false,
                        fieldId: null,
                        value: null
                    }};
                }})()
                """
                
                last_days_result = await self.page.evaluate(last_days_js)
                _log(f"🔧 Last days field result: {last_days_result}")
                
                if last_days_result['found']:
                    _log(f"✅ Set last days field via JavaScript - {last_days_result['fieldId']} = {last_days_result['value']}")
                    await self.page.wait_for_timeout(1000)
                else:
                    _log("❌ Could not find txtLastNumDays field")
                    
            except Exception as js_error:
                _log(f"⚠️ JavaScript last days setting failed: {js_error}")
            
            await self.page.wait_for_timeout(2000)
            
            # Step 5: Submit search
            _log("🔍 Submitting search...")
            try:
                search_js = """
                (() => {
                    let searchClicked = false;
                    
                    // Method 1: Try ASP.NET-specific search button
                    const aspNetButtons = document.querySelectorAll('[id*="btnGo"], [id*="btnSearch"], [name*="btnGo"], [name*="btnSearch"]');
                    for (let button of aspNetButtons) {
                        if (button.type === 'submit' || button.tagName === 'INPUT') {
                            console.log('Found ASP.NET search button:', button.id, button.value);
                            
                            // Trigger ASP.NET postback if possible
                            if (typeof __doPostBack === 'function' && button.name) {
                                console.log('Using __doPostBack for:', button.name);
                                __doPostBack(button.name, '');
                                searchClicked = true;
                                return 'aspnet_postback_clicked';
                            } else {
                                button.click();
                                searchClicked = true;
                                return 'aspnet_button_clicked';
                            }
                        }
                    }
                    
                    // Method 2: Try generic search buttons
                    if (!searchClicked) {
                        const buttons = document.querySelectorAll('input[type="submit"], button[type="submit"], input[type="button"]');
                        for (let button of buttons) {
                            if ((button.value && button.value.toLowerCase().includes('search')) ||
                                (button.textContent && button.textContent.toLowerCase().includes('search'))) {
                                console.log('Found generic search button:', button.value || button.textContent);
                                button.click();
                                searchClicked = true;
                                return 'generic_search_clicked';
                            }
                        }
                    }
                    
                    return 'search_button_not_found';
                })()
                """
                
                search_result = await self.page.evaluate(search_js)
                _log(f"🔧 Enhanced search submission result: {search_result}")
                
                if search_result in ['aspnet_postback_clicked', 'aspnet_button_clicked', 'generic_search_clicked']:
                    _log("✅ Search submitted successfully")
                    
                    # Wait for results to load
                    _log("⏳ Waiting 12 seconds after search submission for results to load...")
                    await self.page.wait_for_timeout(12000)
                    
                    current_url = self.page.url
                    _log(f"📄 Current URL after search: {current_url}")
                else:
                    _log("❌ Could not click search button")
                    
            except Exception as js_error:
                _log(f"⚠️ JavaScript Search submission failed: {js_error}")
            
            _log("✅ Search filters applied successfully")
                
        except Exception as e:
            _log(f"❌ Error applying search filters: {e}")
            raise

    async def _verify_results_page(self) -> Dict[str, Any]:
        """Verify we've actually made it to the results page with data"""
        _log("🔍 Verifying we're on results page with actual data...")
        
        verification_js = """
        (() => {
            const analysis = {
                onResultsPage: false,
                hasSearchForm: false,
                hasDataGrids: false,
                hasResultRows: false,
                hasCaptchaElements: false,
                hasAgreeButtons: false,
                gridRowCount: 0,
                url: window.location.href,
                pageIndicators: []
            };
            
            // Check if we're on the search results page (not details/captcha page)
            if (window.location.href.includes('Search.aspx') && 
                window.location.href.includes('#searchResults')) {
                analysis.onResultsPage = true;
                analysis.pageIndicators.push('on_search_results_page');
            }
            
            // Check for search form elements (indicates results page)
            const searchFormSelectors = [
                '[id*="ddlPopularSearches"]',
                'label.header',
                '[id*="lstCounty"]',
                '[id*="txtLastNumDays"]'
            ];
            
            for (let selector of searchFormSelectors) {
                if (document.querySelector(selector)) {
                    analysis.hasSearchForm = true;
                    analysis.pageIndicators.push(`search_form_${selector}`);
                    break;
                }
            }
            
            // Check for data grids with results using better selectors
            const gridSelectors = [
                '[id*="GridView"]',
                '[id*="WSExtendedGridNP1"]', 
                'table[id*="WSExtended"]',
                '[id*="ContentPlaceHolder1"] table'
            ];
            
            for (let selector of gridSelectors) {
                const grids = document.querySelectorAll(selector);
                
                for (let grid of grids) {
                    const rows = grid.querySelectorAll('tr');
                    analysis.gridRowCount += rows.length;
                    
                    if (rows.length > 1) { // More than just header
                        analysis.hasDataGrids = true;
                        analysis.pageIndicators.push(`data_grid_found_${selector}`);
                        
                        // Check for actual meaningful data rows
                        for (let i = 1; i < rows.length; i++) {
                            const rowText = rows[i].textContent.trim();
                            if (rowText.length > 30 && 
                                !rowText.toLowerCase().includes('no results') && 
                                !rowText.toLowerCase().includes('no records') &&
                                (rowText.includes('GA') || rowText.includes('Cobb') || 
                                 rowText.match(/\\d{1,2}\\/\\d{1,2}\\/\\d{4}/) || 
                                 rowText.includes('Foreclosure'))) {
                                analysis.hasResultRows = true;
                                analysis.pageIndicators.push('meaningful_result_rows_found');
                                break;
                            }
                        }
                    }
                }
            }
            
            // Check if we're still seeing captcha elements from screenshot
            const captchaSelectors = [
                '[data-sitekey*="6LeK4ZoUAAAAAFG3gQ8C4gK9wYrYptUDxNO4D5H"]',
                '#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha',
                '.g-recaptcha'
            ];
            
            for (let selector of captchaSelectors) {
                const elements = document.querySelectorAll(selector);
                for (let element of elements) {
                    if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                        analysis.hasCaptchaElements = true;
                        analysis.pageIndicators.push(`captcha_element_${selector}`);
                        break;
                    }
                }
            }
            
            // Check for agree buttons still visible
            const agreeSelectors = [
                'input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]',
                'input[value*="I Agree" i]',
                'input[value*="View Notice" i]'
            ];
            
            for (let selector of agreeSelectors) {
                const elements = document.querySelectorAll(selector);
                for (let element of elements) {
                    if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                        analysis.hasAgreeButtons = true;
                        analysis.pageIndicators.push(`agree_button_${selector}`);
                        break;
                    }
                }
            }
            
            return analysis;
        })()
        """
        
        try:
            verification_result = await self.page.evaluate(verification_js)
            
            # Log detailed analysis
            _log(f"📊 Results page verification:")
            _log(f"   • On results page: {verification_result['onResultsPage']}")
            _log(f"   • Has search form: {verification_result['hasSearchForm']}")
            _log(f"   • Has data grids: {verification_result['hasDataGrids']}")
            _log(f"   • Has result rows: {verification_result['hasResultRows']}")
            _log(f"   • Total grid rows: {verification_result['gridRowCount']}")
            _log(f"   • Still has captcha: {verification_result['hasCaptchaElements']}")
            _log(f"   • Still has agree buttons: {verification_result['hasAgreeButtons']}")
            
            # Determine overall success
            success = (verification_result['onResultsPage'] and 
                      verification_result['hasSearchForm'] and
                      not verification_result['hasCaptchaElements'] and
                      not verification_result['hasAgreeButtons'])
            
            verification_result['success'] = success
            return verification_result
            
        except Exception as e:
            _log(f"❌ Results page verification failed: {e}")
            return {'success': False, 'error': str(e)}

    async def _debug_captcha_state(self):
        """Comprehensive debugging of captcha state and form validation"""
        _log("🔍 DEBUGGING: Comprehensive captcha state analysis...")
        
        debug_js = """
        (() => {
            const debug = {
                timestamp: new Date().toISOString(),
                url: window.location.href,
                recaptcha: {},
                form: {},
                button: {},
                errors: [],
                console_errors: [],
                network_info: {},
                validation: {}
            };
            
            // Capture any console errors
            const originalConsoleError = console.error;
            const consoleErrors = [];
            console.error = function(...args) {
                consoleErrors.push(args.map(arg => String(arg)).join(' '));
                originalConsoleError.apply(console, arguments);
            };
            debug.console_errors = consoleErrors;
            
            // 1. reCAPTCHA Analysis
            try {
                const recaptchaDiv = document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha');
                const recaptchaElement = document.querySelector('[data-sitekey]') || document.querySelector('.g-recaptcha');
                const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                
                debug.recaptcha = {
                    panel_present: !!recaptchaDiv,
                    panel_visible: recaptchaDiv ? (recaptchaDiv.offsetWidth > 0 && recaptchaDiv.offsetHeight > 0) : false,
                    element_present: !!recaptchaElement,
                    element_visible: recaptchaElement ? (recaptchaElement.offsetWidth > 0 && recaptchaElement.offsetHeight > 0) : false,
                    sitekey: recaptchaElement ? recaptchaElement.getAttribute('data-sitekey') : null,
                    response_element_present: !!recaptchaResponse,
                    response_value: recaptchaResponse ? recaptchaResponse.value : null,
                    response_length: recaptchaResponse ? recaptchaResponse.value.length : 0,
                    is_solved: recaptchaResponse ? (recaptchaResponse.value.length > 0) : false
                };
                
                // Check if reCAPTCHA callback functions exist
                if (typeof grecaptcha !== 'undefined') {
                    debug.recaptcha.grecaptcha_loaded = true;
                    debug.recaptcha.grecaptcha_ready = typeof grecaptcha.ready === 'function';
                } else {
                    debug.recaptcha.grecaptcha_loaded = false;
                }
                
            } catch (e) {
                debug.errors.push(`reCAPTCHA analysis error: ${e.message}`);
            }
            
            // 2. Form Analysis
            try {
                const form = document.querySelector('form');
                const viewNoticeButton = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                
                debug.form = {
                    form_present: !!form,
                    form_id: form ? form.id : null,
                    form_action: form ? form.action : null,
                    form_method: form ? form.method : null,
                    __doPostBack_available: typeof __doPostBack === 'function',
                    __VIEWSTATE_present: !!document.querySelector('input[name="__VIEWSTATE"]'),
                    __EVENTVALIDATION_present: !!document.querySelector('input[name="__EVENTVALIDATION"]')
                };
                
                if (form) {
                    const formData = new FormData(form);
                    debug.form.form_data_keys = Array.from(formData.keys()).slice(0, 10); // First 10 keys
                }
                
            } catch (e) {
                debug.errors.push(`Form analysis error: ${e.message}`);
            }
            
            // 3. Button Analysis
            try {
                const viewNoticeButton = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                
                debug.button = {
                    button_present: !!viewNoticeButton,
                    button_visible: viewNoticeButton ? (viewNoticeButton.offsetWidth > 0 && viewNoticeButton.offsetHeight > 0) : false,
                    button_disabled: viewNoticeButton ? viewNoticeButton.disabled : null,
                    button_value: viewNoticeButton ? viewNoticeButton.value : null,
                    button_name: viewNoticeButton ? viewNoticeButton.name : null,
                    button_type: viewNoticeButton ? viewNoticeButton.type : null,
                    button_onclick: viewNoticeButton ? (viewNoticeButton.onclick ? viewNoticeButton.onclick.toString() : null) : null
                };
                
            } catch (e) {
                debug.errors.push(`Button analysis error: ${e.message}`);
            }
            
            // 4. Validation Checks
            try {
                debug.validation = {
                    page_ready_state: document.readyState,
                    page_loaded: document.readyState === 'complete',
                    jquery_available: typeof $ !== 'undefined',
                    aspnet_postback_available: typeof __doPostBack === 'function',
                    page_contains_error_message: document.body.textContent.toLowerCase().includes('error'),
                    page_contains_validation_message: document.body.textContent.toLowerCase().includes('required') || 
                                                    document.body.textContent.toLowerCase().includes('invalid')
                };
                
            } catch (e) {
                debug.errors.push(`Validation analysis error: ${e.message}`);
            }
            
            return debug;
        })()
        """
        
        try:
            debug_result = await self.page.evaluate(debug_js)
            
            _log("🔍 CAPTCHA DEBUG ANALYSIS:")
            _log(f"   📅 Timestamp: {debug_result['timestamp']}")
            _log(f"   🌐 URL: {debug_result['url'][:100]}...")
            
            _log("🤖 reCAPTCHA State:")
            recaptcha = debug_result['recaptcha']
            _log(f"   • Panel present: {recaptcha.get('panel_present', False)}")
            _log(f"   • Panel visible: {recaptcha.get('panel_visible', False)}")
            _log(f"   • Element present: {recaptcha.get('element_present', False)}")
            _log(f"   • Element visible: {recaptcha.get('element_visible', False)}")
            _log(f"   • Sitekey: {recaptcha.get('sitekey', 'None')}")
            _log(f"   • Response present: {recaptcha.get('response_element_present', False)}")
            _log(f"   • Response length: {recaptcha.get('response_length', 0)}")
            _log(f"   • Is solved: {recaptcha.get('is_solved', False)}")
            _log(f"   • grecaptcha loaded: {recaptcha.get('grecaptcha_loaded', False)}")
            
            _log("📝 Form State:")
            form = debug_result['form']
            _log(f"   • Form present: {form.get('form_present', False)}")
            _log(f"   • Form action: {form.get('form_action', 'None')}")
            _log(f"   • __doPostBack available: {form.get('__doPostBack_available', False)}")
            _log(f"   • __VIEWSTATE present: {form.get('__VIEWSTATE_present', False)}")
            _log(f"   • __EVENTVALIDATION present: {form.get('__EVENTVALIDATION_present', False)}")
            
            _log("🔘 Button State:")
            button = debug_result['button']
            _log(f"   • Button present: {button.get('button_present', False)}")
            _log(f"   • Button visible: {button.get('button_visible', False)}")
            _log(f"   • Button disabled: {button.get('button_disabled', 'Unknown')}")
            _log(f"   • Button value: {button.get('button_value', 'None')}")
            _log(f"   • Button onclick: {str(button.get('button_onclick', 'None'))[:100]}...")
            
            _log("✅ Validation State:")
            validation = debug_result['validation']
            _log(f"   • Page ready: {validation.get('page_loaded', False)}")
            _log(f"   • ASP.NET available: {validation.get('aspnet_postback_available', False)}")
            _log(f"   • Has error messages: {validation.get('page_contains_error_message', False)}")
            _log(f"   • Has validation messages: {validation.get('page_contains_validation_message', False)}")
            
            if debug_result.get('errors'):
                _log("❌ Debug Errors:")
                for error in debug_result['errors']:
                    _log(f"   • {error}")
            
            if debug_result.get('console_errors'):
                _log("🚨 Console Errors:")
                for error in debug_result['console_errors']:
                    _log(f"   • {error}")
            
            return debug_result
            
        except Exception as e:
            _log(f"❌ Debug analysis failed: {e}")
            return None

    async def _attempt_manual_button_click_with_monitoring(self):
        """Attempt button click with comprehensive monitoring of what happens"""
        _log("🎯 ATTEMPTING MANUAL BUTTON CLICK WITH FULL MONITORING...")
        
        # Set up network request monitoring
        network_requests = []
        
        def handle_request(request):
            network_requests.append({
                'url': request.url,
                'method': request.method,
                'timestamp': datetime.now().isoformat()
            })
        
        def handle_response(response):
            for req in network_requests:
                if req['url'] == response.url and 'response' not in req:
                    req['response'] = {
                        'status': response.status,
                        'status_text': response.status_text,
                        'timestamp': datetime.now().isoformat()
                    }
        
        # Attach network listeners
        self.page.on('request', handle_request)
        self.page.on('response', handle_response)
        
        try:
            # Pre-click debug state
            _log("📊 PRE-CLICK STATE:")
            pre_click_debug = await self._debug_captcha_state()
            
            # Enhanced button click with monitoring
            click_monitoring_js = """
            (() => {
                const results = {
                    clicked: false,
                    error: null,
                    events_fired: [],
                    form_submitted: false,
                    postback_called: false,
                    button_state_after: {},
                    page_state_after: {}
                };
                
                try {
                    const button = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                    
                    if (!button) {
                        results.error = 'Button not found';
                        return results;
                    }
                    
                    if (button.disabled) {
                        results.error = 'Button is disabled';
                        return results;
                    }
                    
                    // Monitor events
                    const originalAddEventListener = button.addEventListener;
                    button.addEventListener = function(type, listener, options) {
                        results.events_fired.push(`addEventListener: ${type}`);
                        return originalAddEventListener.call(this, type, listener, options);
                    };
                    
                    // Check reCAPTCHA state before click
                    const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                    const recaptchaSolved = recaptchaResponse && recaptchaResponse.value.length > 0;
                    
                    if (!recaptchaSolved) {
                        results.error = 'reCAPTCHA not solved - response token empty';
                        return results;
                    }
                    
                    // Focus and click button
                    button.focus();
                    results.events_fired.push('button focused');
                    
                    // Try multiple click methods
                    button.click();
                    results.clicked = true;
                    results.events_fired.push('button.click() called');
                    
                    // Try direct event dispatch
                    button.dispatchEvent(new Event('click', { bubbles: true, cancelable: true }));
                    results.events_fired.push('click event dispatched');
                    
                    // Try form submission events
                    const form = button.closest('form');
                    if (form) {
                        button.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
                        results.events_fired.push('submit event dispatched');
                        
                        // Try ASP.NET postback
                        if (typeof __doPostBack === 'function' && button.name) {
                            __doPostBack(button.name, '');
                            results.postback_called = true;
                            results.events_fired.push('__doPostBack called');
                        }
                    }
                    
                    // Check button state after click
                    results.button_state_after = {
                        disabled: button.disabled,
                        value: button.value,
                        visible: button.offsetWidth > 0 && button.offsetHeight > 0
                    };
                    
                    // Check page state after click
                    results.page_state_after = {
                        url: window.location.href,
                        ready_state: document.readyState,
                        has_recaptcha: !!document.querySelector('[data-sitekey]'),
                        has_agree_button: !!document.querySelector('input[value*="I Agree" i]')
                    };
                    
                } catch (e) {
                    results.error = e.message;
                }
                
                return results;
            })()
            """
            
            click_result = await self.page.evaluate(click_monitoring_js)
            
            _log("🎯 BUTTON CLICK MONITORING RESULTS:")
            _log(f"   ✅ Button clicked: {click_result.get('clicked', False)}")
            _log(f"   🚫 Error: {click_result.get('error', 'None')}")
            _log(f"   📋 Events fired: {len(click_result.get('events_fired', []))}")
            for event in click_result.get('events_fired', []):
                _log(f"      • {event}")
            _log(f"   📤 Postback called: {click_result.get('postback_called', False)}")
            
            # Wait for potential navigation/update
            _log("⏳ Waiting 10 seconds for page response...")
            await self.page.wait_for_timeout(10000)
            
            # Check network requests that occurred
            _log(f"🌐 Network requests during click: {len(network_requests)}")
            for req in network_requests[-5:]:  # Last 5 requests
                _log(f"   • {req['method']} {req['url'][:100]}... → {req.get('response', {}).get('status', 'pending')}")
            
            # Post-click debug state
            _log("📊 POST-CLICK STATE:")
            post_click_debug = await self._debug_captcha_state()
            
            # Compare states
            if pre_click_debug and post_click_debug:
                url_changed = pre_click_debug['url'] != post_click_debug['url']
                recaptcha_state_changed = (pre_click_debug['recaptcha'].get('panel_visible') != 
                                         post_click_debug['recaptcha'].get('panel_visible'))
                
                _log(f"🔄 STATE CHANGES:")
                _log(f"   • URL changed: {url_changed}")
                _log(f"   • reCAPTCHA state changed: {recaptcha_state_changed}")
                
                if url_changed:
                    _log(f"   • Old URL: {pre_click_debug['url'][:100]}...")
                    _log(f"   • New URL: {post_click_debug['url'][:100]}...")
            
            return click_result
            
        except Exception as e:
            _log(f"❌ Manual button click monitoring failed: {e}")
            return None
        finally:
            # Remove network listeners
            try:
                self.page.remove_listener('request', handle_request)
                self.page.remove_listener('response', handle_response)
            except:
                pass

    async def _comprehensive_captcha_debug(self):
        """Add detailed debugging to understand why captcha isn't working"""
        _log("🔍 COMPREHENSIVE CAPTCHA DEBUG ANALYSIS...")
        
        debug_js = """
        (() => {
            const debug = {
                recaptcha: {},
                button: {},
                form: {},
                page: {},
                errors: []
            };
            
            try {
                // reCAPTCHA Analysis
                const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                const recaptchaElement = document.querySelector('[data-sitekey]');
                const recaptchaFrame = document.querySelector('.g-recaptcha iframe');
                
                debug.recaptcha = {
                    response_exists: !!recaptchaResponse,
                    response_value: recaptchaResponse ? recaptchaResponse.value : null,
                    response_length: recaptchaResponse ? recaptchaResponse.value.length : 0,
                    element_exists: !!recaptchaElement,
                    sitekey: recaptchaElement ? recaptchaElement.getAttribute('data-sitekey') : null,
                    frame_exists: !!recaptchaFrame,
                    grecaptcha_available: typeof grecaptcha !== 'undefined',
                    is_solved: recaptchaResponse ? (recaptchaResponse.value.length > 0) : false
                };
                
                // Button Analysis  
                const button = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                debug.button = {
                    exists: !!button,
                    disabled: button ? button.disabled : null,
                    visible: button ? (button.offsetWidth > 0 && button.offsetHeight > 0) : false,
                    value: button ? button.value : null,
                    name: button ? button.name : null,
                    onclick_code: button && button.onclick ? button.onclick.toString() : null
                };
                
                // Form Analysis
                const form = document.querySelector('form');
                debug.form = {
                    exists: !!form,
                    action: form ? form.action : null,
                    method: form ? form.method : null,
                    viewstate: !!document.querySelector('input[name="__VIEWSTATE"]'),
                    eventvalidation: !!document.querySelector('input[name="__EVENTVALIDATION"]'),
                    dopostback_function: typeof __doPostBack === 'function'
                };
                
                // Page Analysis
                debug.page = {
                    url: window.location.href,
                    ready_state: document.readyState,
                    has_errors: document.body.textContent.toLowerCase().includes('error'),
                    has_validation: document.body.textContent.toLowerCase().includes('required'),
                    console_errors: window.console._errors || []
                };
                
            } catch (e) {
                debug.errors.push(e.message);
            }
            
            return debug;
        })()
        """
        
        debug_result = await self.page.evaluate(debug_js)
        
        _log("🤖 reCAPTCHA State:")
        recaptcha = debug_result['recaptcha']
        _log(f"   • Response element: {recaptcha['response_exists']}")
        _log(f"   • Response length: {recaptcha['response_length']}")
        _log(f"   • Is solved: {recaptcha['is_solved']}")
        _log(f"   • Sitekey: {recaptcha['sitekey']}")
        _log(f"   • grecaptcha available: {recaptcha['grecaptcha_available']}")
        
        _log("🔘 Button State:")
        button = debug_result['button']
        _log(f"   • Button exists: {button['exists']}")
        _log(f"   • Button disabled: {button['disabled']}")
        _log(f"   • Button visible: {button['visible']}")
        _log(f"   • Button value: {button['value']}")
        
        _log("📝 Form State:")
        form = debug_result['form']
        _log(f"   • Form exists: {form['exists']}")
        _log(f"   • ASP.NET postback: {form['dopostback_function']}")
        _log(f"   • ViewState present: {form['viewstate']}")
        _log(f"   • EventValidation present: {form['eventvalidation']}")
        
        if debug_result['errors']:
            _log("❌ Debug errors:")
            for error in debug_result['errors']:
                _log(f"   • {error}")
        
        return debug_result

    async def _monitor_button_click(self):
        """Monitor what happens when button is clicked with network tracking"""
        _log("🎯 MONITORING BUTTON CLICK WITH NETWORK TRACKING...")
        
        # Track network requests
        requests = []
        
        async def track_request(request):
            requests.append({
                'url': request.url,
                'method': request.method,
                'time': datetime.now().isoformat()
            })
        
        self.page.on('request', track_request)
        
        try:
            # Attempt monitored click
            click_js = """
            (() => {
                const result = {
                    attempted: false,
                    success: false,
                    error: null,
                    events: [],
                    recaptcha_check: {},
                    network_expected: false
                };
                
                try {
                    const button = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                    if (!button) {
                        result.error = 'Button not found';
                        return result;
                    }
                    
                    // Check reCAPTCHA before click
                    const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                    result.recaptcha_check = {
                        response_exists: !!recaptchaResponse,
                        response_value: recaptchaResponse ? recaptchaResponse.value : '',
                        response_length: recaptchaResponse ? recaptchaResponse.value.length : 0,
                        is_solved: recaptchaResponse ? recaptchaResponse.value.length > 0 : false
                    };
                    
                    if (!result.recaptcha_check.is_solved) {
                        result.error = 'reCAPTCHA not solved';
                        return result;
                    }
                    
                    result.attempted = true;
                    
                    // Try click
                    button.focus();
                    result.events.push('focused');
                    
                    button.click();
                    result.events.push('clicked');
                    
                    // Try ASP.NET postback
                    if (typeof __doPostBack === 'function') {
                        __doPostBack(button.name, '');
                        result.events.push('postback_called');
                        result.network_expected = true;
                    }
                    
                    result.success = true;
                    
                } catch (e) {
                    result.error = e.message;
                }
                
                return result;
            })()
            """
            
            click_result = await self.page.evaluate(click_js)
            
            _log("🎯 Click monitoring results:")
            _log(f"   • Attempted: {click_result['attempted']}")
            _log(f"   • Success: {click_result['success']}")
            _log(f"   • Error: {click_result['error']}")
            _log(f"   • Events: {click_result['events']}")
            _log(f"   • reCAPTCHA solved: {click_result['recaptcha_check']['is_solved']}")
            _log(f"   • reCAPTCHA response length: {click_result['recaptcha_check']['response_length']}")
            
            # Wait for network activity
            if click_result['network_expected']:
                _log("⏳ Waiting for network requests...")
                await self.page.wait_for_timeout(5000)
                
                _log(f"🌐 Network requests during click: {len(requests)}")
                for req in requests[-3:]:  # Last 3 requests
                    _log(f"   • {req['method']} {req['url'][:80]}...")
            
            return click_result
            
        finally:
            self.page.remove_listener('request', track_request)

    async def _debug_html_changes_on_click(self):
        """Debug HTML changes when clicking I Agree button"""
        _log("🔍 DEBUGGING HTML CHANGES ON BUTTON CLICK...")
        
        # Capture initial HTML state
        initial_state_js = """
        (() => {
            return {
                url: window.location.href,
                title: document.title,
                html_length: document.documentElement.outerHTML.length,
                body_text_length: document.body.textContent.length,
                form_count: document.querySelectorAll('form').length,
                input_count: document.querySelectorAll('input').length,
                button_count: document.querySelectorAll('button, input[type="submit"], input[type="button"]').length,
                captcha_elements: document.querySelectorAll('[data-sitekey], .g-recaptcha').length,
                agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length,
                recaptcha_response: document.querySelector('textarea[name="g-recaptcha-response"]') ? 
                                   document.querySelector('textarea[name="g-recaptcha-response"]').value.length : 0,
                specific_elements: {
                    recaptcha_panel: !!document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha'),
                    agree_button: !!document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]'),
                    viewstate: !!document.querySelector('input[name="__VIEWSTATE"]'),
                    eventvalidation: !!document.querySelector('input[name="__EVENTVALIDATION"]')
                }
            };
        })()
        """
        
        initial_state = await self.page.evaluate(initial_state_js)
        
        _log("📊 INITIAL STATE:")
        _log(f"   • URL: {initial_state['url'][:100]}...")
        _log(f"   • HTML length: {initial_state['html_length']} chars")
        _log(f"   • Forms: {initial_state['form_count']}")
        _log(f"   • Inputs: {initial_state['input_count']}")
        _log(f"   • Buttons: {initial_state['button_count']}")
        _log(f"   • Captcha elements: {initial_state['captcha_elements']}")
        _log(f"   • Agree buttons: {initial_state['agree_buttons']}")
        _log(f"   • reCAPTCHA response length: {initial_state['recaptcha_response']}")
        
        # Set up DOM mutation observer
        setup_monitoring_js = """
        (() => {
            window.debugData = {
                mutations: [],
                consoleMessages: [],
                errors: []
            };
            
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    window.debugData.mutations.push({
                        type: mutation.type,
                        target: mutation.target.tagName + (mutation.target.id ? '#' + mutation.target.id : ''),
                        addedNodes: mutation.addedNodes.length,
                        removedNodes: mutation.removedNodes.length,
                        attributeName: mutation.attributeName,
                        timestamp: new Date().toISOString()
                    });
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                characterData: true
            });
            
            window.addEventListener('error', (e) => {
                window.debugData.errors.push({
                    message: e.message,
                    filename: e.filename,
                    lineno: e.lineno,
                    timestamp: new Date().toISOString()
                });
            });
            
            return 'monitoring_setup_complete';
        })()
        """
        
        await self.page.evaluate(setup_monitoring_js)
        
        # Set up network monitoring
        network_requests = []
        
        def handle_request(request):
            network_requests.append({
                'url': request.url,
                'method': request.method,
                'timestamp': datetime.now().isoformat(),
                'type': 'request'
            })
        
        def handle_response(response):
            network_requests.append({
                'url': response.url,
                'status': response.status,
                'timestamp': datetime.now().isoformat(),
                'type': 'response'
            })
        
        self.page.on('request', handle_request)
        self.page.on('response', handle_response)
        
        try:
            # Click the button
            _log("🎯 CLICKING 'I AGREE' BUTTON WITH MONITORING...")
            
            click_result_js = """
            (() => {
                const result = {
                    clicked: false,
                    error: null,
                    button_info: {},
                    recaptcha_info: {}
                };
                
                try {
                    const button = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                    
                    if (!button) {
                        result.error = 'Button not found';
                        return result;
                    }
                    
                    result.button_info = {
                        name: button.name,
                        value: button.value,
                        disabled: button.disabled,
                        visible: button.offsetWidth > 0 && button.offsetHeight > 0
                    };
                    
                    const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                    result.recaptcha_info = {
                        response_exists: !!recaptchaResponse,
                        response_length: recaptchaResponse ? recaptchaResponse.value.length : 0,
                        is_solved: recaptchaResponse ? recaptchaResponse.value.length > 0 : false
                    };
                    
                    window.debugData.mutations = [];
                    window.debugData.consoleMessages = [];
                    window.debugData.errors = [];
                    
                    button.focus();
                    button.click();
                    result.clicked = true;
                    
                    if (typeof __doPostBack === 'function' && button.name) {
                        __doPostBack(button.name, '');
                    }
                    
                } catch (e) {
                    result.error = e.message;
                }
                
                return result;
            })()
            """
            
            click_result = await self.page.evaluate(click_result_js)
            
            _log("🎯 BUTTON CLICK RESULTS:")
            _log(f"   • Button clicked: {click_result['clicked']}")
            _log(f"   • Error: {click_result.get('error', 'None')}")
            _log(f"   • Button disabled: {click_result['button_info']['disabled']}")
            _log(f"   • reCAPTCHA solved: {click_result['recaptcha_info']['is_solved']}")
            
            # Wait for changes
            _log("⏳ Waiting 10 seconds for page changes...")
            await self.page.wait_for_timeout(10000)
            
            # Capture final state
            final_analysis_js = """
            (() => {
                const finalState = {
                    url: window.location.href,
                    title: document.title,
                    html_length: document.documentElement.outerHTML.length,
                    body_text_length: document.body.textContent.length,
                    form_count: document.querySelectorAll('form').length,
                    input_count: document.querySelectorAll('input').length,
                    button_count: document.querySelectorAll('button, input[type="submit"], input[type="button"]').length,
                    captcha_elements: document.querySelectorAll('[data-sitekey], .g-recaptcha').length,
                    agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length,
                    recaptcha_response: document.querySelector('textarea[name="g-recaptcha-response"]') ? 
                                       document.querySelector('textarea[name="g-recaptcha-response"]').value.length : 0,
                    specific_elements: {
                        recaptcha_panel: !!document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha'),
                        agree_button: !!document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]'),
                        viewstate: !!document.querySelector('input[name="__VIEWSTATE"]'),
                        eventvalidation: !!document.querySelector('input[name="__EVENTVALIDATION"]')
                    },
                    changes_detected: window.debugData
                };
                
                return finalState;
            })()
            """
            
            final_state = await self.page.evaluate(final_analysis_js)
            
            # Log network activity
            _log(f"🌐 NETWORK ACTIVITY: {len(network_requests)} requests/responses")
            for req in network_requests[-10:]:  # Last 10 network events
                if req['type'] == 'request':
                    _log(f"   → {req['method']} {req['url'][:100]}...")
                else:
                    _log(f"   ← {req['status']} {req['url'][:100]}...")
            
            # Compare states and log changes
            _log("🔄 ANALYZING CHANGES:")
            
            changes = {
                'url_changed': initial_state['url'] != final_state['url'],
                'title_changed': initial_state['title'] != final_state['title'],
                'html_length_diff': final_state['html_length'] - initial_state['html_length'],
                'body_text_diff': final_state['body_text_length'] - initial_state['body_text_length'],
                'form_count_diff': final_state['form_count'] - initial_state['form_count'],
                'input_count_diff': final_state['input_count'] - initial_state['input_count'],
                'button_count_diff': final_state['button_count'] - initial_state['button_count'],
                'captcha_elements_diff': final_state['captcha_elements'] - initial_state['captcha_elements'],
                'agree_buttons_diff': final_state['agree_buttons'] - initial_state['agree_buttons'],
                'recaptcha_response_diff': final_state['recaptcha_response'] - initial_state['recaptcha_response']
            }
            
            _log("📊 CHANGES DETECTED:")
            _log(f"   • URL changed: {changes['url_changed']}")
            if changes['url_changed']:
                _log(f"     OLD: {initial_state['url'][:100]}...")
                _log(f"     NEW: {final_state['url'][:100]}...")
            
            _log(f"   • Title changed: {changes['title_changed']}")
            _log(f"   • HTML length change: {changes['html_length_diff']} chars")
            _log(f"   • Body text change: {changes['body_text_diff']} chars")
            _log(f"   • Form count change: {changes['form_count_diff']}")
            _log(f"   • Input count change: {changes['input_count_diff']}")
            _log(f"   • Button count change: {changes['button_count_diff']}")
            _log(f"   • Captcha elements change: {changes['captcha_elements_diff']}")
            _log(f"   • Agree buttons change: {changes['agree_buttons_diff']}")
            
            # Log specific element changes
            _log("🔍 SPECIFIC ELEMENT CHANGES:")
            for key, value in initial_state['specific_elements'].items():
                final_value = final_state['specific_elements'][key]
                if value != final_value:
                    _log(f"   • {key}: {value} → {final_value}")
                else:
                    _log(f"   • {key}: {value} (no change)")
            
            # Log DOM mutations
            mutations = final_state['changes_detected']['mutations']
            _log(f"🔄 DOM MUTATIONS: {len(mutations)} detected")
            for mutation in mutations[-20:]:  # Last 20 mutations
                _log(f"   • {mutation['type']} on {mutation['target']} at {mutation['timestamp'][-12:-4]}")
                if mutation.get('addedNodes', 0) > 0:
                    _log(f"     Added {mutation['addedNodes']} nodes")
                if mutation.get('removedNodes', 0) > 0:
                    _log(f"     Removed {mutation['removedNodes']} nodes")
            
            # Log console messages and errors
            console_msgs = final_state['changes_detected']['consoleMessages']
            errors = final_state['changes_detected']['errors']
            
            if console_msgs:
                _log(f"💬 CONSOLE MESSAGES: {len(console_msgs)}")
                for msg in console_msgs[-10:]:
                    _log(f"   • [{msg['type'].upper()}] {msg['message'][:100]}...")
            
            if errors:
                _log(f"❌ JAVASCRIPT ERRORS: {len(errors)}")
                for error in errors[-5:]:
                    _log(f"   • {error['message']} at {error.get('filename', 'unknown')}:{error.get('lineno', '?')}")
            
            # Take screenshot of final state
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            debug_screenshot = Path("data") / f"cobb_html_debug_{timestamp}.png"
            await self.page.screenshot(path=debug_screenshot, full_page=True)
            _log(f"📸 Debug screenshot saved: {debug_screenshot}")
            
            return {
                'initial_state': initial_state,
                'final_state': final_state,
                'changes': changes,
                'click_result': click_result,
                'network_requests': len(network_requests),
                'mutations': len(mutations),
                'console_messages': len(console_msgs),
                'errors': len(errors)
            }
            
        finally:
            # Clean up event listeners
            try:
                self.page.remove_listener('request', handle_request)
                self.page.remove_listener('response', handle_response)
            except:
                _log("⚠️ Failed to remove event listeners")
                
    async def _handle_captcha(self) -> bool:
        """Handle captcha challenges on the page - MANUAL INTERVENTION REQUIRED for reCAPTCHA"""
        _log("🔒 Checking for captcha challenges...")
        
        try:
            # Detect if captcha is present
            captcha_detection_js = """
            (() => {
                const captcha_indicators = {
                    found: false,
                    type: '',
                    elements: [],
                    agree_buttons: [],
                    recaptcha_present: false,
                    recaptcha_sitekey: '',
                    recaptcha_solved: false
                };
                
                // Check specifically for reCAPTCHA elements from the screenshot
                const recaptchaDiv = document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha');
                const recaptchaElement = document.querySelector('[data-sitekey*="6LeK4ZoUAAAAAFG3gQ8C4gK9wYrYptUDxNO4D5H"]') || 
                                       document.querySelector('.g-recaptcha') || 
                                       document.querySelector('[data-sitekey]');
                
                if (recaptchaElement || recaptchaDiv) {
                    captcha_indicators.found = true;
                    captcha_indicators.type = 'recaptcha';
                    captcha_indicators.recaptcha_present = true;
                    
                    if (recaptchaElement && recaptchaElement.getAttribute('data-sitekey')) {
                        captcha_indicators.recaptcha_sitekey = recaptchaElement.getAttribute('data-sitekey');
                    }
                    
                    // Check if reCAPTCHA is solved by looking for the response token
                    const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                    if (recaptchaResponse && recaptchaResponse.value && recaptchaResponse.value.length > 0) {
                        captcha_indicators.recaptcha_solved = true;
                    }
                }
                
                // Look for "I Agree, View Notice" buttons with specific selectors from screenshot
                const agreeButtonSelectors = [
                    'input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]',
                    'input[value="I Agree, View Notice"]',
                    'input[value*="I Agree" i]',
                    'input[value*="View Notice" i]',
                    'input[name*="btnViewNotice"]',
                    'input[type="submit"][value*="agree" i]'
                ];
                
                for (let selector of agreeButtonSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            for (let element of elements) {
                                if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                                    captcha_indicators.found = true;
                                    captcha_indicators.type = captcha_indicators.type || 'agree_button';
                                    captcha_indicators.agree_buttons.push({
                                        selector: selector,
                                        name: element.name || '',
                                        value: element.value || '',
                                        id: element.id || '',
                                        visible: true,
                                        disabled: element.disabled || false,
                                        outerHTML: element.outerHTML.substring(0, 200)
                                    });
                                }
                            }
                        }
                    } catch (e) {
                        console.log('Selector error:', selector, e);
                    }
                }
                
                return captcha_indicators;
            })()
            """
            
            captcha_info = await self.page.evaluate(captcha_detection_js)
            
            if captcha_info['found']:
                _log(f"🔒 Captcha detected! Type: {captcha_info['type']}")
                _log(f"🔘 Agree buttons found: {len(captcha_info['agree_buttons'])}")
                _log(f"🤖 reCAPTCHA present: {captcha_info['recaptcha_present']}")
                _log(f"🔑 reCAPTCHA sitekey: {captcha_info['recaptcha_sitekey']}")
                _log(f"✅ reCAPTCHA solved: {captcha_info['recaptcha_solved']}")
                
                # Take screenshot for manual inspection
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    captcha_screenshot = Path("data") / f"cobb_captcha_{timestamp}.png"
                    await self.page.screenshot(path=captcha_screenshot, full_page=True)
                    _log(f"📸 Captcha screenshot saved: {captcha_screenshot}")
                except Exception as screenshot_error:
                    _log(f"⚠️ Captcha screenshot failed: {screenshot_error}")
                
                # Add comprehensive debugging when reCAPTCHA is detected
                _log("🔍 COMPREHENSIVE CAPTCHA DEBUGGING:")
                
                # Debug current state in detail
                debug_state_js = """
                (() => {
                    const debug = {
                        recaptcha_details: {},
                        button_details: {},
                        form_details: {},
                        page_details: {}
                    };
                    
                    // reCAPTCHA detailed analysis
                    const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                    const recaptchaElement = document.querySelector('[data-sitekey]');
                    
                    debug.recaptcha_details = {
                        response_element_exists: !!recaptchaResponse,
                        response_value: recaptchaResponse ? recaptchaResponse.value : null,
                        response_length: recaptchaResponse ? recaptchaResponse.value.length : 0,
                        element_sitekey: recaptchaElement ? recaptchaElement.getAttribute('data-sitekey') : null,
                        grecaptcha_available: typeof grecaptcha !== 'undefined',
                        challenge_visible: !!document.querySelector('.g-recaptcha iframe')
                    };
                    
                    // Button detailed analysis
                    const button = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                    debug.button_details = {
                        button_exists: !!button,
                        button_disabled: button ? button.disabled : null,
                        button_visible: button ? (button.offsetWidth > 0 && button.offsetHeight > 0) : false,
                        button_value: button ? button.value : null,
                        button_onclick: button && button.onclick ? button.onclick.toString().substring(0, 200) : null
                    };
                    
                    // Form analysis
                    const form = document.querySelector('form');
                    debug.form_details = {
                        form_exists: !!form,
                        viewstate_exists: !!document.querySelector('input[name="__VIEWSTATE"]'),
                        eventvalidation_exists: !!document.querySelector('input[name="__EVENTVALIDATION"]'),
                        dopostback_available: typeof __doPostBack === 'function'
                    };
                    
                    // Page analysis
                    debug.page_details = {
                        url: window.location.href,
                        ready_state: document.readyState,
                        has_errors: document.body.textContent.toLowerCase().includes('error'),
                        has_validation_messages: document.body.textContent.toLowerCase().includes('required')
                    };
                    
                    return debug;
                })()
                """
                
                debug_info = await self.page.evaluate(debug_state_js)
                
                _log("🤖 reCAPTCHA Debug Details:")
                recaptcha_details = debug_info['recaptcha_details']
                _log(f"   • Response element exists: {recaptcha_details['response_element_exists']}")
                _log(f"   • Response value length: {recaptcha_details['response_length']}")
                _log(f"   • Sitekey: {recaptcha_details['element_sitekey']}")
                _log(f"   • grecaptcha available: {recaptcha_details['grecaptcha_available']}")
                _log(f"   • Challenge visible: {recaptcha_details['challenge_visible']}")
                
                _log("🔘 Button Debug Details:")
                button_details = debug_info['button_details']
                _log(f"   • Button exists: {button_details['button_exists']}")
                _log(f"   • Button disabled: {button_details['button_disabled']}")
                _log(f"   • Button visible: {button_details['button_visible']}")
                _log(f"   • Button onclick: {button_details['button_onclick']}")
                
                # If reCAPTCHA is present but not solved, we can't proceed automatically
                if captcha_info['recaptcha_present'] and not captcha_info['recaptcha_solved']:
                    _log("🚫 reCAPTCHA detected but not solved - manual intervention required")
                    _log("⚠️ The reCAPTCHA challenge must be solved manually before proceeding")
                    _log("🎯 MANUAL TESTING: Try clicking the reCAPTCHA checkbox and then the 'I Agree, View Notice' button")
                    
                    # Wait a bit longer to see if user solves it manually
                    _log("⏳ Waiting 45 seconds for manual reCAPTCHA solution...")
                    _log("   During this time, please:")
                    _log("   1. Click the reCAPTCHA checkbox ('I'm not a robot')")
                    _log("   2. Complete any image challenges if they appear")
                    _log("   3. Click 'I Agree, View Notice' button")
                    _log("   4. Observe what happens in the browser")
                    
                    await self.page.wait_for_timeout(45000)
                    
                    # Check again if reCAPTCHA was solved
                    recaptcha_check_js = """
                    (() => {
                        const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                        return {
                            solved: recaptchaResponse && recaptchaResponse.value && recaptchaResponse.value.length > 0,
                            response_length: recaptchaResponse ? recaptchaResponse.value.length : 0
                        };
                    })()
                    """
                    
                    recaptcha_status = await self.page.evaluate(recaptcha_check_js)
                    _log(f"🔍 reCAPTCHA status after wait: {recaptcha_status}")
                    
                    if not recaptcha_status['solved']:
                        _log("❌ reCAPTCHA still not solved - cannot proceed with automation")
                        return True  # Return True to indicate captcha is present but not handled
                    else:
                        _log("✅ reCAPTCHA appears to be solved! Proceeding...")
                
                # Try to handle the captcha by clicking "I Agree, View Notice" button
                if captcha_info['agree_buttons']:
                    _log("🎯 Attempting to click 'I Agree, View Notice' button...")
                    
                    # Find the best agree button (not disabled)
                    best_button = None
                    for button in captcha_info['agree_buttons']:
                        if not button.get('disabled', False):
                            best_button = button
                            break
                    
                    if not best_button:
                        best_button = captcha_info['agree_buttons'][0]  # Fallback to first button
                    
                    _log(f"🔘 Clicking button: {best_button['value']} (Name: {best_button['name']}, Disabled: {best_button.get('disabled', False)})")
                    
                    # Run HTML structure debug analysis
                    _log("🔍 RUNNING HTML STRUCTURE DEBUG ANALYSIS...")
                    await self._debug_html_changes_on_click()
                    
                    click_result = await self._attempt_manual_button_click_with_monitoring()
                    
                    if click_result.get('clicked', False):
                        _log("✅ Successfully clicked 'I Agree, View Notice' button")
                        
                        # Wait for page to process the agreement
                        _log("⏳ Waiting for page to process agreement and load results...")
                        await self.page.wait_for_timeout(8000)  # Longer wait
                        
                        # Check if we've actually made it to the results page
                        _log("🔍 Checking if we've reached the results page...")
                        results_check_js = """
                        (() => {
                            // Enhanced results page verification
                            const analysis = {
                                onResultsPage: false,
                                hasSearchForm: false,
                                hasDataGrids: false,
                                hasResultRows: false,
                                hasCaptchaElements: false,
                                hasAgreeButtons: false,
                                gridRowCount: 0,
                                url: window.location.href,
                                pageIndicators: []
                            };
                            
                            // Check if we're on the search results page (contains #searchResults)
                            if (window.location.href.includes('Search.aspx') && 
                                window.location.href.includes('#searchResults')) {
                                analysis.onResultsPage = true;
                                analysis.pageIndicators.push('on_search_results_page');
                            }
                            
                            // Check for search form elements that indicate we're on results page
                            const searchFormSelectors = [
                                '[id*="ddlPopularSearches"]',
                                'label.header',
                                '[id*="lstCounty"]',
                                'input[id*="txtLastNumDays"]'
                            ];
                            for (let selector of searchFormSelectors) {
                                if (document.querySelector(selector)) {
                                    analysis.hasSearchForm = true;
                                    analysis.pageIndicators.push(`search_form_found`);
                                    break;
                                }
                            }
                            
                            // Check for data grids with results using specific selectors
                            const gridSelectors = [
                                '[id*="GridView"]',
                                '[id*="WSExtendedGridNP1"]', 
                                'table[id*="WSExtended"]',
                                '[id*="ContentPlaceHolder1"] table'
                            ];
                            
                            for (let selector of gridSelectors) {
                                const grids = document.querySelectorAll(selector);
                                for (let grid of grids) {
                                    const rows = grid.querySelectorAll('tr');
                                    analysis.gridRowCount += rows.length;
                                    
                                    if (rows.length > 1) { // More than just header row
                                        analysis.hasDataGrids = true;
                                        analysis.pageIndicators.push(`data_grid_found`);
                                        
                                        // Check for actual data rows with meaningful content
                                        for (let i = 1; i < rows.length; i++) {
                                            const rowText = rows[i].textContent.trim();
                                            if (rowText.length > 30 && 
                                                !rowText.toLowerCase().includes('no results') && 
                                                !rowText.toLowerCase().includes('no records') &&
                                                (rowText.includes('GA') || rowText.includes('Cobb') || 
                                                 rowText.match(/\\d{1,2}\\/\\d{1,2}\\/\\d{4}/) || 
                                                 rowText.includes('Foreclosure'))) {
                                                analysis.hasResultRows = true;
                                                analysis.pageIndicators.push('meaningful_result_rows_found');
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Check if we're still seeing captcha elements from the screenshot
                            const captchaSelectors = [
                                '[data-sitekey*="6LeK4ZoUAAAAAFG3gQ8C4gK9wYrYptUDxNO4D5H"]',
                                '#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha',
                                '.g-recaptcha',
                                '[data-sitekey]'
                            ];
                            
                            for (let selector of captchaSelectors) {
                                const elements = document.querySelectorAll(selector);
                                for (let element of elements) {
                                    if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                                        analysis.hasCaptchaElements = true;
                                        analysis.pageIndicators.push(`captcha_still_present`);
                                        break;
                                    }
                                }
                            }
                            
                            // Check if the specific agree button from screenshot is still visible
                            const agreeSelectors = [
                                'input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]',
                                'input[value*="I Agree" i]',
                                'input[value*="View Notice" i]'
                            ];
                            
                            for (let selector of agreeSelectors) {
                                const elements = document.querySelectorAll(selector);
                                for (let element of elements) {
                                    if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                                        analysis.hasAgreeButtons = true;
                                        analysis.pageIndicators.push(`agree_button_still_visible`);
                                        break;
                                    }
                                }
                            }
                            
                            return analysis;
                        })()
                        """
                        
                        results_status = await self.page.evaluate(results_check_js)
                        _log(f"🔍 Enhanced results verification:")
                        _log(f"   📊 On results page: {results_status['onResultsPage']}")
                        _log(f"   🔍 Has search form: {results_status['hasSearchForm']}")
                        _log(f"   📋 Has data grids: {results_status['hasDataGrids']}")
                        _log(f"   📈 Has result rows: {results_status['hasResultRows']}")
                        _log(f"   🔢 Total grid rows: {results_status['gridRowCount']}")
                        _log(f"   🚫 Still has captcha: {results_status['hasCaptchaElements']}")
                        _log(f"   🔘 Still has agree buttons: {results_status['hasAgreeButtons']}")
                        _log(f"   🌐 Current URL: {results_status['url'][:100]}...")
                        
                        # Take a screenshot after clicking to see current state
                        try:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            post_click_screenshot = Path("data") / f"cobb_post_click_{timestamp}.png"
                            await self.page.screenshot(path=post_click_screenshot, full_page=True)
                            _log(f"📸 Post-click screenshot saved: {post_click_screenshot}")
                        except Exception as screenshot_error:
                            _log(f"⚠️ Post-click screenshot failed: {screenshot_error}")
                        
                        # Determine if we've successfully bypassed captcha
                        if (results_status['onResultsPage'] and 
                            results_status['hasSearchForm'] and 
                            not results_status['hasCaptchaElements'] and 
                            not results_status['hasAgreeButtons']):
                            _log("✅ SUCCESS: Bypassed captcha and reached results page!")
                            _log(f"📊 Found {results_status['gridRowCount']} total grid rows")
                            if results_status['hasResultRows']:
                                _log("✅ Results page contains actual data rows!")
                            else:
                                _log("⚠️ Results page found but may be empty (no matching records)")
                            return False  # Captcha resolved successfully
                            
                        elif results_status['hasCaptchaElements'] or results_status['hasAgreeButtons']:
                            _log("❌ STILL ON CAPTCHA PAGE: reCAPTCHA challenge was not solved")
                            _log("🚫 The reCAPTCHA must be solved manually before proceeding")
                            _log("🎯 Please solve the reCAPTCHA challenge and try again")
                            return True   # Still stuck on captcha
                            
                        elif not results_status['onResultsPage']:
                            _log("⚠️ NOT ON EXPECTED RESULTS PAGE: May have navigated elsewhere")
                            _log(f"🌐 Current URL: {results_status['url']}")
                            return True   # Not where we expect to be
                            
                        else:
                            _log("✅ Appears to be past captcha (results page may have no matching data)")
                            return False  # Captcha seems resolved but possibly no results
                else:
                    _log("⚠️ No 'I Agree, View Notice' buttons found - may need manual intervention")
                    return True
                
            else:
                _log("✅ No captcha detected")
                return False
                
        except Exception as captcha_error:
            _log(f"❌ Captcha detection/handling failed: {captcha_error}")
            return False

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
        """Extract records from search results page"""
        _log("🔍 Starting extraction from Georgia Public Notice results")
        
        try:
            # Wait for dynamic content to fully load after search
            await self.page.wait_for_timeout(5000)
            
            # Get page structure information
            structure_js = """
            (() => {
                const structure = {
                    totalTables: document.querySelectorAll('table').length,
                    totalRows: document.querySelectorAll('tr').length,
                    gridViews: document.querySelectorAll('[id*="GridView"]').length,
                    wsExtendedGrid: document.querySelectorAll('[id*="WSExtendedGridNP1"]').length,
                    hasNoResultsText: document.body.textContent.includes('No results') || document.body.textContent.includes('no results'),
                    pageText: document.body.textContent.substring(0, 1000)
                };
                
                return structure;
            })()
            """
            
            structure = await self.page.evaluate(structure_js)
            _log(f"📊 Page structure: {structure}")
            
            # Take screenshot once grid views are detected
            if structure.get('gridViews', 0) > 0 or structure.get('wsExtendedGrid', 0) > 0:
                _log("📸 Grid views detected! Taking screenshot...")
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    screenshot_file = Path("data") / f"cobb_gridviews_{timestamp}.png"
                    screenshot_file.parent.mkdir(exist_ok=True)
                    await self.page.screenshot(path=screenshot_file, full_page=True)
                    _log(f"✅ Grid views screenshot saved to: {screenshot_file}")
                    current_url = self.page.url
                    _log(f"📄 Screenshot taken from URL: {current_url}")
                except Exception as screenshot_error:
                    _log(f"⚠️ Screenshot failed: {screenshot_error}")
            else:
                _log("⚠️ No grid views detected - skipping screenshot")
            
            # Check if we have results or no results
            if structure.get('hasNoResultsText', False):
                _log("📭 No results found for the search criteria")
                return []
            
            # Change results per page to 50 for better data collection
            _log("📄 Changing results per page to 50...")
            try:
                per_page_js = """
                (() => {
                    const perPageSelectors = [
                        '[id*="ddlPerPage"]',
                        '[name*="ddlPerPage"]', 
                        'select[id*="PerPage"]',
                        'select[name*="PerPage"]'
                    ];
                    
                    for (let selector of perPageSelectors) {
                        const dropdown = document.querySelector(selector);
                        
                        if (dropdown && dropdown.tagName === 'SELECT') {
                            console.log('Found per-page dropdown:', dropdown.id || dropdown.name);
                            
                            const hasValue50 = Array.from(dropdown.options).some(option => option.value === '50');
                            
                            if (hasValue50) {
                                console.log('Setting per-page to 50');
                                dropdown.value = '50';
                                dropdown.dispatchEvent(new Event('change', { bubbles: true }));
                                dropdown.dispatchEvent(new Event('input', { bubbles: true }));
                                
                                if (dropdown.onchange) {
                                    dropdown.onchange();
                                }
                                
                                return `per_page_set_50_${dropdown.id || dropdown.name}`;
                            } else {
                                console.log('Value "50" not available in dropdown options');
                                return 'value_50_not_available';
                            }
                        }
                    }
                    
                    return 'per_page_dropdown_not_found';
                })()
                """
                
                per_page_result = await self.page.evaluate(per_page_js)
                _log(f"🔧 Per-page selection result: {per_page_result}")
                
                if 'per_page_set_50' in per_page_result:
                    _log("✅ Successfully set results per page to 50")
                    _log("⏳ Waiting 8 seconds for page to update with 50 results per page...")
                    await self.page.wait_for_timeout(8000)
                else:
                    _log("⚠️ Could not set per-page to 50 - continuing with default pagination")
                    
            except Exception as per_page_error:
                _log(f"⚠️ Per-page selection failed: {per_page_error}")
            
            # Parse individual journal entries for address information
            _log("🏠 Parsing individual journal entries for address information...")
            await self._parse_journal_entries_for_addresses()
            
            # Extract results using basic strategy
            _log("🔍 Looking for results grid/table...")
            results_data = []
            
            try:
                extraction_js = """
                (() => {
                    const results = [];
                    
                    // Look for GridView controls
                    const gridViews = document.querySelectorAll('[id*="GridView"], table[id*="WSExtended"]');
                    
                    for (let grid of gridViews) {
                        const rows = grid.querySelectorAll('tr');
                        
                        for (let i = 1; i < rows.length; i++) { // Skip header row
                            const row = rows[i];
                            const cells = row.querySelectorAll('td');
                            
                            if (cells.length >= 2) {
                                const result = {
                                    case_number: '',
                                    document_type: '',
                                    filing_date: '',
                                    debtor_name: '',
                                    claimant_name: '',
                                    county: 'Cobb',
                                    book_page: '',
                                    document_link: '',
                                    raw_text: row.textContent.trim()
                                };
                                
                                // Extract data from cells
                                for (let j = 0; j < cells.length; j++) {
                                    const cellText = cells[j].textContent.trim();
                                    const links = cells[j].querySelectorAll('a');
                                    
                                    if (links.length > 0) {
                                        result.document_link = links[0].href || '';
                                    }
                                    
                                    // Pattern matching for data extraction
                                    if (cellText.match(/\\d{4}-\\d+/) || cellText.match(/\\w{2,}\\d+/)) {
                                        result.case_number = cellText;
                                    } else if (cellText.match(/\\d{1,2}\\/\\d{1,2}\\/\\d{4}/)) {
                                        result.filing_date = cellText;
                                    } else if (cellText.toLowerCase().includes('foreclosure') || cellText.toLowerCase().includes('notice')) {
                                        result.document_type = cellText;
                                    } else if (cellText.length > 5 && cellText.includes(' ')) {
                                        if (!result.debtor_name) {
                                            result.debtor_name = cellText;
                                        } else if (!result.claimant_name) {
                                            result.claimant_name = cellText;
                                        }
                                    }
                                }
                                
                                // Only add if we have meaningful data
                                if (result.case_number || result.document_type || result.raw_text.length > 20) {
                                    results.push(result);
                                }
                            }
                        }
                    }
                    
                    return results;
                })()
                """
                
                results_data = await self.page.evaluate(extraction_js)
                _log(f"✅ Extraction completed - found {len(results_data)} records")
                
            except Exception as extraction_error:
                _log(f"❌ Extraction failed: {extraction_error}")
                results_data = []
            
            return results_data
            
        except Exception as e:
            _log(f"❌ Extraction failed: {e}")
            return []

    async def _parse_journal_entries_for_addresses(self):
        """Parse individual journal entries by clicking 'view' links to extract address information"""
        _log("🏠 Starting individual journal entry address parsing...")
        
        try:
            # Check for captcha challenges first
            _log("🔒 Checking for captcha before parsing journal entries...")
            captcha_detected = await self._handle_captcha()
            
            if captcha_detected:
                _log("⚠️ Captcha detected - journal entry parsing may be blocked")
            
            # Find all "view" links in the results
            view_links_js = """
            (() => {
                const viewLinks = [];
                
                const allLinks = document.querySelectorAll('a, input[type="submit"], input[type="button"]');
                
                for (let element of allLinks) {
                    const text = element.textContent || element.value || element.title || '';
                    const href = element.href || '';
                    
                    if (text.toLowerCase().includes('view') || 
                        href.toLowerCase().includes('view') ||
                        element.id.toLowerCase().includes('view')) {
                        
                        let parentRow = element.closest('tr');
                        let rowText = parentRow ? parentRow.textContent.trim().substring(0, 100) : '';
                        
                        viewLinks.push({
                            element: element.outerHTML.substring(0, 200),
                            text: text.trim(),
                            href: href,
                            id: element.id || '',
                            className: element.className || '',
                            rowContext: rowText,
                            tagName: element.tagName
                        });
                    }
                }
                
                console.log('Found', viewLinks.length, 'potential view links');
                return viewLinks;
            })()
            """
            
            view_links = await self.page.evaluate(view_links_js)
            _log(f"🔍 Found {len(view_links)} potential view links")
            
            if not view_links:
                _log("⚠️ No view links found - skipping address parsing")
                return
            
            # Try to click the first view link to test functionality
            _log("🎯 Attempting to click first view link for address parsing...")
            
            first_link_click_js = """
            (() => {
                const allLinks = document.querySelectorAll('a, input[type="submit"], input[type="button"]');
                
                for (let element of allLinks) {
                    const text = element.textContent || element.value || element.title || '';
                    const href = element.href || '';
                    
                    if (text.toLowerCase().includes('view') || 
                        href.toLowerCase().includes('view') ||
                        element.id.toLowerCase().includes('view')) {
                        
                        console.log('Clicking first view link:', element.id, element.textContent);
                        
                        if (element.tagName === 'A' && element.href) {
                            window.location.href = element.href;
                            return 'navigated_to_href';
                        } else if (element.tagName === 'INPUT') {
                            element.click();
                            
                            if (typeof __doPostBack === 'function' && element.name) {
                                __doPostBack(element.name, '');
                            }
                            
                            return 'input_button_clicked';
                        } else {
                            element.click();
                            return 'link_clicked';
                        }
                    }
                }
                
                return 'no_clickable_view_link_found';
            })()
            """
            
            click_result = await self.page.evaluate(first_link_click_js)
            _log(f"🔧 First view link click result: {click_result}")
            
            if click_result in ['navigated_to_href', 'input_button_clicked', 'link_clicked']:
                _log("✅ Successfully clicked first view link")
                
                # Wait for navigation or page update
                _log("⏳ Waiting for page to load after clicking view link...")
                await self.page.wait_for_timeout(5000)
                
                # Check for captcha again after navigation
                captcha_detected_after_click = await self._handle_captcha()
                if captcha_detected_after_click:
                    _log("⚠️ Captcha detected after clicking view link")
                
                # Check if we have actual content now
                page_status_js = """
                (() => {
                    return {
                        url: window.location.href,
                        title: document.title,
                        hasAddressText: document.body.textContent.toLowerCase().includes('address') || 
                                       document.body.textContent.toLowerCase().includes('street') ||
                                       document.body.textContent.toLowerCase().includes('property'),
                        hasNoticeAuth: document.body.textContent.toLowerCase().includes('notice authentication') ||
                                      document.body.textContent.toLowerCase().includes('authentication number'),
                        contentLength: document.body.textContent.length,
                        readyState: document.readyState
                    };
                })()
                """
                
                page_status = await self.page.evaluate(page_status_js)
                _log(f"📄 Page status after view click: URL={page_status['url'][:100]}, Has Address Text={page_status['hasAddressText']}, Has Notice Auth={page_status['hasNoticeAuth']}")
                
                if page_status['hasAddressText'] or page_status['hasNoticeAuth']:
                    _log("✅ Successfully accessed journal entry detail page with address/authentication info")
                    
                    # Take a screenshot of the detail page
                    try:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        detail_screenshot = Path("data") / f"cobb_detail_page_{timestamp}.png" 
                        await self.page.screenshot(path=detail_screenshot, full_page=True)
                        _log(f"📸 Detail page screenshot saved: {detail_screenshot}")
                    except Exception as screenshot_error:
                        _log(f"⚠️ Detail page screenshot failed: {screenshot_error}")
                else:
                    _log("⚠️ Detail page may not have loaded completely or captcha is still present")
                
        except Exception as address_parse_error:
            _log(f"❌ Address parsing failed: {address_parse_error}")
            
        _log("✅ Journal entry address parsing completed")

    async def scrape(self, task_params: Dict[str, Any]) -> ScrapingResult:
        """Override base class scrape method to use custom flow"""
        try:
            _log(f"🚀 Starting Cobb GA Public Notice scraping flow")
            
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
            
            _log(f"✅ Cobb GA scraping completed successfully, found {len(records)} records")
            
            return ScrapingResult(
                success=True,
                records=records,
                error_message=None
            )
            
        except Exception as e:
            _log(f"❌ Cobb GA scraping failed: {e}")
            return ScrapingResult(
                success=False,
                records=[],
                error_message=str(e)
            )

    async def _debug_html_changes_on_click(self):
        """Debug HTML changes when clicking I Agree button"""
        _log("🔍 DEBUGGING HTML CHANGES ON BUTTON CLICK...")
        
        try:
            # Capture initial HTML state
            _log("📸 Capturing initial HTML state...")
            initial_state_js = """
            (() => {
                return {
                    url: window.location.href,
                    title: document.title,
                    html_length: document.documentElement.outerHTML.length,
                    body_text_length: document.body.textContent.length,
                    form_count: document.querySelectorAll('form').length,
                    input_count: document.querySelectorAll('input').length,
                    button_count: document.querySelectorAll('button, input[type="submit"], input[type="button"]').length,
                    captcha_elements: document.querySelectorAll('[data-sitekey], .g-recaptcha').length,
                    agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length,
                    recaptcha_response: document.querySelector('textarea[name="g-recaptcha-response"]') ? 
                                       document.querySelector('textarea[name="g-recaptcha-response"]').value.length : 0,
                    specific_elements: {
                        recaptcha_panel: !!document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha'),
                        agree_button: !!document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]'),
                        viewstate: !!document.querySelector('input[name="__VIEWSTATE"]'),
                        eventvalidation: !!document.querySelector('input[name="__EVENTVALIDATION"]')
                    },
                    dom_snapshot: {
                        head_content: document.head.innerHTML.substring(0, 500),
                        body_start: document.body.innerHTML.substring(0, 1000),
                        body_end: document.body.innerHTML.substring(document.body.innerHTML.length - 1000)
                    }
                };
            })()
            """
            
            initial_state = await self.page.evaluate(initial_state_js)
            
            _log("📊 INITIAL STATE:")
            _log(f"   • URL: {initial_state['url'][:100]}...")
            _log(f"   • Title: {initial_state['title']}")
            _log(f"   • HTML length: {initial_state['html_length']} chars")
            _log(f"   • Body text length: {initial_state['body_text_length']} chars")
            _log(f"   • Forms: {initial_state['form_count']}")
            _log(f"   • Inputs: {initial_state['input_count']}")
            _log(f"   • Buttons: {initial_state['button_count']}")
            _log(f"   • Captcha elements: {initial_state['captcha_elements']}")
            _log(f"   • Agree buttons: {initial_state['agree_buttons']}")
            _log(f"   • reCAPTCHA response length: {initial_state['recaptcha_response']}")
            _log(f"   • Has reCAPTCHA panel: {initial_state['specific_elements']['recaptcha_panel']}")
            _log(f"   • Has agree button: {initial_state['specific_elements']['agree_button']}")
            _log(f"   • Has ViewState: {initial_state['specific_elements']['viewstate']}")
            _log(f"   • Has EventValidation: {initial_state['specific_elements']['eventvalidation']}")
            
            # Set up DOM mutation observer and network monitoring
            _log("🔍 Setting up DOM mutation observer and network monitoring...")
            
            setup_monitoring_js = """
            (() => {
                // Store for capturing changes
                window.debugData = {
                    mutations: [],
                    networkRequests: [],
                    consoleMessages: [],
                    errors: []
                };
                
                // DOM Mutation Observer
                const observer = new MutationObserver((mutations) => {
                    mutations.forEach((mutation) => {
                        window.debugData.mutations.push({
                            type: mutation.type,
                            target: mutation.target.tagName + (mutation.target.id ? '#' + mutation.target.id : '') + 
                                   (mutation.target.className ? '.' + mutation.target.className.split(' ').join('.') : ''),
                            addedNodes: mutation.addedNodes.length,
                            removedNodes: mutation.removedNodes.length,
                            attributeName: mutation.attributeName,
                            oldValue: mutation.oldValue,
                            timestamp: new Date().toISOString()
                        });
                    });
                });
                
                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeOldValue: true,
                    characterData: true,
                    characterDataOldValue: true
                });
                
                // Console monitoring
                const originalConsoleLog = console.log;
                const originalConsoleError = console.error;
                const originalConsoleWarn = console.warn;
                
                console.log = function(...args) {
                    window.debugData.consoleMessages.push({
                        type: 'log',
                        message: args.join(' '),
                        timestamp: new Date().toISOString()
                    });
                    originalConsoleLog.apply(console, arguments);
                };
                
                console.error = function(...args) {
                    window.debugData.consoleMessages.push({
                        type: 'error', 
                        message: args.join(' '),
                        timestamp: new Date().toISOString()
                    });
                    originalConsoleError.apply(console, arguments);
                };
                
                console.warn = function(...args) {
                    window.debugData.consoleMessages.push({
                        type: 'warn',
                        message: args.join(' '),
                        timestamp: new Date().toISOString()
                    });
                    originalConsoleWarn.apply(console, arguments);
                };
                
                // Error monitoring
                window.addEventListener('error', (e) => {
                    window.debugData.errors.push({
                        message: e.message,
                        filename: e.filename,
                        lineno: e.lineno,
                        colno: e.colno,
                        timestamp: new Date().toISOString()
                    });
                });
                
                return 'monitoring_setup_complete';
            })()
            """
            
            await self.page.evaluate(setup_monitoring_js)
            
            # Set up network request monitoring
            network_requests = []
            
            def handle_request(request):
                network_requests.append({
                    'url': request.url,
                    'method': request.method,
                    'headers': dict(request.headers),
                    'timestamp': datetime.now().isoformat(),
                    'type': 'request'
                })
            
            def handle_response(response):
                network_requests.append({
                    'url': response.url,
                    'status': response.status,
                    'status_text': response.status_text,
                    'headers': dict(response.headers),
                    'timestamp': datetime.now().isoformat(),
                    'type': 'response'
                })
            
            self.page.on('request', handle_request)
            self.page.on('response', handle_response)
            
            try:
                # Now click the button with comprehensive monitoring
                _log("🎯 CLICKING 'I AGREE' BUTTON WITH FULL MONITORING...")
                
                click_result_js = """
                (() => {
                    const result = {
                        clicked: false,
                        error: null,
                        button_info: {},
                        recaptcha_info: {},
                        click_events: [],
                        immediate_changes: {}
                    };
                    
                    try {
                        // Find the button
                        const button = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                        
                        if (!button) {
                            result.error = 'Button not found';
                            return result;
                        }
                        
                        // Get button info
                        result.button_info = {
                            name: button.name,
                            value: button.value,
                            disabled: button.disabled,
                            visible: button.offsetWidth > 0 && button.offsetHeight > 0,
                            form: button.form ? button.form.id : null
                        };
                        
                        // Get reCAPTCHA info
                        const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                        result.recaptcha_info = {
                            response_exists: !!recaptchaResponse,
                            response_length: recaptchaResponse ? recaptchaResponse.value.length : 0,
                            is_solved: recaptchaResponse ? recaptchaResponse.value.length > 0 : false
                        };
                        
                        // Clear previous debug data
                        window.debugData.mutations = [];
                        window.debugData.networkRequests = [];
                        window.debugData.consoleMessages = [];
                        window.debugData.errors = [];
                        
                        // Click the button
                        button.focus();
                        result.click_events.push('focused');
                        
                        button.click();
                        result.clicked = true;
                        result.click_events.push('clicked');
                        
                        // Try ASP.NET postback
                        if (typeof __doPostBack === 'function' && button.name) {
                            __doPostBack(button.name, '');
                            result.click_events.push('postback_called');
                        }
                        
                        // Capture immediate changes
                        setTimeout(() => {
                            result.immediate_changes = {
                                url_changed: window.location.href !== '{initial_state["url"]}',
                                new_url: window.location.href,
                                mutations_count: window.debugData.mutations.length,
                                console_messages_count: window.debugData.consoleMessages.length,
                                errors_count: window.debugData.errors.length
                            };
                        }, 100);
                        
                    } catch (e) {
                        result.error = e.message;
                    }
                    
                    return result;
                })()
                """.replace('{initial_state["url"]}', initial_state['url'])
                
                click_result = await self.page.evaluate(click_result_js)
                
                _log("🎯 BUTTON CLICK RESULTS:")
                _log(f"   • Button clicked: {click_result['clicked']}")
                _log(f"   • Error: {click_result.get('error', 'None')}")
                _log(f"   • Button disabled: {click_result['button_info']['disabled']}")
                _log(f"   • Button visible: {click_result['button_info']['visible']}")
                _log(f"   • reCAPTCHA solved: {click_result['recaptcha_info']['is_solved']}")
                _log(f"   • reCAPTCHA response length: {click_result['recaptcha_info']['response_length']}")
                _log(f"   • Events fired: {click_result['click_events']}")
                
                # Wait for potential changes
                _log("⏳ Waiting 10 seconds for page changes...")
                await self.page.wait_for_timeout(10000)
                
                # Capture final state and changes
                _log("📸 Capturing final HTML state and changes...")
                
                final_analysis_js = """
                (() => {
                    const finalState = {
                        url: window.location.href,
                        title: document.title,
                        html_length: document.documentElement.outerHTML.length,
                        body_text_length: document.body.textContent.length,
                        form_count: document.querySelectorAll('form').length,
                        input_count: document.querySelectorAll('input').length,
                        button_count: document.querySelectorAll('button, input[type="submit"], input[type="button"]').length,
                        captcha_elements: document.querySelectorAll('[data-sitekey], .g-recaptcha').length,
                        agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length,
                        recaptcha_response: document.querySelector('textarea[name="g-recaptcha-response"]') ? 
                                           document.querySelector('textarea[name="g-recaptcha-response"]').value.length : 0,
                        specific_elements: {
                            recaptcha_panel: !!document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha'),
                            agree_button: !!document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]'),
                            viewstate: !!document.querySelector('input[name="__VIEWSTATE"]'),
                            eventvalidation: !!document.querySelector('input[name="__EVENTVALIDATION"]')
                        },
                        changes_detected: window.debugData,
                        dom_snapshot: {
                            head_content: document.head.innerHTML.substring(0, 500),
                            body_start: document.body.innerHTML.substring(0, 1000),
                            body_end: document.body.innerHTML.substring(document.body.innerHTML.length - 1000)
                        }
                    };
                    
                    return finalState;
                })()
                """
                
                final_state = await self.page.evaluate(final_analysis_js)
                
                # Log network activity
                _log(f"🌐 NETWORK ACTIVITY: {len(network_requests)} requests/responses")
                for req in network_requests[-10:]:  # Last 10 network events
                    if req['type'] == 'request':
                        _log(f"   → {req['method']} {req['url'][:100]}...")
                    else:
                        _log(f"   ← {req['status']} {req['url'][:100]}...")
                
                # Compare states and log changes
                _log("🔄 ANALYZING CHANGES:")
                
                changes = {
                    'url_changed': initial_state['url'] != final_state['url'],
                    'title_changed': initial_state['title'] != final_state['title'],
                    'html_length_diff': final_state['html_length'] - initial_state['html_length'],
                    'body_text_diff': final_state['body_text_length'] - initial_state['body_text_length'],
                    'form_count_diff': final_state['form_count'] - initial_state['form_count'],
                    'input_count_diff': final_state['input_count'] - initial_state['input_count'],
                    'button_count_diff': final_state['button_count'] - initial_state['button_count'],
                    'captcha_elements_diff': final_state['captcha_elements'] - initial_state['captcha_elements'],
                    'agree_buttons_diff': final_state['agree_buttons'] - initial_state['agree_buttons'],
                    'recaptcha_response_diff': final_state['recaptcha_response'] - initial_state['recaptcha_response']
                }
                
                _log("📊 CHANGES DETECTED:")
                _log(f"   • URL changed: {changes['url_changed']}")
                if changes['url_changed']:
                    _log(f"     OLD: {initial_state['url'][:100]}...")
                    _log(f"     NEW: {final_state['url'][:100]}...")
                
                _log(f"   • Title changed: {changes['title_changed']}")
                if changes['title_changed']:
                    _log(f"     OLD: {initial_state['title']}")
                    _log(f"     NEW: {final_state['title']}")
                
                _log(f"   • HTML length change: {changes['html_length_diff']} chars")
                _log(f"   • Body text change: {changes['body_text_diff']} chars")
                _log(f"   • Form count change: {changes['form_count_diff']}")
                _log(f"   • Input count change: {changes['input_count_diff']}")
                _log(f"   • Button count change: {changes['button_count_diff']}")
                _log(f"   • Captcha elements change: {changes['captcha_elements_diff']}")
                _log(f"   • Agree buttons change: {changes['agree_buttons_diff']}")
                
                # Log specific element changes
                _log("🔍 SPECIFIC ELEMENT CHANGES:")
                for key, value in initial_state['specific_elements'].items():
                    final_value = final_state['specific_elements'][key]
                    if value != final_value:
                        _log(f"   • {key}: {value} → {final_value}")
                    else:
                        _log(f"   • {key}: {value} (no change)")
                
                # Log DOM mutations
                mutations = final_state['changes_detected']['mutations']
                _log(f"🔄 DOM MUTATIONS: {len(mutations)} detected")
                for mutation in mutations[-20:]:  # Last 20 mutations
                    _log(f"   • {mutation['type']} on {mutation['target']} at {mutation['timestamp'][-12:-4]}")
                    if mutation.get('addedNodes', 0) > 0:
                        _log(f"     Added {mutation['addedNodes']} nodes")
                    if mutation.get('removedNodes', 0) > 0:
                        _log(f"     Removed {mutation['removedNodes']} nodes")
                    if mutation.get('attributeName'):
                        _log(f"     Attribute changed: {mutation['attributeName']}")
                
                # Log console messages and errors
                console_msgs = final_state['changes_detected']['consoleMessages']
                errors = final_state['changes_detected']['errors']
                
                if console_msgs:
                    _log(f"💬 CONSOLE MESSAGES: {len(console_msgs)}")
                    for msg in console_msgs[-10:]:  # Last 10 messages
                        _log(f"   • [{msg['type'].upper()}] {msg['message'][:100]}...")
                
                if errors:
                    _log(f"❌ JAVASCRIPT ERRORS: {len(errors)}")
                    for error in errors[-5:]:  # Last 5 errors
                        _log(f"   • {error['message']} at {error.get('filename', 'unknown')}:{error.get('lineno', '?')}")
                
                # Take screenshot of final state
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_screenshot = Path("data") / f"cobb_html_debug_{timestamp}.png"
                await self.page.screenshot(path=debug_screenshot, full_page=True)
                _log(f"📸 Debug screenshot saved: {debug_screenshot}")
                
                # Save HTML snapshots for comparison
                html_debug_file = Path("data") / f"cobb_html_debug_{timestamp}.html"
                html_content = await self.page.content()
                with open(html_debug_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                _log(f"💾 HTML content saved: {html_debug_file}")
                
                return {
                    'initial_state': initial_state,
                    'final_state': final_state,
                    'changes': changes,
                    'click_result': click_result,
                    'network_requests': len(network_requests),
                    'mutations': len(mutations),
                    'console_messages': len(console_msgs),
                    'errors': len(errors)
                }
                
            finally:
                # Clean up event listeners
                try:
                    self.page.remove_listener('request', handle_request)
                    self.page.remove_listener('response', handle_response)
                except:
                    pass
                    
        except Exception as e:
            _log(f"❌ HTML change debugging failed: {e}")
            return None

    async def _handle_captcha(self) -> bool:
        """Handle captcha challenges on the page - MANUAL INTERVENTION REQUIRED for reCAPTCHA"""
        _log("🔒 Checking for captcha challenges...")
        
        try:
            # Detect if captcha is present
            captcha_detection_js = """
            (() => {
                const captcha_indicators = {
                    found: false,
                    type: '',
                    elements: [],
                    agree_buttons: [],
                    recaptcha_present: false,
                    recaptcha_sitekey: '',
                    recaptcha_solved: false
                };
                
                // Check specifically for reCAPTCHA elements from the screenshot
                const recaptchaDiv = document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha');
                const recaptchaElement = document.querySelector('[data-sitekey*="6LeK4ZoUAAAAAFG3gQ8C4gK9wYrYptUDxNO4D5H"]') || 
                                       document.querySelector('.g-recaptcha') || 
                                       document.querySelector('[data-sitekey]');
                
                if (recaptchaElement || recaptchaDiv) {
                    captcha_indicators.found = true;
                    captcha_indicators.type = 'recaptcha';
                    captcha_indicators.recaptcha_present = true;
                    
                    if (recaptchaElement && recaptchaElement.getAttribute('data-sitekey')) {
                        captcha_indicators.recaptcha_sitekey = recaptchaElement.getAttribute('data-sitekey');
                    }
                    
                    // Check if reCAPTCHA is solved by looking for the response token
                    const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                    if (recaptchaResponse && recaptchaResponse.value && recaptchaResponse.value.length > 0) {
                        captcha_indicators.recaptcha_solved = true;
                    }
                }
                
                // Look for "I Agree, View Notice" buttons with specific selectors from screenshot
                const agreeButtonSelectors = [
                    'input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]',
                    'input[value="I Agree, View Notice"]',
                    'input[value*="I Agree" i]',
                    'input[value*="View Notice" i]',
                    'input[name*="btnViewNotice"]',
                    'input[type="submit"][value*="agree" i]'
                ];
                
                for (let selector of agreeButtonSelectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            for (let element of elements) {
                                if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                                    captcha_indicators.found = true;
                                    captcha_indicators.type = captcha_indicators.type || 'agree_button';
                                    captcha_indicators.agree_buttons.push({
                                        selector: selector,
                                        name: element.name || '',
                                        value: element.value || '',
                                        id: element.id || '',
                                        visible: true,
                                        disabled: element.disabled || false,
                                        outerHTML: element.outerHTML.substring(0, 200)
                                    });
                                }
                            }
                        }
                    } catch (e) {
                        console.log('Selector error:', selector, e);
                    }
                }
                
                return captcha_indicators;
            })()
            """
            
            captcha_info = await self.page.evaluate(captcha_detection_js)
            
            if captcha_info['found']:
                _log(f"🔒 Captcha detected! Type: {captcha_info['type']}")
                _log(f"🔘 Agree buttons found: {len(captcha_info['agree_buttons'])}")
                _log(f"🤖 reCAPTCHA present: {captcha_info['recaptcha_present']}")
                _log(f"🔑 reCAPTCHA sitekey: {captcha_info['recaptcha_sitekey']}")
                _log(f"✅ reCAPTCHA solved: {captcha_info['recaptcha_solved']}")
                
                # Take screenshot for manual inspection
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    captcha_screenshot = Path("data") / f"cobb_captcha_{timestamp}.png"
                    await self.page.screenshot(path=captcha_screenshot, full_page=True)
                    _log(f"📸 Captcha screenshot saved: {captcha_screenshot}")
                except Exception as screenshot_error:
                    _log(f"⚠️ Captcha screenshot failed: {screenshot_error}")
                
                # Add comprehensive debugging when reCAPTCHA is detected
                _log("🔍 COMPREHENSIVE CAPTCHA DEBUGGING:")
                
                # Debug current state in detail
                debug_state_js = """
                (() => {
                    const debug = {
                        recaptcha_details: {},
                        button_details: {},
                        form_details: {},
                        page_details: {}
                    };
                    
                    // reCAPTCHA detailed analysis
                    const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                    const recaptchaElement = document.querySelector('[data-sitekey]');
                    
                    debug.recaptcha_details = {
                        response_element_exists: !!recaptchaResponse,
                        response_value: recaptchaResponse ? recaptchaResponse.value : null,
                        response_length: recaptchaResponse ? recaptchaResponse.value.length : 0,
                        element_sitekey: recaptchaElement ? recaptchaElement.getAttribute('data-sitekey') : null,
                        grecaptcha_available: typeof grecaptcha !== 'undefined',
                        challenge_visible: !!document.querySelector('.g-recaptcha iframe')
                    };
                    
                    // Button detailed analysis
                    const button = document.querySelector('input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]');
                    debug.button_details = {
                        button_exists: !!button,
                        button_disabled: button ? button.disabled : null,
                        button_visible: button ? (button.offsetWidth > 0 && button.offsetHeight > 0) : false,
                        button_value: button ? button.value : null,
                        button_onclick: button && button.onclick ? button.onclick.toString().substring(0, 200) : null
                    };
                    
                    // Form analysis
                    const form = document.querySelector('form');
                    debug.form_details = {
                        form_exists: !!form,
                        viewstate_exists: !!document.querySelector('input[name="__VIEWSTATE"]'),
                        eventvalidation_exists: !!document.querySelector('input[name="__EVENTVALIDATION"]'),
                        dopostback_available: typeof __doPostBack === 'function'
                    };
                    
                    // Page analysis
                    debug.page_details = {
                        url: window.location.href,
                        ready_state: document.readyState,
                        has_errors: document.body.textContent.toLowerCase().includes('error'),
                        has_validation_messages: document.body.textContent.toLowerCase().includes('required')
                    };
                    
                    return debug;
                })()
                """
                
                debug_info = await self.page.evaluate(debug_state_js)
                
                _log("🤖 reCAPTCHA Debug Details:")
                recaptcha_details = debug_info['recaptcha_details']
                _log(f"   • Response element exists: {recaptcha_details['response_element_exists']}")
                _log(f"   • Response value length: {recaptcha_details['response_length']}")
                _log(f"   • Sitekey: {recaptcha_details['element_sitekey']}")
                _log(f"   • grecaptcha available: {recaptcha_details['grecaptcha_available']}")
                _log(f"   • Challenge visible: {recaptcha_details['challenge_visible']}")
                
                _log("🔘 Button Debug Details:")
                button_details = debug_info['button_details']
                _log(f"   • Button exists: {button_details['button_exists']}")
                _log(f"   • Button disabled: {button_details['button_disabled']}")
                _log(f"   • Button visible: {button_details['button_visible']}")
                _log(f"   • Button onclick: {button_details['button_onclick']}")
                
                # If reCAPTCHA is present but not solved, we can't proceed automatically
                if captcha_info['recaptcha_present'] and not captcha_info['recaptcha_solved']:
                    _log("🚫 reCAPTCHA detected but not solved - manual intervention required")
                    _log("⚠️ The reCAPTCHA challenge must be solved manually before proceeding")
                    _log("🎯 MANUAL TESTING: Try clicking the reCAPTCHA checkbox and then the 'I Agree, View Notice' button")
                    
                    # Wait a bit longer to see if user solves it manually
                    _log("⏳ Waiting 45 seconds for manual reCAPTCHA solution...")
                    _log("   During this time, please:")
                    _log("   1. Click the reCAPTCHA checkbox ('I'm not a robot')")
                    _log("   2. Complete any image challenges if they appear")
                    _log("   3. Click 'I Agree, View Notice' button")
                    _log("   4. Observe what happens in the browser")
                    
                    await self.page.wait_for_timeout(45000)
                    
                    # Check again if reCAPTCHA was solved
                    recaptcha_check_js = """
                    (() => {
                        const recaptchaResponse = document.querySelector('textarea[name="g-recaptcha-response"]');
                        return {
                            solved: recaptchaResponse && recaptchaResponse.value && recaptchaResponse.value.length > 0,
                            response_length: recaptchaResponse ? recaptchaResponse.value.length : 0
                        };
                    })()
                    """
                    
                    recaptcha_status = await self.page.evaluate(recaptcha_check_js)
                    _log(f"🔍 reCAPTCHA status after wait: {recaptcha_status}")
                    
                    if not recaptcha_status['solved']:
                        _log("❌ reCAPTCHA still not solved - cannot proceed with automation")
                        return True  # Return True to indicate captcha is present but not handled
                    else:
                        _log("✅ reCAPTCHA appears to be solved! Proceeding...")
                
                # Try to handle the captcha by clicking "I Agree, View Notice" button
                if captcha_info['agree_buttons']:
                    _log("🎯 Attempting to click 'I Agree, View Notice' button...")
                    
                    # Find the best agree button (not disabled)
                    best_button = None
                    for button in captcha_info['agree_buttons']:
                        if not button.get('disabled', False):
                            best_button = button
                            break
                    
                    if not best_button:
                        best_button = captcha_info['agree_buttons'][0]  # Fallback to first button
                    
                    _log(f"🔘 Clicking button: {best_button['value']} (Name: {best_button['name']}, Disabled: {best_button.get('disabled', False)})")
                    
                    # Run HTML structure debug analysis
                    _log("🔍 RUNNING HTML STRUCTURE DEBUG ANALYSIS...")
                    await self._debug_html_changes_on_click()
                    
                    click_result = await self._attempt_manual_button_click_with_monitoring()
                    
                    if click_result.get('clicked', False):
                        _log("✅ Successfully clicked 'I Agree, View Notice' button")
                        
                        # Wait for page to process the agreement
                        _log("⏳ Waiting for page to process agreement and load results...")
                        await self.page.wait_for_timeout(8000)  # Longer wait
                        
                        # Check if we've actually made it to the results page
                        _log("🔍 Checking if we've reached the results page...")
                        results_check_js = """
                        (() => {
                            // Enhanced results page verification
                            const analysis = {
                                onResultsPage: false,
                                hasSearchForm: false,
                                hasDataGrids: false,
                                hasResultRows: false,
                                hasCaptchaElements: false,
                                hasAgreeButtons: false,
                                gridRowCount: 0,
                                url: window.location.href,
                                pageIndicators: []
                            };
                            
                            // Check if we're on the search results page (contains #searchResults)
                            if (window.location.href.includes('Search.aspx') && 
                                window.location.href.includes('#searchResults')) {
                                analysis.onResultsPage = true;
                                analysis.pageIndicators.push('on_search_results_page');
                            }
                            
                            // Check for search form elements that indicate we're on results page
                            const searchFormSelectors = [
                                '[id*="ddlPopularSearches"]',
                                'label.header',
                                '[id*="lstCounty"]',
                                'input[id*="txtLastNumDays"]'
                            ];
                            for (let selector of searchFormSelectors) {
                                if (document.querySelector(selector)) {
                                    analysis.hasSearchForm = true;
                                    analysis.pageIndicators.push(`search_form_found`);
                                    break;
                                }
                            }
                            
                            // Check for data grids with results using specific selectors
                            const gridSelectors = [
                                '[id*="GridView"]',
                                '[id*="WSExtendedGridNP1"]', 
                                'table[id*="WSExtended"]',
                                '[id*="ContentPlaceHolder1"] table'
                            ];
                            
                            for (let selector of gridSelectors) {
                                const grids = document.querySelectorAll(selector);
                                for (let grid of grids) {
                                    const rows = grid.querySelectorAll('tr');
                                    analysis.gridRowCount += rows.length;
                                    
                                    if (rows.length > 1) { // More than just header row
                                        analysis.hasDataGrids = true;
                                        analysis.pageIndicators.push(`data_grid_found`);
                                        
                                        // Check for actual data rows with meaningful content
                                        for (let i = 1; i < rows.length; i++) {
                                            const rowText = rows[i].textContent.trim();
                                            if (rowText.length > 30 && 
                                                !rowText.toLowerCase().includes('no results') && 
                                                !rowText.toLowerCase().includes('no records') &&
                                                (rowText.includes('GA') || rowText.includes('Cobb') || 
                                                 rowText.match(/\\d{1,2}\\/\\d{1,2}\\/\\d{4}/) || 
                                                 rowText.includes('Foreclosure'))) {
                                                analysis.hasResultRows = true;
                                                analysis.pageIndicators.push('meaningful_result_rows_found');
                                                break;
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Check if we're still seeing captcha elements from the screenshot
                            const captchaSelectors = [
                                '[data-sitekey*="6LeK4ZoUAAAAAFG3gQ8C4gK9wYrYptUDxNO4D5H"]',
                                '#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha',
                                '.g-recaptcha',
                                '[data-sitekey]'
                            ];
                            
                            for (let selector of captchaSelectors) {
                                const elements = document.querySelectorAll(selector);
                                for (let element of elements) {
                                    if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                                        analysis.hasCaptchaElements = true;
                                        analysis.pageIndicators.push(`captcha_still_present`);
                                        break;
                                    }
                                }
                            }
                            
                            // Check if the specific agree button from screenshot is still visible
                            const agreeSelectors = [
                                'input[name="ctl00$ContentPlaceHolder1$PublicNoticeDetailsBody1$btnViewNotice"]',
                                'input[value*="I Agree" i]',
                                'input[value*="View Notice" i]'
                            ];
                            
                            for (let selector of agreeSelectors) {
                                const elements = document.querySelectorAll(selector);
                                for (let element of elements) {
                                    if (element.offsetWidth > 0 && element.offsetHeight > 0) {
                                        analysis.hasAgreeButtons = true;
                                        analysis.pageIndicators.push(`agree_button_still_visible`);
                                        break;
                                    }
                                }
                            }
                            
                            return analysis;
                        })()
                        """
                        
                        results_status = await self.page.evaluate(results_check_js)
                        _log(f"🔍 Enhanced results verification:")
                        _log(f"   📊 On results page: {results_status['onResultsPage']}")
                        _log(f"   🔍 Has search form: {results_status['hasSearchForm']}")
                        _log(f"   📋 Has data grids: {results_status['hasDataGrids']}")
                        _log(f"   📈 Has result rows: {results_status['hasResultRows']}")
                        _log(f"   🔢 Total grid rows: {results_status['gridRowCount']}")
                        _log(f"   🚫 Still has captcha: {results_status['hasCaptchaElements']}")
                        _log(f"   🔘 Still has agree buttons: {results_status['hasAgreeButtons']}")
                        _log(f"   🌐 Current URL: {results_status['url'][:100]}...")
                        
                        # Take a screenshot after clicking to see current state
                        try:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            post_click_screenshot = Path("data") / f"cobb_post_click_{timestamp}.png"
                            await self.page.screenshot(path=post_click_screenshot, full_page=True)
                            _log(f"📸 Post-click screenshot saved: {post_click_screenshot}")
                        except Exception as screenshot_error:
                            _log(f"⚠️ Post-click screenshot failed: {screenshot_error}")
                        
                        # Determine if we've successfully bypassed captcha
                        if (results_status['onResultsPage'] and 
                            results_status['hasSearchForm'] and 
                            not results_status['hasCaptchaElements'] and 
                            not results_status['hasAgreeButtons']):
                            _log("✅ SUCCESS: Bypassed captcha and reached results page!")
                            _log(f"📊 Found {results_status['gridRowCount']} total grid rows")
                            if results_status['hasResultRows']:
                                _log("✅ Results page contains actual data rows!")
                            else:
                                _log("⚠️ Results page found but may be empty (no matching records)")
                            return False  # Captcha resolved successfully
                            
                        elif results_status['hasCaptchaElements'] or results_status['hasAgreeButtons']:
                            _log("❌ STILL ON CAPTCHA PAGE: reCAPTCHA challenge was not solved")
                            _log("🚫 The reCAPTCHA must be solved manually before proceeding")
                            _log("🎯 Please solve the reCAPTCHA challenge and try again")
                            return True   # Still stuck on captcha
                            
                        elif not results_status['onResultsPage']:
                            _log("⚠️ NOT ON EXPECTED RESULTS PAGE: May have navigated elsewhere")
                            _log(f"🌐 Current URL: {results_status['url']}")
                            return True   # Not where we expect to be
                            
                        else:
                            _log("✅ Appears to be past captcha (results page may have no matching data)")
                            return False  # Captcha seems resolved but possibly no results
                else:
                    _log("⚠️ No 'I Agree, View Notice' buttons found - may need manual intervention")
                    return True
                
            else:
                _log("✅ No captcha detected")
                return False
                
        except Exception as captcha_error:
            _log(f"❌ Captcha detection/handling failed: {captcha_error}")
            return False

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def get_existing_case_numbers() -> set:
    """Get existing case numbers from database to avoid duplicates"""
    try:
        async with AsyncSession(engine) as session:
            result = await session.execute(
                text("SELECT case_number FROM cobb_ga_filing WHERE case_number IS NOT NULL")
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
    csv_file = EXPORT_DIR / f"cobb_ga_{timestamp}.csv"
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
              notice_types: List[str] = None, counties: List[str] = None):
    """Main scraping function"""
    
    _log(f"🚀 Starting Cobb County GA Public Notice scraper")
    _log(f"📊 Max records: {max_new_records}, Test mode: {test_mode}")
    
    # Load configuration
    config = CountyConfig.from_json_file("configs/cobb_ga.json")
    
    # Apply stealth settings for better browser protection
    config.headless = not test_mode  # Show browser in test mode for debugging
    config.timeout = 60  # Longer timeout
    config.delay_between_requests = 3.0  # Slower to avoid detection
    
    # Set search date to first of current month (single date input)
    if not from_date:
        today = date.today()
        first_of_month = today.replace(day=1)
        search_date = first_of_month.strftime('%m/%d/%Y')
    else:
        search_date = from_date
    
    # Set default notice types (focus on foreclosures)
    if not notice_types:
        notice_types = ['Foreclosures']
    
    # Get existing case numbers
    existing_case_numbers = await get_existing_case_numbers()
    
    # Single search
    all_records = []
    
    _log(f"🔍 Starting Georgia Public Notice search from first of month: {search_date}")
    
    # Prepare task parameters (only use from_date, ignore to_date)
    task_params = {
        'max_records': max_new_records,
        'test_mode': test_mode,
        'date_from': search_date,
        'notice_types': notice_types,
        'county': 'Cobb'
    }
    
    try:
        # Run scraper with stealth configuration
        async with CobbScraper(config) as scraper:
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
                _log(f"⚠️ No records found or scraping failed")
        
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
    parser = argparse.ArgumentParser(description="Cobb County GA Public Notice Scraper")
    parser.add_argument("--max-records", type=int, default=MAX_NEW_RECORDS,
                        help="Maximum number of records to scrape")
    parser.add_argument("--test", action="store_true",
                        help="Run in test mode (visible browser, no database writes)")
    parser.add_argument("--from-date", 
                        help="Start date (MM/DD/YYYY)")
    parser.add_argument("--to-date",
                        help="End date (MM/DD/YYYY)")
    parser.add_argument("--notice-types", nargs="+",
                        help="Notice types to search for")
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
            notice_types=args.notice_types
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