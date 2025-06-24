from __future__ import annotations

"""Dallas County – document image OCR extractor

This module provides a self-contained, **headless Selenium** workflow that:

1. Navigates to an existing Dallas County search-results page (URL supplied by caller).
2. Processes **up to 25** result rows.
3. For each row it:
   a. Clicks the table-row (`<tr>`) to open the document viewer.
   b. Locates the document image via the CSS selector
      ``section.css-17ke37a div.css-1wwt4ep section.css-1oqbvm2 svg g.css-m91xk0 image.css-1tazvte``.
   c. Downloads the referenced PNG **in memory (no disk writes)**.
   d. Runs Tesseract OCR on the bytes and stores the extracted text.
4. Returns a mapping of *document page URL* → *OCR text*.

All heavy resources (Selenium driver, PIL image objects) are cleaned up promptly to
minimise memory usage.
"""

from io import BytesIO
import gc
import logging
from typing import Dict, List, Tuple

import pytesseract
import requests
from PIL import Image
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ----------------------------------------------------------------------------
# Selenium / Browser helpers
# ----------------------------------------------------------------------------

def _create_headless_driver() -> webdriver.Chrome:
    """Instantiate a **headless** Chrome driver with sane defaults.

    Returns
    -------
    webdriver.Chrome
        Ready-to-use driver instance. Caller is responsible for `quit()`."""

    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # New headless mode (Chrome ≥ 109)
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--log-level=3")  # Suppress noisy logs

    # Performance hints – prevent images/fonts from loading except the target PNGs
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.fonts": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)

    try:
        driver = webdriver.Chrome(options=chrome_options)
    except WebDriverException as err:
        logging.error("Failed to start headless Chrome: %s", err)
        raise

    driver.set_page_load_timeout(60)
    return driver


# ----------------------------------------------------------------------------
# OCR helper – keeps everything in memory
# ----------------------------------------------------------------------------

def _ocr_image_bytes(image_bytes: bytes) -> str:
    """Run Tesseract OCR on the given image bytes and return the extracted text."""
    with Image.open(BytesIO(image_bytes)) as img:
        text = pytesseract.image_to_string(img, lang="eng")
    # Explicit GC to reclaim memory occupied by PIL image
    gc.collect()
    return text


# ----------------------------------------------------------------------------
# Core workflow helpers
# ----------------------------------------------------------------------------

def _get_result_rows(driver: webdriver.Chrome) -> List:
    """Return a list of `<tr>` elements representing search results."""
    selector = (
        "div.search-results__results-wrap div.a11y-table table tbody tr"
    )
    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
    except TimeoutException:
        logging.error("Timed out waiting for search-result rows to appear.")
        return []
    return driver.find_elements(By.CSS_SELECTOR, selector)


def _get_png_bytes(img_url: str, timeout: int = 30) -> bytes | None:
    """Download the PNG pointed to by *img_url* and return raw bytes."""
    try:
        resp = requests.get(img_url, timeout=timeout)
        resp.raise_for_status()
        return resp.content
    except Exception as err:
        logging.warning("Failed to fetch image %s – %s", img_url, err)
        return None


