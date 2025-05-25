import asyncio
import os
import re
from datetime import datetime
from datetime import date
import time
import io
import itertools
import sys
from pathlib import Path
import pandas as pd
from typing import Optional, Tuple, Dict, Any
from urllib.parse import urljoin
from playwright.async_api import async_playwright, Page, Frame, Browser, BrowserContext
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
import pytesseract
import pdf2image
from PIL import Image
import tempfile
import argparse
import smtplib
from email.message import EmailMessage
from PIL import ImageFilter

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
# Create directory for document processing
PDF_DIR = (Path(__file__).parent / "pdfs").resolve()
PDF_DIR.mkdir(parents=True, exist_ok=True)
DB_URL = os.getenv("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL environment variable is required for database connection")

# Configure Tesseract path for Windows
TESSERACT_INSTALLED = False
try:
    # Common Tesseract installation locations on Windows
    _tesseract_candidates = [
        os.environ.get('TESSERACT_PATH'),
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Tesseract-OCR\tesseract.exe'
    ]
    
    # Filter out None values
    _tesseract_candidates = [p for p in _tesseract_candidates if p]
    
    # Try each path
    for candidate in _tesseract_candidates:
        if os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            # Verify installation works by checking version
            pytesseract.get_tesseract_version()
            print(f"Tesseract found at: {candidate}")
            TESSERACT_INSTALLED = True
            break
    
    if not TESSERACT_INSTALLED:
        print("WARNING: Tesseract OCR not found. Address extraction will be limited.")
except Exception as e:
    print(f"Error configuring Tesseract: {e}")
    print("WARNING: Tesseract OCR not found. Address extraction will be limited.")

# Configure Poppler path for Windows
POPPLER_INSTALLED = False
POPPLER_PATH = None
try:
    # Potential Poppler installation locations
    _poppler_candidates = [
        os.environ.get('POPPLER_PATH'),
        r'C:\Program Files\poppler\bin',
        r'C:\Program Files (x86)\poppler\bin',
        r'C:\poppler\bin'
    ]
    
    # Filter out None values and check existence
    _poppler_candidates = [p for p in _poppler_candidates if p]
    
    # Look for pdfinfo executable to verify Poppler installation
    for candidate in _poppler_candidates:
        pdfinfo_path = Path(candidate) / "pdfinfo.exe"
        if pdfinfo_path.exists():
            POPPLER_PATH = candidate
            POPPLER_INSTALLED = True
            print(f"Poppler found at: {candidate}")
            break
    
    # Try finding in PATH if not found in common locations
    if not POPPLER_INSTALLED:
        path_dirs = os.environ.get('PATH', '').split(os.pathsep)
        for path_dir in path_dirs:
            pdfinfo_path = Path(path_dir) / "pdfinfo.exe"
            if pdfinfo_path.exists():
                POPPLER_PATH = path_dir
                POPPLER_INSTALLED = True
                print(f"Poppler found in PATH at: {path_dir}")
                break
    
    if not POPPLER_INSTALLED:
        print("WARNING: Poppler not found. PDF processing will be limited.")
except Exception as e:
    print(f"Error configuring Poppler: {e}")
    print("WARNING: Poppler not found. PDF processing will be limited.")

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

