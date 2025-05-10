import asyncio
import os
from datetime import datetime
import time
import itertools
from pathlib import Path
import pandas as pd
from typing import Optional
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Frame
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

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL   = "https://www.cclerk.hctx.net/applications/websearch/FRCL_R.aspx"
EXPORT_DIR = Path("data"); EXPORT_DIR.mkdir(exist_ok=True)
HEADLESS   = False
YEAR       = datetime.now().year
MONTH: Optional[int] = None  # None ⇒ auto‑pick latest month
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
)

# Google Sheets (optional) ----------------------------------------------------
load_dotenv()
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS")
GSHEET_NAME       = os.getenv("GSHEET_NAME")
GSHEET_WORKSHEET  = os.getenv("GSHEET_TAB")
EXPORT_DIR = (Path(__file__).parent / "data").resolve()
EXPORT_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required for database connection")

# ─────────────────────────────────────────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────────────────────────────────────────
engine = create_async_engine(DB_URL, echo=False)

# ─────────────────────────────────────────────────────────────────────────────
# LOG + SAFE WRAPPER
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str):
    print(f"[{datetime.now():%H:%M:%S}] {msg}")

async def _safe(desc: str, coro):
    try:
        return await coro
    except Exception as e:
        _log(f"❌ {desc} → {e}")
        raise

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
            if await frm.query_selector("select[id*='ddlMonth']"):
                _log("Form frame located")
                return frm
        except Exception:
            pass
    try:
        if await page.query_selector("select[id*='ddlMonth']"):
            _log("Form found in main page")
            return page.main_frame
    except Exception:
        pass
    raise RuntimeError("Search form frame not found.")

async def _apply_filters(frm: Frame, year: int | str, month: Optional[int] = None) -> Frame:
    """
    Select the File-Date radio, choose the given year, and select month if provided.
    """
    # 1) File-Date radio
    await frm.wait_for_selector("input[type=radio][value='FileDate']", timeout=30_000)
    await frm.check("input[type=radio][value='FileDate']")
    _log("➡️ File-Date radio set")

    # 2) Year dropdown
    year_dd = "select[id*='ddlYear']"
    await frm.wait_for_selector(year_dd, timeout=30_000)
    await frm.select_option(year_dd, value=str(year))
    _log(f"➡️ Year set → {year}")
    await frm.wait_for_load_state("networkidle")

    # 3) Month dropdown
    month_dd = "select[id*='ddlMonth']"
    await frm.wait_for_selector(month_dd, timeout=30_000)
    
    # If month is specified, use it; otherwise get available options and select the most recent
    if month is not None:
        month_value = str(month)
        _log(f"➡️ Month set → {month}")
    else:
        # Get available options to find the most recent month
        month_options = await frm.eval_on_selector_all(month_dd + " option", """
            (options) => options
                .filter(o => o.value && !isNaN(parseInt(o.value)))
                .map(o => ({value: o.value, text: o.text}))
        """)
        
        if not month_options:
            # If no options found, default to May (5)
            month_value = "5"
            _log("➡️ No month options found, defaulting to May (5)")
        else:
            # Sort options by value in descending order to get most recent month
            month_options.sort(key=lambda o: int(o["value"]), reverse=True)
            month_value = month_options[0]["value"]
            month_name = month_options[0]["text"]
            _log(f"➡️ Month set → {month_name} ({month_value})")
    
    await frm.select_option(month_dd, value=month_value)
    await frm.wait_for_load_state("networkidle")

    # 4) Click Search
    await frm.wait_for_selector("input[id*='btnSearch']", timeout=30_000)
    await frm.click("input[id*='btnSearch']")
    _log("➡️ Search clicked")
    await frm.wait_for_load_state("networkidle")

    return frm


