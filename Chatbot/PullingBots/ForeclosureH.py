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
INSERT_SQL = """
INSERT INTO foreclosure_filings
(document_id, document_url, sale_date, file_date, pages, scraped_at)
VALUES (:document_id, :document_url, :sale_date, :file_date, :pages, NOW())
ON CONFLICT (document_id) DO UPDATE
SET sale_date  = EXCLUDED.sale_date,
    file_date  = EXCLUDED.file_date,
    pages      = EXCLUDED.pages,
    scraped_at = NOW();
"""


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
    Select the File-Date radio, choose the given year, force-select April (value=4), then click Search.
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

    # 3) Month dropdown — force April (value=4)
    month_dd = "select[id*='ddlMonth']"
    await frm.wait_for_selector(month_dd, timeout=30_000)
    await frm.select_option(month_dd, value="5")
    _log("➡️ Month set → May (5)")
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
        return

    async with AsyncSession(engine) as sess:
        try:
            # Bulk‐execute your INSERT/UPSERT against all records
            await sess.execute(text(INSERT_SQL), records)
            await sess.commit()
        except Exception as e:
            # Roll back on error, log it, then bubble up
            await sess.rollback()
            _log(f"❌ upsert_records failed: {e}")
            raise

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

    _log(f"✅ Sheet updated → {GSHEET_NAME}/{GSHEET_WORKSHEET}")

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
async def run_scraper(year: int | None = None, month: int | None = None):
    current_page = 1
    now = datetime.now()
    year = year or now.year
    month = month or None

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(BASE_URL)

        # 1) Accept any pop-up or disclaimer
        await _maybe_accept(page)

        # 2) Find the form iframe and apply year/month filters
        frm = await _find_frame(page)
        await _apply_filters(frm, year, month)

        # 3) Scrape the first page (optional—if you need it)
        all_records = await _parse_current_page(page)

        # 4) Click the “…” to reveal the final page numbers (if it exists)
        ellipsis = page.locator("tr.pagination-ys a:has-text('…')")
        if await ellipsis.count():
            _log("➡️ Jumping to last page group via ellipsis (…) link")
            await ellipsis.first.click()
            await page.wait_for_load_state("networkidle")

        # 5) Find and click the highest-numbered page link
        links = page.locator("tr.pagination-ys a")
        count = await links.count()
        last_page = None
        for i in range(count - 1, -1, -1):
            txt = (await links.nth(i).inner_text()).strip()
            if txt.isdigit():
                last_page = int(txt)
                break
        if last_page is None:
            raise RuntimeError("Could not find any numeric page links")

        _log(f"➡️ Navigating to final page #{last_page}")
        await page.click(f"tr.pagination-ys a:has-text('{last_page}')")
        await page.wait_for_load_state("networkidle")

        # 6) Scrape records on the final page
        final_records = await _parse_current_page(page)
        _log(f"🔍 Found {len(final_records)} records on page {last_page}")
        all_records.extend(final_records)

        await browser.close()

    # 7) Persist to the database
    if not all_records:
        _log("❌ No records scraped—check selectors.")
        return

    async with AsyncSession(engine) as sess:
        await upsert_records(sess, all_records)
    _log(f"✅ Upserted {len(all_records)} records to database.")

# 8) Export to CSV push to Google Sheets (optional)
    df = pd.DataFrame(all_records)
    csv_path = None
    try: 
        #Export to CSV
        csv_path = await _export_csv(df)
        # Push to Google Sheets (blocking - run it off the event loop)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: _push_sheet(df))
    except Exception as e:
        _log(f"❌ Error exporting to CSV or pushing to Google Sheets: {e}")
    return csv_path
if __name__ == "__main__":
    asyncio.run(run_scraper())