def _process_single_record(driver: webdriver.Chrome) -> Tuple[str, str] | None:
    """Extract OCR text from the currently displayed document page.

    Assumes the driver has *already navigated* to the document view.

    Returns
    -------
    tuple
        (current_page_url, extracted_text) on success; ``None`` on failure."""

    img_selector = (
        "section.css-17ke37a div.css-1wwt4ep section.css-1oqbvm2 svg "
        "g.css-m91xk0 image.css-1tazvte"
    )

    try:
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, img_selector))
        )
        img_el = driver.find_element(By.CSS_SELECTOR, img_selector)
        img_url = img_el.get_attribute("xlink:href")
        if not img_url:
            raise ValueError("image element missing xlink:href attribute")
    except (TimeoutException, NoSuchElementException, ValueError) as err:
        logging.warning("Could not locate image on %s – %s", driver.current_url, err)
        return None

    png_bytes = _get_png_bytes(img_url)
    if png_bytes is None:
        return None

    text = _ocr_image_bytes(png_bytes)
    return driver.current_url, text


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def extract_ocr_from_dallas_results(search_results_url: str, max_records: int = 25) -> Dict[str, str]:
    """High-level convenience wrapper for end-to-end extraction.

    Parameters
    ----------
    search_results_url : str
        URL pointing to a *loaded* Dallas County search-results page. The function
        will not submit search forms; it simply visits the page, iterates over
        the first *max_records* rows and performs OCR on each corresponding
        document image.
    max_records : int, optional
        Safety cap on how many rows to process (default **25**).

    Returns
    -------
    dict
        Mapping of *document page URL* → *extracted OCR text*.
    """

    driver = _create_headless_driver()
    ocr_map: Dict[str, str] = {}

    try:
        logging.info("Navigating to search-results page → %s", search_results_url)
        driver.get(search_results_url)

        rows = _get_result_rows(driver)
        if not rows:
            logging.warning("No result rows found – aborting.")
            return {}

        logging.info("Found %d rows – processing up to %d", len(rows), max_records)
        rows = rows[: max_records]

        original_window = driver.current_window_handle

        for idx, row in enumerate(rows, start=1):
            try:
                logging.info("[%d/%d] Clicking row", idx, len(rows))
                row.click()
            except WebDriverException as click_err:
                logging.warning("Row click failed: %s", click_err)
                continue

            # Handle potential new window/tab
            WebDriverWait(driver, 10).until(lambda d: len(d.window_handles) >= 1)
            new_handles = [h for h in driver.window_handles if h != original_window]
            if new_handles:
                driver.switch_to.window(new_handles[0])

            # Process the document page
            result = _process_single_record(driver)
            if result:
                page_url, text = result
                ocr_map[page_url] = text
                logging.info("OCR extracted – %d characters.", len(text))
            else:
                logging.info("OCR extraction failed for current record.")

            # Close the extra tab if one was opened, then return to results page
            if new_handles:
                driver.close()
                driver.switch_to.window(original_window)
            else:
                driver.back()

            # After navigation back, rows become stale; re-fetch them
            rows = _get_result_rows(driver)
            rows = rows[: max_records]

    finally:
        driver.quit()
        gc.collect()

    return ocr_map


# ----------------------------------------------------------------------------
# Convenience – process explicit list of document URLs
# ----------------------------------------------------------------------------

def extract_ocr_from_doc_urls(doc_urls: list[str]) -> Dict[str, str]:
    """Extract OCR text from each *doc_url* in *doc_urls*.

    This variant skips the search-results page and loads each document page
    directly. Useful when another scraper (e.g., Dallas.py) has already
    collected the individual document links.
    """

    driver = _create_headless_driver()
    out: Dict[str, str] = {}

    try:
        for idx, url in enumerate(doc_urls, start=1):
            logging.info("[%d/%d] Navigating to %s", idx, len(doc_urls), url)
            try:
                driver.get(url)
            except Exception as nav_err:
                logging.warning("Navigation failed: %s", nav_err)
                continue

            result = _process_single_record(driver)
            if result:
                page_url, text = result
                out[page_url] = text
                logging.info("OCR extracted – %d characters.", len(text))
            else:
                logging.info("OCR extraction failed on %s", url)
    finally:
        driver.quit()
        gc.collect()

    return out


# ----------------------------------------------------------------------------
# CLI entry-point for ad-hoc usage / debugging
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        sys.exit("Usage: python DallasDocumentOCR.py <search_results_url> [max_records]")

    url_arg = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 25

    extracted = extract_ocr_from_dallas_results(url_arg, max_records=limit)
    print(json.dumps(extracted, indent=2, ensure_ascii=False)) 