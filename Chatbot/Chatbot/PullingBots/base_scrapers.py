"""
Base Scraper Classes
===================

This module provides base scraper implementations for the three main types
of county websites: static HTML, search-based, and authenticated portals.
"""

import asyncio
import os
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
from pathlib import Path
import logging
import base64
from io import BytesIO

# Browser automation
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup

# OCR capabilities
try:
    import pytesseract
    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    logging.warning("OCR libraries not available. Install with: pip install pytesseract pillow")

# Local imports
from config_schemas import (
    CountyConfig, ScrapingResult, ScrapingRecord, FieldMapping, 
    SelectorConfig, ScraperType, PaginationType, AuthType
)

# Setup logging
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# BASE SCRAPER ABSTRACT CLASS
# ─────────────────────────────────────────────────────────────────────────────

class BaseScraper(ABC):
    """Abstract base class for all scrapers"""
    
    def __init__(self, config: CountyConfig):
        self.config = config
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_browser()
    
    async def start_browser(self):
        """Initialize browser and page"""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(
            headless=self.config.headless,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        
        self.context = await self.browser.new_context(
            user_agent=self.config.user_agent,
            viewport={'width': 1920, 'height': 1080}
        )
        
        # Add custom headers if specified
        if self.config.custom_headers:
            await self.context.set_extra_http_headers(self.config.custom_headers)
        
        self.page = await self.context.new_page()
        
        # Set timeout
        self.page.set_default_timeout(self.config.timeout * 1000)
    
    async def close_browser(self):
        """Clean up browser resources properly to avoid asyncio warnings"""
        try:
            if self.page:
                await self.page.close()
                self.page = None
                
            if self.context:
                await self.context.close()
                self.context = None
                
            if self.browser:
                await self.browser.close()
                self.browser = None
                
        except Exception as e:
            logger.debug(f"Error during browser cleanup: {e}")
            # Force close if normal close fails
            try:
                if self.browser:
                    await self.browser.close()
                    self.browser = None
            except Exception as e2:
                logger.debug(f"Force close also failed: {e2}")
    
    async def navigate_to_url(self, url: str):
        """Navigate to URL with error handling"""
        try:
            await self.page.goto(url, wait_until='networkidle')
            await self.page.wait_for_timeout(1000)  # Brief pause
        except Exception as e:
            logger.error(f"Navigation failed to {url}: {e}")
            raise
    
    async def extract_field_data(self, element, field_mapping: FieldMapping, record_data: Optional[Dict] = None) -> Optional[str]:
        """Extract data from element using field mapping"""
        # Handle OCR extraction if required
        if field_mapping.requires_ocr:
            # For OCR fields, we need the film code URL from the same row
            film_code_url = None
            
            # Try to get the film code URL from the record data if available
            if record_data and 'film_code_url' in record_data:
                film_code_url = record_data['film_code_url']
            else:
                # Otherwise, try to extract it from the current element
                film_selector = "td:last-child a"
                try:
                    target_element = await element.query_selector(film_selector)
                    if target_element:
                        href = await target_element.get_attribute("href")
                        if href:
                            # Convert relative URL to absolute if needed
                            if href.startswith('/'):
                                from urllib.parse import urljoin
                                film_code_url = urljoin(self.config.base_url, href)
                            else:
                                film_code_url = href
                except Exception as e:
                    logger.debug(f"Failed to get film code URL: {e}")
            
            # If we found a film code URL, try OCR extraction
            if film_code_url:
                print(f"DEBUG: Attempting OCR extraction for {field_mapping.field_name} from {film_code_url[:50]}...")
                ocr_result = await self.extract_with_ocr(film_code_url, field_mapping)
                if ocr_result:
                    print(f"DEBUG: OCR extracted address: {ocr_result}")
                    return ocr_result
                else:
                    print(f"DEBUG: OCR extraction failed or returned no address")
            else:
                print(f"DEBUG: No film code URL found for OCR extraction")
        
        # Normal extraction logic
        for selector_config in field_mapping.selectors:
            try:
                if selector_config.selector_type == "css":
                    target_element = await element.query_selector(selector_config.selector)
                else:  # xpath
                    target_element = await element.query_selector(f"xpath={selector_config.selector}")
                
                if target_element:
                    if selector_config.attribute:
                        if selector_config.attribute == "text":
                            value = await target_element.text_content()
                        else:
                            value = await target_element.get_attribute(selector_config.attribute)
                    else:
                        value = await target_element.text_content()
                    
                    if value:
                        value = value.strip()
                        # Apply post-processing if specified
                        if field_mapping.post_process:
                            value = self.apply_post_processing(value, field_mapping.post_process)
                        
                        # Apply validation if specified
                        if field_mapping.validation:
                            if not re.match(field_mapping.validation, value):
                                continue
                        
                        return value
            except Exception as e:
                logger.debug(f"Selector failed {selector_config.selector}: {e}")
                continue
        
        return None
    
    def apply_post_processing(self, value: str, process_type: str) -> str:
        """Apply post-processing to extracted values"""
        if process_type == "clean_whitespace":
            return re.sub(r'\s+', ' ', value).strip()
        elif process_type == "extract_numbers":
            numbers = re.findall(r'\d+', value)
            return ''.join(numbers)
        elif process_type == "clean_case_number":
            # Remove common prefixes/suffixes from case numbers
            return re.sub(r'[^\w\-]', '', value)
        elif process_type == "parse_date":
            # Basic date parsing - can be extended
            return value.replace('/', '-')
        
        return value
    
    async def delay(self):
        """Apply configured delay between requests"""
        await asyncio.sleep(self.config.delay_between_requests)
    
    async def extract_with_ocr(self, url: str, field_mapping: FieldMapping) -> Optional[str]:
        """Extract text from a document using OCR"""
        if not OCR_AVAILABLE:
            logger.warning("OCR not available, skipping OCR extraction")
            return None
        
        try:
            # Navigate to the document URL
            print(f"DEBUG: Attempting OCR extraction from URL: {url}")
            await self.page.goto(url, wait_until='networkidle')
            await self.page.wait_for_timeout(2000)
            
            # Take a screenshot of the document
            screenshot = await self.page.screenshot(full_page=True)
            
            # Convert to PIL Image and perform OCR
            image = Image.open(BytesIO(screenshot))
            ocr_text = pytesseract.image_to_string(image)
            
            print(f"DEBUG: OCR extracted text length: {len(ocr_text)}")
            
            # Look for address patterns in the OCR text
            address_text = self.extract_address_from_ocr(ocr_text)
            print(f"DEBUG: Extracted address from OCR: {address_text}")
            
            return address_text
            
        except Exception as e:
            logger.error(f"OCR extraction failed for {url}: {e}")
            return None
    
    def extract_address_from_ocr(self, ocr_text: str) -> Optional[str]:
        """Extract address information from OCR text"""
        if not ocr_text:
            return None
        
        # Common address patterns for Texas
        address_patterns = [
            # Street address with number
            r'\d+\s+[A-Z][A-Za-z\s]+(STREET|ST|AVENUE|AVE|ROAD|RD|DRIVE|DR|LANE|LN|BOULEVARD|BLVD|WAY|PLACE|PL|COURT|CT|CIRCLE|CIR)',
            # Property description patterns
            r'LOT\s+\d+.*?BLOCK\s+\d+',
            r'TRACT\s+\d+.*?BLOCK\s+\d+',
            r'SUBDIVISION.*?HARRIS\s+COUNTY',
        ]
        
        # Clean the OCR text
        clean_text = re.sub(r'\s+', ' ', ocr_text).strip()
        
        # Try each pattern
        for pattern in address_patterns:
            matches = re.findall(pattern, clean_text, re.IGNORECASE)
            if matches:
                # Return the first match, cleaned up
                address = matches[0].strip()
                return re.sub(r'\s+', ' ', address)
        
        # If no specific pattern matches, look for lines that might be addresses
        lines = clean_text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for lines with numbers and street-like words
            if (re.search(r'\d+', line) and 
                len(line) > 10 and 
                any(word in line.upper() for word in ['ST', 'STREET', 'AVE', 'AVENUE', 'RD', 'ROAD', 'DR', 'DRIVE', 'LN', 'LANE'])):
                return line
        
        # Return first meaningful line if nothing else matches
        for line in lines:
            line = line.strip()
            if len(line) > 15 and re.search(r'\d+', line):
                return line
        
        return None
    
    @abstractmethod
    async def scrape(self, task_params: Dict[str, Any]) -> ScrapingResult:
        """Main scraping method - must be implemented by subclasses"""
        pass

# ─────────────────────────────────────────────────────────────────────────────
# STATIC HTML SCRAPER
# ─────────────────────────────────────────────────────────────────────────────

class StaticHtmlScraper(BaseScraper):
    """Scraper for static HTML sites with pagination"""
    
    async def scrape(self, task_params: Dict[str, Any]) -> ScrapingResult:
        """Scrape static HTML pages with pagination"""
        logger.info(f"Starting static HTML scraping for {self.config.name}")
        
        records = []
        pages_scraped = 0
        max_records = task_params.get('max_records', 10)
        
        try:
            await self.start_browser()
            
            # Start from base URL
            current_url = self.config.base_url
            
            while pages_scraped < (self.config.pagination_config.max_pages if self.config.pagination_config else 1):
                logger.info(f"Scraping page {pages_scraped + 1}: {current_url}")
                
                await self.navigate_to_url(current_url)
                
                # Extract records from current page
                page_records = await self.extract_records_from_page()
                records.extend(page_records)
                
                pages_scraped += 1
                
                # Check if we have enough records
                if len(records) >= max_records:
                    records = records[:max_records]
                    break
                
                # Try to navigate to next page
                next_url = await self.get_next_page_url()
                if not next_url:
                    break
                
                current_url = next_url
                await self.delay()
            
            await self.close_browser()
            
            return ScrapingResult(
                success=True,
                records=[ScrapingRecord(data=record) for record in records],
                total_pages_scraped=pages_scraped
            )
            
        except Exception as e:
            logger.error(f"Static HTML scraping failed: {e}")
            if self.browser:
                await self.close_browser()
            
            return ScrapingResult(
                success=False,
                error_message=str(e),
                total_pages_scraped=pages_scraped
            )
    
    async def extract_records_from_page(self) -> List[Dict[str, Any]]:
        """Extract records from the current page"""
        records = []
        
        # Common container selectors to try
        container_selectors = [
            'tbody tr',  # Table rows
            '.record',   # Record class
            '.result',   # Result class
            'tr',        # All table rows
            'div[data-record]',  # Data attributes
        ]
        
        row_elements = None
        for selector in container_selectors:
            try:
                row_elements = await self.page.query_selector_all(selector)
                if row_elements and len(row_elements) > 1:  # More than just header
                    break
            except:
                continue
        
        if not row_elements:
            logger.warning("No record containers found on page")
            return records
        
        logger.info(f"Found {len(row_elements)} potential record elements")
        
        for element in row_elements:
            try:
                record_data = {}
                
                # Extract each configured field (first non-OCR, then OCR)
                for field_mapping in self.config.field_mappings:
                    if not field_mapping.requires_ocr:
                        value = await self.extract_field_data(element, field_mapping)
                        if value:
                            record_data[field_mapping.field_name] = value
                
                # Second pass for OCR fields
                for field_mapping in self.config.field_mappings:
                    if field_mapping.requires_ocr:
                        value = await self.extract_field_data(element, field_mapping, record_data)
                        if value:
                            record_data[field_mapping.field_name] = value
                
                # Only include records that have required fields
                if self.has_required_fields(record_data):
                    record_data['source_url'] = self.page.url
                    records.append(record_data)
                
            except Exception as e:
                logger.debug(f"Failed to extract record: {e}")
                continue
        
        logger.info(f"Successfully extracted {len(records)} records from page")
        return records
    
    async def get_next_page_url(self) -> Optional[str]:
        """Get URL for next page if pagination is configured"""
        if not self.config.pagination_config:
            return None
        
        try:
            if self.config.pagination_config.pagination_type == PaginationType.NEXT_PREVIOUS:
                next_button = await self.page.query_selector(
                    self.config.pagination_config.next_button_selector
                )
                if next_button:
                    href = await next_button.get_attribute('href')
                    if href:
                        from urllib.parse import urljoin
                        return urljoin(self.config.base_url, href)
            
            elif self.config.pagination_config.pagination_type == PaginationType.NUMBERED:
                # Look for next numbered page
                current_page = 1  # This would need to be tracked
                next_page_selector = f"a:has-text('{current_page + 1}')"
                next_page_link = await self.page.query_selector(next_page_selector)
                if next_page_link:
                    href = await next_page_link.get_attribute('href')
                    if href:
                        from urllib.parse import urljoin
                        return urljoin(self.config.base_url, href)
        
        except Exception as e:
            logger.debug(f"Failed to find next page: {e}")
        
        return None
    
    def has_required_fields(self, record_data: Dict[str, Any]) -> bool:
        """Check if record has all required fields"""
        for field in self.config.required_fields:
            if field not in record_data or not record_data[field]:
                return False
        return True

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH FORM SCRAPER
# ─────────────────────────────────────────────────────────────────────────────

class SearchFormScraper(BaseScraper):
    """Scraper for search-based systems"""
    
    async def scrape(self, task_params: Dict[str, Any]) -> ScrapingResult:
        """Scrape using search form"""
        logger.info(f"Starting search form scraping for {self.config.name}")
        
        records = []
        pages_scraped = 0
        max_records = task_params.get('max_records', 100)
        
        try:
            await self.start_browser()
            
            # Navigate to search page
            search_url = self.config.search_config.search_url
            await self.navigate_to_url(search_url)
            
            # Fill and submit search form
            await self.fill_search_form(task_params)
            await self.submit_search_form()
            
            # Wait for results
            await self.wait_for_search_results()
            
            # Extract records from result pages
            while pages_scraped < (self.config.pagination_config.max_pages if self.config.pagination_config else 1):
                logger.info(f"Extracting results from page {pages_scraped + 1}")
                
                page_records = await self.extract_search_results()
                records.extend(page_records)
                
                pages_scraped += 1
                
                # Check if we have enough records
                if len(records) >= max_records:
                    records = records[:max_records]
                    break
                
                # Try to navigate to next page of results
                if not await self.go_to_next_results_page():
                    break
                
                await self.delay()
            
            await self.close_browser()
            
            return ScrapingResult(
                success=True,
                records=[ScrapingRecord(data=record) for record in records],
                total_pages_scraped=pages_scraped
            )
            
        except Exception as e:
            logger.error(f"Search form scraping failed: {e}")
            if self.browser:
                await self.close_browser()
            
            return ScrapingResult(
                success=False,
                error_message=str(e),
                total_pages_scraped=pages_scraped
            )
    
    async def fill_search_form(self, task_params: Dict[str, Any]):
        """Fill search form with parameters"""
        search_config = self.config.search_config
        
        # Wait for form to be present
        await self.page.wait_for_selector(search_config.search_form_selector)
        
        # Fill date range if provided
        date_range = task_params.get('date_range')
        if date_range and 'date_from' in search_config.search_fields:
            date_from_selector = search_config.search_fields['date_from']
            date_to_selector = search_config.search_fields.get('date_to')
            
            await self.page.fill(date_from_selector, date_range.get('from', ''))
            if date_to_selector:
                await self.page.fill(date_to_selector, date_range.get('to', ''))
        
        # Fill search terms if provided
        search_terms = task_params.get('search_terms', [])
        if search_terms and 'search_term' in search_config.search_fields:
            search_term_selector = search_config.search_fields['search_term']
            await self.page.fill(search_term_selector, ' '.join(search_terms))
        
        # Fill other form fields as configured
        for field_name, selector in search_config.search_fields.items():
            if field_name in task_params:
                await self.page.fill(selector, str(task_params[field_name]))
    
    async def submit_search_form(self):
        """Submit the search form"""
        submit_selector = self.config.search_config.submit_button_selector
        await self.page.click(submit_selector)
    
    async def wait_for_search_results(self):
        """Wait for search results to load"""
        results_selector = self.config.search_config.results_container_selector
        await self.page.wait_for_selector(results_selector, timeout=30000)
        await self.page.wait_for_load_state('networkidle')
    
    async def extract_search_results(self) -> List[Dict[str, Any]]:
        """Extract records from search results"""
        results_container = self.config.search_config.results_container_selector
        
        # Find all result rows
        row_selectors = [
            f"{results_container} tr",
            f"{results_container} .result",
            f"{results_container} .record",
            f"{results_container} > div"
        ]
        
        row_elements = None
        for selector in row_selectors:
            try:
                row_elements = await self.page.query_selector_all(selector)
                if row_elements and len(row_elements) > 0:
                    break
            except:
                continue
        
        if not row_elements:
            return []
        
        records = []
        for element in row_elements:
            try:
                record_data = {}
                
                # Extract each configured field (first non-OCR, then OCR)
                for field_mapping in self.config.field_mappings:
                    if not field_mapping.requires_ocr:
                        value = await self.extract_field_data(element, field_mapping)
                        if value:
                            record_data[field_mapping.field_name] = value
                
                # Second pass for OCR fields
                for field_mapping in self.config.field_mappings:
                    if field_mapping.requires_ocr:
                        value = await self.extract_field_data(element, field_mapping, record_data)
                        if value:
                            record_data[field_mapping.field_name] = value
                
                # Only include records that have required fields
                if self.has_required_fields(record_data):
                    record_data['source_url'] = self.page.url
                    records.append(record_data)
                
            except Exception as e:
                logger.debug(f"Failed to extract search result: {e}")
                continue
        
        return records
    
    async def go_to_next_results_page(self) -> bool:
        """Navigate to next page of search results"""
        if not self.config.pagination_config:
            return False
        
        try:
            next_selector = self.config.pagination_config.next_button_selector
            if next_selector:
                next_button = await self.page.query_selector(next_selector)
                if next_button:
                    await next_button.click()
                    await self.wait_for_search_results()
                    return True
        except Exception as e:
            logger.debug(f"Failed to navigate to next results page: {e}")
        
        return False
    
    def has_required_fields(self, record_data: Dict[str, Any]) -> bool:
        """Check if record has all required fields"""
        for field in self.config.required_fields:
            if field not in record_data or not record_data[field]:
                return False
        return True

# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATED SCRAPER
# ─────────────────────────────────────────────────────────────────────────────

class AuthenticatedScraper(BaseScraper):
    """Scraper for authenticated portals with login and CAPTCHA handling"""
    
    async def scrape(self, task_params: Dict[str, Any]) -> ScrapingResult:
        """Scrape authenticated portal"""
        logger.info(f"Starting authenticated scraping for {self.config.name}")
        
        try:
            await self.start_browser()
            
            # Perform authentication
            auth_success = await self.authenticate(task_params)
            if not auth_success:
                return ScrapingResult(
                    success=False,
                    error_message="Authentication failed"
                )
            
            # After successful authentication, use appropriate scraping method
            if self.config.search_config:
                # Use search-based approach
                scraper = SearchFormScraper(self.config)
                scraper.browser = self.browser
                scraper.context = self.context
                scraper.page = self.page
                
                result = await scraper.scrape(task_params)
            else:
                # Use static HTML approach
                scraper = StaticHtmlScraper(self.config)
                scraper.browser = self.browser
                scraper.context = self.context
                scraper.page = self.page
                
                result = await scraper.scrape(task_params)
            
            await self.close_browser()
            return result
            
        except Exception as e:
            logger.error(f"Authenticated scraping failed: {e}")
            if self.browser:
                await self.close_browser()
            
            return ScrapingResult(
                success=False,
                error_message=str(e)
            )
    
    async def authenticate(self, task_params: Dict[str, Any]) -> bool:
        """Perform authentication"""
        auth_config = self.config.auth_config
        if not auth_config:
            logger.error("No authentication configuration provided")
            return False
        
        try:
            # Navigate to login page
            await self.navigate_to_url(auth_config.login_url)
            
            # Handle different authentication types
            if auth_config.auth_type == AuthType.FORM:
                return await self.handle_form_auth(task_params)
            elif auth_config.auth_type == AuthType.BASIC:
                return await self.handle_basic_auth(task_params)
            else:
                logger.error(f"Unsupported auth type: {auth_config.auth_type}")
                return False
                
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False
    
    async def handle_form_auth(self, task_params: Dict[str, Any]) -> bool:
        """Handle form-based authentication"""
        auth_config = self.config.auth_config
        
        # Get credentials from task params or environment
        username = task_params.get('username') or os.getenv('SCRAPER_USERNAME')
        password = task_params.get('password') or os.getenv('SCRAPER_PASSWORD')
        
        if not username or not password:
            logger.error("Username or password not provided")
            return False
        
        # Fill login form
        await self.page.fill(auth_config.username_field, username)
        await self.page.fill(auth_config.password_field, password)
        
        # Handle CAPTCHA if present
        if auth_config.captcha_present:
            captcha_solved = await self.handle_captcha()
            if not captcha_solved:
                logger.warning("CAPTCHA not solved, attempting login anyway")
        
        # Submit login form
        await self.page.click(auth_config.login_button_selector)
        
        # Wait for login to complete
        await self.page.wait_for_load_state('networkidle')
        
        # Check if login was successful
        return await self.verify_login_success()
    
    async def handle_basic_auth(self, task_params: Dict[str, Any]) -> bool:
        """Handle HTTP Basic Authentication"""
        # This would be handled at the context level
        username = task_params.get('username') or os.getenv('SCRAPER_USERNAME')
        password = task_params.get('password') or os.getenv('SCRAPER_PASSWORD')
        
        if username and password:
            await self.context.set_http_credentials(
                username=username,
                password=password
            )
            return True
        
        return False
    
    async def handle_captcha(self) -> bool:
        """Handle CAPTCHA requiring user interaction
        
        IMPORTANT: This function requires explicit user interaction to solve CAPTCHA.
        The system does not automatically solve CAPTCHAs. Users must manually solve
        any CAPTCHA challenges that appear during authentication or data collection.
        
        This function pauses execution to allow the authenticated user to solve
        the CAPTCHA challenge in their browser session.
        """
        logger.warning("CAPTCHA detected - user interaction required")
        
        # Wait for user to manually solve CAPTCHA (in non-headless mode)
        if not self.config.headless:
            logger.info("CAPTCHA challenge detected. Please solve the CAPTCHA in the browser window.")
            logger.info("After solving the CAPTCHA, press Enter to continue...")
            input("Press Enter after solving CAPTCHA...")
            return True
        
        # In headless mode, cannot solve CAPTCHA - authentication will fail
        logger.error("CAPTCHA detected in headless mode. User interaction required but unavailable.")
        return False
    
    async def verify_login_success(self) -> bool:
        """Verify that login was successful"""
        # Common indicators of successful login
        success_indicators = [
            'dashboard', 'welcome', 'logout', 'account', 'profile'
        ]
        
        failure_indicators = [
            'login failed', 'invalid', 'error', 'incorrect', 'try again'
        ]
        
        page_content = await self.page.content()
        page_text = page_content.lower()
        
        # Check for failure indicators first
        if any(indicator in page_text for indicator in failure_indicators):
            return False
        
        # Check for success indicators
        if any(indicator in page_text for indicator in success_indicators):
            return True
        
        # If we're no longer on the login page, assume success
        current_url = self.page.url
        login_url = self.config.auth_config.login_url
        
        return current_url != login_url