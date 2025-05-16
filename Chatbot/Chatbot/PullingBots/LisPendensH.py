import asyncio
import os
from datetime import datetime
import time
import itertools
from pathlib import Path
import pandas as pd
from typing import Optional, TypedDict, List, Dict, Any
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Frame
import pytesseract
import pdf2image
from PIL import Image, ImageFilter
import tempfile
import re

class LisPendensRecord(TypedDict):
    case_number: str
    case_url: Optional[str]
    file_date: str
    property_address: str
    filing_no: str
    volume_no: str
    page_no: str

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
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta 

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL   = "https://www.cclerk.hctx.net/Applications/WebSearch/RP.aspx"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
HEADLESS   = False
YEAR       = datetime.now().year
MONTH: Optional[int] = None  # None ⇒ auto‑pick latest month
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
MAX_NEW_RECORDS = 10   # Maximum number of new records to scrape per run (testing)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Google Sheets (optional) ----------------------------------------------------
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME       = os.getenv("GSHEET_NAME")
LIS_PENDENS_TAB   = os.getenv("LIS_PENDENS_TAB")  # Default to "LisPendens" if not set
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
INSERT INTO lis_pendens_filings
  (case_no,
   case_url,
   file_date,
   property_address,
   filing_no,
   volume_no,
   page_no,
   scraped_at)
VALUES
  (:case_number,
   :case_url,
   :file_date,
   :property_address,
   :filing_no,
   :volume_no,
   :page_no,
   NOW())
ON CONFLICT (case_no) DO UPDATE
SET
  case_url         = EXCLUDED.case_url,
  file_date        = EXCLUDED.file_date,
  property_address = EXCLUDED.property_address,
  filing_no        = EXCLUDED.filing_no,
  volume_no        = EXCLUDED.volume_no,
  page_no          = EXCLUDED.page_no,
  scraped_at       = NOW();
