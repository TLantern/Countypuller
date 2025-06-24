import asyncio
from pathlib import Path
import json
from typing import Dict, Any
import random
import csv

from base_scrapers import SearchFormScraper
from config_schemas import CountyConfig, ScrapingResult
import pytesseract
from pdf2image import convert_from_bytes
import gc

from DallasDocumentOCR import extract_ocr_from_doc_urls

CONFIG_PATH = Path(__file__).parent / "configs" / "dallas_tx.json"

# Mapping of task file_type to search keyword text
FILE_TYPE_KEYWORDS = {
    "lis_pendens": "Lis Pendens",
    "notice_of_default": "Notice of Default",
    "bankruptcy": "Bankruptcy",
    "auction": "Auction",
}

# Delay range (milliseconds) used to mimic human browsing speed
HUMAN_MIN_DELAY_MS = 300
HUMAN_MAX_DELAY_MS = 700

# Helper for PDF OCR extraction
def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    print("[Dallas OCR][DEBUG] Starting PDF-to-image conversion...")
    images = convert_from_bytes(pdf_bytes, dpi=300)
    print(f"[Dallas OCR][DEBUG] Converted to {len(images)} image(s)")
    out = []
    for idx, img in enumerate(images):
        print(f"[Dallas OCR][DEBUG] OCR on page {idx+1}/{len(images)}...")
        try:
            text = pytesseract.image_to_string(img, lang="eng")
            print(f"[Dallas OCR][DEBUG] Extracted {len(text)} characters from page {idx+1}")
            out.append(text)
        except Exception as ocr_err:
            print(f"[Dallas OCR][ERROR] OCR failed on page {idx+1}: {ocr_err}")
        img.close()
    del images
    gc.collect()
    print("[Dallas OCR][DEBUG] OCR extraction complete.")
    return "\n".join(out)

