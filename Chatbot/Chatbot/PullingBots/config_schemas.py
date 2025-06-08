"""
Configuration Schemas for Modular County Scraper
================================================

This module defines Pydantic models for county scraper configurations,
site analysis results, and related data structures.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator, HttpUrl
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# ENUMS
# ─────────────────────────────────────────────────────────────────────────────

class ScraperType(str, Enum):
    """Types of scrapers based on site structure"""
    STATIC_HTML = "static_html"
    SEARCH_FORM = "search_form"
    AUTHENTICATED = "authenticated"

class PaginationType(str, Enum):
    """Types of pagination patterns"""
    NUMBERED = "numbered"
    NEXT_PREVIOUS = "next_previous"
    INFINITE_SCROLL = "infinite_scroll"
    NONE = "none"

class AuthType(str, Enum):
    """Authentication types"""
    NONE = "none"
    BASIC = "basic"
    FORM = "form"
    OAUTH = "oauth"
    CAPTCHA = "captcha"

class FieldType(str, Enum):
    """Data field types"""
    TEXT = "text"
    DATE = "date"
    URL = "url"
    NUMBER = "number"
    ADDRESS = "address"
    PERSON_NAME = "person_name"
    CASE_NUMBER = "case_number"

# ─────────────────────────────────────────────────────────────────────────────
# SELECTOR DEFINITIONS
# ─────────────────────────────────────────────────────────────────────────────

class SelectorConfig(BaseModel):
    """Configuration for a CSS/XPath selector"""
    selector: str = Field(description="CSS selector or XPath")
    selector_type: str = Field(default="css", description="Type: css or xpath")
    attribute: Optional[str] = Field(default=None, description="Attribute to extract (href, text, etc.)")
    required: bool = Field(default=True, description="Whether this field is required")
    multiple: bool = Field(default=False, description="Whether to extract multiple values")
    
class FieldMapping(BaseModel):
    """Maps a data field to one or more selectors"""
    field_name: str = Field(description="Name of the data field")
    field_type: FieldType = Field(description="Type of data field")
    selectors: List[SelectorConfig] = Field(description="Selectors to try in order")
    post_process: Optional[str] = Field(default=None, description="Post-processing function name")
    validation: Optional[str] = Field(default=None, description="Validation regex pattern")
    requires_ocr: bool = Field(default=False, description="Whether this field requires OCR extraction from linked documents")

# ─────────────────────────────────────────────────────────────────────────────
# SEARCH AND PAGINATION
# ─────────────────────────────────────────────────────────────────────────────

class SearchConfig(BaseModel):
    """Configuration for search functionality"""
    search_url: str = Field(description="URL of the search page")
    search_form_selector: str = Field(description="Selector for the search form")
    search_fields: Dict[str, str] = Field(description="Form field names and selectors")
    submit_button_selector: str = Field(description="Submit button selector")
    results_container_selector: str = Field(description="Container for search results")
    
class PaginationConfig(BaseModel):
    """Configuration for pagination handling"""
    pagination_type: PaginationType = Field(description="Type of pagination")
    next_button_selector: Optional[str] = Field(default=None)
    page_number_selector: Optional[str] = Field(default=None)
    results_per_page: Optional[int] = Field(default=None)
    max_pages: int = Field(default=10, description="Maximum pages to scrape")

# ─────────────────────────────────────────────────────────────────────────────
# AUTHENTICATION
# ─────────────────────────────────────────────────────────────────────────────

class AuthConfig(BaseModel):
    """Configuration for authentication"""
    auth_type: AuthType = Field(description="Type of authentication required")
    login_url: Optional[str] = Field(default=None)
    username_field: Optional[str] = Field(default=None)
    password_field: Optional[str] = Field(default=None)
    login_button_selector: Optional[str] = Field(default=None)
    captcha_present: bool = Field(default=False)
    captcha_selector: Optional[str] = Field(default=None)
    
# ─────────────────────────────────────────────────────────────────────────────
# SITE ANALYSIS
# ─────────────────────────────────────────────────────────────────────────────

class SiteAnalysis(BaseModel):
    """Result of analyzing a county website"""
    url: str = Field(description="Website URL analyzed")
    scraper_type: ScraperType = Field(description="Recommended scraper type")
    complexity: int = Field(ge=1, le=10, description="Complexity score 1-10")
    authentication_required: bool = Field(description="Whether authentication is needed")
    captcha_present: bool = Field(description="Whether CAPTCHA is present")
    pagination_type: PaginationType = Field(description="Type of pagination detected")
    required_fields: List[str] = Field(description="Required data fields identified")
    suggested_selectors: Dict[str, str] = Field(description="AI-suggested selectors")
    javascript_heavy: bool = Field(default=False, description="Whether site relies heavily on JS")
    rate_limit_detected: bool = Field(default=False, description="Whether rate limiting was detected")
    robots_txt_url: Optional[str] = Field(default=None, description="URL to robots.txt if found")
    
# ─────────────────────────────────────────────────────────────────────────────
# MAIN COUNTY CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

class CountyConfig(BaseModel):
    """Complete configuration for a county scraper"""
    
    # Basic Information
    name: str = Field(description="County name")
    state: str = Field(description="State abbreviation")
    base_url: str = Field(description="Base URL of the county website")
    description: Optional[str] = Field(default=None, description="Description of the county system")
    
    # Scraper Configuration
    scraper_type: ScraperType = Field(description="Type of scraper to use")
    field_mappings: List[FieldMapping] = Field(description="Field extraction configurations")
    
    # Search Configuration (if applicable)
    search_config: Optional[SearchConfig] = Field(default=None)
    
    # Pagination Configuration
    pagination_config: Optional[PaginationConfig] = Field(default=None)
    
    # Authentication (if required)
    auth_config: Optional[AuthConfig] = Field(default=None)
    
    # Browser Configuration
    user_agent: str = Field(default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    headless: bool = Field(default=True, description="Run browser in headless mode")
    timeout: int = Field(default=30, description="Default timeout in seconds")
    delay_between_requests: float = Field(default=1.0, description="Delay between requests in seconds")
    
    # Data Processing
    duplicate_check_field: str = Field(default="case_number", description="Field to check for duplicates")
    required_fields: List[str] = Field(description="Fields that must be present")
    
    # Advanced Options
    javascript_enabled: bool = Field(default=True)
    cookies_file: Optional[str] = Field(default=None, description="Path to cookies file")
    proxy_config: Optional[Dict[str, str]] = Field(default=None)
    custom_headers: Dict[str, str] = Field(default_factory=dict)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    version: str = Field(default="1.0.0")
    tested: bool = Field(default=False, description="Whether configuration has been tested")
    
    @validator('base_url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('base_url must start with http:// or https://')
        return v
    
    @validator('field_mappings')
    def validate_field_mappings(cls, v):
        if not v:
            raise ValueError('At least one field mapping is required')
        return v
    
    def to_json_file(self, file_path: str):
        """Save configuration to JSON file"""
        import json
        from pathlib import Path
        
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(self.dict(), f, indent=2, default=str)
    
    @classmethod
    def from_json_file(cls, file_path: str):
        """Load configuration from JSON file"""
        import json
        with open(file_path, 'r') as f:
            data = json.load(f)
        return cls(**data)

# ─────────────────────────────────────────────────────────────────────────────
# SCRAPING RESULTS
# ─────────────────────────────────────────────────────────────────────────────

class ScrapingRecord(BaseModel):
    """A single scraped record"""
    data: Dict[str, Any] = Field(description="Extracted data fields")
    source_url: Optional[str] = Field(default=None, description="URL where data was found")
    scraped_at: datetime = Field(default_factory=datetime.now)
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Data quality score")
    
class ScrapingResult(BaseModel):
    """Result of a scraping operation"""
    success: bool = Field(description="Whether scraping was successful")
    records: List[ScrapingRecord] = Field(default_factory=list)
    records_saved: int = Field(default=0, description="Number of records saved to database")
    total_pages_scraped: int = Field(default=0)
    execution_time: float = Field(default=0.0, description="Execution time in seconds")
    error_message: Optional[str] = Field(default=None)
    warnings: List[str] = Field(default_factory=list)
    
# ─────────────────────────────────────────────────────────────────────────────
# TEMPLATE CONFIGURATIONS
# ─────────────────────────────────────────────────────────────────────────────

def get_static_html_template() -> CountyConfig:
    """Template for static HTML sites with pagination"""
    return CountyConfig(
        name="Template County",
        state="XX",
        base_url="https://example.com",
        scraper_type=ScraperType.STATIC_HTML,
        field_mappings=[
            FieldMapping(
                field_name="case_number",
                field_type=FieldType.CASE_NUMBER,
                selectors=[SelectorConfig(selector=".case-number")]
            ),
            FieldMapping(
                field_name="file_date",
                field_type=FieldType.DATE,
                selectors=[SelectorConfig(selector=".file-date")]
            ),
            FieldMapping(
                field_name="party_name",
                field_type=FieldType.PERSON_NAME,
                selectors=[SelectorConfig(selector=".party-name")]
            )
        ],
        pagination_config=PaginationConfig(
            pagination_type=PaginationType.NUMBERED,
            next_button_selector=".next-page"
        ),
        required_fields=["case_number", "file_date"]
    )

def get_search_form_template() -> CountyConfig:
    """Template for search-based systems"""
    return CountyConfig(
        name="Template County Search",
        state="XX",
        base_url="https://example.com",
        scraper_type=ScraperType.SEARCH_FORM,
        field_mappings=[
            FieldMapping(
                field_name="document_number",
                field_type=FieldType.CASE_NUMBER,
                selectors=[SelectorConfig(selector=".doc-number")]
            ),
            FieldMapping(
                field_name="recorded_date",
                field_type=FieldType.DATE,
                selectors=[SelectorConfig(selector=".recorded-date")]
            )
        ],
        search_config=SearchConfig(
            search_url="https://example.com/search",
            search_form_selector="#search-form",
            search_fields={
                "date_from": "#date_from",
                "date_to": "#date_to"
            },
            submit_button_selector="#search-submit",
            results_container_selector=".search-results"
        ),
        required_fields=["document_number", "recorded_date"]
    )

def get_authenticated_template() -> CountyConfig:
    """Template for authenticated portals"""
    return CountyConfig(
        name="Template County Auth",
        state="XX",
        base_url="https://example.com",
        scraper_type=ScraperType.AUTHENTICATED,
        field_mappings=[
            FieldMapping(
                field_name="case_id",
                field_type=FieldType.CASE_NUMBER,
                selectors=[SelectorConfig(selector=".case-id")]
            )
        ],
        auth_config=AuthConfig(
            auth_type=AuthType.FORM,
            login_url="https://example.com/login",
            username_field="#username",
            password_field="#password",
            login_button_selector="#login-submit"
        ),
        required_fields=["case_id"]
    ) 