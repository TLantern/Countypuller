import asyncio
import logging
from aspnet_scraper import AspNetSearchFormScraper
from lph_config import lph_config
from datetime import date, timedelta
import sys

# Set up detailed logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_task_params():
    # Flexible date range - accept from command line or use defaults
    if len(sys.argv) >= 3:
        date_from = sys.argv[1]  # Format: MM/DD/YYYY or YYYY-MM-DD
        date_to = sys.argv[2]    # Format: MM/DD/YYYY or YYYY-MM-DD
        
        # Convert to MM/DD/YYYY format for Harris County system
        if '-' in date_from:  # Convert YYYY-MM-DD to MM/DD/YYYY
            from datetime import datetime
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
            date_from = dt_from.strftime('%m/%d/%Y')
        if '-' in date_to:    # Convert YYYY-MM-DD to MM/DD/YYYY
            from datetime import datetime
            dt_to = datetime.strptime(date_to, '%Y-%m-%d')
            date_to = dt_to.strftime('%m/%d/%Y')
    else:
        # Default: Last 7 days (smaller range for debugging)
        today = date.today()
        seven_days_ago = today - timedelta(days=7)
        date_from = seven_days_ago.strftime('%m/%d/%Y')  # MM/DD/YYYY format
        date_to = today.strftime('%m/%d/%Y')              # MM/DD/YYYY format
    
    print(f"DEBUG: Using date range {date_from} to {date_to}")
    
    return {
        'date_range': {'from': date_from, 'to': date_to},
        'search_terms': ['L/P'],  # Instrument type for Lis Pendens
        'max_records': 50
    }

class DebugAspNetScraper(AspNetSearchFormScraper):
    """Debug version with extensive logging"""
    
    async def fill_search_form(self, task_params):
        """Debug version of form filling"""
        search_config = self.config.search_config
        
        print("DEBUG: Starting form fill process...")
        
        # Check if form exists
        form_elements = await self.page.query_selector_all("form")
        print(f"DEBUG: Found {len(form_elements)} forms on page")
        
        # Wait for form to be present
        try:
            await self.page.wait_for_selector(search_config.search_form_selector, timeout=10000)
            print(f"DEBUG: Form selector '{search_config.search_form_selector}' found")
        except Exception as e:
            print(f"DEBUG: Form selector '{search_config.search_form_selector}' not found: {e}")
            return
        
        # Wait for ASP.NET to fully load
        await self.page.wait_for_load_state('networkidle')
        await self.page.wait_for_timeout(2000)
        
        # Check and fill date fields
        date_range = task_params.get('date_range')
        if date_range:
            for field_name, selector in [('date_from', search_config.search_fields.get('date_from')), 
                                        ('date_to', search_config.search_fields.get('date_to'))]:
                if selector:
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            date_value = date_range.get('from' if field_name == 'date_from' else 'to', '')
                            await self.page.fill(selector, '')
                            await self.page.fill(selector, date_value)
                            print(f"DEBUG: Filled {field_name} with '{date_value}'")
                            await self.page.wait_for_timeout(500)
                        else:
                            print(f"DEBUG: {field_name} element not found with selector '{selector}'")
                    except Exception as e:
                        print(f"DEBUG: Error filling {field_name}: {e}")
        
        # Check and fill search terms
        search_terms = task_params.get('search_terms', [])
        if search_terms and 'search_term' in search_config.search_fields:
            selector = search_config.search_fields['search_term']
            try:
                element = await self.page.query_selector(selector)
                if element:
                    search_value = ' '.join(search_terms)
                    await self.page.fill(selector, '')
                    await self.page.fill(selector, search_value)
                    print(f"DEBUG: Filled search term with '{search_value}'")
                    await self.page.wait_for_timeout(500)
                else:
                    print(f"DEBUG: Search term element not found with selector '{selector}'")
            except Exception as e:
                print(f"DEBUG: Error filling search term: {e}")
    
    async def submit_search_form(self):
        """Debug version of form submission"""
        submit_selector = self.config.search_config.submit_button_selector
        print(f"DEBUG: Looking for submit button with selector '{submit_selector}'")
        
        try:
            submit_button = await self.page.query_selector(submit_selector)
            if submit_button:
                print("DEBUG: Submit button found, clicking...")
                await self.page.wait_for_load_state('networkidle')
                await submit_button.click()
                print("DEBUG: Submit button clicked")
                
                # Wait for AJAX response
                await self.page.wait_for_load_state('networkidle', timeout=30000)
                await self.page.wait_for_timeout(2000)
                print("DEBUG: Waited for page to load after submit")
            else:
                print(f"DEBUG: Submit button not found with selector '{submit_selector}'")
                # Try alternative selectors
                alt_selectors = ["input[type='submit']", "button[type='submit']", "*[onclick*='Search']"]
                for alt_sel in alt_selectors:
                    alt_button = await self.page.query_selector(alt_sel)
                    if alt_button:
                        print(f"DEBUG: Found alternative submit button: {alt_sel}")
                        await alt_button.click()
                        await self.page.wait_for_load_state('networkidle', timeout=30000)
                        break
        except Exception as e:
            print(f"DEBUG: Error submitting form: {e}")
    
    async def wait_for_search_results(self):
        """Debug version of waiting for results"""
        results_selector = self.config.search_config.results_container_selector
        print(f"DEBUG: Waiting for results container '{results_selector}'")
        
        try:
            await self.page.wait_for_selector(results_selector, timeout=30000)
            print("DEBUG: Results container found")
            
            # Check what's in the results container
            results_html = await self.page.inner_html(results_selector)
            print(f"DEBUG: Results container HTML length: {len(results_html)} characters")
            
            # Count rows
            rows = await self.page.query_selector_all(f"{results_selector} tr")
            print(f"DEBUG: Found {len(rows)} rows in results table")
            
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            await self.page.wait_for_timeout(3000)
            
        except Exception as e:
            print(f"DEBUG: Error waiting for results: {e}")
            # Take screenshot for debugging
            await self.page.screenshot(path="debug_after_submit.png")
            print("DEBUG: Screenshot saved as debug_after_submit.png")

async def main():
    task_params = get_task_params()
    async with DebugAspNetScraper(lph_config) as scraper:
        result = await scraper.scrape(task_params)
        if result.success:
            print(f"Scraped {len(result.records)} records from {result.total_pages_scraped} pages.")
            for i, rec in enumerate(result.records[:5]):  # Show first 5 records
                print(f"Record {i+1}: {rec.data}")
        else:
            print(f"Scraping failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(main()) 