class DallasScraper(SearchFormScraper):
    """Dallas County TX official records scraper implementation"""

    async def human_delay(self):
        """Pause for a short random interval to mimic human behaviour."""
        await self.page.wait_for_timeout(random.randint(HUMAN_MIN_DELAY_MS, HUMAN_MAX_DELAY_MS))

    async def fill_search_form(self, task_params: Dict[str, Any]):
        """Run a keyword and/or date-based search."""
        if "file_type" in task_params:
            file_type = task_params.get("file_type", "lis_pendens")
            keyword = FILE_TYPE_KEYWORDS.get(file_type.lower(), FILE_TYPE_KEYWORDS["lis_pendens"])
            search_input = self.page.locator('input[data-testid="searchInputBox"]')
            await search_input.wait_for(timeout=self.config.timeout * 1000)
            await search_input.fill(keyword)
            await self.human_delay()

        if "start_date" in task_params:
            date_input = self.page.locator('input[aria-label="Starting Recorded Date"]')
            await date_input.wait_for(timeout=self.config.timeout * 1000)
            await date_input.fill(task_params["start_date"])
            await self.human_delay()

    async def submit_search_form(self):
        """Submit the search by clicking the search icon button."""
        search_button = self.page.locator('button:has(img#basicsearch-icon)')
        await search_button.click()
        await self.human_delay()
        print("[Dallas][CONSOLE] Search button clicked.")

    async def wait_for_search_results(self):
        """Wait for results to appear."""
        selector = "div.search-results__results-wrap div.a11y-table table tbody tr"
        await self.page.wait_for_selector(selector, timeout=self.config.timeout * 1000)
        print("[Dallas][CONSOLE] Search results table detected.")

    async def extract_search_results(self) -> list[dict[str, Any]]:
        print("[Dallas][CONSOLE] Extraction started.")
        # Increase default timeout for slow loading pages
        self.page.set_default_timeout(3000)

        # ------------------------------------------------------------------
        # Click the 'Recorded Date' header twice to sort by most recent
        # ------------------------------------------------------------------
        recorded_date_header_selector = (
            "div.search-results__results-wrap div.a11y-table table thead th.col6.is-draggable.is-sortable"
        )
        print("[Dallas][CONSOLE] Waiting for Recorded Date header...")
        await self.page.wait_for_selector(recorded_date_header_selector, timeout=15000)
        for click_idx in range(2):
            try:
                await self.page.click(recorded_date_header_selector, timeout=5000)
                print(f"[Dallas][CONSOLE] Recorded Date header click {click_idx+1} succeeded.")
            except Exception as click_err:
                print(f"[Dallas][ERROR] Recorded Date header click {click_idx+1} failed: {click_err}")
            await self.page.wait_for_timeout(500)
        print("[Dallas][CONSOLE] Clicked Recorded Date header twice to sort by most recent.")
        # Wait for grid to finish reloading after sort
        await self.page.wait_for_load_state('networkidle')
        await self.page.wait_for_selector(
            "div.search-results__results-wrap div.a11y-table table tbody tr",
            timeout=60000
        )
        print("[Dallas][CONSOLE] Grid reloaded and rows are present after sort.")

        # ------------------------------------------------------------------
        # 1. Build an ordered, filtered list of header labels
        # ------------------------------------------------------------------
        header_selector_all = (
            "div.search-results__results-wrap div.a11y-table table thead th"
        )
        header_cells = self.page.locator(header_selector_all)
        header_count = await header_cells.count()
        print(f"[Dallas][DEBUG] Total <th> elements: {header_count}")

        # Physical index to logical header mapping (skip decorative cols 0-2)
        header_meta: list[tuple[int, str]] = []  # (physical_index, label)
        for idx in range(header_count):
            th = header_cells.nth(idx)
            # Attempt to grab deepest visible text (nested <p>/<span>/<div>)
            nested_locator = th.locator("p, span, div")
            label: str = ""
            if await nested_locator.count() > 0:
                label = (await nested_locator.first.inner_text()).strip()
            if not label:
                label = (await th.inner_text()).strip()

            if idx <= 2 or label == "":
                # Decorative/blank header → ignore
                continue
            header_meta.append((idx, label))
        logical_headers = [lbl for _, lbl in header_meta]
        print(f"[Dallas][DEBUG] Logical headers: {logical_headers}")

        # ------------------------------------------------------------------
        # 2. Ensure rows are present (the grid sometimes reloads after sort)
        # ------------------------------------------------------------------
        body_row_selector = (
            "div.search-results__results-wrap div.a11y-table table tbody tr"
        )
        await self.page.wait_for_selector(body_row_selector, timeout=60000)
        all_rows = self.page.locator(body_row_selector)
        row_count = await all_rows.count()
        print(f"[Dallas][CONSOLE] Found {row_count} rows in results table.")

        row_limit = min(row_count, 25)  # Safety cap
        print(f"[Dallas][CONSOLE] Parsing first {row_limit} rows (max capped at 25).")

        # ------------------------------------------------------------------
        # 3. Iterate rows & map cells to headers
        # ------------------------------------------------------------------
        def _clean(value: str | None) -> str | None:
            if value is None:
                return None
            trimmed = value.strip()
            if trimmed == "--/--/--":
                return None
            return trimmed

        results: list[dict[str, Any]] = []
        for i in range(row_limit):
            # Because navigating away will stale the locator list, fetch rows fresh each iteration
            all_rows = self.page.locator(body_row_selector)
            row = all_rows.nth(i)
            cells = row.locator("td")
            cell_count = await cells.count()
            mapped_row: dict[str, Any] = {}

            for (physical_idx, header_label) in header_meta:
                raw_text = await cells.nth(physical_idx).text_content() if physical_idx < cell_count else ""
                mapped_row[header_label] = _clean(raw_text)

            # ------------------------------------------------------------------
            # NEW ➜ delay before interacting with the row (human-like pause)
            # ------------------------------------------------------------------
            await self.human_delay()

            # ------------------------------------------------------------------
            # NEW ➜ click row to capture document URL
            # ------------------------------------------------------------------
            doc_url: str | None = None
            try:
                async with self.page.expect_navigation(wait_until="load", timeout=15000):
                    await row.click()
                doc_url = self.page.url
                mapped_row["DOC_URL"] = doc_url
                print(f"[Dallas][DEBUG] Row {i+1}: captured DOC_URL → {doc_url}")
            except Exception as nav_err:
                print(f"[Dallas][ERROR] Row {i+1}: failed to open document page – {nav_err}")
            finally:
                # Always attempt to return to the results grid so next iteration works
                try:
                    await self.page.go_back()
                    await self.page.wait_for_selector(body_row_selector, timeout=60000)
                    await self.human_delay()
                except Exception as back_err:
                    print(f"[Dallas][ERROR] Failed to navigate back to results page – {back_err}")
                    # Break out of loop; we can still return what we have so far
                    results.append(mapped_row)
                    break

            results.append(mapped_row)
            await self.human_delay()

        print(
            f"[Dallas][CONSOLE] Extraction finished. Total records processed: {len(results)}."
        )
        return results


def load_dallas_config() -> CountyConfig:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config_data = json.load(f)
    return CountyConfig(**config_data)

async def main(task_params=None):
    config = load_dallas_config()
    scraper = DallasScraper(config)
    if task_params is None:
        task_params = {
            "file_type": "lis_pendens",
            "start_date": "01/06/2025"
        }
    result: list[dict[str, Any]] = await scraper.scrape(task_params)
    print(result)

    # Save to CSV
    if result and isinstance(result, list):
        csv_path = "dallas_results.csv"
        headers = list(result[0].keys())
        with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(result)
        print(f"[Dallas][CONSOLE] Results saved to {csv_path}")

    # ──────────────────────────────────────────────────────────
    # Trigger OCR extraction on collected document URLs
    # ──────────────────────────────────────────────────────────
    doc_urls = [rec.get("DOC_URL") for rec in result if rec.get("DOC_URL")]
    if doc_urls:
        print(f"[Dallas][CONSOLE] Starting OCR on {len(doc_urls)} document URLs…")
        ocr_map = extract_ocr_from_doc_urls(doc_urls)
        print("[Dallas][CONSOLE] OCR extraction complete.")
        # Merge OCR text back into result records
        for rec in result:
            doc_url = rec.get("DOC_URL")
            if doc_url and doc_url in ocr_map:
                rec["OCR_TEXT"] = ocr_map[doc_url]

        # Optionally write combined CSV
        combined_csv = "dallas_results_with_ocr.csv"
        headers = list(result[0].keys())
        with open(combined_csv, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(result)
        print(f"[Dallas][CONSOLE] Combined results + OCR saved to {combined_csv}")

if __name__ == "__main__":
    asyncio.run(main())