"""
# ─────────────────────────────────────────────────────────────────────────────
# LOG + SAFE WRAPPER
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")
# ─────────────────────────────────────────────────────────────────────────────
# POP‑UP DISCLAIMER
# ─────────────────────────────────────────────────────────────────────────────
async def _maybe_accept(page: Page):
    for sel in [
        "button:has-text('Accept')",
        "button:has-text('I Accept')",
        "input[value='Accept']",
        r"text=/^Accept$/i",
        r"text=/^I\s*Accept$/i",
    ]:
        try:
            if await page.locator(sel).count():
                _log(f"Accepting disclaimer via {sel}")
                await page.locator(sel).first.click()
                await page.wait_for_load_state("networkidle")
                break
        except Exception:
            pass
# ─────────────────────────────────────────────────────────────────────────────
# HELPERS – frame, filters, pagination
# ─────────────────────────────────────────────────────────────────────────────
async def _find_frame(page: Page) -> Frame:
    """
    Find the frame containing the search form, or return the main frame if not found.
    """
    await page.wait_for_load_state("domcontentloaded")
    
    # First check for main page elements
    try:
        if await page.query_selector("input[id*='txtInstrument'], input[id*='ContentPlaceHolder1_txtInstrument']"):
            _log("Form found in main page")
            return page.main_frame
    except Exception as e:
        _log(f"Warning: Error checking main page: {e}")
    
    # Then check frames if not found on main page
    for frm in page.frames:
        try:
            if await frm.query_selector("div[id*='PgImg'], input[id*='txtInstrument']"):
                _log("Form frame located")
                print(f"Frame name: {frm.name}")
                return frm
        except Exception as e:
            _log(f"Warning: Error checking frame {frm.name}: {e}")
    
    # If we get here, just return the main frame and log a warning
    _log("Warning: Specific search form elements not found, using main frame")
    return page.main_frame

async def _apply_filters(
    page: Page,
    frm: Frame,
) -> None:
    """
    Apply filters on the Lis Pendens search page, then click Search.
    • Instrument Type: L/P (for Lis Pendens)
    • File Date (From): 2 weeks ago
    • File Date (To): today
    """
    # 1) Calculate dates
    today = date.today()
    two_weeks_ago = today - timedelta(days=14)

    # 2) Fill Instrument Type with "L/P" for Lis Pendens
    instrument_selectors = [
        "input[id*='txtInstrument']",
        "input[id*='ContentPlaceHolder1_txtInstrument']",
    ]
    
    for selector in instrument_selectors:
        try:
            if await frm.query_selector(selector):
                await frm.fill(selector, "L/P")
                _log("➡️ Instrument Type set → L/P (Lis Pendens)")
                break
        except Exception as e:
            _log(f"Warning: Could not use selector {selector}: {e}")
    
    # 3) Fill "From" date field
    date_from_selectors = [
        "input[id*='txtFrom']",
        "input[id*='ContentPlaceHolder1_txtFrom']",
    ]
    
    for selector in date_from_selectors:
        try:
            if await frm.query_selector(selector):
                await frm.fill(selector, two_weeks_ago.strftime("%m/%d/%Y"))
                _log(f"➡️ File Date (From) set → {two_weeks_ago:%m/%d/%Y}")
                break
        except Exception as e:
            _log(f"Warning: Could not use selector {selector}: {e}")

    # 4) Fill "To" date field
    date_to_selectors = [
        "input[id*='txtTo']",
        "input[id*='ContentPlaceHolder1_txtTo']",
    ]
    
    for selector in date_to_selectors:
        try:
            if await frm.query_selector(selector):
                await frm.fill(selector, today.strftime("%m/%d/%Y"))
                _log(f"➡️ File Date (To) set → {today:%m/%d/%Y}")
                break
        except Exception as e:
            _log(f"Warning: Could not use selector {selector}: {e}")

    # 5) Click Search and wait for the page to load results
    search_selectors = [
        "input[id*='btnSearch']",
        "input[id*='ContentPlaceHolder1_btnSearch']",
    ]
    
    search_button = None
    for selector in search_selectors:
        try:
            search_button = await frm.query_selector(selector)
            if search_button:
                _log(f"Found search button with selector: {selector}")
                break
        except Exception as e:
            _log(f"Warning: Could not find search button with selector {selector}: {e}")
    
    if not search_button:
        raise RuntimeError("Could not find search button on page")
    
    # Tie click to page navigation/network-idle
    async with page.expect_navigation(wait_until="networkidle"):
        await search_button.click()
    _log("➡️ Search clicked → page navigation complete")

# ─────────────────────────────────────────────────────────────────────────────
async def _get_lis_pendens_records(page: Page) -> list[LisPendensRecord]:
    """
    Extract Lis Pendens records from the search results page.
    """
    # Find the frame containing results
    for frm in page.frames:
        if await frm.query_selector("table[id*='itemPlaceholderContainer']"):
            parse_ctx = frm
            break
    else:
        raise RuntimeError("Couldn't locate the frame with itemPlaceholderContainer")
    
    # The selector for rows based on the screenshot HTML structure
    selector = "table#itemPlaceholderContainer > tbody > tr[valign='top']"

    await parse_ctx.wait_for_selector(selector, timeout=30_000)
    rows = await parse_ctx.query_selector_all(selector)
    _log(f"➡️ Found {len(rows)} result rows using selector: {selector!r}")
    
    lis_pendens_records = []
    for idx, row in enumerate(rows):
        # Stop early if we've hit our test limit of records
        if len(lis_pendens_records) >= MAX_NEW_RECORDS:
            _log(f"Reached test limit of {MAX_NEW_RECORDS} records, stopping further row processing.")
            break
        try:
            # Extract data from each row based on the HTML structure in the screenshots
            # File number (case number)
            file_no_element = await row.query_selector("span[id*='lblFileNo']")
            case_number = (await file_no_element.inner_text()).strip() if file_no_element else ""
            
            # Find the last TD in the row which contains the case link
            all_tds = await row.query_selector_all("td")
            if len(all_tds) > 0:
                last_td = all_tds[-1]
                
                # Look for the link with multiple possible patterns shown in the screenshots
                case_link = await last_td.query_selector(
                    "a[id*='HyperLinkFCEC'], a[class='doclinks'], a[href*='fComm/ViewEdoc.aspx']"
                )
                
                if case_link:
                    case_url_rel = await case_link.get_attribute("href")
                    
                    # If it's a relative URL, convert to absolute
                    if case_url_rel and not case_url_rel.startswith(('http://', 'https://')):
                        case_url = urljoin(BASE_URL, case_url_rel)
                        _log(f"Converted relative URL to absolute: {case_url}")
                    else:
                        case_url = case_url_rel
                    
                    _log(f"Found case URL for record {idx+1}: {case_url}")
                else:
                    # If we can't find the link but have film code, try to construct URL
                    film_code_text = await last_td.inner_text()
                    if "RP-" in film_code_text:
                        # Extract the film code value
                        film_code = None
                        for line in film_code_text.split("\n"):
                            if line.strip().startswith("RP-"):
                                film_code = line.strip().split("</a>")[0].strip() if "</a>" in line else line.strip()
                                break
                        
                        if film_code:
                            _log(f"Found film code in text: {film_code}, but no direct link")
                            case_url = None
                        else:
                            case_url = None
                            _log(f"No film code found in text for record {idx+1}")
                    else:
                        case_url = None
                        _log(f"No case link found in last TD for record {idx+1}")
            else:
                case_url = None
                _log(f"No TD elements found for record {idx+1}")
            
            # File date
            file_date_element = await row.query_selector("span[id*='lblFileDate']")
            file_date = (await file_date_element.inner_text()).strip() if file_date_element else ""
            
            # Filing number 
            filing_no_element = await row.query_selector("span[id*='lblVolNo']")
            filing_no = (await filing_no_element.inner_text()).strip() if filing_no_element else ""
            
            # Volume number
            volume_no_element = await row.query_selector("span[id*='lblPg']")
            volume_no = (await volume_no_element.inner_text()).strip() if volume_no_element else ""
            
            # Page number
            page_no_element = await row.query_selector("td:nth-child(7) span")
            page_no = (await page_no_element.inner_text()).strip() if page_no_element else ""
            
            # Instead of just reading property_address from the table, extract from PDF
            extracted_address = await extract_address_from_document(case_number, case_url, page)
            record = {
                "case_number": case_number,
                "case_url": case_url,
                "file_date": file_date,
                "property_address": extracted_address,
                "filing_no": filing_no,
                "volume_no": volume_no,
                "page_no": page_no,
            }
            
            lis_pendens_records.append(record)
            _log(f"✅ Extracted record {idx+1}: {case_number}")
            
        except Exception as e:
            _log(f"Error extracting data for row {idx+1}: {e}")
    
    return lis_pendens_records

async def get_existing_case_numbers():
    """
    Fetch all existing case numbers from the database.
    
    Returns a set of existing case numbers in the database or an empty set if the query fails.
    """
    existing_ids = set()
    
    # SQL options to try
    sql_options = [
        "SELECT case_no FROM lis_pendens_filings",
        "SELECT case_number FROM lis_pendens_filings",
        "SELECT id FROM lis_pendens_filings"
    ]
    
    async with AsyncSession(engine) as sess:
        for i, sql in enumerate(sql_options):
            try:
                result = await sess.execute(text(sql))
                rows = result.fetchall()
                
                # Extract IDs from result rows
                for row in rows:
                    existing_ids.add(row[0])
                
                _log(f"✅ Successfully fetched {len(existing_ids)} existing case numbers using SQL option {i+1}")
                return existing_ids
            except Exception as e:
                _log(f"⚠️ Failed to fetch existing IDs with SQL option {i+1}: {e}")
    
    _log("⚠️ Could not fetch existing case numbers from any database column")
    return existing_ids

async def upsert_records(records: list[dict]):
    """
    Insert or update a batch of records.
    
    :param records: a list of dicts matching INSERT_SQL parameters
    """
    if not records:
        return False
        
    # First check if the table exists
    async with AsyncSession(engine) as sess:
        try:
            # Check for lis_pendens_filings table
            table_check = await sess.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'lis_pendens_filings')"))
            table_exists = table_check.scalar()
            
            if not table_exists:
                _log("❌ The 'lis_pendens_filings' table does not exist in the database")
                _log("⚠️ Create the table or update the script to use the correct table name")
                return False
                
            # Get table columns to help diagnose schema issues
            columns_query = await sess.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'lis_pendens_filings'
                ORDER BY ordinal_position
            """))
            columns = columns_query.fetchall()
            _log(f"Table columns: {', '.join(f'{col[0]} ({col[1]})' for col in columns)}")
        except Exception as e:
            _log(f"❌ Error checking table schema: {e}")

        # Process records before insert - convert dates from strings to proper date objects
        processed_records = []
        for record in records:
            processed_record = record.copy()
            
            # Convert file_date from string to date object if it's a string
            if "file_date" in processed_record and isinstance(processed_record["file_date"], str):
                try:
                    # Parse the date string format MM/DD/YYYY to a datetime object
                    file_date = datetime.strptime(processed_record["file_date"], "%m/%d/%Y").date()
                    processed_record["file_date"] = file_date
                    _log(f"Converted date: {record['file_date']} -> {file_date}")
                except Exception as e:
                    _log(f"❌ Error converting date '{processed_record['file_date']}': {e}")
                    # If date conversion fails, provide a fallback value
                    processed_record["file_date"] = datetime.now().date()
            
            # Ensure case_url is properly handled
            if "case_url" in processed_record and processed_record["case_url"] is None:
                # If URL is None but we have a case number, create a placeholder URL
                if processed_record.get("case_number"):
                    _log(f"No URL found for case {processed_record['case_number']}, setting to empty string")
                    processed_record["case_url"] = ""
            
            processed_records.append(processed_record)

        # Try to insert the records
        try:
            await sess.execute(text(INSERT_SQL), processed_records)
            await sess.commit()
            _log(f"✅ Successfully inserted/updated {len(processed_records)} records")
            return True
        except Exception as e:
            await sess.rollback()
            # Get the full error message with details
            error_msg = str(e)
            if hasattr(e, '__cause__') and e.__cause__:
                error_msg += f" | Cause: {str(e.__cause__)}"
            _log(f"❌ Database error: {error_msg}")
            
            # Try alternative SQL without some fields
            try:
                alternative_sql = """
                INSERT INTO lis_pendens_filings
                (case_no, file_date, scraped_at)
                VALUES
                (:case_number, :file_date, NOW())
                ON CONFLICT (case_no) DO UPDATE
                SET
                file_date = EXCLUDED.file_date,
                scraped_at = NOW();
                """
                
                await sess.execute(text(alternative_sql), processed_records)
                await sess.commit()
                _log(f"✅ Successfully inserted/updated {len(processed_records)} records with minimal fields")
                return True
            except Exception as e2:
                await sess.rollback()
                _log(f"❌ Alternative SQL also failed: {e2}")
                return False

