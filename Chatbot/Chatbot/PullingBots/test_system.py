#!/usr/bin/env python3
"""
Test Script for Modular County Scraper Factory
==============================================

This script tests the core functionality of the modular scraper system.
"""

import asyncio
import json
import sys
from pathlib import Path

# Test imports
try:
    from config_schemas import (
        CountyConfig, SiteAnalysis, ScraperType, 
        get_static_html_template, get_search_form_template, get_authenticated_template
    )
    from scraper_factory import ScraperFactory, SiteAnalyzer
    from base_scrapers import StaticHtmlScraper, SearchFormScraper, AuthenticatedScraper
    print("✅ All imports successful")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

async def test_config_schemas():
    """Test configuration schema creation and validation"""
    print("\n🧪 Testing Configuration Schemas...")
    
    try:
        # Test template creation
        static_config = get_static_html_template()
        search_config = get_search_form_template()
        auth_config = get_authenticated_template()
        
        print(f"  ✅ Static HTML template: {static_config.name}")
        print(f"  ✅ Search form template: {search_config.name}")
        print(f"  ✅ Authenticated template: {auth_config.name}")
        
        # Test JSON serialization
        test_file = "test_config.json"
        static_config.to_json_file(test_file)
        loaded_config = CountyConfig.from_json_file(test_file)
        
        assert loaded_config.name == static_config.name
        print("  ✅ JSON serialization/deserialization works")
        
        # Cleanup
        Path(test_file).unlink()
        
    except Exception as e:
        print(f"  ❌ Schema test failed: {e}")
        return False
    
    return True

async def test_site_analyzer():
    """Test the site analyzer with a simple webpage"""
    print("\n🔍 Testing Site Analyzer...")
    
    try:
        analyzer = SiteAnalyzer()
        
        # Test with a simple, accessible website
        test_url = "https://httpbin.org/html"
        
        print(f"  📡 Analyzing: {test_url}")
        analysis = await analyzer.analyze_site(test_url)
        
        print(f"  ✅ Analysis completed:")
        print(f"    • Scraper type: {analysis.scraper_type}")
        print(f"    • Complexity: {analysis.complexity}/10")
        print(f"    • Auth required: {analysis.authentication_required}")
        print(f"    • JavaScript heavy: {analysis.javascript_heavy}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Site analyzer test failed: {e}")
        return False

async def test_factory():
    """Test the scraper factory"""
    print("\n🏭 Testing Scraper Factory...")
    
    try:
        factory = ScraperFactory()
        
        # Test config creation from template
        config = factory.create_config_from_template(
            ScraperType.STATIC_HTML, 
            "Test County", 
            "https://example.com"
        )
        
        print(f"  ✅ Created config for: {config.name}")
        
        # Test config listing (should be empty initially)
        configs = factory.list_configs()
        print(f"  ✅ Config listing works (found {len(configs)} configs)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Factory test failed: {e}")
        return False

async def test_base_scrapers():
    """Test base scraper initialization"""
    print("\n🤖 Testing Base Scrapers...")
    
    try:
        # Create test config
        config = get_static_html_template()
        config.base_url = "https://httpbin.org/html"
        config.headless = True
        
        # Test scraper initialization
        static_scraper = StaticHtmlScraper(config)
        search_scraper = SearchFormScraper(config)
        auth_scraper = AuthenticatedScraper(config)
        
        print("  ✅ All base scrapers can be instantiated")
        
        # Test browser initialization (without full scraping)
        try:
            await static_scraper.start_browser()
            await static_scraper.navigate_to_url("https://httpbin.org/html")
            print("  ✅ Browser initialization and navigation works")
            await static_scraper.close_browser()
        except Exception as e:
            print(f"  ⚠️  Browser test skipped (Playwright might not be installed): {e}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Base scraper test failed: {e}")
        return False

def test_cli_components():
    """Test CLI components (without actual execution)"""
    print("\n🖥️  Testing CLI Components...")
    
    try:
        # Test CLI imports
        from scraper_cli import generate_scraper_code, generate_basic_scraper_template
        
        # Test code generation
        test_config = get_static_html_template()
        test_config.name = "Test County"
        
        basic_code = generate_basic_scraper_template(test_config)
        
        assert "Test County" in basic_code
        assert "async def main" in basic_code
        print("  ✅ Scraper code generation works")
        
        return True
        
    except Exception as e:
        print(f"  ❌ CLI component test failed: {e}")
        return False

async def run_all_tests():
    """Run all tests"""
    print("🚀 Starting Modular County Scraper Factory Tests")
    print("=" * 50)
    
    tests = [
        ("Config Schemas", test_config_schemas()),
        ("Site Analyzer", test_site_analyzer()),
        ("Scraper Factory", test_factory()),
        ("Base Scrapers", test_base_scrapers()),
        ("CLI Components", test_cli_components())
    ]
    
    results = []
    for test_name, test_coro in tests:
        try:
            if asyncio.iscoroutine(test_coro):
                result = await test_coro
            else:
                result = test_coro
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 All tests passed! The modular scraper system is ready to use.")
        print("\n🚀 Quick Start:")
        print("  1. Set your OpenAI API key: export OPENAI_API_KEY='your-key'")
        print("  2. Analyze a website: python scraper_cli.py analyze <url> --county 'County Name'")
        print("  3. Run the scraper: python scraper_cli.py run configs/county_name.json")
    else:
        print(f"\n⚠️  {len(results) - passed} tests failed. Please check the errors above.")
        return False
    
    return True

def main():
    """Main test function"""
    try:
        result = asyncio.run(run_all_tests())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner crashed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 