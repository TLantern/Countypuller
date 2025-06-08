"""
Debug script for Harris County Lis Pendens film code extraction
This script will help identify why film code URLs are missing
"""

import asyncio
import sys
from pathlib import Path
from playwright.async_api import async_playwright

# Add the PullingBots directory to sys.path to import our modules
sys.path.append(str(Path(__file__).parent))

from aspnet_scraper import AspNetSearchFormScraper
from lph_config import lph_config

async def debug_film_code_extraction():
    """Debug the film code URL extraction process"""
    
    print("🔍 Starting Harris County film code extraction debug...")
    
    # Create scraper instance
    scraper = AspNetSearchFormScraper(lph_config)
    
    try:
        # Start browser
        await scraper.start_browser()
        
        # Navigate to the search page
        print("📖 Navigating to Harris County search page...")
        await scraper.page.goto(lph_config.base_url)
        
        # Wait for page to load
        await scraper.page.wait_for_load_state('networkidle')
        await scraper.page.wait_for_timeout(3000)
        
        # Fill search form with a small date range to get some results
        print("📝 Filling search form...")
        task_params = {
            'date_range': {
                'from': '01/01/2024',
                'to': '01/07/2024'  # Small range for testing
            },
            'search_terms': ['L/P']  # Looking for Lis Pendens
        }
        
        await scraper.fill_search_form(task_params)
        await scraper.submit_search_form()
        await scraper.wait_for_search_results()
        
        print("🔍 Analyzing search results structure...")
        
        # Get the results container
        results_container = lph_config.search_config.results_container_selector
        print(f"Results container selector: {results_container}")
        
        # Check if results container exists
        container = await scraper.page.query_selector(results_container)
        if not container:
            print("❌ Results container not found!")
            
            # Try alternative selectors
            alt_selectors = [
                "table",
                "#itemPlaceholderContainer",
                "tbody",
                ".results-table",
                "[id*='results']"
            ]
            
            for alt_selector in alt_selectors:
                alt_container = await scraper.page.query_selector(alt_selector)
                if alt_container:
                    print(f"✅ Found alternative container: {alt_selector}")
                    container = alt_container
                    break
        else:
            print("✅ Results container found!")
        
        if not container:
            print("❌ No results container found with any selector")
            return
        
        # Get all rows using odd/even classes
        rows = await container.query_selector_all("tr.odd, tr.even")
        print(f"📊 Found {len(rows)} data rows (odd/even) in results")
        
        if len(rows) == 0:
            print("❌ No rows found in results container")
            return
        
        # Analyze first few rows (limit for testing)
        for i, row in enumerate(rows[:3]):  # Check first 3 rows
            print(f"\n🔍 Analyzing Row {i+1}:")
            
            # Get all cells
            cells = await row.query_selector_all("td, th")
            print(f"   Cells: {len(cells)}")
            
            for j, cell in enumerate(cells):
                cell_text = await cell.text_content()
                cell_html = await cell.inner_html()
                print(f"   Cell {j+1}: '{cell_text.strip()[:50]}...'")
                
                # Check for links in this cell
                links = await cell.query_selector_all("a")
                if links:
                    print(f"   └─ Found {len(links)} links in cell {j+1}")
                    for k, link in enumerate(links):
                        href = await link.get_attribute("href")
                        link_text = await link.text_content()
                        print(f"      Link {k+1}: href='{href}', text='{link_text.strip()}'")
            
            # Special focus on last cell (where film code should be)
            last_cell = await row.query_selector("td:last-child")
            if last_cell:
                print(f"   📎 Last cell analysis:")
                last_cell_html = await last_cell.inner_html()
                last_cell_text = await last_cell.text_content()
                print(f"      HTML: {last_cell_html}")
                print(f"      Text: '{last_cell_text.strip()}'")
                
                # Check for film code patterns
                film_patterns = [
                    "RP-",
                    "film",
                    "Film",
                    "FILM",
                    "ViewFilmPrint",
                    ".pdf",
                    "view",
                    "View"
                ]
                
                for pattern in film_patterns:
                    if pattern in last_cell_html or pattern in last_cell_text:
                        print(f"      🎯 Found pattern '{pattern}' in last cell!")
        
        # Test the actual extraction method
        print(f"\n🧪 Testing actual extraction method...")
        results = await scraper.extract_search_results()
        
        print(f"📊 Extraction Results:")
        print(f"   Total records extracted: {len(results)}")
        
        for i, record in enumerate(results[:3]):  # Show first 3 records
            print(f"   Record {i+1}:")
            for key, value in record.items():
                print(f"      {key}: {value}")
            print()
        
        # Count how many records have film_code_url
        records_with_film = [r for r in results if r.get('film_code_url')]
        print(f"   Records with film_code_url: {len(records_with_film)}/{len(results)}")
        
        if len(records_with_film) < len(results):
            print(f"   ⚠️  Missing film_code_url in {len(results) - len(records_with_film)} records")
        
    except Exception as e:
        print(f"❌ Error during debug: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        await scraper.close_browser()
        print("🏁 Debug complete!")

if __name__ == "__main__":
    asyncio.run(debug_film_code_extraction()) 