async def _export_csv(df: pd.DataFrame) -> Path:
    # Export to CSV
    fname = EXPORT_DIR / f"harris_lis_pendens_{datetime.now():%Y%m%d_%H%M%S}.csv"
    df.to_csv(fname, index=False)
    _log(f"CSV saved → {fname}")
    
    return fname

MAX_ROWS_PER_BATCH = 500

def _push_sheet(df: pd.DataFrame):
    if not GOOGLE_CREDS_FILE or not Path(GOOGLE_CREDS_FILE).exists():
        _log("Google creds missing – skipping Sheet sync")
        return
    if not GSHEET_NAME or not LIS_PENDENS_TAB:
        _log("Sheet name/config missing – skipping Sheet sync")
        return
    
    worksheet_name = LIS_PENDENS_TAB
    
    df = df.fillna("").astype(str)
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(GOOGLE_CREDS_FILE, scopes=scope)
    client = gspread.authorize(creds)

    # 1) Open or bail
    try:
        sh = client.open(GSHEET_NAME)
    except SpreadsheetNotFound:
        _log(f"❌ Spreadsheet not found: {GSHEET_NAME}")
        return

    # 2) Get or create the worksheet
    try:
        ws = sh.worksheet(worksheet_name)
        _log(f"✔ Found existing worksheet '{worksheet_name}' – clearing contents.")
        ws.clear()
    except WorksheetNotFound:
        _log(f"➕ Creating worksheet '{worksheet_name}'.")
        ws = sh.add_worksheet(
            title=worksheet_name,
            rows=len(df) + 10,
            cols=len(df.columns) + 5,
        )

    # 3) Batch‐update the data
    header = [df.columns.tolist()]
    rows = df.values.tolist()
    batches = itertools.zip_longest(
        *[iter(rows)] * MAX_ROWS_PER_BATCH, fillvalue=None
    )
    
    for batch in batches:
        payload = header + [r for r in batch if r is not None]
        tries, delay = 0, 1
        while True:
            try:
                ws.update(values=payload)
                break
            except APIError as e:
                code = int(e.response.status_code) if e.response else None
                if code in (429,) or (code is not None and 500 <= code < 600 and tries < 5):
                    _log(f"⚠️ APIError {code}, retrying in {delay}s…")
                    time.sleep(delay)
                    tries += 1
                    delay *= 2
                else:
                    raise
        header = []  # only include header in the first batch

    _log(f"✅ Sheet updated → {GSHEET_NAME}/{worksheet_name}")

