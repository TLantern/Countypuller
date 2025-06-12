#!/usr/bin/env python3
"""
🔍 Page Loading Debug Script for Georgia Public Notice
Run this to get detailed insights into what's preventing the page from fully loading
"""

import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime

async def debug_page_loading():
    """Debug the Georgia Public Notice page loading issues"""
    print("🚀 Starting Georgia Public Notice loading debug...")
    
    async with async_playwright() as p:
        # Launch browser with debugging enabled
        browser = await p.chromium.launch(
            headless=False,  # Show browser for visual debugging
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-first-run',
                '--disable-default-apps',
                '--disable-dev-shm-usage',
                '--disable-extensions',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--enable-logging',
                '--log-level=0'
            ]
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        page = await context.new_page()
        
        # Enable console logging
        page.on("console", lambda msg: print(f"🖥️ CONSOLE: {msg.text}"))
        page.on("pageerror", lambda err: print(f"❌ PAGE ERROR: {err}"))
        page.on("requestfailed", lambda req: print(f"📡 REQUEST FAILED: {req.url} - {req.failure}"))
        
        # Track network requests
        requests_started = []
        requests_finished = []
        
        def on_request(request):
            requests_started.append({
                'url': request.url,
                'method': request.method,
                'timestamp': datetime.now().isoformat(),
                'resource_type': request.resource_type
            })
            print(f"📤 REQUEST START: {request.method} {request.url}")
        
        def on_response(response):
            requests_finished.append({
                'url': response.url,
                'status': response.status,
                'timestamp': datetime.now().isoformat()
            })
            if response.status >= 400:
                print(f"⚠️ REQUEST ERROR: {response.status} {response.url}")
            else:
                print(f"📥 REQUEST COMPLETE: {response.status} {response.url}")
        
        page.on("request", on_request)
        page.on("response", on_response)
        
        try:
            print("🌐 Navigating to Georgia Public Notice...")
            await page.goto('https://www.georgiapublicnotice.com/Search.aspx', timeout=30000)
            await page.wait_for_load_state('domcontentloaded', timeout=15000)
            
            print("✅ Initial navigation complete")
            
            # Run the comprehensive debug script
            print("🔍 Running comprehensive loading analysis...")
            with open('debug_network_loading.js', 'r') as f:
                debug_script = f.read()
            
            await page.evaluate(debug_script)
            print("✅ Debug script injected - check browser console for detailed analysis")
            
            # Wait and monitor for 30 seconds
            print("⏳ Monitoring for 30 seconds...")
            for i in range(6):  # 6 x 5 seconds = 30 seconds
                await asyncio.sleep(5)
                
                # Check current status
                status = await page.evaluate("""
                () => {
                    return {
                        readyState: document.readyState,
                        activeImages: Array.from(document.querySelectorAll('img')).filter(img => !img.complete).length,
                        activeScripts: Array.from(document.querySelectorAll('script[src]')).filter(script => 
                            script.readyState && script.readyState !== 'complete').length,
                        timestamp: new Date().toISOString(),
                        url: window.location.href.substring(0, 100)
                    }
                }
                """)
                
                print(f"📊 Status check {i+1}/6: {status}")
                
                # Call the debug function we injected
                debug_result = await page.evaluate("window.debugLoadingStatus()")
                print(f"🔍 Debug result {i+1}/6: Pending resources: {len(debug_result.get('resourceAnalysis', {}).get('pendingResources', []))}")
            
            # Final comprehensive report
            print("\n📋 FINAL COMPREHENSIVE REPORT:")
            print("=" * 50)
            
            final_debug = await page.evaluate("window.debugLoadingStatus()")
            
            print(f"📊 Resource Analysis:")
            resource_analysis = final_debug.get('resourceAnalysis', {})
            print(f"  - Images: {resource_analysis.get('totalImages', 0)} total, {resource_analysis.get('loadingImages', 0)} still loading")
            print(f"  - Scripts: {resource_analysis.get('totalScripts', 0)} total, {resource_analysis.get('loadingScripts', 0)} still loading")
            print(f"  - Stylesheets: {resource_analysis.get('totalStylesheets', 0)} total, {resource_analysis.get('loadingStylesheets', 0)} still loading")
            print(f"  - Iframes: {resource_analysis.get('totalIframes', 0)} total, {resource_analysis.get('loadingIframes', 0)} still loading")
            
            print(f"\n🏛️ ASP.NET Analysis:")
            aspnet_analysis = final_debug.get('aspNetAnalysis', {})
            print(f"  - ViewState: {'✅' if aspnet_analysis.get('hasViewState') else '❌'} (Size: {aspnet_analysis.get('viewStateSize', 0)} chars)")
            print(f"  - Script Manager: {'✅' if aspnet_analysis.get('hasScriptManager') else '❌'}")
            print(f"  - Update Panels: {aspnet_analysis.get('hasUpdatePanels', 0)}")
            print(f"  - AJAX Framework: {'✅' if aspnet_analysis.get('hasAjaxFramework') else '❌'}")
            
            print(f"\n📡 Network Activity:")
            print(f"  - Active AJAX/Fetch requests: {final_debug.get('activeRequests', 0)}")
            print(f"  - Total requests started: {len(requests_started)}")
            print(f"  - Total requests finished: {len(requests_finished)}")
            print(f"  - Pending requests: {len(requests_started) - len(requests_finished)}")
            
            # Show pending resources
            pending_resources = resource_analysis.get('pendingResources', [])
            if pending_resources:
                print(f"\n⚠️ PENDING RESOURCES ({len(pending_resources)}):")
                for i, resource in enumerate(pending_resources[:10]):  # Show first 10
                    print(f"  {i+1}. {resource.get('type', 'unknown')}: {resource.get('src', resource.get('href', 'unknown'))[:80]}")
                if len(pending_resources) > 10:
                    print(f"  ... and {len(pending_resources) - 10} more")
            
            # Show recent requests
            recent_requests = final_debug.get('requestLog', [])
            if recent_requests:
                print(f"\n📡 RECENT REQUESTS ({len(recent_requests)}):")
                for i, request in enumerate(recent_requests[-5:]):  # Show last 5
                    print(f"  {i+1}. {request.get('type', 'unknown')} {request.get('method', '')} {request.get('url', '')[:60]}")
            
            # Save detailed debug info
            debug_file = f"debug_loading_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(debug_file, 'w') as f:
                json.dump({
                    'final_debug': final_debug,
                    'requests_started': requests_started,
                    'requests_finished': requests_finished,
                    'timestamp': datetime.now().isoformat()
                }, f, indent=2)
            
            print(f"\n💾 Detailed debug info saved to: {debug_file}")
            print("\n🎯 RECOMMENDATIONS:")
            
            # Provide recommendations based on findings
            if resource_analysis.get('loadingImages', 0) > 0:
                print("  - Images are still loading - consider blocking image loading or increasing timeout")
            
            if resource_analysis.get('loadingScripts', 0) > 0:
                print("  - Scripts are still loading - may be analytics or tracking scripts")
            
            if aspnet_analysis.get('hasAjaxFramework'):
                print("  - ASP.NET AJAX framework is active - may be doing background updates")
            
            if len(requests_started) > len(requests_finished):
                print(f"  - {len(requests_started) - len(requests_finished)} requests are still pending")
            
            if aspnet_analysis.get('hasUpdatePanels', 0) > 0:
                print("  - ASP.NET UpdatePanels detected - may be continuously updating")
            
            print("\n✅ Debug analysis complete!")
            print("💡 Check the browser console for real-time monitoring")
            print("💡 The browser will stay open for manual inspection")
            
            # Keep browser open for manual inspection
            input("\n⏸️ Press Enter to close browser and exit...")
            
        except Exception as e:
            print(f"❌ Debug failed: {e}")
            
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_page_loading()) 