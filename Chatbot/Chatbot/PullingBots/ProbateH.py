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

class Event(TypedDict):
    event_case: str
    event_date: str
    event_desc: str
    event_comment: str

class Party(TypedDict):
    role: str
    name: str
    attorney: str

class Record(TypedDict):
    case_number: str
    case_url: Optional[str]
    status: str
    file_date: str
    type_desc: str
    sub_type: str
    style: str
    parties: List[Party]
    events: List[Event]
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
BASE_URL   = "https://www.cclerk.hctx.net/applications/websearch/CourtSearch.aspx?CaseType=Probate"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
HEADLESS   = False
YEAR       = datetime.now().year
MONTH: Optional[int] = None  # None ⇒ auto‑pick latest month
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)
MAX_NEW_RECORDS = 50  # Maximum number of new records to scrape per run

# Google Sheets (optional) ----------------------------------------------------
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME       = os.getenv("GSHEET_NAME")
GSHEET_WORKSHEET  = os.getenv("GSHEET_TAB")
PROBATE_TAB       = os.getenv("PROBATE_TAB")  # Default to "Probate" if not set
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
INSERT INTO foreclosure_filings
  (case_no,
   case_url,
   file_date,
   status,
   type_desc,
   sub_type,
   style,
   parties,
   events,
   scraped_at)
VALUES
  (:case_number,
   :case_url,
   :file_date,
   :status,
   :type_desc,
   :sub_type,
   :style,
   :parties::jsonb,
   :events::jsonb,
   NOW())
ON CONFLICT (case_no) DO UPDATE
SET
  case_url   = EXCLUDED.case_url,
  file_date  = EXCLUDED.file_date,
  status     = EXCLUDED.status,
  type_desc  = EXCLUDED.type_desc,
  sub_type   = EXCLUDED.sub_type,
  style      = EXCLUDED.style,
  parties    = EXCLUDED.parties,
  events     = EXCLUDED.events,
  scraped_at = NOW();
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
    await page.wait_for_load_state("domcontentloaded")
    for frm in page.frames:
        try:
            if await frm.query_selector("div[id*='PgImg']"):
                _log("Form frame located")
                print(f"Frame name: {frm.name}")
                return frm
        except Exception:
            pass
    try:
        if await page.query_selector("div[id*='PgImg']"):
            _log("Form found in main page")
            return page.main_frame
    except Exception:
        pass
    raise RuntimeError("Search form frame not found.")

async def _apply_filters(
    page: Page,
    frm: Frame,
) -> None:
    """
    Apply filters on the Probate Courts document search page, then click Search.
    • Status: always set to "Open"
    • File Date (From): 6 months ago
    • File Date (To): 30 days ago
    """
    # 1) Calculate dates
    today = date.today()
    six_months_ago = today - relativedelta(months=6)
    thirty_days_ago = today - timedelta(days=30)

    await frm.select_option("select[id*='DropDownListStatus']", value="Open")
    _log(f"➡️ Status set → Open")

    await frm.fill("input[id*='txtFrom']", six_months_ago.strftime("%m/%d/%Y"))
    _log(f"➡️ File Date (From) set → {six_months_ago:%m/%d/%Y}")

    await frm.fill("input[id*='txtTo']", thirty_days_ago.strftime("%m/%d/%Y"))
    _log(f"➡️ File Date (To) set → {thirty_days_ago:%m/%d/%Y}")

    # 2) Click Search **and** wait for the **parent** page to load results
    sel_search = "input[id*='btnSearch']"
    await frm.wait_for_selector(sel_search, timeout=30_000)

    # THIS is the magic: tie your click to the page navigation/network-idle
    async with page.expect_navigation(wait_until="networkidle"):
        await frm.click(sel_search)
    _log("➡️ Search clicked → page navigation complete")

