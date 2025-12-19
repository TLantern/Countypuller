"""
HCAD Playwright Scraper - Browser automation for HCAD property lookup
Uses Playwright to automate real browser interactions with HCAD website
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import async_playwright, Page, Browser
import re

logger = logging.getLogger(__name__)

# Screenshot directory setup
SCREENSHOT_DIR = Path(__file__).parent / "results"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

class HCADPlaywrightScraper:
    """Scraper for HCAD using Playwright browser automation."""
    
    def __init__(self, headless: bool = True, timeout: int = 60000):
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    async def __aenter__(self):
        """Async context manager entry - starts browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        
        # Set reasonable timeouts
        self.page.set_default_timeout(self.timeout)
        
        # Set user agent to appear more like a real browser
        await self.page.set_extra_http_headers({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - closes browser."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
    
    async def search_advanced(self, owner_name: str, legal_description: str = "", tax_year: str = "2025") -> Dict[str, Any]:
        """
        Search HCAD using advanced search with both owner name and legal description.
        
        Args:
            owner_name: Full owner name (e.g., "SMITH JOHN")
            legal_description: Legal description (e.g., "LT 4 BLK 2 GROVES SEC 22")
            tax_year: Tax year to search (default: "2025")
            
        Returns:
            Dict with property information or error details
        """
        if not self.page:
            raise ValueError("Browser not initialized - use as async context manager")
        
        logger.info(f"🔍 HCAD Advanced search - Owner: '{owner_name}', Legal: '{legal_description}'")
        
        try:
            # Step 1: Navigate to HCAD advanced search page
            search_url = "https://public.hcad.org/records/Real.asp?search=advanced"
            logger.debug(f"📍 Navigating to: {search_url}")
            
            await self.page.goto(search_url)
            await self.page.wait_for_load_state('networkidle')
            
            # Step 2: Fill in the advanced search form
            logger.debug("📝 Filling advanced search form...")
            
            # Select tax year with timeout
            try:
                await asyncio.wait_for(
                    self.page.select_option('select[name="TaxYear"]', tax_year),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout selecting tax year - taking screenshot")
                await self._take_debug_screenshot("timeout_selecting_tax_year", owner_name)
                raise
            
            # Enter owner name
            if owner_name:
                try:
                    await asyncio.wait_for(
                        self.page.fill('input[name="name"]', owner_name),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Timeout filling owner name - taking screenshot")
                    await self._take_debug_screenshot("timeout_filling_owner_name", owner_name)
                    raise
            
            # Enter legal description
            if legal_description:
                try:
                    await asyncio.wait_for(
                        self.page.fill('input[name="legal"]', legal_description),
                        timeout=10.0
                    )
                except asyncio.TimeoutError:
                    logger.warning("⚠️ Timeout filling legal description - taking screenshot")
                    await self._take_debug_screenshot("timeout_filling_legal_desc", owner_name)
                    raise
            
            # Take screenshot BEFORE any submission - showing completed form
            logger.debug("📸 Taking screenshot of completed form before submission")
            try:
                await self._take_debug_screenshot("form_completed_before_submit", owner_name)
            except:
                pass  # Ignore screenshot errors
            
            # Step 3: Submit the form
            logger.debug("🚀 Submitting advanced search form...")
            
            try:
                await asyncio.wait_for(
                    self.page.click('input[type="submit"][value="Search"]'),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout clicking search button - taking screenshot")
                await self._take_debug_screenshot("timeout_clicking_search", owner_name)
                raise
            
            # Wait for results page to load with timeout
            try:
                await asyncio.wait_for(
                    self.page.wait_for_load_state('networkidle'),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout waiting for results page - taking screenshot")
                await self._take_debug_screenshot("timeout_waiting_for_results", owner_name)
                raise
            
            # Step 4: Check for results
            current_url = self.page.url
            logger.debug(f"📄 Results page URL: {current_url}")
            
            # Check if we got redirected to error page
            if 'error' in current_url.lower():
                logger.warning("⚠️ HCAD redirected to error page")
                try:
                    await self._take_debug_screenshot("error_page_redirect", owner_name)
                except:
                    pass  # Ignore screenshot errors
                return self._build_empty_result(owner_name, "HCAD error page redirect")
            
            # Get page content
            content = await self.page.content()
            
            # Take screenshot of results before parsing (to capture table structure)
            try:
                await self._take_debug_screenshot("results_table_before_parsing", owner_name)
            except:
                pass  # Ignore screenshot errors
            
            # Step 5: Parse results
            return await self._parse_results_page(content, owner_name)
            
        except asyncio.TimeoutError:
            logger.error(f"❌ HCAD Advanced search timed out for {owner_name}")
            try:
                await self._take_debug_screenshot("search_timeout", owner_name)
            except:
                pass  # Ignore screenshot errors if browser is closing
            return self._build_empty_result(owner_name, "Search timed out")
        except Exception as e:
            logger.error(f"❌ HCAD Advanced search failed: {e}")
            try:
                await self._take_debug_screenshot("search_error", owner_name)
            except:
                pass  # Ignore screenshot errors if browser is closing
            return self._build_empty_result(owner_name, str(e))

    async def search_by_owner_name(self, owner_name: str, tax_year: str = "2025") -> Dict[str, Any]:
        """
        Search HCAD by owner name using browser automation.
        
        Args:
            owner_name: Full owner name (e.g., "SMITH JOHN")
            tax_year: Tax year to search (default: "2025")
            
        Returns:
            Dict with property information or error details
        """
        if not self.page:
            raise ValueError("Browser not initialized - use as async context manager")
        
        logger.info(f"🔍 HCAD Playwright search for owner: '{owner_name}'")
        
        try:
            # Step 1: Navigate to HCAD owner name search page
            search_url = "https://public.hcad.org/records/Real.asp?search=name"
            logger.debug(f"📍 Navigating to: {search_url}")
            
            await self.page.goto(search_url)
            await self.page.wait_for_load_state('networkidle')
            
            # Step 2: Fill in the search form
            logger.debug("📝 Filling search form...")
            
            # Select tax year with timeout
            try:
                await asyncio.wait_for(
                    self.page.select_option('select[name="TaxYear"]', tax_year),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout selecting tax year - taking screenshot")
                await self._take_debug_screenshot("timeout_selecting_tax_year", owner_name)
                raise
            
            # Enter owner name with timeout
            try:
                await asyncio.wait_for(
                    self.page.fill('input[name="searchval"]', owner_name),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout filling search value - taking screenshot")
                await self._take_debug_screenshot("timeout_filling_search_value", owner_name)
                raise
            
            # Take screenshot BEFORE any submission - showing completed form
            logger.debug("📸 Taking screenshot of completed form before submission")
            try:
                await self._take_debug_screenshot("form_completed_before_submit", owner_name)
            except:
                pass  # Ignore screenshot errors
            
            # Step 3: Submit the form
            logger.debug("🚀 Submitting search form...")
            
            try:
                await asyncio.wait_for(
                    self.page.click('input[type="submit"][value="Search"]'),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout clicking search button - taking screenshot")
                await self._take_debug_screenshot("timeout_clicking_search", owner_name)
                raise
            
            # Wait for results page to load with timeout
            try:
                await asyncio.wait_for(
                    self.page.wait_for_load_state('networkidle'),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.warning("⚠️ Timeout waiting for results page - taking screenshot")
                await self._take_debug_screenshot("timeout_waiting_for_results", owner_name)
                raise
            
            # Step 4: Check for results
            current_url = self.page.url
            logger.debug(f"📄 Results page URL: {current_url}")
            
            # Check if we got redirected to error page
            if 'error' in current_url.lower():
                logger.warning("⚠️ HCAD redirected to error page")
                try:
                    await self._take_debug_screenshot("error_page_redirect", owner_name)
                except:
                    pass  # Ignore screenshot errors
                return self._build_empty_result(owner_name, "HCAD error page redirect")
            
            # Get page content
            content = await self.page.content()
            
            # Take screenshot of results before parsing (to capture table structure)
            try:
                await self._take_debug_screenshot("results_table_before_parsing", owner_name)
            except:
                pass  # Ignore screenshot errors
            
            # Step 5: Parse results
            return await self._parse_results_page(content, owner_name)
            
        except asyncio.TimeoutError:
            logger.error(f"❌ HCAD owner search timed out for {owner_name}")
            try:
                await self._take_debug_screenshot("owner_search_timeout", owner_name)
            except:
                pass  # Ignore screenshot errors if browser is closing
            return self._build_empty_result(owner_name, "Search timed out")
        except Exception as e:
            logger.error(f"❌ HCAD owner search failed: {e}")
            try:
                await self._take_debug_screenshot("owner_search_error", owner_name)
            except:
                pass  # Ignore screenshot errors if browser is closing
            return self._build_empty_result(owner_name, str(e))
    
    async def _parse_results_page(self, html: str, owner_name: str) -> Dict[str, Any]:
        """Parse the HCAD results page for property information."""
        html_lower = html.lower()
        
        # Check for no results message
        if any(pattern in html_lower for pattern in [
            'no records found', 'no match', 'not found', 'no results'
        ]):
            logger.info("🔍 No HCAD records found for this owner")
            try:
                await self._take_debug_screenshot("no_results_found", owner_name)
            except:
                pass  # Ignore screenshot errors
            return self._build_empty_result(owner_name, "No records found")
        
        # Check for results table
        if '<table' in html_lower and ('account' in html_lower or 'property' in html_lower):
            logger.info("✅ Found HCAD results - parsing property data")
            return self._extract_property_data(html, owner_name)
        
        # Check for multiple results selection page
        if 'select' in html_lower and ('record' in html_lower or 'account' in html_lower):
            logger.info("📋 Multiple records found - extracting first result")
            return await self._handle_multiple_results(html, owner_name)
        
        # Unknown page format
        logger.warning(f"⚠️ Unknown HCAD page format. Content length: {len(html)}")
        try:
            await self._take_debug_screenshot("unknown_page_format", owner_name)
        except:
            pass  # Ignore screenshot errors
        return self._build_empty_result(owner_name, "Unknown page format")
    
    def _extract_property_data(self, html: str, owner_name: str) -> Dict[str, Any]:
        """Extract property data from HCAD results table."""
        result = self._build_empty_result(owner_name)
        
        # Extract property address
        address_patterns = [
            r'Property Address[:\s]*</td>\s*<td[^>]*>\s*([^<]+)',
            r'Address[:\s]*</td>\s*<td[^>]*>\s*([^<]+)',
            r'Location[:\s]*</td>\s*<td[^>]*>\s*([^<]+)',
            r'(\d+\s+[A-Z\s]+(?:ST|DR|AVE|RD|LN|CT|PL|WAY|BLVD|CIRCLE|DRIVE))',
        ]
        
        for pattern in address_patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                address = match.group(1).strip()
                if address and len(address) > 5:  # Basic validation
                    result['address'] = address
                    logger.info(f"📍 Extracted address: {address}")
                    break
        
        # Extract account/parcel number
        account_patterns = [
            r'Account(?:\s+Number)?[:\s]*</td>\s*<td[^>]*>\s*([0-9-]+)',
            r'Parcel[:\s]*</td>\s*<td[^>]*>\s*([0-9-]+)',
            r'Account[:\s]*([0-9-]+)',
        ]
        
        for pattern in account_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                parcel_id = match.group(1).strip()
                if parcel_id:
                    result['parcel_id'] = parcel_id
                    logger.info(f"🏷️ Extracted parcel ID: {parcel_id}")
                    break
        
        # Extract market value
        value_patterns = [
            r'Market\s+Value[:\s]*</td>\s*<td[^>]*>\s*\$?([\d,]+)',
            r'Total\s+Market\s+Value[:\s]*</td>\s*<td[^>]*>\s*\$?([\d,]+)',
        ]
        
        for pattern in value_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                market_value = match.group(1).replace(',', '')
                if market_value.isdigit():
                    result['market_value'] = int(market_value)
                    logger.info(f"💰 Extracted market value: ${market_value}")
                    break
        
        # Extract square footage
        sqft_patterns = [
            r'Living\s+Area[:\s]*</td>\s*<td[^>]*>\s*([\d,]+)',
            r'Square\s+Feet[:\s]*</td>\s*<td[^>]*>\s*([\d,]+)',
            r'(?:Improvement|Building)\s*S\.?F\.?[:\s]*</td>\s*<td[^>]*>\s*([\d,]+)',
        ]
        
        for pattern in sqft_patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                sqft = match.group(1).replace(',', '')
                if sqft.isdigit():
                    result['impr_sqft'] = int(sqft)
                    logger.info(f"📐 Extracted square footage: {sqft} sqft")
                    break
        
        # Mark as successful if we got any data
        if result['address'] or result['parcel_id']:
            result['error'] = None
            logger.info("✅ Successfully extracted property data")
        else:
            result['error'] = "No property data found in results"
            logger.warning("⚠️ No property data could be extracted")
        
        return result
    
    async def _handle_multiple_results(self, html: str, owner_name: str) -> Dict[str, Any]:
        """Handle page with multiple property records."""
        # For now, try to extract the first result from the list
        # In a full implementation, you might want to click on the first result
        # and navigate to its detail page
        
        logger.info("📋 Multiple results detected - extracting available data")
        
        # Try to extract basic info from the selection page
        result = self._build_empty_result(owner_name)
        
        # Look for the first account number link
        account_match = re.search(r'href="[^"]*account=([0-9-]+)[^"]*"', html, re.IGNORECASE)
        if account_match:
            result['parcel_id'] = account_match.group(1)
            logger.info(f"🏷️ Found account from multiple results: {result['parcel_id']}")
        
        # Could implement clicking on first result to get full details
        # For now, return what we can extract
        result['error'] = "Multiple results - partial data only"
        return result
    
    def _build_empty_result(self, owner_name: str, error: str = None) -> Dict[str, Any]:
        """Build empty result structure."""
        return {
            'address': None,
            'parcel_id': None,
            'error': error,
            'owner_name': owner_name,
            'impr_sqft': None,
            'market_value': None,
            'appraised_value': None,
            'source': 'HCAD_Playwright'
        }

    async def _take_debug_screenshot(self, scenario: str, owner_name: str) -> None:
        """Take a debug screenshot for troubleshooting"""
        try:
            # Check if page and browser are still valid
            if not self.page or not self.browser:
                logger.debug(f"⚠️ Cannot take screenshot - browser/page not available")
                return
            
            # Check if page is closed
            if self.page.is_closed():
                logger.debug(f"⚠️ Cannot take screenshot - page is closed")
                return
            
            # Clean owner name for filename
            clean_name = "".join(c for c in owner_name if c.isalnum() or c in (' ', '-', '_')).strip()
            clean_name = clean_name.replace(' ', '_')[:20]  # Limit length
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            screenshot_path = SCREENSHOT_DIR / f"hcad_{scenario}_{clean_name}_{timestamp}.png"
            
            # Take screenshot with a short timeout
            await asyncio.wait_for(
                self.page.screenshot(path=str(screenshot_path), full_page=True),
                timeout=5.0  # 5 second timeout for screenshot
            )
            logger.info(f"🖼️ Debug screenshot saved: {screenshot_path}")
            
        except (asyncio.TimeoutError, Exception) as e:
            logger.debug(f"⚠️ Could not take debug screenshot: {e}")


# Main interface function
async def hcad_playwright_lookup(owner_name: str, legal_description: str = "", headless: bool = True) -> Dict[str, Any]:
    """
    Perform HCAD property lookup using Playwright browser automation.
    
    Args:
        owner_name: Full owner name to search for
        legal_description: Legal description (e.g., "LT 4 BLK 2 GROVES SEC 22")
        headless: Whether to run browser in headless mode
        
    Returns:
        Dictionary with property information
    """
    async with HCADPlaywrightScraper(headless=headless) as scraper:
        # Use advanced search if we have legal description, otherwise use owner name only
        if legal_description and legal_description.strip():
            return await scraper.search_advanced(owner_name, legal_description)
        else:
            return await scraper.search_by_owner_name(owner_name)


# Example usage
async def main():
    """Example usage of the HCAD Playwright scraper."""
    test_names = [
        "SMITH JOHN",
        "ITANI TARIQ ZIAD",
        "JONES MARY"
    ]
    
    for name in test_names:
        print(f"\n🔍 Testing HCAD lookup for: {name}")
        result = await hcad_playwright_lookup(name, headless=True)
        print(f"📊 Result: {result}")


if __name__ == "__main__":
    asyncio.run(main()) 