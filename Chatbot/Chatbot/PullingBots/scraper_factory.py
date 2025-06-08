"""
Modular Scraper Factory
=======================

This module provides a factory for creating and managing county scrapers.
It can analyze websites, generate configurations, and execute scraping tasks
using different scraper types.
"""

import asyncio
import json
import re
import time
from typing import Dict, List, Optional, Any, Type
from pathlib import Path
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import logging

# Browser automation
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from bs4 import BeautifulSoup
import requests

# Local imports
from config_schemas import (
    CountyConfig, SiteAnalysis, ScraperType, PaginationType, 
    FieldMapping, SelectorConfig, FieldType, AuthType, AuthConfig,
    SearchConfig, PaginationConfig, ScrapingResult, ScrapingRecord
)
from base_scrapers import StaticHtmlScraper, SearchFormScraper, AuthenticatedScraper

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# SITE ANALYZER
# ─────────────────────────────────────────────────────────────────────────────

class SiteAnalyzer:
    """Analyzes county websites to determine scraper configuration"""
    
    def __init__(self):
        self.common_patterns = {
            'case_number': [
                r'case\s*(?:number|no|#)',
                r'document\s*(?:number|no|#)',
                r'filing\s*(?:number|no|#)',
                r'record\s*(?:number|no|#)'
            ],
            'date': [
                r'date\s*(?:filed|recorded|created)',
                r'filing\s*date',
                r'record\s*date'
            ],
            'party_name': [
                r'plaintiff',
                r'defendant',
                r'grantor',
                r'grantee',
                r'party\s*name'
            ],
            'property_address': [
                r'property\s*address',
                r'real\s*estate',
                r'premises',
                r'location'
            ]
        }
    
    async def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze a county website and return structured analysis"""
        logger.info(f"Analyzing site: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            try:
                # Navigate to the site
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=10000)
                
                # Get page content
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                
                # Analyze different aspects
                scraper_type = self._determine_scraper_type(soup, page)
                complexity = await self._calculate_complexity(page, soup)
                auth_required = await self._check_authentication(page, soup)
                captcha_present = self._check_captcha(soup)
                pagination_type = self._determine_pagination_type(soup)
                required_fields = self._identify_required_fields(soup)
                suggested_selectors = await self._generate_selectors(page, soup)
                js_heavy = await self._check_javascript_dependency(page)
                
                # Check robots.txt
                robots_url = None
                try:
                    robots_response = requests.get(f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt")
                    if robots_response.status_code == 200:
                        robots_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}/robots.txt"
                except:
                    pass
                
                return SiteAnalysis(
                    url=url,
                    scraper_type=scraper_type,
                    complexity=complexity,
                    authentication_required=auth_required,
                    captcha_present=captcha_present,
                    pagination_type=pagination_type,
                    required_fields=required_fields,
                    suggested_selectors=suggested_selectors,
                    javascript_heavy=js_heavy,
                    robots_txt_url=robots_url
                )
                
            finally:
                await browser.close()
    
    def _determine_scraper_type(self, soup: BeautifulSoup, page: Page) -> ScraperType:
        """Determine the appropriate scraper type"""
        # Check for login forms
        login_indicators = soup.find_all(['form', 'input'], attrs={'name': re.compile(r'login|user|pass', re.I)})
        if login_indicators:
            return ScraperType.AUTHENTICATED
        
        # Check for search forms
        search_forms = soup.find_all('form')
        for form in search_forms:
            inputs = form.find_all('input')
            if any(inp.get('type') in ['search', 'text'] for inp in inputs):
                return ScraperType.SEARCH_FORM
        
        # Default to static HTML
        return ScraperType.STATIC_HTML
    
    async def _calculate_complexity(self, page: Page, soup: BeautifulSoup) -> int:
        """Calculate complexity score 1-10"""
        complexity = 1
        
        # Check for JavaScript frameworks
        js_frameworks = ['angular', 'react', 'vue', 'ember']
        page_text = soup.get_text().lower()
        for framework in js_frameworks:
            if framework in page_text:
                complexity += 2
                break
        
        # Check for AJAX/dynamic content
        scripts = soup.find_all('script')
        if any('ajax' in script.get_text().lower() for script in scripts if script.string):
            complexity += 2
        
        # Check for multiple forms
        forms = soup.find_all('form')
        if len(forms) > 2:
            complexity += 1
        
        # Check for iframe usage
        iframes = soup.find_all('iframe')
        if iframes:
            complexity += 2
        
        return min(complexity, 10)
    
    async def _check_authentication(self, page: Page, soup: BeautifulSoup) -> bool:
        """Check if authentication is required"""
        auth_indicators = [
            'login', 'sign in', 'authenticate', 'password', 'username',
            'access denied', 'unauthorized', 'please log in'
        ]
        
        page_text = soup.get_text().lower()
        return any(indicator in page_text for indicator in auth_indicators)
    
    def _check_captcha(self, soup: BeautifulSoup) -> bool:
        """Check for CAPTCHA presence"""
        captcha_indicators = [
            'captcha', 'recaptcha', 'security code', 'verification code'
        ]
        
        page_text = soup.get_text().lower()
        return any(indicator in page_text for indicator in captcha_indicators)
    
    def _determine_pagination_type(self, soup: BeautifulSoup) -> PaginationType:
        """Determine pagination type"""
        # Look for pagination indicators
        pagination_classes = ['pagination', 'pager', 'page-nav']
        for cls in pagination_classes:
            if soup.find(attrs={'class': re.compile(cls, re.I)}):
                # Check for numbered pagination
                if soup.find('a', string=re.compile(r'\d+')):
                    return PaginationType.NUMBERED
                # Check for next/previous
                if soup.find('a', string=re.compile(r'next|previous', re.I)):
                    return PaginationType.NEXT_PREVIOUS
        
        return PaginationType.NONE
    
    def _identify_required_fields(self, soup: BeautifulSoup) -> List[str]:
        """Identify required data fields based on page content"""
        required_fields = []
        page_text = soup.get_text().lower()
        
        for field_type, patterns in self.common_patterns.items():
            if any(re.search(pattern, page_text, re.I) for pattern in patterns):
                required_fields.append(field_type)
        
        return required_fields
    
    async def _generate_selectors(self, page: Page, soup: BeautifulSoup) -> Dict[str, str]:
        """Generate suggested CSS selectors for common fields"""
        selectors = {}
        
        # Common selector patterns
        selector_patterns = {
            'case_number': [
                '[class*="case"]', '[id*="case"]', '[class*="number"]',
                'td:contains("Case")', 'span:contains("No.")'
            ],
            'date': [
                '[class*="date"]', '[id*="date"]', 'td:contains("Date")',
                '.filed-date', '.record-date'
            ],
            'party_name': [
                '[class*="party"]', '[class*="name"]', 'td:contains("Name")',
                '.plaintiff', '.defendant'
            ],
            'property_address': [
                '[class*="address"]', '[class*="property"]', 'td:contains("Address")',
                '.location', '.premises'
            ]
        }
        
        for field, patterns in selector_patterns.items():
            for pattern in patterns:
                try:
                    # Test if selector exists
                    element = soup.select_one(pattern)
                    if element:
                        selectors[field] = pattern
                        break
                except:
                    continue
        
        return selectors
    
    async def _check_javascript_dependency(self, page: Page) -> bool:
        """Check if the site heavily depends on JavaScript"""
        # Disable JavaScript and check if content changes significantly
        try:
            await page.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false,});")
            content_with_js = await page.content()
            
            # Create new page without JS
            context = await page.context.browser.new_context(java_script_enabled=False)
            no_js_page = await context.new_page()
            await no_js_page.goto(page.url)
            content_without_js = await no_js_page.content()
            await context.close()
            
            # Compare content length as rough indicator
            return len(content_without_js) < len(content_with_js) * 0.7
            
        except:
            return False

# ─────────────────────────────────────────────────────────────────────────────
# SCRAPER FACTORY
# ─────────────────────────────────────────────────────────────────────────────

class ScraperFactory:
    """Factory for creating and managing county scrapers"""
    
    def __init__(self):
        self.analyzer = SiteAnalyzer()
        self.scrapers = {
            ScraperType.STATIC_HTML: StaticHtmlScraper,
            ScraperType.SEARCH_FORM: SearchFormScraper,
            ScraperType.AUTHENTICATED: AuthenticatedScraper
        }
    
    async def analyze_site(self, url: str) -> SiteAnalysis:
        """Analyze a county website"""
        return await self.analyzer.analyze_site(url)
    
    async def generate_config(self, county_name: str, analysis: SiteAnalysis) -> CountyConfig:
        """Generate scraper configuration based on site analysis"""
        logger.info(f"Generating configuration for {county_name}")
        
        # Create base configuration
        config = CountyConfig(
            name=county_name,
            state="XX",  # Will need to be updated
            base_url=analysis.url,
            scraper_type=analysis.scraper_type,
            field_mappings=self._generate_field_mappings(analysis),
            required_fields=analysis.required_fields,
            javascript_enabled=analysis.javascript_heavy,
            headless=True,
            delay_between_requests=2.0 if analysis.complexity > 5 else 1.0
        )
        
        # Add search configuration if needed
        if analysis.scraper_type == ScraperType.SEARCH_FORM:
            config.search_config = SearchConfig(
                search_url=analysis.url,
                search_form_selector="form",
                search_fields={"date_from": "#date_from", "date_to": "#date_to"},
                submit_button_selector="input[type='submit']",
                results_container_selector=".results"
            )
        
        # Add pagination configuration
        if analysis.pagination_type != PaginationType.NONE:
            config.pagination_config = PaginationConfig(
                pagination_type=analysis.pagination_type,
                next_button_selector=".next" if analysis.pagination_type == PaginationType.NEXT_PREVIOUS else None,
                max_pages=10
            )
        
        # Add authentication configuration if needed
        if analysis.authentication_required:
            config.auth_config = AuthConfig(
                auth_type=AuthType.FORM,
                login_url=analysis.url,
                username_field="#username",
                password_field="#password",
                login_button_selector="input[type='submit']",
                captcha_present=analysis.captcha_present
            )
        
        return config
    
    def _generate_field_mappings(self, analysis: SiteAnalysis) -> List[FieldMapping]:
        """Generate field mappings based on analysis"""
        mappings = []
        
        # Create mappings for identified fields
        field_type_map = {
            'case_number': FieldType.CASE_NUMBER,
            'date': FieldType.DATE,
            'party_name': FieldType.PERSON_NAME,
            'property_address': FieldType.ADDRESS
        }
        
        for field in analysis.required_fields:
            if field in field_type_map:
                selector = analysis.suggested_selectors.get(field, f".{field}")
                mappings.append(
                    FieldMapping(
                        field_name=field,
                        field_type=field_type_map[field],
                        selectors=[SelectorConfig(selector=selector)]
                    )
                )
        
        # Ensure we have at least one mapping
        if not mappings:
            mappings.append(
                FieldMapping(
                    field_name="record_id",
                    field_type=FieldType.TEXT,
                    selectors=[SelectorConfig(selector="td:first-child")]
                )
            )
        
        return mappings
    
    async def execute_scraping(self, config: CountyConfig, task_params: Dict[str, Any]) -> ScrapingResult:
        """Execute scraping using the provided configuration"""
        logger.info(f"Executing scraping for {config.name}")
        
        # Get appropriate scraper class
        scraper_class = self.scrapers.get(config.scraper_type)
        if not scraper_class:
            return ScrapingResult(
                success=False,
                error_message=f"No scraper available for type: {config.scraper_type}"
            )
        
        # Create and run scraper
        scraper = scraper_class(config)
        
        try:
            start_time = time.time()
            result = await scraper.scrape(task_params)
            execution_time = time.time() - start_time
            
            result.execution_time = execution_time
            return result
            
        except Exception as e:
            logger.error(f"Scraping failed: {e}")
            return ScrapingResult(
                success=False,
                error_message=str(e)
            )
    
    def create_config_from_template(self, scraper_type: ScraperType, county_name: str, base_url: str) -> CountyConfig:
        """Create configuration from template"""
        from config_schemas import get_static_html_template, get_search_form_template, get_authenticated_template
        
        templates = {
            ScraperType.STATIC_HTML: get_static_html_template,
            ScraperType.SEARCH_FORM: get_search_form_template,
            ScraperType.AUTHENTICATED: get_authenticated_template
        }
        
        template_func = templates.get(scraper_type)
        if not template_func:
            raise ValueError(f"No template available for scraper type: {scraper_type}")
        
        config = template_func()
        config.name = county_name
        config.base_url = base_url
        
        return config
    
    def save_config(self, config: CountyConfig, config_dir: str = "configs") -> str:
        """Save configuration to file"""
        config_path = Path(config_dir)
        config_path.mkdir(exist_ok=True)
        
        filename = f"{config.name.lower().replace(' ', '_')}.json"
        file_path = config_path / filename
        
        config.to_json_file(str(file_path))
        logger.info(f"Configuration saved to {file_path}")
        
        return str(file_path)
    
    def load_config(self, config_file: str) -> CountyConfig:
        """Load configuration from file"""
        return CountyConfig.from_json_file(config_file)
    
    def list_configs(self, config_dir: str = "configs") -> List[str]:
        """List available configuration files"""
        config_path = Path(config_dir)
        if not config_path.exists():
            return []
        
        return [f.name for f in config_path.glob("*.json")]

# ─────────────────────────────────────────────────────────────────────────────
# XPATH GENERATOR WITH LANGCHAIN
# ─────────────────────────────────────────────────────────────────────────────

class XPathGenerator:
    """AI-powered XPath selector generation"""
    
    def __init__(self, openai_api_key: str = None):
        import os
        from langchain_openai import ChatOpenAI
        
        self.llm = ChatOpenAI(
            temperature=0.1,
            model="gpt-4-turbo-preview",
            openai_api_key=openai_api_key or os.getenv("OPENAI_API_KEY")
        )
    
    async def generate_xpath(self, html_content: str, field_description: str) -> str:
        """Generate XPath selector for a specific field"""
        prompt = f"""
        You are an expert in web scraping and XPath selectors. 
        
        Given this HTML content, generate the most accurate XPath selector for: {field_description}
        
        HTML:
        {html_content[:2000]}...
        
        Requirements:
        1. Return only the XPath selector, no explanation
        2. Make it as specific as possible to avoid false matches
        3. Consider the field might appear in a table or list
        4. Use text matching if necessary
        
        XPath selector:
        """
        
        try:
            response = await self.llm.apredict(prompt)
            return response.strip()
        except Exception as e:
            logger.error(f"XPath generation failed: {e}")
            return f"//*[contains(text(), '{field_description}')]"

# ─────────────────────────────────────────────────────────────────────────────
# CONVENIENCE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

async def quick_analyze(url: str) -> Dict[str, Any]:
    """Quick site analysis"""
    factory = ScraperFactory()
    analysis = await factory.analyze_site(url)
    return analysis.dict()

async def generate_config_from_url(county_name: str, url: str) -> CountyConfig:
    """Generate configuration from URL analysis"""
    factory = ScraperFactory()
    analysis = await factory.analyze_site(url)
    return await factory.generate_config(county_name, analysis) 