# ─────────────────────────────────────────────────────────────────────────────
async def _get_basic_case_info(page: Page) -> list[dict]:
    """
    First pass to quickly extract just the case numbers and basic info without expanding details.
    This allows us to check which records are new before spending time on detailed parsing.
    """
    # 1) find the real parsing context
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
    
    basic_records = []
    for idx, row in enumerate(rows):
        try:
            # Extract only the basic case info without expanding details
            case_cell = await row.query_selector("td:nth-child(2)")
            case_number = (await case_cell.inner_text()).strip() if case_cell else ""
            case_link = await row.query_selector("td:nth-child(2) a.doclinks")
            case_url = await case_link.get_attribute("href") if case_link else None
            file_date_element = await row.query_selector("td:nth-child(4)")
            file_date = (await file_date_element.inner_text()).strip() if file_date_element else ""
            status_element = await row.query_selector("td:nth-child(5)")
            status = (await status_element.inner_text()).strip() if status_element else ""
            type_element = await row.query_selector("td:nth-child(6)")
            type_desc = (await type_element.inner_text()).strip() if type_element else ""
            sub_type_element = await row.query_selector("td:nth-child(7)")
            sub_type = (await sub_type_element.inner_text()).strip() if sub_type_element else ""
            style_element = await row.query_selector("td:nth-child(8)")
            style = (await style_element.inner_text()).strip() if style_element else ""
            
            basic_records.append({
                "case_number": case_number,
                "case_url": case_url,
                "file_date": file_date,
                "status": status,
                "type_desc": type_desc,
                "sub_type": sub_type,
                "style": style,
                "row_index": idx  # Store row index for later reference
            })
        except Exception as e:
            _log(f"Error extracting basic info for row {idx+1}: {e}")
    
    return basic_records