# Row parsing + (optional) single‑page scrape --------------------------------
async def _parse_current_page(page: Page) -> list[dict]:
    frm = page.frame(name="main") or page
    await frm.wait_for_selector("tbody tr")
    rows = await frm.query_selector_all("tbody tr")


    records = []
    for row in rows:
        link = await row.query_selector("a.doclinks")
        if not link:
            continue

        doc_id  = (await link.inner_text()).strip()
        href    = await link.get_attribute("href")
        doc_url = urljoin(BASE_URL, href)

        cell1 = await row.query_selector("td:nth-child(3) span")
        raw_sale = (await cell1.inner_text()).strip() if cell1 else None
        cell2 = await row.query_selector("td:nth-child(4) span")
        raw_file = (await cell2.inner_text()).strip() if cell2 else None
        cell3 = await row.query_selector("td:nth-child(5) span")
        raw_pages = (await cell3.inner_text()).strip() if cell3 else None

        # === PARSE ===
        # 1) Dates: convert MM/DD/YYYY → datetime.date
        def parse_date(s: str):
            try:
                return datetime.strptime(s, "%m/%d/%Y").date()
            except Exception:
                return None

        sale_dt = parse_date(raw_sale) if raw_sale is not None else None
        file_dt = parse_date(raw_file) if raw_file is not None else None

        # 2) Pages: convert to int
        try:
            pages = int(raw_pages) if raw_pages is not None else None
        except ValueError:
            pages = None

        records.append({
            "document_id": doc_id,
            "document_url": doc_url,
            "sale_date":    sale_dt,
            "file_date":    file_dt,
            "pages":        pages,
        })

    return records

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT / SHEET
# ─────────────────────────────────────────────────────────────────────────────
async def upsert_records(sess: AsyncSession, records: list[dict]):
    """
    Insert or update a batch of records using a single execute call.
    
    :param sess:      your AsyncSession
    :param records:   a list of dicts matching INSERT_SQL parameters
    """
    if not records:
        return False

    # Try different SQL statements with different column names
    sql_options = [
        # Option 1: original column names
        """
        INSERT INTO foreclosure_filings
        (document_id, document_url, sale_date, file_date, pages, scraped_at)
        VALUES (:document_id, :document_url, :sale_date, :file_date, :pages, NOW())
        ON CONFLICT (document_id) DO UPDATE
        SET sale_date = EXCLUDED.sale_date,
            file_date = EXCLUDED.file_date,
            pages = EXCLUDED.pages,
            scraped_at = NOW();
        """,
        
        # Option 2: alternative column names
        """
        INSERT INTO foreclosure_filings
        (doc_id, doc_url, sale_date, file_date, page_count, scraped_at)
        VALUES (:document_id, :document_url, :sale_date, :file_date, :pages, NOW())
        ON CONFLICT (doc_id) DO UPDATE
        SET sale_date = EXCLUDED.sale_date,
            file_date = EXCLUDED.file_date,
            page_count = EXCLUDED.page_count,
            scraped_at = NOW();
        """,
        
        # Option 3: id column instead of document_id
        """
        INSERT INTO foreclosure_filings
        (id, document_url, sale_date, file_date, pages, scraped_at)
        VALUES (:document_id, :document_url, :sale_date, :file_date, :pages, NOW())
        ON CONFLICT (id) DO UPDATE
        SET sale_date = EXCLUDED.sale_date,
            file_date = EXCLUDED.file_date,
            pages = EXCLUDED.pages,
            scraped_at = NOW();
        """
    ]

    async with AsyncSession(engine) as sess:
        for i, sql in enumerate(sql_options):
            try:
                await sess.execute(text(sql), records)
                await sess.commit()
                _log(f"✅ Successfully inserted/updated {len(records)} records using SQL option {i+1}")
                return True
            except Exception as e:
                await sess.rollback()
                _log(f"⚠️ SQL option {i+1} failed: {e}")
        
        # If we get here, all options failed
        _log("❌ All SQL options failed. Skipping database update.")
        return False

