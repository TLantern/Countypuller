# 🔍 Modular County Scraper Factory

A comprehensive, AI-powered system for scraping county websites efficiently and intelligently. This system can analyze any county website, generate appropriate configurations, and execute scraping tasks with minimal manual intervention.

## 🌟 Features

- **🤖 LangChain ChatGPT Agent**: AI-powered analysis and optimization
- **🏭 Modular Factory System**: Support for 3 main scraper types
- **📋 Configuration-Driven**: JSON configs for easy customization
- **🚀 CLI Tool**: Generate scrapers in under 5 minutes
- **🎯 Smart Selectors**: AI-generated XPath and CSS selectors
- **🔄 Automatic Pagination**: Handle multiple page types
- **🔐 Authentication Support**: Login forms, CAPTCHA, and more
- **⚡ Headless Browser**: Playwright-powered automation
- **📊 Rich Output**: Beautiful CLI interface with progress bars

## 🏗️ Architecture

### Three Scraper Types

1. **Static HTML with Pagination**
   - Direct HTML parsing
   - Simple pagination handling
   - Fast and reliable

2. **Search-Based Systems**
   - Form submission
   - Dynamic result loading
   - Date range filtering

3. **Authenticated Portals**
   - Login handling
   - CAPTCHA support
   - Session management

### Core Components

```
lang.py              # LangChain ChatGPT Agent
scraper_factory.py   # Main factory and site analyzer
config_schemas.py    # Pydantic data models
base_scrapers.py     # Base scraper implementations
scraper_cli.py       # Command-line interface
configs/             # County configuration files
```

## 🚀 Quick Start

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Set environment variables
export OPENAI_API_KEY="your-openai-key"
export DB_URL="your-database-url"  # Optional
```

### 2. Analyze a County Website

```bash
# Analyze and generate configuration
python scraper_cli.py analyze "https://county.example.com/records" --county "Sample County"

# This will:
# - Analyze the website structure
# - Determine the best scraper type
# - Generate CSS/XPath selectors
# - Create a configuration file
```

### 3. Run the Scraper

```bash
# Test the generated scraper
python scraper_cli.py run configs/sample_county.json --test --max-records 10

# Full scraping with date range
python scraper_cli.py run configs/sample_county.json \
  --date-from 2024-01-01 \
  --date-to 2024-01-31 \
  --max-records 500
```

### 4. Generate Standalone Scraper

```bash
# Generate a Python file
python scraper_cli.py generate configs/sample_county.json --template advanced

# This creates: sample_county_scraper.py
python sample_county_scraper.py --help
```

## 🎯 Configuration Files

County configurations are JSON files that define how to scrape a specific site:

```json
{
  "name": "Harris County",
  "state": "TX",
  "base_url": "https://harris.foreclosures.com",
  "scraper_type": "search_form",
  "field_mappings": [
    {
      "field_name": "case_number",
      "field_type": "case_number",
      "selectors": [
        {
          "selector": "td:nth-child(1)",
          "selector_type": "css",
          "required": true
        }
      ]
    }
  ],
  "search_config": {
    "search_url": "https://harris.foreclosures.com/search",
    "search_form_selector": "#search-form",
    "search_fields": {
      "date_from": "#date_from",
      "date_to": "#date_to"
    }
  }
}
```

### Key Configuration Sections

- **field_mappings**: Define what data to extract and how
- **search_config**: Form submission configuration
- **pagination_config**: How to handle multiple pages
- **auth_config**: Login and authentication settings

## 🤖 AI-Powered Features

### LangChain Integration

The system includes a ChatGPT agent that can:

```python
from lang import CountyScrapingAgent

agent = CountyScrapingAgent()

# Analyze and scrape in one command
result = await agent.analyze_and_scrape(
    county_name="Harris County",
    website_url="https://harris.foreclosures.com",
    search_terms=["foreclosure", "lis pendens"],
    max_records=100
)
```

### Interactive Chat Mode

```bash
python scraper_cli.py chat

# Chat with the AI agent:
# > analyze https://county.example.com --county "Test County"
# > scrape the last 30 days of foreclosure records
# > optimize my configuration for better performance
```

### XPath Generation

```python
from scraper_factory import XPathGenerator

generator = XPathGenerator()
xpath = await generator.generate_xpath(
    html_content="<table><tr><td>Case: 123</td></tr></table>",
    field_description="case number"
)
# Returns: "//td[contains(text(), 'Case:')]"
```

## 📋 CLI Commands

### Analysis
```bash
# Analyze a website
scraper_cli.py analyze <url> --county "County Name"

# With custom output
scraper_cli.py analyze <url> --county "County Name" --output my_config.json
```

### Templates
```bash
# Create from template
scraper_cli.py template --type search_form --county "County Name" --url <url>