# Address extraction helper functions
def extract_address_from_text(text: str, doc_id: str = None) -> dict:
    """
    Extract address patterns from OCR text by focusing only on the Legal Description section for now.
    Returns a dictionary with address and source information.
    """
    result = {
        "address": "",
        "source": "",
        "has_exhibit_a": False
    }

    # DEBUG: Save OCR text for inspection
    if doc_id:
        try:
            debug_dir = Path(__file__).parent / "ocr_debug"
            debug_dir.mkdir(exist_ok=True)
            debug_path = debug_dir / f"ocr_debug_{doc_id}.txt"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception as e:
            print(f"[DEBUG] Failed to save OCR debug text for {doc_id}: {e}")

    # Only use Legal Description for now
    legal_desc_match = re.search(r"Legal\s+Description:?:?\s*(.{10,300})", text, re.IGNORECASE)
    if legal_desc_match:
        candidate = legal_desc_match.group(1)
        candidate = candidate.split(". ")[0].split("\n")[0].strip()
        if len(candidate) > 10:
            result["address"] = candidate
            result["source"] = "Legal Description Section"
            _log(f"✅ Extracted after 'Legal Description': {candidate}")
            return result

    _log("⚠️ No valid property address found (Legal Description only)")
    return result

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text from PDF using OCR with pdf2image and Tesseract
    Improved: Higher DPI and image preprocessing for better OCR accuracy.
    """
    if not TESSERACT_INSTALLED:
        _log("⚠️ Tesseract not installed - skipping text extraction")
        return ""

    extracted_text = ""
    DPI = 400  # Higher DPI for better OCR
    
    # Use pdf2image with poppler if available
    if POPPLER_INSTALLED:
        try:
            _log(f"Using pdf2image with Poppler at {POPPLER_PATH} (DPI={DPI})")
            images = pdf2image.convert_from_path(file_path, poppler_path=POPPLER_PATH, dpi=DPI)
            for img in images:
                # Image preprocessing: binarization and sharpening
                img = img.convert('L')  # Grayscale
                img = img.point(lambda x: 0 if x < 180 else 255, '1')  # Binarize
                img = img.filter(ImageFilter.SHARPEN)
                # Apply OCR to each page
                page_text = pytesseract.image_to_string(img)
                extracted_text += page_text + "\n"
            return clean_extracted_text(extracted_text)
        except Exception as e:
            _log(f"⚠️ Error using pdf2image with Poppler: {e}")
            # Continue to fallback methods
    else:
        _log("Poppler not found, trying alternative methods")

    # Fallback method 3: Last resort - try with temporary files
    if file_path.lower().endswith('.pdf'):
        try:
            # Create a temporary directory to store converted images
            with tempfile.TemporaryDirectory() as tmp_dir:
                _log(f"Fallback 2: Using temporary directory for PDF processing in {tmp_dir}")
                
                # Try using poppler command-line tools directly
                try:
                    _log("Attempting to use pdftoppm or pdftocairo command-line tools")
                    if os.name == 'nt':  # Windows
                        pdf_prefix = os.path.join(tmp_dir, "page")
                        if POPPLER_PATH:
                            pdftoppm_path = os.path.join(POPPLER_PATH, "pdftoppm.exe")
                            if os.path.exists(pdftoppm_path):
                                os.system(f'"{pdftoppm_path}" -png "{file_path}" "{pdf_prefix}"')
                                success = True
                        else:
                            # Try using it from PATH
                            os.system(f'pdftoppm -png "{file_path}" "{pdf_prefix}"')
                    else:  # Linux/Mac
                        pdf_prefix = os.path.join(tmp_dir, "page")
                        os.system(f'pdftoppm -png "{file_path}" "{pdf_prefix}"')
                    
                    # Process any images we generated
                    for img_file in sorted(os.listdir(tmp_dir)):
                        if img_file.endswith('.png'):
                            img_path = os.path.join(tmp_dir, img_file)
                            img = Image.open(img_path)
                            page_text = pytesseract.image_to_string(img)
                            extracted_text += page_text + "\n"
                    
                    if extracted_text:
                        return clean_extracted_text(extracted_text)
                except Exception as e:
                    _log(f"⚠️ Command-line PDF tools error: {e}")
        except Exception as e:
            _log(f"⚠️ Last resort fallback failed: {e}")

    # If all methods failed, return empty string
    _log("⚠️ All PDF text extraction methods failed")
    return ""

def clean_extracted_text(text: str) -> str:
    """
    Clean up OCR text to improve address extraction
    """
    if not text:
        return ""
        
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    
    # Clean up common OCR errors in addresses
    text = text.replace('|', 'I')  # Vertical bar to I
    text = text.replace('l1', '11')  # Lowercase l + 1 to 11
    text = text.replace('O0', '00')  # Capital O + 0 to 00
    
    # Replace specific OCR errors in street names
    text = re.sub(r'(?i)Streel', 'Street', text)
    text = re.sub(r'(?i)Slreet', 'Street', text)
    text = re.sub(r'(?i)Streot', 'Street', text)
    text = re.sub(r'(?i)Avonue', 'Avenue', text)
    text = re.sub(r'(?i)Avenuo', 'Avenue', text)
    
    # Fix spacing around colons for property address labels
    text = re.sub(r'Property\s+Address\s*:?\s*', 'Property Address: ', text)
    
    # Preserve paragraph structure by adding newlines
    text = re.sub(r'(\.)(\s+[A-Z])', r'\1\n\2', text)
    
    return text

# Extract the paragraph containing 'Legal Description' or 'Property Description' from OCR text
def extract_description_paragraph(text: str) -> str:
    # Define start and end regex patterns
    start_patterns = [
        r"Property/Legal Description:",
        r"The property to be sold is described as follows:",
        r"Commonly known as:",
        r"Property",  # Standalone 'Property' (may be too broad, but included as requested)
        r"Property Address"
    ]
    end_patterns = [
        r"In accordance with TEX, PROP. CODE §51.0076 and the Deed of Trust",
        r"Instrument to be Foreclosed",
        r"MORTGAGE SERVICING INFORMATION:"
    ]
    lines = text.splitlines()
    collecting = False
    result_lines = []
    for line in lines:
        if not collecting:
            for pat in start_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    # Optionally, get everything after the label on this line
                    after_label = re.split(pat, line, flags=re.IGNORECASE)
                    if len(after_label) > 1:
                        result_lines.append(after_label[1].strip())
                    collecting = True
                    break
        else:
            for pat in end_patterns:
                if re.search(pat, line, re.IGNORECASE):
                    collecting = False
                    break
            if not collecting:
                break
            result_lines.append(line.strip())
    if result_lines:
        return ' '.join(result_lines).strip()
    return text.strip()

semaphore = asyncio.Semaphore(3)  # Limit to 3 concurrent downloads

async def limited_download(*args, **kwargs):
    async with semaphore:
        return await download_pdf(*args, **kwargs)

async def download_pdf(page: Page, doc_url: str, doc_id: str) -> str:
    SCREENSHOT_DIR = (Path(__file__).parent / "screenshots").resolve()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        browser = page.context.browser
        context = await browser.new_context(user_agent=USER_AGENT)
        doc_page = await context.new_page()

        # Simple navigation (no network capture)
        await doc_page.goto(doc_url, wait_until="domcontentloaded", timeout=60000)
        await doc_page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(4)

        # --- LOGIN LOGIC (triggered if login form is present) ---
        USERNAME = os.getenv("FRCL_USERNAME") or os.getenv("LP_USERNAME")
        PASSWORD = os.getenv("FRCL_PASSWORD") or os.getenv("LP_PASSWORD")
        if await doc_page.query_selector('input[id="ctl00_ContentPlaceHolder1_Login1_UserName"]'):
            await doc_page.fill('input[id="ctl00_ContentPlaceHolder1_Login1_UserName"]', USERNAME)
            await doc_page.fill('input[id="ctl00_ContentPlaceHolder1_Login1_Password"]', PASSWORD)
            await doc_page.check('input[id="ctl00_ContentPlaceHolder1_Login1_RememberMe"]')
            await doc_page.click('input[id="ctl00_ContentPlaceHolder1_Login1_LoginButton"]')
            await doc_page.wait_for_load_state("networkidle")

        # Wait for the document viewer to be visible before screenshotting
        try:
            await doc_page.wait_for_selector('embed, iframe, .pdfViewer, .some-pdf-class', timeout=3000)
        except Exception as e:
            _log(f'⚠️ PDF viewer not found for {doc_id}: {e}')

        await doc_page.set_viewport_size({"width": 1920, "height": 1080})
        await doc_page.evaluate("""
            () => {
                document.body.style.margin = '0';
                document.documentElement.style.margin = '0';
            }
        """)
        screenshot_path = SCREENSHOT_DIR / f"screenshot_{doc_id.replace('/', '_')}_{datetime.now():%Y%m%d_%H%M%S}.png"
        await doc_page.screenshot(path=str(screenshot_path), full_page=True)
        _log(f"🖼️ Saved screenshot for {doc_id} at {screenshot_path}")
        await doc_page.close()
        await context.close()

        try:
            from PIL import Image
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

# OCR a specific region from an image

def ocr_region_from_image(image_path: str, region: tuple[int, int, int, int], debug_path: str = None) -> str:
    """
    Crop the image to the specified region and run OCR on that region.
    :param image_path: Path to the image file.
    :param region: (left, upper, right, lower) pixel coordinates.
    :param debug_path: Optional path to save the cropped region for debugging.
    :return: OCR'd text from the region.
    """
    img = Image.open(image_path)
    cropped = img.crop(region)
    # Optional: preprocess (sharpen, binarize) for better OCR
    cropped = cropped.convert('L').filter(ImageFilter.SHARPEN)
    if debug_path:
        cropped.save(debug_path)
    text = pytesseract.image_to_string(cropped)
    return text

# Helper to screenshot the last page (simulate by adding a suffix to doc_id for filename uniqueness)
async def download_last_page_screenshot(page: Page, doc_url: str, doc_id: str) -> str:
    return await download_pdf(page, doc_url, f"{doc_id}_lastpage")

async def extract_address_from_document(doc_id: str, doc_url: str, page: Page) -> Tuple[str, str]:
    """
    Download and process document to extract address information
    Args:
        doc_id: Document ID
        doc_url: URL to the document
        page: Current Playwright page
    Returns:
        Tuple of (extracted_address, pdf_path)
    """
    try:
        _log(f"📄 Processing document {doc_id} for address extraction")
        # Download the PDF or screenshot
        file_path = await download_pdf(page, doc_url, doc_id)
        address = ""
        extracted_text = ""
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            if file_path and TESSERACT_INSTALLED:
                _log(f"Attempt {attempt}: OCR on file: {file_path}")
                if file_path.lower().endswith('.pdf'):
                    extracted_text = extract_text_from_pdf(file_path)
                elif file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    try:
                        from PIL import Image
                        img = Image.open(file_path)
                        left = 0
                        upper = 345
                        right = img.width
                        lower = 392
                        region = (left, upper, right, lower)
                        debug_crop_path = str(Path(file_path).with_name(f"crop_{Path(file_path).name}"))
                        extracted_text = ocr_region_from_image(file_path, region, debug_path=debug_crop_path)
                    except Exception as e:
                        _log(f"❌ Error running region-based OCR on screenshot: {e}")
                if extracted_text:
                    address = extract_description_paragraph(extracted_text)
                    if address:
                        _log(f"✅ Extracted text from region for {doc_id} (length: {len(address)})")
                        break
                    else:
                        _log(f"⏭️ Skipping record {doc_id} - no address found")
        if not address:
            _log(f"⚠️ No address found in document {doc_id} after {max_attempts} attempts")
        return address, file_path or ""
    except Exception as e:
        _log(f"❌ Error extracting address from document {doc_id}: {e}")
        return "", ""

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
            "case_number": doc_id,
            "case_url": doc_url,
            "file_date":    file_dt,
            "status": sale_dt,
            "type_desc": None,
            "sub_type": None,
            "style": None,
            "deceased_name": None,
            "parties": None,
            "events": None,
        })

    return records

# ─────────────────────────────────────────────────────────────────────────────
# EXPORT / SHEET
# ─────────────────────────────────────────────────────────────────────────────
async def upsert_records(sess: AsyncSession, records: list[dict]):
    """
    Insert or update a batch of records using a single execute call.
    
    :param sess:      your AsyncSession
    :param records:   a list of dicts matching foreclosure_filings parameters
    """
    if not records:
        return False

    # Convert all datetime.date/datetime.datetime to string (YYYY-MM-DD)
    def convert_dates(obj):
        if isinstance(obj, dict):
            return {k: convert_dates(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_dates(v) for v in obj]
        elif isinstance(obj, (datetime, date)):
            return obj.strftime('%Y-%m-%d')
        return obj

    records = [convert_dates(r) for r in records]

    sql = """
    INSERT INTO foreclosure_filings
    (case_number, case_url, file_date, status, type_desc, sub_type, style, deceased_name, parties, events, scraped_at)
    VALUES
    (:case_number, :case_url, :file_date, :status, :type_desc, :sub_type, :style, :deceased_name, :parties, :events, NOW())
    ON CONFLICT (case_number) DO UPDATE
    SET
        case_url = EXCLUDED.case_url,
        file_date = EXCLUDED.file_date,
        status = EXCLUDED.status,
        type_desc = EXCLUDED.type_desc,
        sub_type = EXCLUDED.sub_type,
        style = EXCLUDED.style,
        deceased_name = EXCLUDED.deceased_name,
        parties = EXCLUDED.parties,
        events = EXCLUDED.events,
        scraped_at = NOW();
    """

    try:
        await sess.execute(text(sql), records)
        await sess.commit()
        _log(f"✅ Successfully inserted/updated {len(records)} records using correct schema")
        return True
    except Exception as e:
        await sess.rollback()
        _log(f"❌ SQL failed: {e}")
        return False

async def _export_csv(df: pd.DataFrame) -> Path:
    # Remove 'case_url' column if present
    if 'case_url' in df.columns:
        df = df.drop(columns=['case_url'])
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
    Fetch all existing case_numbers from the database.
    
    Returns a set of existing case_numbers in the database or an empty set if the query fails.
    """
    existing_ids = set()
    sql = "SELECT case_number FROM foreclosure_filings"
    async with AsyncSession(engine) as sess:
        try:
            result = await sess.execute(text(sql))
            rows = result.fetchall()
            for row in rows:
                existing_ids.add(row[0])
            _log(f"✅ Successfully fetched {len(existing_ids)} existing case_numbers from database")
            return existing_ids
        except Exception as e:
            _log(f"⚠️ Failed to fetch existing case_numbers: {e}")
    _log("⚠️ Could not fetch existing case_numbers from database")
    return existing_ids