async def _parse_case_details(page: Page, row_index: int, basic_info: dict) -> Record:
    """Parse detailed party and event information for a single case."""
    # Find the real parsing context
    for frm in page.frames:
        if await frm.query_selector("table[id*='itemPlaceholderContainer']"):
            parse_ctx = frm
            break
    else:
        raise RuntimeError("Couldn't locate the frame with itemPlaceholderContainer")
    
    selector = "table#itemPlaceholderContainer > tbody > tr[valign='top']"
    await parse_ctx.wait_for_selector(selector, timeout=30_000)
    rows = await parse_ctx.query_selector_all(selector)
    
    if row_index >= len(rows):
        raise RuntimeError(f"Row index {row_index} is out of range (only {len(rows)} rows available)")
    
    row = rows[row_index]
    case_number = basic_info["case_number"]
    
    # Create record with basic info we already have
    record: Record = {
        "case_number": basic_info["case_number"],
        "case_url": basic_info["case_url"],
        "file_date": basic_info["file_date"],
        "status": basic_info["status"],
        "type_desc": basic_info["type_desc"],
        "sub_type": basic_info["sub_type"],
        "style": basic_info["style"],
        "parties": [],
        "events": [],
    }
    
    _log(f"=== Processing details for case {case_number} ===")
    
    # Find expand buttons by their specific IDs
    right_td = await row.query_selector("td[align='right']")
    if right_td:
        # STEP 1: First handle parties for this record
        _log(f"STEP 1: Looking for parties data for case {case_number}")
        parties_btn = await right_td.query_selector("a[id^='img216']")
        if parties_btn:
            _log(f"Found parties button with ID: {await parties_btn.get_attribute('id')}")
            
            try:
                # Get a count of visible party tables before expanding
                visible_tables_before = await parse_ctx.query_selector_all("table:visible:has(th:has-text('Role'))")
                before_count = len(visible_tables_before)
                _log(f"Before expansion: found {before_count} visible party tables")
                
                # Click to expand parties section
                await parties_btn.click()
                await asyncio.sleep(1)  # Wait for expansion
                
                # Look for newly appeared tables
                visible_tables_after = await parse_ctx.query_selector_all("table:visible:has(th:has-text('Role'))")
                after_count = len(visible_tables_after)
                _log(f"After expansion: found {after_count} visible party tables")
                
                # Focus on the newly appeared table if found
                party_table = None
                if after_count > before_count:
                    # Use the most recently appeared table (likely the one that just expanded)
                    party_table = visible_tables_after[-1]
                    
                    # Check that we have a reasonable number of rows
                    party_rows = await party_table.query_selector_all("tr:not(:first-child)")
                    row_count = len(party_rows)
                    _log(f"Party table has {row_count} rows")
                    
                    # Safety check - if we have more than 20 rows, this is probably wrong
                    if row_count > 20:
                        _log("WARNING: More than 20 party rows - likely grabbed wrong table")
                        party_table = None
                    
                    # Process the parties if we found a valid table
                    if party_table and row_count > 0:
                        _log(f"Processing {row_count} parties for this record")
                        
                        for prow in party_rows:
                            cols = await prow.query_selector_all("td")
                            if len(cols) >= 3:
                                record["parties"].append({
                                    "role": (await cols[0].inner_text()).strip(),
                                    "name": (await cols[1].inner_text()).strip().split('\n')[0],
                                    "attorney": (await cols[2].inner_text()).strip(),
                                })
                        
                        _log(f"Extracted {len(record['parties'])} parties for this record")
                else:
                    _log("No new party table found after clicking expand button")
                
                # Close parties section
                await parties_btn.click()
                await asyncio.sleep(0.5)
            except Exception as e:
                _log(f"Error extracting parties: {e}")
        else:
            _log(f"No parties button found for case {case_number}")
        
        # STEP 2: Now handle events for the SAME record
        _log(f"STEP 2: Looking for events data for case {case_number}")
        
        # Try locating events button based on the structure in the screenshot
        # First, try to find the first td element that contains an <a> tag
        first_td = await row.query_selector("td:first-child")
        events_btn = None
        
        if first_td:
            # Look for an <a> tag inside this first td
            events_btn = await first_td.query_selector("a")
            if events_btn:
                _log(f"Found events button in first td with ID: {await events_btn.get_attribute('id')}")
        
        # If not found in first td, try the width="70" approach
        if not events_btn:
            td_width_70 = await row.query_selector("td[width='70']")
            if td_width_70:
                events_btn = await td_width_70.query_selector("a")
                if events_btn:
                    _log(f"Found events button in td[width='70'] with ID: {await events_btn.get_attribute('id')}")
        
        # If still not found, fall back to standard approach with img1
        if not events_btn:
            _log("Falling back to standard img1 selectors")
            events_btn = await right_td.query_selector("a[id='img1']")
            if not events_btn:
                events_btn = await right_td.query_selector("a[id^='img1']")
                
                # Make sure we didn't accidentally grab an img216* button (parties)
                if events_btn:
                    btn_id = await events_btn.get_attribute('id')
                    if btn_id and btn_id.startswith('img216'):
                        _log(f"Found button with ID {btn_id} but it's a parties button, not events")
                        events_btn = None
        
        # If still not found, try with glyphicon
        if not events_btn:
            _log("Trying to find events button using glyphicon class")
            events_btn = await right_td.query_selector("a:has(span.glyphicon-option-vertical)")
            
        if events_btn:
            btn_id = await events_btn.get_attribute('id')
            if btn_id and btn_id.startswith('img1'):
                _log(f"Found confirmed events button with ID: {btn_id}")
            else:
                _log(f"Found potential events button with ID: {btn_id}")
            
            try:
                # Look for events table - using a more specific approach
                # Get a count of visible event tables before expanding
                visible_tables_before = await parse_ctx.query_selector_all("table:visible:has(th:has-text('Date'))")
                before_count = len(visible_tables_before)
                _log(f"Before expansion: found {before_count} visible tables with Date header")
                
                # Click to expand events section
                await events_btn.click()
                await asyncio.sleep(1.5)  # Wait longer for expansion
                
                # Find newly visible table elements that weren't visible before
                await asyncio.sleep(1)  # Give tables time to appear
                visible_tables_after = await parse_ctx.query_selector_all("table:visible:has(th:has-text('Date'))")
                after_count = len(visible_tables_after)
                _log(f"After expansion: found {after_count} visible tables with Date header")
                
                # The relevant table should be the closest one to our button
                event_table = None
                
                if after_count > before_count:
                    # Focus only on the newly appeared table
                    _log("Found new event table after expansion")
                    
                    # We want the newly appeared table - should be the last one
                    event_table = visible_tables_after[-1]
                    
                    # Verify this is the right table - should have a limited number of rows
                    # for this specific case, not hundreds
                    event_rows = await event_table.query_selector_all("tr:not(:first-child)")
                    row_count = len(event_rows)
                    _log(f"Table has {row_count} event rows")
                    
                    # Safety check - if we have more than 20 rows, this is probably wrong
                    if row_count > 20:
                        _log("WARNING: More than 20 event rows - likely grabbed wrong table")
                        event_table = None
                    
                    # Process the events from the table
                    if event_table and row_count > 0:
                        _log(f"Processing {row_count} events for this record")
                        
                        # Extract only events for this record
                        for erow in event_rows:
                            cols = await erow.query_selector_all("td")
                            if len(cols) >= 3:
                                event_case = (await cols[0].inner_text()).strip() if len(cols) > 0 else ""
                                event_date = (await cols[1].inner_text()).strip() if len(cols) > 1 else ""
                                event_desc = (await cols[2].inner_text()).strip() if len(cols) > 2 else ""
                                event_comment = (await cols[3].inner_text()).strip() if len(cols) > 3 else ""
                                
                                # Only add if case matches or is empty (assuming it belongs to current case)
                                if not event_case or event_case == case_number:
                                    record["events"].append({
                                        "event_case": event_case or case_number,
                                        "event_date": event_date,
                                        "event_desc": event_desc,
                                        "event_comment": event_comment,
                                    })
                        
                        _log(f"Extracted {len(record['events'])} events for this record")
                else:
                    _log("No new event table found after clicking expand button")
                
                # Close events section
                await events_btn.click()
                await asyncio.sleep(0.5)
            except Exception as e:
                _log(f"Error extracting events: {e}")
        else:
            _log(f"No events button found for case {case_number}")

        # Try an alternative approach if events weren't found
        if not record["events"]:
            _log("Attempting alternative events button detection")
            try:
                # Try with onclick pattern from the screenshot
                events_btn = await right_td.query_selector("a[onclick*='javascriptxpand']")
                if events_btn:
                    _log(f"Found events button with alternative selector: {await events_btn.get_attribute('id')}")
                    
                    # Click to expand events section
                    await events_btn.click()
                    # Wait longer for the expansion
                    await asyncio.sleep(2)
                    
                    # Look for events table with broader selector
                    event_tables = await parse_ctx.query_selector_all("table")
                    for table in event_tables:
                        # Check if this looks like an events table by examining header row
                        header_row = await table.query_selector("tr:first-child")
                        if header_row:
                            header_text = await header_row.inner_text()
                            if "Date" in header_text and ("Description" in header_text or "Event" in header_text):
                                _log("Found events table with alternative approach")
                                # Get all event rows (skip header)
                                event_rows = await table.query_selector_all("tr:not(:first-child)")
                                for erow in event_rows:
                                    cols = await erow.query_selector_all("td")
                                    if len(cols) >= 3:
                                        event_case = (await cols[0].inner_text()).strip() if len(cols) > 0 else ""
                                        event_date = (await cols[1].inner_text()).strip() if len(cols) > 1 else ""
                                        event_desc = (await cols[2].inner_text()).strip() if len(cols) > 2 else ""
                                        event_comment = (await cols[3].inner_text()).strip() if len(cols) > 3 else ""
                                        
                                        record["events"].append({
                                            "event_case": event_case or case_number,
                                            "event_date": event_date,
                                            "event_desc": event_desc,
                                            "event_comment": event_comment,
                                        })
                                
                                _log(f"Extracted {len(record['events'])} events with alternative approach")
                                break
                    
                    # Close events section
                    await events_btn.click()
                    await asyncio.sleep(1)
            except Exception as e:
                _log(f"Error extracting events with alternative approach: {e}")
    
    # Check if this is a valid record with both parties and events
    is_complete = bool(record["parties"]) and bool(record["events"])
    if is_complete:
        _log(f"✅ COMPLETE RECORD: {case_number} with {len(record['parties'])} parties and {len(record['events'])} events")
    else:
        _log(f"⚠️ INCOMPLETE RECORD: {case_number} (has_parties={bool(record['parties'])}, has_events={bool(record['events'])})")
    
    return record

