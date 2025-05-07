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
async def _parse_current_page(page: Page) -> List[Record]:
    # 1) find the real parsing context
    for frm in page.frames:
        if await frm.query_selector("table[id*='itemPlaceholderContainer']"):
            parse_ctx = frm
            break
    else:
        raise RuntimeError("Couldn’t locate the frame with itemPlaceholderContainer")
    
    selector = "table#itemPlaceholderContainer > tbody > tr[valign='top']"

    await parse_ctx.wait_for_selector(selector, timeout=30_000)
    rows = await parse_ctx.query_selector_all(selector)
    _log(f"➡️ Found {len(rows)} result rows using selector: {selector!r}")
    records = []
    for row in rows:
        # ─── top‐level metadata ────────────────────────────────────────────────
        case_link = await row.query_selector("td:nth-child(2) a.doclinks")
        case_cell = await row.query_selector("td:nth-child(2)")
        case_number = (await case_cell.inner_text()).strip() if case_cell else ""
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

        record: Record = {
            "case_number": case_number,
            "case_url":    case_url,
            "file_date":   file_date,
            "status":      status,
            "type_desc":   type_desc,
            "sub_type":    sub_type,
            "style":       style,
            "parties":     [],
            "events":      [],
        }

        # ─── expand & scrape subtables ─────────────────────────────────────────
        expand_btn = await row.query_selector("td:first-child a.doclinks")
    if expand_btn:
        await expand_btn.click()

        # 2) parties
        await parse_ctx.wait_for_selector(
            "table#gridView > tbody > tr[align='center']", timeout=10_000
        )
        party_rows = await parse_ctx.query_selector_all(
            "table#gridView > tbody > tr[align='center']"
        )
        for prow in party_rows:
            cols = await prow.query_selector_all("td")
            record["parties"].append({
                "role":     (await cols[1].inner_text()).strip(),
                "name":     (await cols[2]
                               .evaluate("el => el.innerText.split('\\n')[0]")
                             ).strip(),
                "attorney": (await cols[3].inner_text()).strip(),
            })

        # 3) events
        await parse_ctx.wait_for_selector(
            "table#gridViewEvents tbody tr:not(:first-child)", timeout=10_000
        )
        ev_rows = await parse_ctx.query_selector_all(
            "table#gridViewEvents tbody tr:not(:first-child)"
        )
        for ev in ev_rows:
            cols = await ev.query_selector_all("td")
            record["events"].append({
                "event_case":    (await cols[0].inner_text()).strip(),
                "event_date":    (await cols[1].inner_text()).strip(),
                "event_desc":    (await cols[2].inner_text()).strip(),
                "event_comment": (await cols[3].inner_text()).strip(),
            })

        # 4) collapse back
        await expand_btn.click()
        await asyncio.sleep(0.05)

    records.append(record)
    _log(f"➡️ {len(records)} records parsed")
    return records
# EXPORT / SHEET

async def upsert_records(sess: AsyncSession, records: list[dict]):
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
"""

async def _export_csv(df: pd.DataFrame) -> Path:
    fname = EXPORT_DIR / f"harris_probates_{datetime.now():%Y%m%d_%H%M%S}.csv"
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


async def run():
    async with async_playwright() as pw:
        # Launch Chromium with your HEADLESS flag
        browser = await pw.chromium.launch(headless=HEADLESS)
        # Apply your custom user‑agent
        context = await browser.new_context(user_agent=USER_AGENT)
        page = await context.new_page()
        
        # Now you’ll actually see the browser if HEADLESS=False
        await page.goto(BASE_URL)
        await _maybe_accept(page)
        frm = await _find_frame(page)
        await _apply_filters(page,frm)
        all_records = await _parse_current_page(page)
        async with AsyncSession(engine) as sess:
          await upsert_records(sess, all_records)
        _log(f"✅ Upserted {len(all_records)} records to database.")
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
        
    await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