async def run_scraper(year: int | None = None, month: int | None = None, record_limit: int = None):
    """
    Run the foreclosure scraper
    
    Args:
        year: Year to scrape (defaults to current year)
        month: Month to scrape (defaults to latest available)
        record_limit: Maximum number of records to process (for testing)
    """
    # Track start time for performance measurement
    start_time = time.time()
    
    now = datetime.now()
    year = year or now.year
    month = month or None
    all_records = []
    
    # Track testing limit
    if record_limit:
        _log(f"⚠️ Testing mode: Limiting to {record_limit} records")
    
    # Get existing case_numbers from database to avoid duplicates
    _log("Fetching existing case_numbers from database...")
    try:
        existing_ids = await get_existing_document_ids()
        _log(f"Found {len(existing_ids)} existing case_numbers in database")
    except Exception as e:
        _log(f"❌ Error fetching existing case_numbers: {e}")
        _log("Continuing with empty set - may result in duplicate records")
        existing_ids = set()
    
    # Track statistics
    stats = {
        "new_records": 0,
        "skipped_records": 0,
        "failed_records": 0,
        "records_with_address": 0,
        "records_without_address": 0,
        "pdf_success": 0,
        "pdf_failed": 0,
        "screenshot_fallback": 0,
        "total_processed": 0,
        "download_errors": 0,
        "pages_scraped": 0,
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS)
            context = await browser.new_context(user_agent=USER_AGENT)
            page    = await context.new_page()
            try:
                await page.goto(BASE_URL, timeout=60000)
            except Exception as e:
                _log(f"❌ Error loading main page: {e}")
                _log("Trying again with a longer timeout...")
                await page.goto(BASE_URL, timeout=120000)

            # 1) Accept any pop-up or disclaimer
            await _maybe_accept(page)

            # 2) Find the form iframe and apply year/month filters
            try:
                frm = await _find_frame(page)
                await _apply_filters(frm, year, month)
            except Exception as e:
                _log(f"❌ Error setting up search filters: {e}")
                await browser.close()
                return None

            # 3) Jump to the last page using ellipsis and highest page number
            await page.wait_for_selector('tr.pagination-ys a')
            links = await page.query_selector_all('tr.pagination-ys a')
            ellipsis = None
            for link in links:
                txt = (await link.inner_text()).strip()
                if txt == '…':
                    ellipsis = link
                    break
            if ellipsis:
                await ellipsis.click()
                await page.wait_for_load_state("networkidle")
                links = await page.query_selector_all('tr.pagination-ys a')
            # Find the highest page number
            last_page_num = 1
            last_page_link = None
            for link in links:
                txt = (await link.inner_text()).strip()
                if txt.isdigit() and int(txt) > last_page_num:
                    last_page_num = int(txt)
                    last_page_link = link
            if last_page_link:
                await last_page_link.click()
                await page.wait_for_load_state("networkidle")
            _log(f"➡️ Jumped to last page: {last_page_num}")

            # 4) Process records from last page to first, bottom to top
            all_records = []
            page_num = last_page_num
            has_prev_page = True
            while has_prev_page and (not record_limit or len(all_records) < record_limit):
                _log(f"📄 Processing page {page_num} (reverse order)...")
                page_records = await _parse_current_page(page)
                if not page_records:
                    _log(f"⚠️ No records found on page {page_num}")
                    break
                for rec in reversed(page_records):
                    if record_limit and len(all_records) >= record_limit:
                        break
                    doc_id = rec["case_number"]
                    try:
                        address, file_path = await extract_address_from_document(
                            doc_id,
                            rec["case_url"],
                            page
                        )
                        rec["scraped_address"] = address
                        if address:
                            all_records.append(rec)
                            _log(f"✅ Processed record: {doc_id}")
                        else:
                            _log(f"⏭️ Skipping record {doc_id} - no address found")
                    except Exception as e:
                        _log(f"❌ Error processing record {doc_id}: {e}")
                # Find Previous button
                prev_button = None
                for frm in page.frames:
                    try:
                        selectors = [
                            "a:has-text('Previous')",
                            "a[aria-label='Previous']",
                            "input[id*='BtnPrev'][value='Previous']",
                            "input[id*='ContentPlaceHolder1_BtnPrev']",
                            "input[class*='btn-primary'][value='Previous']",
                            "input[type='submit'][value='Previous']"
                        ]
                        for selector in selectors:
                            prev_button = await frm.query_selector(selector)
                            if prev_button:
                                _log(f"✅ Found Previous button using selector: {selector}")
                                break
                        if prev_button:
                            break
                    except Exception as e:
                        _log(f"Error looking for Previous button in frame: {e}")
                if prev_button and (not record_limit or len(all_records) < record_limit):
                    _log("⏮️ Clicking Previous button to go to previous page...")
                    try:
                        await prev_button.click()
                        await page.wait_for_load_state("networkidle")
                        page_num -= 1
                    except Exception as e:
                        _log(f"❌ Error clicking Previous button: {e}")
                        has_prev_page = False
                else:
                    _log("⚠️ No Previous button found - reached first page or hit record limit")
                    has_prev_page = False
            await browser.close()

    except Exception as e:
        _log(f"❌ Unhandled error in scraper: {e}")
        return None

    # Calculate scraping duration
    duration = time.time() - start_time
    duration_str = f"{duration/60:.1f} minutes" if duration > 60 else f"{duration:.1f} seconds"

    # Detailed summary of scraping results
    _log("\n" + "="*80)
    _log(f"📊 SCRAPING SUMMARY ({duration_str})")
    _log("="*80)
    _log(f"📌 Pages scraped: {stats['pages_scraped']} of {page_num}")
    _log(f"📝 Total records processed: {stats['total_processed']}")
    _log(f"✅ Records with addresses: {stats['records_with_address']}")
    _log(f"❌ Records without addresses: {stats['records_without_address']}")
    _log(f"🆕 New records saved: {stats['new_records']}")
    _log(f"⏭️ Duplicate records skipped: {stats['skipped_records']}")
    _log(f"🚫 Failed records: {stats['failed_records']}")
    _log(f"📄 PDF download success: {stats['pdf_success']}")
    _log(f"🖼️ Screenshot fallback used: {stats['screenshot_fallback']}")
    _log(f"📉 PDF download failures: {stats['pdf_failed']}")
    if stats['total_processed'] > 0:
        _log(f"📊 Address extraction rate: {stats['records_with_address']/stats['total_processed']*100:.1f}%")
    _log("="*80)

    # 5) Persist to the database (only records with addresses)
    db_success = False
    if all_records:
        try:
            async with AsyncSession(engine) as sess:
                db_success = await upsert_records(sess, all_records)
            if db_success:
                _log(f"✅ Upserted {len(all_records)} new records to database.")
            else:
                _log(f"⚠️ Database operations failed, but continuing with export")
        except Exception as db_error:
            _log(f"❌ Database error: {db_error}")
            _log("Continuing with CSV export")
    else:
        _log("⚠️ No new records to add to database.")
        if stats["skipped_records"] > 0:
            _log(f"All {stats['skipped_records']} records found were already in the database.")
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
                try:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, lambda: _push_sheet(df))
                    _log("✅ Pushed data to Google Sheets")
                except Exception as sheets_error:
                    _log(f"❌ Error pushing to Google Sheets: {sheets_error}")

            # Send the CSV via email
            try:
                send_email_with_csv(
                    subject="New Foreclosure Records",
                    body="Attached are the new foreclosure records found in the latest scraping cycle.",
                    to_email=os.getenv("EMAIL_TO"),
                    csv_path=csv_path,
                    from_email=os.getenv("EMAIL_FROM"),
                    smtp_server=os.getenv("SMTP_SERVER"),
                    smtp_port=int(os.getenv("SMTP_PORT")),
                    smtp_user=os.getenv("EMAIL_USER"),
                    smtp_password=os.getenv("EMAIL_PASS"),
                )
                _log(f"✅ Sent new records to {os.getenv('EMAIL_TO')}")
            except Exception as e:
                _log(f"❌ Failed to send email: {e}")
        except Exception as e:
            _log(f"❌ Error exporting to CSV: {e}")
    else:
        _log("ℹ️ No CSV exported - no records with addresses to save")
    
    return csv_path

