import asyncio
import os
import random
from datetime import datetime, timedelta
import time
from pathlib import Path
import pandas as pd
import json
from typing import Optional, TypedDict, List, Dict, Any
from playwright.async_api import async_playwright, Page, Frame
import argparse
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
from dotenv import load_dotenv
import re
import pygetwindow as gw

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL = "https://casesearch.courts.state.md.us/casesearch/inquirySearch.jis"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
HEADLESS = False  # Keep browser visible for manual interaction
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
MAX_NEW_RECORDS = 18  # Default for backwards compatibility (6 letters × 3 records each)
USER_ID = None  # Will be set from command line argument
DATE_FILTER_DAYS = 7  # Will be set from command line argument, defaults to 7 days
COOKIES_FILE = "md_cookies.json"  # File to store manual cookies

# Load environment variables
load_dotenv()
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required for database connection")

# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────
engine = create_async_engine(DB_URL, echo=False)
INSERT_SQL = """
INSERT INTO md_case_search_filing
  (case_number,
   case_url,
   file_date,
   party_name,
   case_type,
   county,
   created_at,
   is_new,
   doc_type,
   "userId",
   property_address,
   defendant_info,
   case_details_raw,
   case_details_scraped_at)
VALUES
  (:case_number,
   :case_url,
   :file_date,
   :party_name,
   :case_type,
   :county,
   :created_at,
   :is_new,
   :doc_type,
   :user_id_param,
   :property_address,
   :defendant_info,
   :case_details_raw,
   :case_details_scraped_at)
ON CONFLICT (case_number) DO UPDATE
SET
  case_url         = EXCLUDED.case_url,
  file_date        = EXCLUDED.file_date,
  party_name       = EXCLUDED.party_name,
  case_type        = EXCLUDED.case_type,
  county           = EXCLUDED.county,
  created_at       = EXCLUDED.created_at,
  is_new           = EXCLUDED.is_new,
  doc_type         = EXCLUDED.doc_type,
  "userId"         = EXCLUDED."userId",
  property_address = EXCLUDED.property_address,
  defendant_info   = EXCLUDED.defendant_info,
  case_details_raw = EXCLUDED.case_details_raw,
  case_details_scraped_at = EXCLUDED.case_details_scraped_at;
"""

# ─────────────────────────────────────────────────────────────────────────────
# LOG + SAFE WRAPPER
# ─────────────────────────────────────────────────────────────────────────────
def _log(msg: str):
    try:
        print(f"[{datetime.now():%H:%M:%S}] {msg}")
    except UnicodeEncodeError:
        # Handle Unicode characters that can't be encoded by Windows console
        safe_msg = msg.encode('ascii', errors='replace').decode('ascii')
        print(f"[{datetime.now():%H:%M:%S}] {safe_msg}")

# ─────────────────────────────────────────────────────────────────────────────
# COOKIE MANAGEMENT (RESTORED)
# ─────────────────────────────────────────────────────────────────────────────
async def load_cookies(page: Page) -> bool:
    """Load cookies from manual browser session"""
    if not Path(COOKIES_FILE).exists():
        _log(f"[WARNING] Cookie file {COOKIES_FILE} not found!")
        _log("[INFO] MANUAL COOKIE SETUP:")
        _log("1. Open Chrome/Edge and go to: https://casesearch.courts.state.md.us/casesearch/inquirySearch.jis")
        _log("2. Accept the disclaimer manually (solve any CAPTCHA)")
        _log("3. Press F12, go to Console tab")
        _log("4. Run: JSON.stringify(document.cookie.split(';').map(c => {let [name,value] = c.trim().split('='); return {name, value, domain: '.courts.state.md.us', path: '/'}}))")
        _log("5. Copy the output and save it to md_cookies.json")
        _log("6. Run this script again")
        return False
    
    try:
        with open(COOKIES_FILE, 'r') as f:
            cookies = json.load(f)
        
        await page.context.add_cookies(cookies)
        _log(f"[SUCCESS] Loaded {len(cookies)} cookies from {COOKIES_FILE}")
        return True
    except Exception as e:
        _log(f"[ERROR] Error loading cookies: {e}")
        return False