async def _parse_current_page(page: Page) -> List[Record]:
    """
    Optimized parsing that first identifies new cases, then only parses details for those.
    Limited to a maximum of MAX_NEW_RECORDS new records.
    """
    # Step 1: Get the basic case information for all records on the page
    basic_records = await _get_basic_case_info(page)
    _log(f"Found {len(basic_records)} total records on page")
    
    # Step 2: Check which records are new (not in the database)
    existing_ids = await get_existing_case_numbers()
    _log(f"Checking against {len(existing_ids)} existing case numbers in database")
    
    # Filter to only records that don't exist in the database, limited to MAX_NEW_RECORDS
    new_records_info = []
    skipped_existing = 0
    
    for record in basic_records:
        case_number = record["case_number"]
        if case_number in existing_ids:
            skipped_existing += 1
        else:
            new_records_info.append(record)
            # Stop once we reach the maximum number of new records to process
            if len(new_records_info) >= MAX_NEW_RECORDS:
                _log(f"Reached maximum of {MAX_NEW_RECORDS} new records to process - stopping scan")
                break
    
    _log(f"Skipped {skipped_existing} existing records")
    _log(f"Found {len(new_records_info)} new records to parse details for (limit: {MAX_NEW_RECORDS})")
    
    # Step 3: Only parse detailed information for new records
    complete_records = []
    for record_info in new_records_info:
        try:
            # Parse detailed party and event information
            detailed_record = await _parse_case_details(page, record_info["row_index"], record_info)
            
            # Only add complete records with both parties and events
            if detailed_record["parties"] and detailed_record["events"]:
                complete_records.append(detailed_record)
                _log(f"Added complete record: {detailed_record['case_number']} ({len(complete_records)}/{len(new_records_info)})")
            else:
                _log(f"Skipping incomplete record: {detailed_record['case_number']}")
                
        except Exception as e:
            _log(f"Error parsing details for {record_info['case_number']}: {e}")
    
    _log(f"Completed parsing {len(complete_records)} new records with complete details")
    return complete_records