# Available types: static_html, search_form, authenticated
```

### Execution
```bash
# Run scraper
scraper_cli.py run <config_file> [options]

# Options:
#   --max-records N        Maximum records to scrape
#   --test                 Run in test mode
#   --date-from YYYY-MM-DD Start date
#   --date-to YYYY-MM-DD   End date
#   --search-terms TERM    Search terms (multiple allowed)
#   --headless/--no-headless Browser mode
```

### Management
```bash
# List configurations
scraper_cli.py list-configs

# Generate Python scraper
scraper_cli.py generate <config_file> --template advanced
```

## 🔧 Advanced Usage

### Custom Scrapers

Extend the base scrapers for specialized needs:

```python
from base_scrapers import SearchFormScraper
from config_schemas import CountyConfig

class CustomCountyScraper(SearchFormScraper):
    async def handle_special_case(self):
        # Custom logic for specific county requirements
        pass
    
    async def extract_records_from_page(self):
        # Override default extraction
        records = await super().extract_records_from_page()
        # Add custom processing
        return self.process_custom_fields(records)
```

### Database Integration

```python
from scraper_factory import ScraperFactory
import asyncpg

async def scrape_to_database():
    factory = ScraperFactory()
    result = await factory.execute_scraping(config, task_params)
    
    # Save to database
    conn = await asyncpg.connect(database_url)
    for record in result.records:
        await conn.execute(
            "INSERT INTO county_records (...) VALUES (...)",
            *record.data.values()
        )
```

### Scheduled Scraping

```python
import asyncio
from datetime import datetime, timedelta

async def daily_scraper():
    """Run scraper daily for new records"""
    while True:
        today = datetime.now().strftime('%Y-%m-%d')
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        
        result = await factory.execute_scraping(config, {
            'date_range': {'from': yesterday, 'to': today},
            'max_records': 1000
        })
        
        print(f"Scraped {len(result.records)} new records")
        await asyncio.sleep(24 * 60 * 60)  # Wait 24 hours

# Run with: asyncio.run(daily_scraper())
```

## 🛡️ Best Practices

### Ethical Scraping
- Respect robots.txt files
- Use appropriate delays between requests
- Monitor rate limits and blocking
- Cache results to avoid repeated requests

### Error Handling
- Implement retry logic for network errors
- Handle dynamic content loading
- Validate extracted data
- Monitor for website changes

### Performance Optimization
- Use headless browsing when possible
- Minimize browser instances
- Implement connection pooling
- Cache session data

## 🔍 Troubleshooting

### Common Issues

**1. Selectors Not Working**
```bash
# Test with non-headless mode to see the page
scraper_cli.py run config.json --no-headless --test

# Generate new selectors with AI
python -c "
from scraper_factory import XPathGenerator
generator = XPathGenerator()
print(asyncio.run(generator.generate_xpath(html, 'field description')))
"
```

**2. Authentication Failures**
```bash
# Set credentials in environment
export SCRAPER_USERNAME="your_username"
export SCRAPER_PASSWORD="your_password"

# Or pass in task parameters
scraper_cli.py run config.json --username user --password pass
```

**3. Rate Limiting**
```json
// Increase delays in configuration
{
  "delay_between_requests": 5.0,
  "timeout": 60
}
```

### Debug Mode

Enable verbose logging:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📊 Examples

### Example: Brevard County (Static HTML)
```bash
# Analyze
scraper_cli.py analyze "https://vaclmweb1.brevardclerk.us/AcclaimWeb/search/SearchTypeDocType" \
  --county "Brevard County"

# Run
scraper_cli.py run configs/brevard_county.json \
  --date-from 2024-01-01 \
  --max-records 100
```

### Example: Hillsborough NH (Search Form)
```bash
# Analyze
scraper_cli.py analyze "https://ava.fidlar.com/NHHillsborough/AvaWeb/#/search" \
  --county "Hillsborough NH"

# Run with search terms
scraper_cli.py run configs/hillsborough_nh.json \
  --search-terms "foreclosure" "lis pendens" \
  --max-records 50
```

### Example: Authenticated Portal
```bash
# Create template for authenticated site
scraper_cli.py template --type authenticated \
  --county "Secure County" \
  --url "https://secure.county.gov/login"

# Customize auth_config in the generated file, then run:
scraper_cli.py run configs/secure_county.json
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

### Adding New Scraper Types

1. Create a new class in `base_scrapers.py`
2. Add the type to `ScraperType` enum in `config_schemas.py`
3. Register in the factory's `scrapers` dictionary
4. Add template in `config_schemas.py`

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

- Create an issue for bugs or feature requests
- Use the chat mode for AI assistance: `scraper_cli.py chat`
- Check existing configurations in the `configs/` directory for examples

---

**Happy Scraping! 🚀** 