# Address extraction helpers (copied from ForeclosureH.py)
def extract_address_from_text(text: str) -> dict:
    result = {
        "address": "",
        "source": "",
        "has_exhibit_a": False
    }
    # New extraction for 'legally described as'
    leg_desc_match = re.search(r'(?i)legally described as[:\\s]*([\\s\\S]+?\\d{5})', text)
    if leg_desc_match:
        candidate = leg_desc_match.group(1).strip()
        result["address"] = candidate
        result["source"] = "Legally Described"
        return result

    invalid_phrases = [
        "DEED OF TRUST", "DEED", "TRUSTEE", "MORTGAGE", "FORECLOSURE", 
        "SUBSTITUTE", "LIEN", "NOTICE", "APPOINTMENT"
    ]
    terminator_phrases = [
        "IN ACCORDANCE WITH", "AS REQUIRED BY", "PURSUANT TO", 
        "AS DEFINED IN", "COMMONLY KNOWN AS", "ALSO KNOWN AS"
    ]
    def standardize_numbers(text_segment):
        text_segment = text_segment.replace('@', '(').replace('#', ')')
        number_words = {
            'ONE': '1', 'TWO': '2', 'THREE': '3', 'FOUR': '4', 'FIVE': '5',
            'SIX': '6', 'SEVEN': '7', 'EIGHT': '8', 'NINE': '9', 'TEN': '10',
            'ELEVEN': '11', 'TWELVE': '12', 'THIRTEEN': '13', 'FOURTEEN': '14',
            'FIFTEEN': '15', 'SIXTEEN': '16', 'SEVENTEEN': '17', 'EIGHTEEN': '18',
            'NINETEEN': '19', 'TWENTY': '20', 'THIRTY': '30', 'FORTY': '40',
            'FIFTY': '50', 'SIXTY': '60', 'SEVENTY': '70', 'EIGHTY': '80', 'NINETY': '90'
        }
        for word, num in number_words.items():
            text_segment = re.sub(rf'{word}\s*\((\d+)\)', r'\1', text_segment, flags=re.IGNORECASE)
            text_segment = re.sub(rf'\b{word}\b', num, text_segment, flags=re.IGNORECASE)
        text_segment = re.sub(r'\((\d+)\)', r'\1', text_segment)
        text_segment = re.sub(r'LOTS?\s+(\d+)[- ](\d+)', r'LOTS \1-\2', text_segment, flags=re.IGNORECASE)
        return text_segment
    def clean_and_standardize_match(match_text):
        for phrase in terminator_phrases:
            phrase_pos = match_text.upper().find(phrase)
            if phrase_pos > 0:
                match_text = match_text[:phrase_pos].strip()
        match_text = standardize_numbers(match_text)
        match_text = match_text.replace('SlJBDIVISION', 'SUBDIVISION')
        match_text = match_text.replace('r.', ',')
        match_text = match_text.upper()
        if not match_text.endswith('.'):
            match_text = match_text + '.'
        return match_text
    prop_addr_match = re.search(r"Property\s*Address\s*:?", text, re.IGNORECASE)
    if prop_addr_match:
        addr_line1 = prop_addr_match.group(1) or ""
        addr_line2 = prop_addr_match.group(2) or ""
        candidate = (addr_line1 + " " + addr_line2).strip().replace("\n", " ")
        if len(candidate) > 10:
            result["address"] = candidate
            result["source"] = "Property Address Label"
            return result
    legal_desc_match = re.search(r"Legal\s+Description:?:?\s*(.{10,300})", text, re.IGNORECASE)
    if legal_desc_match:
        candidate = legal_desc_match.group(1)
        candidate = candidate.split(". ")[0].split("\n")[0].strip()
        if len(candidate) > 10:
            result["address"] = candidate
            result["source"] = "Legal Description Section"
            return result
    lot_block_patterns = [
        r"(LOT\s+(?:\w+|\(\w+\)|\d+)(?:[,,\s]+|[,,\s]+AND[,,\s]+)BLOCK\s+(?:\w+|\(\w+\)|\d+)[,,\s]+(?:OF|IN)?\s+[A-Za-z0-9\s\.,\-]+(?:SECTION|SEC\.|SUBDIVISION|SUBDIV\.|SUB\.|ADDITION|ADD\.|ESTATES|ESTATE|VILLAGE|WEST|EAST|NORTH|SOUTH)(?:[^\.]{5,150}))",
        r"(LOT\s+\d+,?\s+BLOCK\s+\d+,?\s+[^,\.]+,\s+(?:A\s+SUBDIVISION|SECTION)\s+(?:[^\.]{5,150}))",
        r"(LOT\s+(?:\w+|\(\w+\))\s*(?:\(?\d+\)?),?\s+(?:IN\s+)?BLOCK\s+(?:\w+|\(\w+\))\s*(?:\(?\d+\)?),?\s+(?:OF|IN)?[^\.]{5,150})",
        r"(LOT\s+(?:\w+|\(\w+\)|\d+)[,,\s]+BLOCK\s+(?:\w+|\(\w+\)|\d+))"
    ]
    for pattern in lot_block_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            match_text = match.strip()
            if not match_text.endswith('.') and '.' in text[text.find(match_text) + len(match_text):text.find(match_text) + len(match_text) + 50]:
                extended_match = text[text.find(match_text):text.find(match_text) + len(match_text) + 50]
                period_pos = extended_match.find('.', len(match_text))
                if period_pos > 0:
                    match_text = extended_match[:period_pos+1].strip()
            match_text = clean_and_standardize_match(match_text)
            if not any(invalid in match_text.upper() for invalid in invalid_phrases):
                result["address"] = match_text
                result["source"] = "Lot/Block Pattern"
                return result
    exhibit_patterns = [
        r"EXHIBIT\s+A",
        r"EXHIBIT\s*['\"]?A['\"]?",
        r"SEE\s+EXHIBIT\s+A",
        r"ATTACHED\s+EXHIBIT\s+A",
        r"LEGAL\s+DESCRIPTION\s+ATTACHED\s+AS\s+EXHIBIT\s+A"
    ]
    for pattern in exhibit_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            result["has_exhibit_a"] = True
            result["source"] = "EXHIBIT A reference found"
            break
    legal_desc_patterns = [
        r"(?:Legal\s+Description:?)?\s*(LOT\s+\d+,?\s+BLOCK\s+\d+[^\.]+(?:COUNTY|COUNTIES),\s+TEXAS[^\.]+(?:VOLUME|VOL\.)\s+\d+[^\.]+(?:PAGE|PG\.)\s+\d+[^\.]+(?:COUNTY|COUNTIES),\s+TEXAS\.?)",
        r"(?:Legal\s+Description:?)?\s*(LOT\s+\d+,?\s+BLOCK\s+\d+[^\.]+(?:SUBDIVISION|ADDITION|SECTION|ESTATE)[^\.]+(?:COUNTY|COUNTIES),\s+TEXAS\.?)"
    ]
    for pattern in legal_desc_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            match_text = match.strip()
            match_text = clean_and_standardize_match(match_text)
            if not any(invalid in match_text.upper() for invalid in invalid_phrases):
                result["address"] = match_text
                result["source"] = "Complete Legal Description"
                return result
    address_with_zip_patterns = [
        r"(\d+\s+[A-Za-z0-9\.\s]+,\s*[A-Za-z\s]+,\s*[A-Z]{2}\s+\d{5}(?:-\d{4})?)",
        r"(\d+\s+[A-Za-z0-9\.\s]+,\s*[A-Za-z\s]+,\s*TX\s+\d{5}(?:-\d{4})?)"
    ]
    for pattern in address_with_zip_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            match_text = match.strip()
            if not any(invalid in match_text.upper() for invalid in invalid_phrases):
                result["address"] = match_text
                result["source"] = "Complete Street Address"
                return result
    return result

def clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('|', 'I')
    text = text.replace('l1', '11')
    text = text.replace('O0', '00')
    text = re.sub(r'(?i)Streel', 'Street', text)
    text = re.sub(r'(?i)Slreet', 'Street', text)
    text = re.sub(r'(?i)Streot', 'Street', text)
    text = re.sub(r'(?i)Avonue', 'Avenue', text)
    text = re.sub(r'(?i)Avenuo', 'Avenue', text)
    text = re.sub(r'Property\s+Address\s*:?:?\s*', 'Property Address: ', text)
    text = re.sub(r'(\.)(\s+[A-Z])', r'\1\n\2', text)
    return text

def extract_text_from_pdf(file_path: str) -> str:
    if not pytesseract.pytesseract.tesseract_cmd:
        return ""
    extracted_text = ""
    DPI = 400
    POPPLER_BIN = r"C:\Program Files\poppler\Library\bin"
    # Step 1: Convert PDF pages to images (requires Poppler on PATH for Windows)
    try:
        images = pdf2image.convert_from_path(file_path, dpi=DPI, poppler_path=POPPLER_BIN)
    except Exception as e:
        print(f"[PDF2Image ERROR] Could not convert PDF to images ({file_path}): {e}")
        return ""
    # Step 2: OCR each image
    for img in images:
        img = img.convert('L')
        img = img.point(lambda x: 0 if x < 180 else 255, '1')
        img = img.filter(ImageFilter.SHARPEN)
        try:
            page_text = pytesseract.image_to_string(img)
        except Exception as ocr_e:
            print(f"[TESSERACT ERROR] OCR failed on image from {file_path}: {ocr_e}")
            continue
        extracted_text += page_text + "\n"
    # Step 3: Clean and debug-print the extracted text
    cleaned = clean_extracted_text(extracted_text)
    print(f"[OCR DEBUG] Cleaned text from {file_path}:\n{cleaned}")
    return cleaned

semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent downloads

async def limited_download(*args, **kwargs):
    async with semaphore:
        return await download_pdf(*args, **kwargs)

async def download_pdf(page: Page, doc_url: str, doc_id: str) -> str:
    PDF_DIR = (Path(__file__).parent / "pdfs").resolve()
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    try:
        browser = page.context.browser
        context = await browser.new_context(user_agent=USER_AGENT)
        doc_page = await context.new_page()

        # Revert to simple navigation (no network capture)
        await doc_page.goto(doc_url, wait_until="domcontentloaded", timeout=60000)
        await doc_page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(2)

        # --- LOGIN LOGIC (triggered if login form is present) ---
        USERNAME = os.getenv("LP_USERNAME")
        PASSWORD = os.getenv("LP_PASSWORD")
        if await doc_page.query_selector('input[id="ctl00_ContentPlaceHolder1_Login1_UserName"]'):
            await doc_page.fill('input[id="ctl00_ContentPlaceHolder1_Login1_UserName"]', USERNAME)
            await doc_page.fill('input[id="ctl00_ContentPlaceHolder1_Login1_Password"]', PASSWORD)
            await doc_page.check('input[id="ctl00_ContentPlaceHolder1_Login1_RememberMe"]')
            await doc_page.click('input[id="ctl00_ContentPlaceHolder1_Login1_LoginButton"]')
            await doc_page.wait_for_load_state("networkidle")

        # Expand PDF embed to fullscreen for full-page printing
        await doc_page.set_viewport_size({"width":1920, "height":1080})
        await doc_page.evaluate("""() => {
            const embed = document.querySelector('embed') || document.querySelector('iframe');
            if (embed) {
                embed.style.position = 'fixed';
                embed.style.top = '0';
                embed.style.left = '0';
                embed.style.width = '100vw';
                embed.style.height = '100vh';
                document.body.style.margin = '0';
                document.documentElement.style.margin = '0';
            }
        }""")
        pdf_path = PDF_DIR / f"doc_{doc_id.replace('/', '_')}_{datetime.now():%Y%m%d_%H%M%S}.pdf"
        try:
            download_button = doc_page.locator("a:has-text('Download')")
            if await download_button.count() > 0:
                with doc_page.expect_download() as download_info:
                    await download_button.click()
                download = await download_info.value
                await download.save_as(pdf_path)
            else:
                # Fallback: print page as PDF (includes embedded PDF viewer full-screen)
                pdf_bytes = await doc_page.pdf(print_background=True)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_bytes)
        except Exception:
            pass
        await doc_page.close()
        await context.close()
        return str(pdf_path)
    except Exception as e:
        _log(f"❌ Error downloading document {doc_id}: {e}")
        return None

