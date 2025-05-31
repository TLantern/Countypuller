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
from PIL import Image, ImageFilter, ImageEnhance
import tempfile
import re
import cv2
import numpy as np
import argparse
import pyap
import openai

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
HEADLESS   = True
YEAR       = datetime.now().year
MONTH: Optional[int] = None  # None ⇒ auto‑pick latest month
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
MAX_NEW_RECORDS = 100   # Maximum number of new records to scrape per run (default)
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
INSERT INTO lis_pendens_filing
  (case_number,
   case_url,
   file_date,
   property_address,
   filing_no,
   volume_no,
   page_no,
   county,
   created_at,
   is_new,
   doc_type)
VALUES
  (:case_number,
   :case_url,
   :file_date,
   :property_address,
   :filing_no,
   :volume_no,
   :page_no,
   :county,
   :created_at,
   :is_new,
   :doc_type)
ON CONFLICT (case_number) DO UPDATE
SET
  case_url         = EXCLUDED.case_url,
  file_date        = EXCLUDED.file_date,
  property_address = EXCLUDED.property_address,
  filing_no        = EXCLUDED.filing_no,
  volume_no        = EXCLUDED.volume_no,
  page_no          = EXCLUDED.page_no,
  county           = EXCLUDED.county,
  created_at       = EXCLUDED.created_at,
  is_new           = EXCLUDED.is_new,
  doc_type         = EXCLUDED.doc_type;
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
async def _get_lis_pendens_records(page: Page, existing_case_numbers: set, max_new_records: int) -> list[LisPendensRecord]:
    """
    Extract Lis Pendens records from the search results page, skipping any that already exist in the database.
    Only count and log new records, and stop when max_new_records is reached.
    """
    # Find the frame containing results
    for frm in page.frames:
        if await frm.query_selector("table[id*='itemPlaceholderContainer']"):
            parse_ctx = frm
            break
    else:
        raise RuntimeError("Couldn't locate the frame with itemPlaceholderContainer")
    
    selector = "table#itemPlaceholderContainer > tbody > tr[valign='top']"
    await parse_ctx.wait_for_selector(selector, timeout=30_000)
    rows = await parse_ctx.query_selector_all(selector)
    _log(f"➡️ Found {len(rows)} result rows using selector: {selector!r}")
    
    lis_pendens_records = []
    new_record_count = 0
    for idx, row in enumerate(rows):
        # Extract case_number as early as possible
        file_no_element = await row.query_selector("span[id*='lblFileNo']")
        case_number = (await file_no_element.inner_text()).strip() if file_no_element else ""
        # Skip if already in DB
        if case_number in existing_case_numbers:
            _log(f"Skipping existing case_number: {case_number}")
            continue
        if new_record_count >= max_new_records:
            _log(f"Reached max_new_records limit of {max_new_records}, stopping further row processing.")
            break
        try:
            # Find the last TD in the row which contains the case link
            all_tds = await row.query_selector_all("td")
            if len(all_tds) > 0:
                last_td = all_tds[-1]
                case_link = await last_td.query_selector(
                    "a[id*='HyperLinkFCEC'], a[class='doclinks'], a[href*='fComm/ViewEdoc.aspx']"
                )
                if case_link:
                    case_url_rel = await case_link.get_attribute("href")
                    if case_url_rel and not case_url_rel.startswith(('http://', 'https://')):
                        case_url = urljoin(BASE_URL, case_url_rel)
                        _log(f"Converted relative URL to absolute: {case_url}")
                    else:
                        case_url = case_url_rel
                    _log(f"Found case URL for record {new_record_count+1}: {case_url}")
                else:
                    film_code_text = await last_td.inner_text()
                    if "RP-" in film_code_text:
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
                            _log(f"No film code found in text for record {new_record_count+1}")
                    else:
                        case_url = None
                        _log(f"No case link found in last TD for record {new_record_count+1}")
            else:
                case_url = None
                _log(f"No TD elements found for record {new_record_count+1}")
            file_date_element = await row.query_selector("span[id*='lblFileDate']")
            file_date = (await file_date_element.inner_text()).strip() if file_date_element else ""
            filing_no_element = await row.query_selector("span[id*='lblVolNo']")
            filing_no = (await filing_no_element.inner_text()).strip() if filing_no_element else ""
            volume_no_element = await row.query_selector("span[id*='lblPg']")
            volume_no = (await volume_no_element.inner_text()).strip() if volume_no_element else ""
            page_no_element = await row.query_selector("td:nth-child(7) span")
            page_no = (await page_no_element.inner_text()).strip() if page_no_element else ""
            extracted_address = await extract_address_from_document(case_number, case_url, page)
            record = {
                "case_number": case_number,
                "case_url": case_url,
                "file_date": file_date,
                "property_address": extracted_address,
                "filing_no": filing_no,
                "volume_no": volume_no,
                "page_no": page_no,
                "county": "Harris",
                "created_at": datetime.now(),
                "is_new": True,
                "doc_type": "L/P",
            }
            lis_pendens_records.append(record)
            new_record_count += 1
            _log(f"✅ Extracted record {new_record_count}: {case_number}")
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
        "SELECT case_number FROM lis_pendens_filing",
        "SELECT id FROM lis_pendens_filing"
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
            table_check = await sess.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'lis_pendens_filing')"))
            table_exists = table_check.scalar()
            
            if not table_exists:
                _log("❌ The 'lis_pendens_filing' table does not exist in the database")
                _log("⚠️ Create the table or update the script to use the correct table name")
                return False
                
            # Get table columns to help diagnose schema issues
            columns_query = await sess.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'lis_pendens_filing'
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
            
            # Try alternative SQL with minimal required fields
            try:
                alternative_sql = """
                INSERT INTO lis_pendens_filing
                (case_number, file_date, created_at)
                VALUES
                (:case_number, :file_date, :created_at)
                ON CONFLICT (case_number) DO UPDATE
                SET
                file_date = EXCLUDED.file_date,
                created_at = EXCLUDED.created_at;
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
    # Only use a single regex for property extraction
    property_regex = re.compile(
        r'(?i)(legally described as:|being a portion of)([\s\S]+?)(?=This action seeks|by the applicable\')',
        re.IGNORECASE
    )
    match = property_regex.search(text)
    if match:
        candidate = match.group(2).strip()
        result["address"] = candidate
        result["source"] = "Property Regex Block"
        return result
    return result

def clean_extracted_text(text: str) -> str:
    if not text:
        return ""
    # Normalize unicode quotes and dashes
    text = text.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    text = text.replace("—", "-").replace("–", "-")
    # Fix common OCR errors (expanded)
    corrections = {
        "Lx": "Ln",
        "l1": "11",
        "O0": "00",
        "Streel": "Street",
        "Slreet": "Street",
        "Streot": "Street",
        "Avonue": "Avenue",
        "Avenuo": "Avenue",
        "Comiurtt": "Community",
        "howe, ing": "housing",
        "rown as": "known as",
        "Set.": "Sec.",
        "l6": "lis",
        # Only replace '6' with 'b' in 'Lis Pendens' context
        "LI6 PENDENS": "LIS PENDENS",
        "LI6": "LIS",
        "6": "b",  # Use with caution, only in 'Lis Pendens' context
    }
    for wrong, right in corrections.items():
        text = re.sub(rf"\\b{re.escape(wrong)}\\b", right, text, flags=re.IGNORECASE)
    # Remove hyphenation at line breaks (e.g., Pinebrook Hol-\nlow Ln -> Pinebrook Hollow Ln)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Join lines that are split in the middle of sentences
    text = re.sub(r"\n+", " ", text)  # Replace newlines with space
    text = re.sub(r"\s+", " ", text)  # Collapse whitespace
    # Standardize key phrases
    key_phrases = [
        "legally described as", "known as", "property located at", "commonly known as"
    ]
    for phrase in key_phrases:
        text = re.sub(rf"{phrase}[:\s]*", f"{phrase}: ", text, flags=re.IGNORECASE)
    # Remove non-content lines
    text = re.sub(r"SIGNED this the.*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"RP-\d{4,}-\d{5,}", "", text)
    # Remove lines with only numbers or symbols
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[$#@!%^&*()_+=\[\]{}|;:'\",.<>/?`~\\-]+\s*$", "", text, flags=re.MULTILINE)
    # Optional: Spell correction for address components using textblob
    try:
        from textblob import TextBlob
        # Only correct words that are likely to be part of an address
        def correct_address_words(s):
            # Only correct if the word is not all uppercase (to avoid state/city abbreviations)
            return ' '.join([
                w if w.isupper() or w.istitle() else str(TextBlob(w).correct())
                for w in s.split()
            ])
        text = correct_address_words(text)
    except ImportError:
        pass  # If textblob is not installed, skip spell correction
    # Final trim
    text = text.strip()
    return text

def clean_address_with_llm(address: str) -> str:
    """
    Use OpenAI GPT-3.5 Turbo to extract and return only the clean US mailing address from the input text.
    Requires OPENAI_API_KEY to be set in the environment.
    """
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[LLM CLEAN WARNING] OPENAI_API_KEY not set in environment.")
        return address
    openai.api_key = api_key
    prompt = (
        "Return only the US street address, city, state, and ZIP code. "
        "Do not include any names, legal phrases, suite numbers, or extra words. "
        "If no valid address is found, return an empty string.\n\n"
        f"{address}"
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=60,
            temperature=0.0,
        )
        cleaned = response.choices[0].message['content'].strip()
        return cleaned
    except Exception as e:
        print(f"[LLM CLEAN ERROR] {e}")
        return address  # Fallback to original if LLM fails

def needs_llm_polish(address: str) -> bool:
    # If the address contains a likely street address and state/ZIP, do not polish unless legalese is present
    street_pattern = r"\d+\s+\w+\s+(St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Ln|Lane|Dr|Drive|Ct|Court|Pl|Place|Way|Terrace|Ter|Loop|Pkwy|Parkway)"
    state_zip_pattern = r"[A-Z]{2}\s*\d{5}(-\d{4})?"
    if re.search(street_pattern, address, re.IGNORECASE) and re.search(state_zip_pattern, address):
        # Only polish if legalese is present
        legalese_phrases = [
            "lot", "block", "section", "plat", "file no", "map record", "recorded in", "volume", "page", "cause no", "attorney", "notary", "signed this", "state of", "county of", "before me", "plaintiff", "defendant"
        ]
        for phrase in legalese_phrases:
            if phrase in address.lower():
                return True
        return False
    # If no clear street/state/zip, or if too long, or contains legalese, polish
    if len(address) > 80:
        return True
    legalese_phrases = [
        "lot", "block", "section", "plat", "file no", "map record", "recorded in", "volume", "page", "cause no", "attorney", "notary", "signed this", "state of", "county of", "before me", "plaintiff", "defendant"
    ]
    for phrase in legalese_phrases:
        if phrase in address.lower():
            return True
    return False

semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent downloads

async def limited_download(*args, **kwargs):
    async with semaphore:
        return await download_pdf(*args, **kwargs)

def ocr_region_from_image(image_path: str, debug_path: str = None) -> str:
    img = Image.open(image_path)
    # Contrast Enhancement
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.05)  # Reduced contrast boost for more natural result
    # Convert to OpenCV format
    open_cv_image = np.array(img)
    if open_cv_image.ndim == 3:
        if open_cv_image.shape[2] == 4:  # RGBA
            open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGBA2BGR)
        else:
            open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, h=30)
    # Adaptive Thresholding (replaces Otsu)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
    )
    # Deskew
    coords = np.column_stack(np.where(thresh > 0))
    angle = 0.0
    if coords.shape[0] > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
    (h, w) = thresh.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    deskewed = cv2.warpAffine(thresh, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # Save debug image if needed
    if debug_path:
        cv2.imwrite(debug_path, deskewed)
    # Convert back to PIL for pytesseract
    pil_img = Image.fromarray(deskewed)
    text = pytesseract.image_to_string(pil_img)
    return text

async def download_pdf(page: Page, doc_url: str, doc_id: str) -> str:
    SCREENSHOT_DIR = (Path(__file__).parent / "screenshots").resolve()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        browser = page.context.browser
        context = await browser.new_context(user_agent=USER_AGENT)
        doc_page = await context.new_page()

        await doc_page.goto(doc_url, wait_until="domcontentloaded", timeout=60000)
        await doc_page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(4)

        USERNAME = os.getenv("LP_USERNAME")
        PASSWORD = os.getenv("LP_PASSWORD")
        if await doc_page.query_selector('input[id="ctl00_ContentPlaceHolder1_Login1_UserName"]'):
            await doc_page.fill('input[id="ctl00_ContentPlaceHolder1_Login1_UserName"]', USERNAME)
            await doc_page.fill('input[id="ctl00_ContentPlaceHolder1_Login1_Password"]', PASSWORD)
            await doc_page.check('input[id="ctl00_ContentPlaceHolder1_Login1_RememberMe"]')
            await doc_page.click('input[id="ctl00_ContentPlaceHolder1_Login1_LoginButton"]')
            await doc_page.wait_for_load_state("networkidle")

        await doc_page.set_viewport_size({"width": 1414, "height": 746})
        await doc_page.evaluate("""
            () => {
                document.body.style.margin = '0';
                document.documentElement.style.margin = '0';
            }
        """)
        await asyncio.sleep(2)
        screenshot_path = SCREENSHOT_DIR / f"screenshot_{doc_id.replace('/', '_')}_{datetime.now():%Y%m%d_%H%M%S}.png"
        await doc_page.screenshot(path=str(screenshot_path), full_page=True)
        _log(f"🖼️ Saved screenshot for {doc_id} at {screenshot_path}")
        await doc_page.close()
        await context.close()

        try:
            img = Image.open(screenshot_path)
            img_sharpened = img.filter(ImageFilter.SHARPEN)
            img_sharpened.save(screenshot_path)
            _log(f"🖼️ Sharpened screenshot for {doc_id}")
        except Exception as e:
            _log(f"⚠️ Could not sharpen screenshot for {doc_id}: {e}")

        return str(screenshot_path)
    except Exception as e:
        _log(f"❌ Error taking screenshot for {doc_id}: {e}")
        return None

async def extract_address_from_document(doc_id: str, doc_url: str, page: Page) -> str:
    try:
        file_path = await download_pdf(page, doc_url, doc_id)
        address = ""
        extracted_text = ""
        if file_path:
            if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                try:
                    # OCR the entire image, no cropping
                    extracted_text = ocr_region_from_image(file_path, debug_path=None)
                    print(f"[OCR OUTPUT for {doc_id}]\n{extracted_text}\n---")
                except Exception as e:
                    _log(f"❌ Error running OCR on screenshot: {e}")
            if extracted_text:
                # Use prioritized regex patterns to extract the description
                patterns = [
                    r"(?:commonly known|known as|is commonly known|is commonly)(.*?)(?:this action seeks)",
                    r"(?:commonly known as|commonly known|this proceeding is|property affected:|known as|is commonly known|property located at|common address|legally described as)(.*?)(?:the instrument|this action seeks|and/or stats|by the applicable|to unpaid|this action|that the lawsuit|to whom it|parcel id|authorized|recovery of|and being legally described|and being|may concern)"
                ]
                address = ""
                for pat in patterns:
                    match = re.search(pat, extracted_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        address = match.group(1).strip()
                        break
                if not address:
                    # Fallback: use pyap to extract address
                    print(f"[PYAP INPUT for {doc_id}]\n{extracted_text}\n---")
                    cleaned_text = clean_extracted_text(extracted_text)
                    addresses = pyap.parse(cleaned_text, country='US')
                    if addresses:
                        address = addresses[0].full_address
                        print(f"[PYAP OUTPUT for {doc_id}]\n{address}\n---")
                        if needs_llm_polish(address):
                            address = clean_address_with_llm(address)
                    else:
                        address = clean_address_with_llm(cleaned_text)
                        print(f"[PYAP OUTPUT for {doc_id}]\nNo address found by pyap.\n---")
                print(f"[PARSED ADDRESS for {doc_id}]\n{address}\n---")
        return address
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
        
        existing_case_numbers = await get_existing_case_numbers()
        
        while has_next_page and len(all_records) < MAX_NEW_RECORDS:
            _log(f"📄 Processing page {page_num}...")
            page_records = await _get_lis_pendens_records(page, existing_case_numbers, MAX_NEW_RECORDS - len(all_records))
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
    parser = argparse.ArgumentParser(description="Lis Pendens Scraper")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of new records to process")
    args = parser.parse_args()

    # Override MAX_NEW_RECORDS if --limit is provided
    if args.limit is not None:
        MAX_NEW_RECORDS = args.limit
        print(f"[INFO] Overriding MAX_NEW_RECORDS to {MAX_NEW_RECORDS} due to --limit argument.")

    asyncio.run(run())