async def _export_csv(df: pd.DataFrame) -> Path:
    fname = EXPORT_DIR / f"harris_foreclosures_{datetime.now():%Y%m%d_%H%M%S}.csv"
    df.to_csv(fname, index=False)
    _log(f"CSV saved → {fname}")
    return fname

MAX_ROWS_PER_BATCH = 500

def _push_sheet(df: pd.DataFrame):
    if not GOOGLE_CREDS_FILE or not Path(GOOGLE_CREDS_FILE).exists():
        _log("Google creds missing – skipping Sheet sync")
        return
    if not GSHEET_NAME or not GSHEET_WORKSHEET:
        _log("Sheet name/config missing – skipping Sheet sync")
        return
    
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
        ws = sh.worksheet(GSHEET_WORKSHEET)
        _log(f"✔ Found existing worksheet '{GSHEET_WORKSHEET}' – clearing contents.")
        ws.clear()
    except WorksheetNotFound:
        _log(f"➕ Creating worksheet '{GSHEET_WORKSHEET}'.")
        ws = sh.add_worksheet(
            title=GSHEET_WORKSHEET,
            rows=len(df) + 10,
            cols=len(df.columns) + 5,
        )

    # 3) Prepare data for batch updates with headers
    header = df.columns.tolist()
    data_rows = df.values.tolist()
    
    # First, update the header row separately
    ws.update('A1', [header])
    _log("➡️ Updated header row")
    
    # Then update the data in batches
    if data_rows:
        # Calculate how many batches we need
        total_rows = len(data_rows)
        num_batches = (total_rows + MAX_ROWS_PER_BATCH - 1) // MAX_ROWS_PER_BATCH
        
        for batch_num in range(num_batches):
            start_idx = batch_num * MAX_ROWS_PER_BATCH
            end_idx = min(start_idx + MAX_ROWS_PER_BATCH, total_rows)
            batch_data = data_rows[start_idx:end_idx]
            
            # Calculate the starting row in the sheet (row 2 is the first data row after header)
            start_row = start_idx + 2
            
            # Retry logic for API errors
            tries, delay = 0, 1
            while True:
                try:
                    # Update the range starting from A{start_row}
                    ws.update(f'A{start_row}', batch_data)
                    _log(f"➡️ Updated batch {batch_num+1}/{num_batches} ({len(batch_data)} rows)")
                    break
                except APIError as e:
                    code = int(e.response.status_code) if e.response else None
                    if code in (429,) or (code is not None and 500 <= code < 600 and tries < 5):
                        _log(f"⚠️ APIError {code}, retrying in {delay}s…")
                        time.sleep(delay)
                        tries += 1
                        delay *= 2
                    else:
                        _log(f"❌ APIError {code}: {str(e)}")
                        raise

    _log(f"✅ Sheet updated → {GSHEET_NAME}/{GSHEET_WORKSHEET}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
async def get_existing_document_ids():
    """
    Fetch all existing document IDs from the database.
    
    Returns a set of existing document IDs in the database or an empty set if the query fails.
    """
    existing_ids = set()
    
    # SQL options to try - these match the column naming options in upsert_records
    sql_options = [
        "SELECT document_id FROM foreclosure_filings",
        "SELECT doc_id FROM foreclosure_filings",
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
                
                _log(f"✅ Successfully fetched {len(existing_ids)} existing document IDs using SQL option {i+1}")
                return existing_ids
            except Exception as e:
                _log(f"⚠️ Failed to fetch existing IDs with SQL option {i+1}: {e}")
    
    _log("⚠️ Could not fetch existing document IDs from any database column")
    return existing_ids

async def run_scraper(year: int | None = None, month: int | None = None):
    now = datetime.now()
    year = year or now.year
    month = month or None
    all_records = []
    
    # Get existing document IDs from database to avoid duplicates
    _log("Fetching existing document IDs from database...")
    existing_ids = await get_existing_document_ids()
    _log(f"Found {len(existing_ids)} existing document IDs in database")
    
    # Track new and skipped records
    new_records_count = 0
    skipped_records_count = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        page = await browser.new_page(user_agent=USER_AGENT)
        await page.goto(BASE_URL)

        # 1) Accept any pop-up or disclaimer
        await _maybe_accept(page)

        # 2) Find the form iframe and apply year/month filters
        frm = await _find_frame(page)
        await _apply_filters(frm, year, month)

        # 3) Find the total number of pages
        links = page.locator("tr.pagination-ys a")
        count = await links.count()
        last_page = 1
        
        # Try to find the highest page number
        ellipsis = page.locator("tr.pagination-ys a:has-text('…')")
        if await ellipsis.count():
            _log("➡️ Jumping to last page group via ellipsis (…) link")
            await ellipsis.first.click()
            await page.wait_for_load_state("networkidle")
            
            links = page.locator("tr.pagination-ys a")
            count = await links.count()
            for i in range(count - 1, -1, -1):
                txt = (await links.nth(i).inner_text()).strip()
                if txt.isdigit():
                    last_page = int(txt)
                    break
        else:
            # No ellipsis, find the highest page number from available links
            for i in range(count):
                txt = (await links.nth(i).inner_text()).strip()
                if txt.isdigit() and int(txt) > last_page:
                    last_page = int(txt)
        
        _log(f"Found {last_page} pages to scrape")
        
        # Go back to first page if we jumped to last
        if await page.locator("tr.pagination-ys a:has-text('1')").count():
            await page.click("tr.pagination-ys a:has-text('1')")
            await page.wait_for_load_state("networkidle")
        
        # 4) Iterate through all pages and scrape
        current_page = 1
        while current_page <= last_page:
            _log(f"🔍 Scraping page {current_page} of {last_page}")
            page_records = await _parse_current_page(page)
            
            # Filter out records that already exist in the database
            new_page_records = []
            for record in page_records:
                doc_id = record["document_id"]
                if doc_id in existing_ids:
                    skipped_records_count += 1
                else:
                    new_page_records.append(record)
                    # Add to existing_ids to avoid duplicates within this scraping session
                    existing_ids.add(doc_id)
                    new_records_count += 1
            
            _log(f"Found {len(page_records)} records on page {current_page}, {len(new_page_records)} new, {len(page_records) - len(new_page_records)} skipped")
            all_records.extend(new_page_records)
            
            # Go to next page if not on the last page
            if current_page < last_page:
                # Try clicking the "Next" button first
                next_button = page.locator("tr.pagination-ys a:has-text('Next')")
                if await next_button.count():
                    await next_button.click()
                else:
                    # Otherwise click the next page number
                    next_page = current_page + 1
                    await page.click(f"tr.pagination-ys a:has-text('{next_page}')")
                
                await page.wait_for_load_state("networkidle")
                current_page += 1
            else:
                break

        await browser.close()

    # Summary of scraping results
    _log(f"🔍 Scraping complete: {new_records_count} new records found, {skipped_records_count} duplicates skipped")

    # 5) Persist to the database
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
        if skipped_records_count > 0:
            _log(f"All {skipped_records_count} records found were already in the database.")
        else:
            _log("No records were found at all - check selectors.")
        return None

    # 6) Export to CSV and push to Google Sheets (optional)
    df = pd.DataFrame(all_records)
    csv_path = None
    if not df.empty:
        try: 
            # Export to CSV
            csv_path = await _export_csv(df)
            _log(f"✅ Exported {len(all_records)} new records to CSV: {csv_path}")
            
            # Push to Google Sheets (blocking - run it off the event loop)
            if GOOGLE_CREDS_FILE and GSHEET_NAME and GSHEET_WORKSHEET:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: _push_sheet(df))
                _log("✅ Pushed data to Google Sheets")
        except Exception as e:
            _log(f"❌ Error exporting to CSV or pushing to Google Sheets: {e}")
    else:
        _log("ℹ️ No CSV exported - no new records to save")
    
    return csv_path

if __name__ == "__main__":
    asyncio.run(run_scraper())