async def extract_address_from_document(doc_id: str, doc_url: str, page: Page) -> str:
    try:
        pdf_path = await download_pdf(page, doc_url, doc_id)
        if pdf_path:
            text = extract_text_from_pdf(pdf_path)
            address_info = extract_address_from_text(text)
            return address_info["address"]
        return ""
    except Exception as e:
        _log(f"❌ Error extracting address from document {doc_id}: {e}")
        return ""

async def run():
    """Main function to run the scraper."""
    async with async_playwright() as pw:
        # Launch Chromium with your HEADLESS flag
        browser = await pw.chromium.launch(headless=HEADLESS)
        # Apply your custom user‑agent
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Go to the Lis Pendens search page
        await page.goto(BASE_URL)

        await _maybe_accept(page)
        frm = await _find_frame(page)
        await _apply_filters(page, frm)
        
        # Parse records from all pages until we hit our max or no more pages
        all_records = []
        page_num = 1
        has_next_page = True
        
        while has_next_page and len(all_records) < MAX_NEW_RECORDS:  # Fetch only up to MAX_NEW_RECORDS for testing
            _log(f"📄 Processing page {page_num}...")
            # Get records from current page
            page_records = await _get_lis_pendens_records(page)
            if page_records:
                all_records.extend(page_records)
                _log(f"✅ Found {len(page_records)} records on page {page_num}. Total so far: {len(all_records)}")
            else:
                _log(f"⚠️ No records found on page {page_num}")
                break
                
            # Check for the Next button
            next_button = None
            for frm in page.frames:
                try:
                    # Look for Next button with multiple possible selectors based on screenshot
                    selectors = [
                        "input[id*='BtnNext'][value='Next']",
                        "input[id*='ContentPlaceHolder1_BtnNext']",
                        "input[class*='btn-primary'][value='Next']",
                        "input[type='submit'][value='Next']"
                    ]
                    
                    for selector in selectors:
                        next_button = await frm.query_selector(selector)
                        if next_button:
                            _log(f"✅ Found Next button using selector: {selector}")
                            break
                            
                    if next_button:
                        break
                except Exception as e:
                    _log(f"Error looking for Next button in frame: {e}")
            
            if next_button:
                # Click the Next button and wait for page to load
                _log("⏭️ Clicking Next button to go to next page...")
                try:
                    await next_button.click()
                    await page.wait_for_load_state("networkidle")
                    page_num += 1
                except Exception as e:
                    _log(f"❌ Error clicking Next button: {e}")
                    has_next_page = False
            else:
                _log("⚠️ No Next button found - reached last page")
                has_next_page = False
        
        # Close the browser
        await browser.close()
        
        # Summary of scraping results
        _log(f"🔍 Scraping complete: {len(all_records)} records found across {page_num} page(s)")
        
        # Check which records are new (not in the database)
        existing_ids = await get_existing_case_numbers()
        _log(f"Checking against {len(existing_ids)} existing case numbers in database")
        
        # Filter to only records that don't exist in the database
        new_records = []
        for record in all_records:
            if record["case_number"] not in existing_ids:
                new_records.append(record)
                # Stop once we reach the maximum number of new records to process
                if len(new_records) >= MAX_NEW_RECORDS:
                    _log(f"Reached maximum of {MAX_NEW_RECORDS} new records to process")
                    break
        
        _log(f"Found {len(new_records)} new records")
        
        # Only update the database if we have new records
        db_success = False
        if new_records:
            db_success = await upsert_records(new_records)
            if db_success:
                _log(f"✅ Upserted {len(new_records)} new records to database.")
            else:
                _log(f"⚠️ Database operations failed, but continuing with export")
        else:
            _log("⚠️ No new records to add to database.")
            return None
        
        # Export to CSV and push to Google Sheets
        df = pd.DataFrame(new_records)
        csv_path = None
        if not df.empty:
            try:
                # Export to CSV
                csv_path = await _export_csv(df)
                _log(f"✅ Exported {len(new_records)} new records to CSV: {csv_path}")
                
                # Push to Google Sheets (blocking - run it off the event loop)
                if GOOGLE_CREDS_FILE and GSHEET_NAME and LIS_PENDENS_TAB:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, lambda: _push_sheet(df))
                    _log("✅ Pushed data to Google Sheets")
            except Exception as e:
                _log(f"❌ Error exporting to CSV or pushing to Google Sheets: {e}")
        else:
            _log("ℹ️ No CSV exported - no new records to save")
            
        return csv_path

if __name__ == "__main__":
    asyncio.run(run())