async def get_existing_case_numbers():
    """
    Fetch all existing case numbers from the database.
    
    Returns a set of existing case numbers in the database or an empty set if the query fails.
    """
    existing_ids = set()
    
    # SQL options to try - these match the column naming options in upsert_records
    sql_options = [
        "SELECT case_no FROM foreclosure_filings",
        "SELECT case_number FROM foreclosure_filings",
        "SELECT id FROM foreclosure_filings"
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

async def upsert_records(sess: AsyncSession, records: list[dict]):
    """
    Insert or update a batch of records using a single execute call.
    
    :param sess:      your AsyncSession
    :param records:   a list of dicts matching INSERT_SQL parameters
    """
    if not records:
        return False
        
    # First check if the table exists
    try:
        # Check for foreclosure_filings table
        table_check = await sess.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'foreclosure_filings')"))
        table_exists = table_check.scalar()
        
        # Check for probate_filings table as an alternative
        probate_check = await sess.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'probate_filings')"))
        probate_exists = probate_check.scalar()
        
        if not table_exists and not probate_exists:
            _log("❌ Neither 'foreclosure_filings' nor 'probate_filings' table exists in the database")
            _log("⚠️ Create the appropriate table or update the script to use the correct table name")
            return False
            
        # Get table columns to help diagnose schema issues
        table_name = 'probate_filings' if probate_exists else 'foreclosure_filings'
        _log(f"Using table: {table_name}")
        
        columns_query = await sess.execute(text(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position
        """))
        columns = columns_query.fetchall()
        _log(f"Table columns: {', '.join(f'{col[0]} ({col[1]})' for col in columns)}")
    except Exception as e:
        _log(f"❌ Error checking table schema: {e}")

    # Try different SQL statements with different column names
    sql_options = [
        # Option 1: case_no column in foreclosure_filings
        """
        INSERT INTO foreclosure_filings
          (case_no,
           case_url,
           file_date,
           status,
           type_desc,
           sub_type,
           style,
           parties,
           events,
           scraped_at)
        VALUES
          (:case_number,
           :case_url,
           :file_date,
           :status,
           :type_desc,
           :sub_type,
           :style,
           CAST(:parties AS JSONB),
           CAST(:events  AS JSONB),
           NOW())
        ON CONFLICT (case_no) DO UPDATE
        SET
          case_url   = EXCLUDED.case_url,
          file_date  = EXCLUDED.file_date,
          status     = EXCLUDED.status,
          type_desc  = EXCLUDED.type_desc,
          sub_type   = EXCLUDED.sub_type,
          style      = EXCLUDED.style,
          parties    = EXCLUDED.parties,
          events     = EXCLUDED.events,
          scraped_at = NOW();
        """,
        
        # Option 2: case_number column in foreclosure_filings
        """
        INSERT INTO foreclosure_filings
          (case_number,
           case_url,
           file_date,
           status,
           type_desc,
           sub_type,
           style,
           parties,
           events,
           scraped_at)
        VALUES
          (:case_number,
           :case_url,
           :file_date,
           :status,
           :type_desc,
           :sub_type,
           :style,
           CAST(:parties AS JSONB),
           CAST(:events  AS JSONB),
           NOW())
        ON CONFLICT (case_number) DO UPDATE
        SET
          case_url   = EXCLUDED.case_url,
          file_date  = EXCLUDED.file_date,
          status     = EXCLUDED.status,
          type_desc  = EXCLUDED.type_desc,
          sub_type   = EXCLUDED.sub_type,
          style      = EXCLUDED.style,
          parties    = EXCLUDED.parties,
          events     = EXCLUDED.events,
          scraped_at = NOW();
        """,
        
        # Option 3: probate_filings table with case_no
        """
        INSERT INTO probate_filings
          (case_no,
           case_url,
           file_date,
           status,
           type_desc,
           sub_type,
           style,
           parties,
           events,
           scraped_at)
        VALUES
          (:case_number,
           :case_url,
           :file_date,
           :status,
           :type_desc,
           :sub_type,
           :style,
           CAST(:parties AS JSONB),
           CAST(:events  AS JSONB),
           NOW())
        ON CONFLICT (case_no) DO UPDATE
        SET
          case_url   = EXCLUDED.case_url,
          file_date  = EXCLUDED.file_date,
          status     = EXCLUDED.status,
          type_desc  = EXCLUDED.type_desc,
          sub_type   = EXCLUDED.sub_type,
          style      = EXCLUDED.style,
          parties    = EXCLUDED.parties,
          events     = EXCLUDED.events,
          scraped_at = NOW();
        """,
        
        # Option 4: Without JSONB casting (for non-PostgreSQL databases)
        """
        INSERT INTO foreclosure_filings
          (case_no,
           case_url,
           file_date,
           status,
           type_desc,
           sub_type,
           style,
           scraped_at)
        VALUES
          (:case_number,
           :case_url,
           :file_date,
           :status,
           :type_desc,
           :sub_type,
           :style,
           NOW())
        ON CONFLICT (case_no) DO UPDATE
        SET
          case_url   = EXCLUDED.case_url,
          file_date  = EXCLUDED.file_date,
          status     = EXCLUDED.status,
          type_desc  = EXCLUDED.type_desc,
          sub_type   = EXCLUDED.sub_type,
          style      = EXCLUDED.style,
          scraped_at = NOW();
        """
    ]

    async with AsyncSession(engine) as sess:
        for i, sql in enumerate(sql_options):
            try:
                # Extract a sample record to show what we're trying to insert
                if i == 0:
                    sample = records[0] if records else {}
                    _log(f"Sample record keys: {list(sample.keys())}")
                    
                await sess.execute(text(sql), records)
                await sess.commit()
                _log(f"✅ Successfully inserted/updated {len(records)} records using SQL option {i+1}")
                return True
            except Exception as e:
                await sess.rollback()
                # Get the full error message with details
                error_msg = str(e)
                if hasattr(e, '__cause__') and e.__cause__:
                    error_msg += f" | Cause: {str(e.__cause__)}"
                _log(f"⚠️ SQL option {i+1} failed: {error_msg}")
        
        # If we get here, all options failed
        _log("❌ All SQL options failed. Skipping database update.")
        _log("⚠️ Check that your database table structure matches one of the SQL statements")
        return False

async def _export_csv(df: pd.DataFrame) -> Path:
    # Create a simplified dataframe with only the basic record details
    # Remove the 'parties' and 'events' columns from the output
    export_df = df[['case_number', 'case_url', 'file_date', 'status', 'type_desc', 'sub_type', 'style']].copy()
    
    # Export to CSV
    fname = EXPORT_DIR / f"harris_probates_{datetime.now():%Y%m%d_%H%M%S}.csv"
    export_df.to_csv(fname, index=False)
    _log(f"CSV saved → {fname} (basic record details only, no party/event data)")
    
    return fname

MAX_ROWS_PER_BATCH = 500

def _push_sheet(df: pd.DataFrame):
    if not GOOGLE_CREDS_FILE or not Path(GOOGLE_CREDS_FILE).exists():
        _log("Google creds missing – skipping Sheet sync")
        return
    if not GSHEET_NAME or not PROBATE_TAB:
        _log("Sheet name/config missing – skipping Sheet sync")
        return
    
    # Use PROBATE_TAB instead of GSHEET_WORKSHEET
    worksheet_name = PROBATE_TAB
    
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

async def run():
    """Main function to run the scraper."""
    async with async_playwright() as pw:
        # Launch Chromium with your HEADLESS flag
        browser = await pw.chromium.launch(headless=HEADLESS)
        # Apply your custom user‑agent
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Now you'll actually see the browser if HEADLESS=False
        await page.goto(BASE_URL)
        await _maybe_accept(page)
        frm = await _find_frame(page)
        await _apply_filters(page, frm)
        
        # Parse all records from the current page
        # The _parse_current_page function now checks for existing records
        # and only parses details for new ones
        all_records = await _parse_current_page(page)
        
        # Close the browser
        await browser.close()
        
        # Summary of scraping results
        _log(f"🔍 Scraping complete: {len(all_records)} new records found with complete details")
        
        # Only update the database if we have new records
        db_success = False
        if all_records:
            async with AsyncSession(engine) as sess:
                db_success = await upsert_records(sess, all_records)
            if db_success:
                _log(f"✅ Upserted {len(all_records)} new records to database.")
            else:
                _log(f"⚠️ Database operations failed, but continuing with export")
        else:
            _log("⚠️ No new records to add to database.")
            return None
        
        # Export to CSV and push to Google Sheets
        df = pd.DataFrame(all_records)
        csv_path = None
        if not df.empty:
            try:
                # Export to CSV
                csv_path = await _export_csv(df)
                _log(f"✅ Exported {len(all_records)} new records to CSV: {csv_path}")
                
                # Push to Google Sheets (blocking - run it off the event loop)
                if GOOGLE_CREDS_FILE and GSHEET_NAME and PROBATE_TAB:
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