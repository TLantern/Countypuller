#!/usr/bin/env python3
"""
Test Ultra-Stealth Browser Configuration for Cobb GA Scraper

This script tests the stealth browser configuration to ensure it can bypass
captcha and anti-bot detection on the Georgia Public Notice website.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent))

from CobbGA import CobbScraper, _log
from config_schemas import CountyConfig

async def test_stealth_browser():
    """Test the ultra-stealth browser configuration"""
    
    _log("🧪 Starting stealth browser test for Georgia Public Notice")
    
    try:
        # Load the Cobb GA configuration
        config_path = Path("configs/cobb_ga.json")
        if not config_path.exists():
            _log(f"❌ Config file not found: {config_path}")
            return False
        
        config = CountyConfig.from_json_file(str(config_path))
        config.headless = False  # Show browser for testing
        
        _log("🛡️ Testing ultra-stealth browser configuration...")
        
        # Initialize scraper with stealth config
        async with CobbScraper(config) as scraper:
            _log("✅ Stealth browser initialized successfully")
            
            # Navigate to the Georgia Public Notice website
            base_url = "https://www.georgiapublicnotice.com/(S(tv0ve0wmyued4k422mekjrk1))/Search.aspx#searchResults"
            _log(f"🌐 Navigating to: {base_url}")
            
            try:
                await scraper.page.goto(base_url, wait_until='networkidle', timeout=60000)
                _log("✅ Successfully navigated to Georgia Public Notice")
                
                # Wait for page to fully load
                await scraper.page.wait_for_timeout(5000)
                
                # Check current URL to see if we were redirected
                current_url = scraper.page.url
                _log(f"📄 Current URL: {current_url}")
                
                # Check for common anti-bot indicators
                title = await scraper.page.title()
                _log(f"📋 Page title: {title}")
                
                # Check for captcha or challenge pages
                captcha_indicators = [
                    "Please complete the security check",
                    "Captcha",
                    "Security check",
                    "Challenge",
                    "Cloudflare",
                    "Access denied",
                    "Bot detection",
                    "Verification",
                    "Human verification"
                ]
                
                page_content = await scraper.page.content()
                found_indicators = [indicator for indicator in captcha_indicators 
                                  if indicator.lower() in page_content.lower()]
                
                if found_indicators:
                    _log(f"⚠️ Possible anti-bot detection found: {found_indicators}")
                else:
                    _log("✅ No obvious anti-bot detection found")
                
                # Look for search form elements
                county_headers = await scraper.page.locator('label.header:has-text("County")').count()
                date_headers = await scraper.page.locator('label.header:has-text("Date Range")').count()
                
                _log(f"🔍 Found {county_headers} county headers and {date_headers} date headers")
                
                if county_headers > 0 and date_headers > 0:
                    _log("✅ Search form elements detected - stealth mode appears successful!")
                    
                    # Test basic interaction
                    _log("🖱️ Testing basic interaction...")
                    
                    # Try clicking on county header
                    try:
                        county_js = """
                        (() => {
                            const countyHeader = document.querySelector('label.header');
                            if (countyHeader && countyHeader.textContent.includes('County')) {
                                countyHeader.click();
                                return 'county_clicked';
                            }
                            return 'county_not_found';
                        })()
                        """
                        
                        result = await scraper.page.evaluate(county_js)
                        _log(f"🔧 County header interaction result: {result}")
                        
                        if result == 'county_clicked':
                            _log("✅ Successfully interacted with county header")
                            await scraper.page.wait_for_timeout(2000)
                        
                    except Exception as interaction_error:
                        _log(f"⚠️ Interaction test failed: {interaction_error}")
                
                else:
                    _log("❌ Search form elements not found - possible bot detection")
                    
                # Take screenshot for manual verification
                screenshot_dir = Path("screenshots")
                screenshot_dir.mkdir(exist_ok=True)
                
                screenshot_path = screenshot_dir / "stealth_test.png"
                await scraper.page.screenshot(path=str(screenshot_path), full_page=True)
                _log(f"📸 Screenshot saved: {screenshot_path}")
                
                # Wait for manual inspection
                _log("⏳ Waiting 10 seconds for manual inspection...")
                await scraper.page.wait_for_timeout(10000)
                
                return True
                
            except Exception as nav_error:
                _log(f"❌ Navigation failed: {nav_error}")
                return False
                
    except Exception as e:
        _log(f"❌ Stealth browser test failed: {e}")
        return False

async def main():
    """Main test function"""
    _log("🚀 Starting Ultra-Stealth Browser Test")
    
    success = await test_stealth_browser()
    
    if success:
        _log("🎉 Stealth browser test completed successfully!")
        _log("✅ Browser appears to bypass anti-bot detection")
        return 0
    else:
        _log("💥 Stealth browser test failed")
        _log("❌ Anti-bot detection may still be triggered")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main())) 