# ─────────────────────────────────────────────────────────────────────────────
# PERIODIC RUNNER
# ─────────────────────────────────────────────────────────────────────────────
async def run_periodically(year=None, month=None, record_limit=None, interval_minutes=60):
    while True:
        _log(f"⏰ Starting a new scraping cycle at {datetime.now()}")
        try:
            await run_scraper(year=year, month=month, record_limit=record_limit)
        except Exception as e:
            _log(f"❌ Error during scraping cycle: {e}")
        _log(f"⏳ Waiting {interval_minutes} minutes before next run...")
        await asyncio.sleep(interval_minutes * 60)

def send_email_with_csv(subject, body, to_email, csv_path, from_email, smtp_server, smtp_port, smtp_user, smtp_password):
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    msg.set_content(body)

    # Attach the CSV file
    with open(csv_path, 'rb') as f:
        file_data = f.read()
        file_name = os.path.basename(csv_path)
    msg.add_attachment(file_data, maintype='text', subtype='csv', filename=file_name)

    # Send the email
    with smtplib.SMTP_SSL(smtp_server, smtp_port) as smtp:
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Harris County Foreclosure Records Scraper")
    parser.add_argument("--year", type=int, help="Year to scrape (defaults to current year)")
    parser.add_argument("--month", type=int, help="Month to scrape (defaults to latest available)")
    parser.add_argument("--limit", type=int, help="Limit the number of records to process (for testing)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode (no browser UI)")
    args = parser.parse_args()
    
    if args.headless:
        HEADLESS = True
        _log("Running in headless mode")
    
    # Display welcome message
    _log("="*80)
    _log("Harris County Foreclosure Records Scraper")
    _log("="*80)
    _log(f"Tesseract OCR installed: {'Yes' if TESSERACT_INSTALLED else 'No'}")
    _log(f"Poppler installed: {'Yes' if POPPLER_INSTALLED else 'No'}")
    try:
        import fitz
        _log("PyMuPDF (fitz) installed: Yes")
    except ImportError:
        _log("PyMuPDF (fitz) installed: No")
    _log(f"Database URL: {DB_URL.split('@')[-1] if '@' in DB_URL else 'SQLite DB'}")
    _log(f"Output directory: {EXPORT_DIR}")
    _log("="*80)
    
    # Run periodically every 60 minutes
    try:
        asyncio.run(run_periodically(
            year=args.year,
            month=args.month,
            record_limit=args.limit,
            interval_minutes=60
        ))
    except KeyboardInterrupt:
        _log("\n⚠️ Scraper stopped by user")
    except Exception as e:
        _log(f"\n❌ Critical error: {e}")