async def save_cookies(page: Page):
    """Save current cookies for future use"""
    try:
        cookies = await page.context.cookies()
        with open(COOKIES_FILE, 'w') as f:
            json.dump(cookies, f, indent=2)
        _log(f"[SUCCESS] Saved {len(cookies)} cookies to {COOKIES_FILE}")
    except Exception as e:
        _log(f"[ERROR] Error saving cookies: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# ULTRA-MINIMAL STEALTH (AVOID DATADOME TRIGGERS)
# ─────────────────────────────────────────────────────────────────────────────
async def setup_ultra_minimal_stealth(page: Page) -> None:
    """Apply absolute minimal stealth to avoid DataDome detection"""
    
    # Only hide the most basic webdriver property - nothing else
    await page.add_init_script("""
        // Only hide webdriver - don't touch anything else that might trigger DataDome
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        console.log('Minimal stealth applied');
    """)
    _log("[SUCCESS] Applied ultra-minimal stealth (DataDome-safe)")

async def human_like_typing(element, text: str) -> None:
    """Type text with realistic delays"""
    await element.click()
    await asyncio.sleep(0.3)
    
    for char in text:
        await element.type(char)
        await asyncio.sleep(random.uniform(0.08, 0.12))

async def human_like_click(element) -> None:
    """Click with realistic delay"""
    await asyncio.sleep(random.uniform(0.5, 1.0))
    await element.click()
    await asyncio.sleep(random.uniform(0.3, 0.7))

# ─────────────────────────────────────────────────────────────────────────────
# MANUAL DISCLAIMER BYPASS WITH DATADOME HANDLING
# ─────────────────────────────────────────────────────────────────────────────
async def auto_start_search_process(page: Page) -> bool:
    """Automatically click case number field and start search process"""
    _log("[BOT] Starting automated interaction with search form...")
    
    try:
        # Wait a moment for page to be fully loaded
        await page.wait_for_timeout(2000)
        
        # Try to find and click the case number input using name attribute
        case_number_input = page.locator('input[name="caseId"]')
        
        # Wait for the element to be visible
        try:
            await case_number_input.wait_for(state='visible', timeout=10000)
            _log("[SUCCESS] Case Number input found")
            
            # Click on it to simulate user interaction
            await human_like_click(case_number_input)
            _log("[TARGET] Clicked on Case Number input")
            
        except Exception as e:
            _log(f"[WARNING] Could not find/click case number input: {e}")
            # Continue anyway - we'll try to apply filters
        
        # Give a brief moment for any page reactions
        await page.wait_for_timeout(1000)
        
        _log("[START] Proceeding with automated search...")
        return True
        
    except Exception as e:
        _log(f"[ERROR] Error in auto start: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────
async def _apply_filters_and_search(page: Page, letter: str) -> bool:
    """Apply filters and search for a specific letter"""
    _log(f"[SEARCH] Starting search for letter '{letter}'...")
    
    # Look for Party Search accordion
    try:
        party_search = page.locator('h3:has-text("Party Search")')
        if await party_search.count() > 0:
            await human_like_click(party_search)
            _log("Clicked Party Search")
    except Exception as e:
        _log(f"Note: Party Search not found or already open: {e}")
    
    # Look for Advanced Search accordion  
    try:
        advanced_search = page.locator('h3:has-text("Advanced Search")')
        if await advanced_search.count() > 0:
            await human_like_click(advanced_search)
            _log("Clicked Advanced Search")
    except Exception as e:
        _log(f"Note: Advanced Search not found or already open: {e}")
    
    # Fill in search criteria - target elements within Advanced Search tabpanel specifically
    try:
        # Get the Advanced Search tabpanel as our scope
        advanced_search_panel = page.get_by_role("tabpanel", name="Advanced Search")
        
        # Clear and fill first name with % (wildcard for any first name)
        first_name_input = advanced_search_panel.locator('#firstName')
        if await first_name_input.count() > 0:
            await first_name_input.clear()  # Clear existing value
            await human_like_typing(first_name_input, "%")
            _log(f"Cleared and filled first name with '%' (Advanced Search panel)")
        else:
            _log("[ERROR] Could not find firstName input in Advanced Search panel")
        
        # Clear and fill last name with the letter to search for names starting with that letter
        last_name_input = advanced_search_panel.locator('#lastName')
        if await last_name_input.count() > 0:
            await last_name_input.clear()  # Clear existing value
            await human_like_typing(last_name_input, f"{letter}%")
            _log(f"Cleared and filled last name with '{letter}%' (Advanced Search panel)")
        else:
            _log("[ERROR] Could not find lastName input in Advanced Search panel")
        
        # Select only CIVIL case type within Advanced Search panel
        civil_checkbox = advanced_search_panel.locator('input[type="radio"][name="site"][value="CIVIL"]')
        if await civil_checkbox.count() > 0:
            await civil_checkbox.click()
            _log("Selected case type: CIVIL (Advanced Search panel)")
        else:
            # Try alternative selector for CIVIL
            civil_checkbox_alt = advanced_search_panel.locator('input[value="CIVIL"]')
            if await civil_checkbox_alt.count() > 0:
                await civil_checkbox_alt.first.click()
                _log("Selected case type: CIVIL (alternative selector, Advanced Search panel)")
            else:
                _log("[ERROR] Could not find CIVIL radio button in Advanced Search panel")
        
        # Select county within Advanced Search panel
        county_select = advanced_search_panel.locator('select[name="countyName"]')
        if await county_select.count() > 0:
            _log("[SUCCESS] Found county select dropdown")
            
            # Debug: List all available county options
            try:
                county_options = await county_select.locator('option').all()
                _log(f"🐛 DEBUG: Found {len(county_options)} county options:")
                for i, option in enumerate(county_options):
                    try:
                        option_value = await option.get_attribute('value') or 'no-value'
                        option_text = await option.inner_text() or 'no-text'
                        if 'montgomery' in option_text.lower() or 'montgomery' in option_value.lower():
                            _log(f"  [TARGET] Option {i+1}: value='{option_value}', text='{option_text}' *** MONTGOMERY ***")
                        else:
                            _log(f"  Option {i+1}: value='{option_value}', text='{option_text}'")
                    except Exception as e:
                        _log(f"  Option {i+1}: Error getting attributes - {e}")
            except Exception as e:
                _log(f"[ERROR] Error debugging county options: {e}")
            
            # Try multiple ways to select Montgomery County
            montgomery_selected = False
            
            # Method 1: Try exact value match
            try:
                await county_select.select_option(value="MONTGOMERY COUNTY")
                _log("[SUCCESS] Selected Montgomery County (Method 1: exact value)")
                montgomery_selected = True
            except Exception as e1:
                _log(f"Method 1 failed: {e1}")
                
                # Method 2: Try by visible text
                try:
                    await county_select.select_option(label="Montgomery County")
                    _log("[SUCCESS] Selected Montgomery County (Method 2: by label)")
                    montgomery_selected = True
                except Exception as e2:
                    _log(f"Method 2 failed: {e2}")
                    
                    # Method 3: Try to find option containing "montgomery" (case insensitive)
                    try:
                        montgomery_option = county_select.locator('option').filter(has_text=re.compile("montgomery", re.IGNORECASE))
                        if await montgomery_option.count() > 0:
                            montgomery_value = await montgomery_option.first.get_attribute('value')
                            await county_select.select_option(value=montgomery_value)
                            _log(f"[SUCCESS] Selected Montgomery County (Method 3: found by text match, value='{montgomery_value}')")
                            montgomery_selected = True
                        else:
                            _log("[ERROR] Method 3: No Montgomery option found by text")
                    except Exception as e3:
                        _log(f"Method 3 failed: {e3}")
            
            if not montgomery_selected:
                _log("[ERROR] Failed to select Montgomery County using all methods")
        else:
            _log("[ERROR] Could not find County select in Advanced Search panel")
        
        # Set filing date range (using configurable date filter)
        from_date = (datetime.now() - timedelta(days=DATE_FILTER_DAYS)).strftime("%m/%d/%Y")
        to_date = datetime.now().strftime("%m/%d/%Y")
        _log(f"[DATE_RANGE] Searching from {from_date} to {to_date} ({DATE_FILTER_DAYS} days back)")
        
        # Clear and fill filing date from
        filing_date_from = advanced_search_panel.locator('input[name="filingStart"]')
        if await filing_date_from.count() > 0:
            await filing_date_from.clear()  # Clear existing value
            await human_like_typing(filing_date_from, from_date)
            _log(f"Cleared and set filing date from: {from_date} (Advanced Search panel)")
            
            # Click apply button after filling "from" date
            apply_button = advanced_search_panel.locator('button.btn.btn-primary:has-text("Apply")')
            if await apply_button.count() > 0:
                await human_like_click(apply_button)
                _log("Clicked apply button after setting from date (Advanced Search panel)")
                # Wait for button to be disabled
                await page.wait_for_timeout(1000)
            
        # Clear and fill filing date to
        filing_date_to = advanced_search_panel.locator('input[name="filingEnd"]')
        if await filing_date_to.count() > 0:
            await filing_date_to.clear()  # Clear existing value
            await human_like_typing(filing_date_to, to_date)
            _log(f"Cleared and set filing date to: {to_date} (Advanced Search panel)")
            
            await page.keyboard.press('Enter')
            _log("[SUCCESS] Pressed Enter key")

            await page.wait_for_selector('span.pagebanner', timeout=10000)
            _log("Results page detected via pagebanner.")
            return True
        
    except Exception as e:
        _log(f"[ERROR] Error filling search criteria in Advanced Search panel: {e}")
    

async def _get_case_records(page: Page, existing_case_numbers: set, max_new_records: int = 5) -> list[dict]:
    """Extract case records from the search results page, sorted by Filing Date descending, skipping Date of Birth and not storing any links except for all <a> in the first td."""
    global USER_ID
    records = []
    new_record_count = 0
    seen_names = set()  # Track names we've already seen to ensure uniqueness

    # 1. Wait for the results table to appear
    await page.wait_for_selector('table#row.results', timeout=15000)

    # Get column headers for mapping
    headers = []
    header_cells = await page.locator('table#row.results thead th.sortable').all()
    for th in header_cells:
        header_text = (await th.inner_text()).strip()
        headers.append(header_text)
    _log(f"Detected headers: {headers}")

    # 2. Click the Filing Date header twice to sort by most recent
    filing_date_header = page.locator('table#row.results th a', has_text="Filing Date")
    if await filing_date_header.count() > 0:
        await filing_date_header.first.click()
        _log("Clicked Filing Date header (first click).")
        await page.wait_for_timeout(1000)
        await filing_date_header.first.click()
        _log("Clicked Filing Date header (second click).")
        await page.wait_for_timeout(1500)
    else:
        _log("Could not find Filing Date header to sort results.")

    # 3. Parse each row in the table body (odd and even rows)
    rows = await page.locator('table#row.results tbody tr.odd, table#row.results tbody tr.even').all()
    _log(f"Found {len(rows)} result rows in results table.")
    
    def is_name_similar(new_name: str, seen_names: set) -> bool:
        """Check if the new name is similar to any previously seen names"""
        if not new_name or not new_name.strip():
            return False
            
        new_name_clean = new_name.strip().lower()
        new_name_words = set(new_name_clean.split())
        
        for seen_name in seen_names:
            seen_name_clean = seen_name.strip().lower()
            seen_name_words = set(seen_name_clean.split())
            
            # Check for exact match
            if new_name_clean == seen_name_clean:
                return True
                
            # Check if there's any word overlap (partial match)
            if new_name_words & seen_name_words:  # Set intersection
                return True
                
            # Check if one name is contained in the other
            if new_name_clean in seen_name_clean or seen_name_clean in new_name_clean:
                return True
                
        return False
    
    for idx, row in enumerate(rows):
        try:
            # Use Playwright Locator API to get all <td> elements in the row
            cols = await row.locator('td').all()
            if not cols or len(cols) < 1:
                _log(f"Row {idx+1} is empty or has no <td> elements, skipping.")
                continue  # Skip empty rows
            
            # Extract all td values as a list
            td_values = [(await td.inner_text()).strip() for td in cols]
            
            # Extract case number link from first td
            case_number_link = None
            case_url = None
            link_anchor = cols[0].locator('a')
            if await link_anchor.count() > 0:
                href = await link_anchor.first.get_attribute('href')
                text = (await link_anchor.first.inner_text()).strip()
                case_number_link = {"href": href, "text": text}
                # Create full URL for case_url
                if href and not href.startswith('http'):
                    case_url = f"https://casesearch.courts.state.md.us/casesearch/{href}"
                else:
                    case_url = href
            
            # Map td_values to proper field names based on expected structure
            # Expected: Case Number, Case number link, name, party type, court, case type, case status, filing date, case caption
            case_number = td_values[0] if len(td_values) > 0 else ""
            party_name = td_values[1] if len(td_values) > 1 else ""
            # Skip Date of Birth (td_values[2])
            party_type = td_values[3] if len(td_values) > 3 else ""
            court = td_values[4] if len(td_values) > 4 else ""
            case_type = td_values[5] if len(td_values) > 5 else ""
            case_status = td_values[6] if len(td_values) > 6 else ""
            filing_date = td_values[7] if len(td_values) > 7 else ""
            case_caption = td_values[8] if len(td_values) > 8 else ""
            
            # Skip if already in DB (by case number text)
            if case_number in existing_case_numbers:
                _log(f"Skipping existing case_number: {case_number}")
                continue
                
            # Check for name uniqueness (skip if we've seen this name or similar before)
            if is_name_similar(party_name, seen_names):
                _log(f"Skipping duplicate/similar name: {party_name} (already seen similar)")
                continue
                
            # Check if we've reached our limit
            if new_record_count >= max_new_records:
                _log(f"Reached max_new_records limit of {max_new_records}, stopping further row processing.")
                break
            
            # Add the name to our seen set
            seen_names.add(party_name)
            
            # Parse filing_date string to datetime object for database compatibility
            parsed_file_date = None
            if filing_date:
                try:
                    parsed_file_date = datetime.strptime(filing_date, "%m/%d/%Y")
                except ValueError:
                    try:
                        parsed_file_date = datetime.strptime(filing_date, "%m-%d-%Y")
                    except ValueError:
                        _log(f"[WARNING] Could not parse date '{filing_date}', using None")
                        parsed_file_date = None
            
            record = {
                "case_number": case_number,
                "case_url": case_url,
                "file_date": parsed_file_date,
                "party_name": party_name,
                "case_type": case_type,
                "county": court,  # Using court as county for now
                "case_status": case_status,
                "party_type": party_type,
                "case_caption": case_caption,
                "case_number_link": case_number_link,
                "created_at": datetime.now(),
                "is_new": True,
                "doc_type": "MD_CASE",
                "user_id_param": USER_ID,
                # New fields for case details (will be populated during enrichment)
                "property_address": None,
                "defendant_info": None,
                "case_details_raw": None,
                "case_details_scraped_at": None,
            }
            records.append(record)
            new_record_count += 1
            _log(f"[SUCCESS] Extracted unique record {new_record_count}: {case_number} ({party_name})")
        except Exception as e:
            _log(f"Error extracting data for row {idx+1}: {e}")
    
    _log(f"[DATA] Final summary: Found {len(records)} unique records from {len(rows)} total rows")
    _log(f"[PEOPLE] Unique names collected: {list(seen_names)}")
    
    # Navigate to each case details page and enrich all records
    if records:
        _log("[START] Starting enrichment process for all records...")
        enriched_records = await _enrich_all_records_with_case_details(page, records)
        _log(f"[SUCCESS] Enrichment process completed for {len(enriched_records)} records")
        return enriched_records
    
    return records

async def get_existing_case_numbers():
    """Fetch existing case numbers from database"""
    existing_ids = set()
    sql = "SELECT case_number FROM md_case_search_filing"
    async with AsyncSession(engine) as sess:
        try:
            result = await sess.execute(text(sql))
            rows = result.fetchall()
            for row in rows:
                existing_ids.add(row[0])
            _log(f"[SUCCESS] Successfully fetched {len(existing_ids)} existing case numbers")
            return existing_ids
        except Exception as e:
            _log(f"[WARNING] Failed to fetch existing IDs: {e}")
    return existing_ids

async def upsert_records(records: list[dict]):
    """Insert/update records in database"""
    if not records:
        return False
    async with AsyncSession(engine) as sess:
        try:
            await sess.execute(text(INSERT_SQL), records)
            await sess.commit()
            _log(f"[SUCCESS] Successfully inserted/updated {len(records)} records")
            return True
        except Exception as e:
            await sess.rollback()
            _log(f"[ERROR] Database error: {e}")
            return False

async def _export_csv(df: pd.DataFrame) -> Path:
    fname = EXPORT_DIR / f"md_case_search_{datetime.now():%Y%m%d_%H%M%S}.csv"
    df.to_csv(fname, index=False)
    _log(f"CSV saved to {fname}")
    return fname

async def _scrape_case_details(page: Page) -> dict:
    """Scrape case details page for structured and unstructured data"""
    case_details = {
        "property_address": None,
        "defendant_info": None,
        "case_details_raw": None,
        "case_details_scraped_at": datetime.now()
    }
    
    try:
        # Wait for page to load
        await page.wait_for_timeout(3000)
        
        # Get the full page content for LLM context (unstructured)
        page_content = await page.content()
        case_details["case_details_raw"] = page_content
        _log("[SUCCESS] Captured full page content for LLM context")
        
        # Extract structured data - property address
        try:
            # Look for address after "Address:" under Involved Parties Information
            page_text = await page.inner_text('body')
            property_address = None
            
            # Method 1: Look for "Address:" pattern and extract until zip code or "Attorney"
            address_pattern = re.compile(
                r'Address:\s*(.*?)(?:\d{5}(?:-\d{4})?|Attorney)',  # Capture after "Address:" until zip or "Attorney"
                re.IGNORECASE | re.DOTALL
            )
            address_match = address_pattern.search(page_text)
            if address_match:
                raw_address = address_match.group(1).strip()
                # Clean up the address - remove extra whitespace and line breaks
                property_address = re.sub(r'\s+', ' ', raw_address).strip()
                # If it ends with partial zip, try to capture the zip code too
                zip_pattern = re.compile(r'(\d{5}(?:-\d{4})?)')
                zip_match = zip_pattern.search(page_text[address_match.end()-10:address_match.end()+10])
                if zip_match:
                    property_address += ' ' + zip_match.group(1)
                _log(f"Found property address (Method 1): {property_address}")
            
            # Method 2: More specific HTML parsing if Method 1 fails
            if not property_address:
                # Look for address in table cells containing "Address"
                address_cells = page.locator('td:has-text("Address"), span:has-text("Address")').locator('..')
                if await address_cells.count() > 0:
                    for i in range(await address_cells.count()):
                        try:
                            cell_text = await address_cells.nth(i).inner_text()
                            if 'address:' in cell_text.lower():
                                # Extract everything after "Address:"
                                address_start = cell_text.lower().find('address:') + 8
                                potential_address = cell_text[address_start:].strip()
                                # Look for zip code pattern
                                zip_match = re.search(r'\d{5}(?:-\d{4})?', potential_address)
                                if zip_match:
                                    property_address = potential_address[:zip_match.end()].strip()
                                    _log(f"Found property address (Method 2): {property_address}")
                                    break
                        except:
                            continue
            
            case_details["property_address"] = property_address
            
        except Exception as e:
            _log(f"[WARNING] Error extracting property address: {e}")
        
        # Extract structured data - plaintiff and defendant information  
        try:
            plaintiff_info = []
            defendant_info = []
            
            # Get the full page content for parsing
            page_content = await page.content()
            
            # Method 1: Look for combined "Tenant / Defendant" sections
            tenant_sections_pattern = re.compile(
                r'<h6[^>]*>Tenant\s*/\s*Defendant</h6>(.*?)(?=<h6[^>]*>(?!.*Tenant.*Defendant)|</body>|$)',
                re.IGNORECASE | re.DOTALL
            )
            
            tenant_sections = tenant_sections_pattern.findall(page_content)
            _log(f"Found {len(tenant_sections)} Tenant/Defendant sections")
            
            for idx, section in enumerate(tenant_sections):
                # Within each section, look for "Name:" followed by the actual name value
                name_pattern = re.compile(
                    r'<span[^>]*class="[^"]*FirstColumnPrompt[^"]*"[^>]*>Name:</span>.*?<span[^>]*class="[^"]*Value[^"]*"[^>]*>([^<]+)</span>',
                    re.IGNORECASE | re.DOTALL
                )
                
                name_matches = name_pattern.findall(section)
                
                for name_match in name_matches:
                    clean_name = name_match.strip()
                    if len(clean_name) > 2 and clean_name not in defendant_info:
                        defendant_info.append(clean_name)
                        _log(f"Found tenant/defendant name in section {idx + 1}: {clean_name}")
            
            # Method 2: Look for separate Plaintiff sections
            plaintiff_sections_pattern = re.compile(
                r'<h6[^>]*>Plaintiff</h6>(.*?)(?=<h6[^>]*>(?!.*Plaintiff)|</body>|$)',
                re.IGNORECASE | re.DOTALL
            )
            
            plaintiff_sections = plaintiff_sections_pattern.findall(page_content)
            _log(f"Found {len(plaintiff_sections)} Plaintiff sections")
            
            for idx, section in enumerate(plaintiff_sections):
                # Within each section, look for "Name:" followed by the actual name value
                name_pattern = re.compile(
                    r'<span[^>]*class="[^"]*FirstColumnPrompt[^"]*"[^>]*>Name:</span>.*?<span[^>]*class="[^"]*Value[^"]*"[^>]*>([^<]+)</span>',
                    re.IGNORECASE | re.DOTALL
                )
                
                name_matches = name_pattern.findall(section)
                
                for name_match in name_matches:
                    clean_name = name_match.strip()
                    if len(clean_name) > 2 and clean_name not in plaintiff_info:
                        plaintiff_info.append(clean_name)
                        _log(f"Found plaintiff name in section {idx + 1}: {clean_name}")
            
            # Method 3: Look for separate Defendant sections (in addition to Tenant/Defendant)
            defendant_sections_pattern = re.compile(
                r'<h6[^>]*>Defendant</h6>(.*?)(?=<h6[^>]*>(?!.*Defendant)|</body>|$)',
                re.IGNORECASE | re.DOTALL
            )
            
            defendant_sections = defendant_sections_pattern.findall(page_content)
            _log(f"Found {len(defendant_sections)} Defendant sections")
            
            for idx, section in enumerate(defendant_sections):
                # Within each section, look for "Name:" followed by the actual name value
                name_pattern = re.compile(
                    r'<span[^>]*class="[^"]*FirstColumnPrompt[^"]*"[^>]*>Name:</span>.*?<span[^>]*class="[^"]*Value[^"]*"[^>]*>([^<]+)</span>',
                    re.IGNORECASE | re.DOTALL
                )
                
                name_matches = name_pattern.findall(section)
                
                for name_match in name_matches:
                    clean_name = name_match.strip()
                    if len(clean_name) > 2 and clean_name not in defendant_info:
                        defendant_info.append(clean_name)
                        _log(f"Found defendant name in section {idx + 1}: {clean_name}")
            
            # Method 4: Fallback using page locators for more precision
            if not plaintiff_info and not defendant_info:
                _log("HTML regex methods failed, trying page locators...")
                try:
                    # Find all relevant h6 elements
                    party_headers = page.locator('h6:has-text("Tenant / Defendant"), h6:has-text("Plaintiff"), h6:has-text("Defendant")')
                    header_count = await party_headers.count()
                    _log(f"Found {header_count} party headers")
                    
                    for i in range(header_count):
                        try:
                            header = party_headers.nth(i)
                            header_text = await header.inner_text()
                            parent = header.locator('xpath=..')
                            
                            # Look for "Name:" span within this section
                            name_labels = parent.locator('span:has-text("Name:")')
                            name_count = await name_labels.count()
                            
                            for j in range(name_count):
                                try:
                                    name_label = name_labels.nth(j)
                                    label_td = name_label.locator('xpath=ancestor::td[1]')
                                    value_td = label_td.locator('xpath=following-sibling::td[1]')
                                    
                                    if await value_td.count() > 0:
                                        name_text = await value_td.inner_text()
                                        clean_name = name_text.strip()
                                        
                                        if len(clean_name) > 2:
                                            if 'plaintiff' in header_text.lower():
                                                if clean_name not in plaintiff_info:
                                                    plaintiff_info.append(clean_name)
                                                    _log(f"Found plaintiff name (locator method): {clean_name}")
                                            else:  # defendant or tenant/defendant
                                                if clean_name not in defendant_info:
                                                    defendant_info.append(clean_name)
                                                    _log(f"Found defendant name (locator method): {clean_name}")
                                                    
                                except Exception as e:
                                    _log(f"Error extracting name from section {i+1}, name {j+1}: {e}")
                                    continue
                                    
                        except Exception as e:
                            _log(f"Error processing party section {i+1}: {e}")
                            continue
                            
                except Exception as e:
                    _log(f"Error in locator method: {e}")
            
            # Format as "Plaintiff vs Defendant"
            plaintiff_vs_defendant = ""
            
            if plaintiff_info and defendant_info:
                plaintiff_str = ", ".join(plaintiff_info)
                defendant_str = ", ".join(defendant_info)
                plaintiff_vs_defendant = f"{plaintiff_str} vs {defendant_str}"
            elif plaintiff_info:
                plaintiff_str = ", ".join(plaintiff_info)
                plaintiff_vs_defendant = f"{plaintiff_str} vs [Unknown Defendant]"
            elif defendant_info:
                defendant_str = ", ".join(defendant_info)
                plaintiff_vs_defendant = f"[Unknown Plaintiff] vs {defendant_str}"
            
            # Store the formatted result
            case_details["defendant_info"] = plaintiff_vs_defendant if plaintiff_vs_defendant else None
            
            if plaintiff_vs_defendant:
                _log(f"[SUCCESS] Successfully extracted party info: {plaintiff_vs_defendant}")
            else:
                _log("[WARNING] No plaintiff/defendant information found")
            
        except Exception as e:
            _log(f"[WARNING] Error extracting party info: {e}")
            import traceback
            traceback.print_exc()
        
        _log("[SUCCESS] Case details scraping completed")
        
    except Exception as e:
        _log(f"[ERROR] Error scraping case details: {e}")
        import traceback
        traceback.print_exc()
    
    return case_details

async def _enrich_all_records_with_case_details(page: Page, records: list[dict]) -> list[dict]:
    """Navigate to each case, scrape details, and enrich the records"""
    if not records:
        _log("[ERROR] No records to enrich")
        return records
    
    _log(f"[START] Starting to enrich {len(records)} records with case details...")
    
    for idx, record in enumerate(records):
        try:
            _log(f"[INFO] Processing record {idx + 1}/{len(records)}: {record['case_number']}")
            
            # Navigate to the specific case
            navigation_success = await _navigate_to_specific_case(page, record)
            
            if navigation_success:
                # Scrape the case details
                case_details = await _scrape_case_details(page)
                
                # Merge case details into the record
                record.update(case_details)
                _log(f"[SUCCESS] Enriched record {idx + 1}: {record['case_number']}")
                
                # Go back to search results page (except for the last record)
                if idx < len(records) - 1:
                    back_success = await _go_back_to_search_results(page)
                    if not back_success:
                        _log(f"[ERROR] Failed to go back after record {idx + 1}, stopping enrichment")
                        break
                    
                    # Small delay between cases to be courteous
                    await page.wait_for_timeout(1000)
            else:
                _log(f"[ERROR] Failed to navigate to case {record['case_number']}, adding empty details")
                # Add empty case details to maintain schema consistency
                record.update({
                    "property_address": None,
                    "defendant_info": None, 
                    "case_details_raw": None,
                    "case_details_scraped_at": None
                })
                
        except Exception as e:
            _log(f"[ERROR] Error processing record {idx + 1}: {e}")
            # Add empty case details for failed records
            record.update({
                "property_address": None,
                "defendant_info": None, 
                "case_details_raw": None,
                "case_details_scraped_at": None
            })
    
    _log(f"[DONE] Completed enriching records. {len([r for r in records if r.get('case_details_raw')])} records successfully enriched.")
    return records

async def _navigate_to_specific_case(page: Page, record: dict) -> bool:
    """Navigate to a specific case details page by clicking on the case URL"""
    try:
        if not record.get("case_url") or not record.get("case_number_link"):
            _log(f"[ERROR] No valid case URL found for {record.get('case_number')}")
            return False
        
        case_number = record["case_number"]
        case_url = record["case_url"]
        _log(f"[LINK] Navigating to case details for: {case_number}")
        
        # Find the table row with this case number and click the link
        case_link_selector = f'table#row.results tbody tr td a[href*="{record["case_number_link"]["href"]}"]'
        case_link = page.locator(case_link_selector).first
        
        if await case_link.count() > 0:
            await human_like_click(case_link)
            _log(f"[SUCCESS] Clicked on case link for {case_number}")
            
            # Wait for navigation to complete
            await page.wait_for_load_state('networkidle', timeout=15000)
            _log("[SUCCESS] Navigation to case details completed")
            
            # Wait for case details content to load
            await page.wait_for_timeout(2000)
            
            return True
                
        else:
            _log(f"[ERROR] Could not find clickable link for case {case_number}")
            return False
            
    except Exception as e:
        _log(f"[ERROR] Error navigating to case details: {e}")
        import traceback
        traceback.print_exc()
        return False

async def _go_back_to_search_results(page: Page) -> bool:
    """Go back to the search results page"""
    try:
        _log("Going back to search results page...")
        await page.go_back()
        await page.wait_for_load_state('networkidle', timeout=10000)
        
        # Wait for results table to be visible
        await page.wait_for_selector('table#row.results', timeout=10000)
        _log("Successfully returned to search results page")
        return True
        
    except Exception as e:
        _log(f"Error going back to search results: {e}")
        return False

# ─────────────────────────────────────────────────────────────────────────────
# MAIN SCRAPER LOGIC
# ─────────────────────────────────────────────────────────────────────────────
async def run():
    """Main function with cookie loading + DataDome handling + manual bypass + automated searching for letters A-F"""
    async with async_playwright() as pw:
        # Launch browser with absolute minimal settings to avoid DataDome
        browser = await pw.chromium.launch(
            headless=HEADLESS
            # NO ARGS - completely clean browser to avoid DataDome detection
        )
        
        _log(f"Using clean browser configuration (DataDome-safe)")
        
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={'width': 1366, 'height': 768},
            locale='en-US'
            # Minimal context to avoid DataDome triggers
        )
        
        page = await context.new_page()
        
        try:
            # Give user 5 seconds to manually interact, then minimize browser
            _log("[TIMER] Browser will minimize in 5 seconds - please click 'Agree' on any disclaimers if needed...")
            await page.wait_for_timeout(5000)
            
            # Minimize all Chromium windows using pygetwindow (same as LpH.py)
            try:
                for w in gw.getWindowsWithTitle('Chromium'):
                    w.minimize()
                _log("[SUCCESS] Browser minimized using pygetwindow")
            except Exception as e:
                _log(f"[WARNING] Could not minimize browser window: {e}")
                _log("[NOTE] Browser will remain visible during scraping")
            
            # Try to load existing cookies first
            cookies_loaded = await load_cookies(page)
            
            # Apply ultra-minimal stealth
            await setup_ultra_minimal_stealth(page)
            
            # Navigate to search page
            _log("Navigating to Maryland Case Search...")
            await page.goto(BASE_URL, wait_until='networkidle')
            
            # Skip page state detection and proceed directly to search page logic
            _log("Proceeding as if on search page...")
            
            # Save successful cookies for future use
            await save_cookies(page)
            
            # Get existing case numbers once at the beginning
            existing_case_numbers = await get_existing_case_numbers()
            
            # Accumulate all records from all letters
            all_records = []
            letters_to_process = ['a', 'b', 'c', 'd', 'e', 'f']
            
            _log(f"Starting to process letters: {', '.join(letter.upper() for letter in letters_to_process)}")
            
            # Automatically start the search process
            if await auto_start_search_process(page):
                
                for letter_idx, letter in enumerate(letters_to_process):
                    _log(f"Processing Letter {letter_idx + 1}/{len(letters_to_process)}: '{letter.upper()}'")
                    
                    # Apply filters and perform the search for current letter
                    search_success = await _apply_filters_and_search(page, letter)

                    if search_success:
                        # Get records for this letter (limit to 3 per letter)
                        letter_records = await _get_case_records(page, existing_case_numbers, 3)
                        _log(f"Letter '{letter.upper()}': Parsed {len(letter_records)} records (max 3 per letter)")
                        
                        # Add these records to our accumulator
                        all_records.extend(letter_records)
                        
                        # Add the new case numbers to our existing set to avoid duplicates in subsequent letters
                        for record in letter_records:
                            existing_case_numbers.add(record["case_number"])
                        
                        # Show quick preview for this letter
                        if letter_records:
                            _log(f"Letter '{letter.upper()}' preview: {letter_records[0]['party_name']}, {letter_records[-1]['party_name']}")
                        
                        # Go back to search page for next letter (except for the last letter)
                        if letter_idx < len(letters_to_process) - 1:
                            _log(f"Going back to search page for next letter...")
                            await page.goto(BASE_URL, wait_until='networkidle')
                            await page.wait_for_timeout(2000)  # Give page time to load
                            
                            # Re-initialize search process for next letter
                            await auto_start_search_process(page)
                    else:
                        _log(f"Failed to search for letter '{letter.upper()}'")
                
                # After processing all letters, save everything to DB and export CSV
                _log(f"Completed processing all letters! Total records collected: {len(all_records)}")
                
                if all_records:
                    _log("Saving all records to database...")
                    await upsert_records(all_records)
                    
                    _log("Exporting enriched data to CSV...")
                    # Prepare DataFrame for export with ALL enriched data
                    df = pd.DataFrame([
                        {
                            "Case Number": r["case_number"],
                            "Case URL": r["case_url"], 
                            "Name": r["party_name"],
                            "Property Address": r.get("property_address", ""),  # Enriched address data
                            "Party Type": r["party_type"],
                            "Court": r["county"],  # court is stored as county
                            "Case Type": r["case_type"],
                            "Case Status": r["case_status"],
                            "Filing Date": r["file_date"],
                            "Case Caption": r["case_caption"],
                            "Plaintiff vs Defendant": r.get("defendant_info", ""),  # Enriched party info
                        }
                        for r in all_records
                    ])
                    await _export_csv(df)
                    
                    _log(f"Successfully processed and saved {len(all_records)} total records from {len(letters_to_process)} letters")
                    
                    # Summary by letter
                    letter_counts = {}
                    for record in all_records:
                        first_letter = record["party_name"][0].lower() if record["party_name"] else "unknown"
                        letter_counts[first_letter] = letter_counts.get(first_letter, 0) + 1
                    
                    _log("Final summary by letter:")
                    for letter, count in sorted(letter_counts.items()):
                        _log(f"  Letter '{letter.upper()}': {count} records")
                        
                else:
                    _log("No records collected from any letters")
                    
            else:
                _log("Failed to start automated search process.")
            
        except Exception as e:
            _log(f"Error during execution: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()
            _log("Browser closed. Script completed!")
            
        return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Maryland Case Search Scraper - DataDome + Cookie Enabled")
    parser.add_argument("--limit", type=int, default=5, help="Maximum number of new records to process (default: 5)")
    parser.add_argument("--user-id", type=str, required=False, help="User ID to associate records with (optional for testing)")
    parser.add_argument("--date-filter", type=int, default=7, help="Number of days back to search (default: 7)")
    args = parser.parse_args()
    if args.limit is not None:
        MAX_NEW_RECORDS = args.limit
        print(f"[INFO] Overriding MAX_NEW_RECORDS to {MAX_NEW_RECORDS} due to --limit argument.")
    else:
        MAX_NEW_RECORDS = 10
    if args.user_id:
        USER_ID = args.user_id
        print(f"[INFO] Using USER_ID: {USER_ID}")
    else:
        USER_ID = "test"
        print("[WARNING] No --user-id provided. Using USER_ID='test' for testing mode.")
    
    # Set the global date filter
    DATE_FILTER_DAYS = args.date_filter
    print(f"[INFO] Using DATE_FILTER: {DATE_FILTER_DAYS} days")
    
    asyncio.run(run()) 