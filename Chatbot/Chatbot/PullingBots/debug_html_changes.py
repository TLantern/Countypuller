"""
Debug script to monitor HTML structure changes when clicking I Agree button
"""

import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

async def debug_html_changes():
    """Debug HTML changes when clicking I Agree button"""
    print("🚀 Starting Cobb GA HTML structure debug test...")
    
    # Create data directory
    Path("data").mkdir(exist_ok=True)
    
    # Launch browser
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        # Navigate to Georgia Public Notice search page
        print("🌐 Navigating to Georgia Public Notice...")
        await page.goto("https://www.georgiapublicnotice.com")
        await page.wait_for_load_state("networkidle")
        
        print("⏳ Waiting 5 seconds for page to fully load...")
        await page.wait_for_timeout(5000)
        
        # Take initial screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        initial_screenshot = Path("data") / f"debug_initial_{timestamp}.png"
        await page.screenshot(path=initial_screenshot, full_page=True)
        print(f"📸 Initial screenshot: {initial_screenshot}")
        
        print("\n🔍 MANUAL NAVIGATION REQUIRED:")
        print("   1. Please navigate to a foreclosure notice that shows the captcha")
        print("   2. Solve the reCAPTCHA if present")
        print("   3. When ready to test the 'I Agree' button, press Enter...")
        
        input("\nPress Enter when you're on the captcha page...")
        
        # Check current page state
        captcha_check_js = """
        (() => {
            return {
                has_recaptcha: !!document.querySelector('[data-sitekey], .g-recaptcha'),
                has_agree_button: !!document.querySelector('input[value*="I Agree" i], input[name*="btnViewNotice"]'),
                agree_button_details: (() => {
                    const btn = document.querySelector('input[value*="I Agree" i], input[name*="btnViewNotice"]');
                    return btn ? {
                        name: btn.name,
                        value: btn.value,
                        id: btn.id,
                        disabled: btn.disabled
                    } : null;
                })(),
                recaptcha_solved: (() => {
                    const response = document.querySelector('textarea[name="g-recaptcha-response"]');
                    return response ? response.value.length > 0 : false;
                })(),
                url: window.location.href
            };
        })()
        """
        
        captcha_info = await page.evaluate(captcha_check_js)
        print("\n🔍 CURRENT PAGE STATE:")
        print(f"   • Has reCAPTCHA: {captcha_info['has_recaptcha']}")
        print(f"   • Has I Agree button: {captcha_info['has_agree_button']}")
        print(f"   • reCAPTCHA solved: {captcha_info['recaptcha_solved']}")
        print(f"   • Button details: {captcha_info['agree_button_details']}")
        print(f"   • URL: {captcha_info['url'][:100]}...")
        
        if not captcha_info['has_agree_button']:
            print("❌ No I Agree button found. Please navigate to a captcha page first.")
            return
        
        # Capture initial HTML state
        initial_state_js = """
        (() => {
            return {
                url: window.location.href,
                title: document.title,
                html_length: document.documentElement.outerHTML.length,
                body_text_length: document.body.textContent.length,
                form_count: document.querySelectorAll('form').length,
                input_count: document.querySelectorAll('input').length,
                button_count: document.querySelectorAll('button, input[type="submit"], input[type="button"]').length,
                captcha_elements: document.querySelectorAll('[data-sitekey], .g-recaptcha').length,
                agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length
            };
        })()
        """
        
        initial_state = await page.evaluate(initial_state_js)
        print("\n📊 INITIAL STATE CAPTURED:")
        print(f"   • URL: {initial_state['url'][:100]}...")
        print(f"   • HTML length: {initial_state['html_length']} chars")
        print(f"   • Body text length: {initial_state['body_text_length']} chars")
        print(f"   • Forms: {initial_state['form_count']}")
        print(f"   • Inputs: {initial_state['input_count']}")
        print(f"   • Buttons: {initial_state['button_count']}")
        print(f"   • Captcha elements: {initial_state['captcha_elements']}")
        print(f"   • Agree buttons: {initial_state['agree_buttons']}")
        
        # Set up DOM mutation observer
        setup_observer_js = """
        (() => {
            window.debugData = {
                mutations: [],
                errors: [],
                clicks: []
            };
            
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    window.debugData.mutations.push({
                        type: mutation.type,
                        target: mutation.target.tagName + (mutation.target.id ? '#' + mutation.target.id : ''),
                        addedNodes: mutation.addedNodes.length,
                        removedNodes: mutation.removedNodes.length,
                        attributeName: mutation.attributeName,
                        timestamp: new Date().toISOString()
                    });
                });
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                characterData: true
            });
            
            // Monitor all clicks
            document.addEventListener('click', (e) => {
                window.debugData.clicks.push({
                    timestamp: new Date().toISOString(),
                    target: e.target.tagName + '#' + (e.target.id || e.target.name || 'no-id'),
                    target_value: e.target.value || '',
                    event_type: 'click'
                });
            });
            
            window.addEventListener('error', (e) => {
                window.debugData.errors.push({
                    message: e.message,
                    filename: e.filename,
                    lineno: e.lineno,
                    timestamp: new Date().toISOString()
                });
            });
            
            return 'observer_setup_complete';
        })()
        """
        
        await page.evaluate(setup_observer_js)
        print("✅ DOM mutation observer active")
        
        # Set up network monitoring
        network_requests = []
        
        def handle_request(request):
            network_requests.append({
                'url': request.url,
                'method': request.method,
                'timestamp': datetime.now().isoformat(),
                'type': 'request'
            })
        
        def handle_response(response):
            network_requests.append({
                'url': response.url,
                'status': response.status,
                'timestamp': datetime.now().isoformat(),
                'type': 'response'
            })
        
        page.on('request', handle_request)
        page.on('response', handle_response)
        print("✅ Network monitoring active")
        
        print("\n🎯 READY FOR BUTTON CLICK TEST:")
        print("   • Now click the 'I Agree, View Notice' button")
        print("   • Monitoring will run for 30 seconds")
        print("   • Watch for real-time change detection below...")
        
        input("\nPress Enter to start 30-second monitoring period...")
        
        print("\n🔴 MONITORING ACTIVE - CLICK THE BUTTON NOW!")
        
        # Monitor for 30 seconds with periodic updates
        for i in range(30):
            await page.wait_for_timeout(1000)
            
            # Check for changes every 5 seconds
            if i % 5 == 0 and i > 0:
                current_mutations = await page.evaluate("window.debugData.mutations.length")
                current_clicks = await page.evaluate("window.debugData.clicks.length")
                current_network = len(network_requests)
                print(f"   ⏱️ {i}s: {current_mutations} mutations, {current_clicks} clicks, {current_network} network events")
        
        print("\n⏹️ Monitoring complete. Analyzing results...")
        
        # Capture final state
        final_state_js = """
        (() => {
            return {
                url: window.location.href,
                title: document.title,
                html_length: document.documentElement.outerHTML.length,
                body_text_length: document.body.textContent.length,
                form_count: document.querySelectorAll('form').length,
                input_count: document.querySelectorAll('input').length,
                button_count: document.querySelectorAll('button, input[type="submit"], input[type="button"]').length,
                captcha_elements: document.querySelectorAll('[data-sitekey], .g-recaptcha').length,
                agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length,
                changes_detected: window.debugData
            };
        })()
        """
        
        final_state = await page.evaluate(final_state_js)
        
        # Take final screenshot
        final_screenshot = Path("data") / f"debug_final_{timestamp}.png"
        await page.screenshot(path=final_screenshot, full_page=True)
        print(f"📸 Final screenshot: {final_screenshot}")
        
        # Detailed analysis
        print("\n📊 COMPREHENSIVE CHANGE ANALYSIS:")
        
        changes = {
            'url_changed': initial_state['url'] != final_state['url'],
            'title_changed': initial_state['title'] != final_state['title'],
            'html_length_diff': final_state['html_length'] - initial_state['html_length'],
            'body_text_diff': final_state['body_text_length'] - initial_state['body_text_length'],
            'form_count_diff': final_state['form_count'] - initial_state['form_count'],
            'input_count_diff': final_state['input_count'] - initial_state['input_count'],
            'button_count_diff': final_state['button_count'] - initial_state['button_count'],
            'captcha_elements_diff': final_state['captcha_elements'] - initial_state['captcha_elements'],
            'agree_buttons_diff': final_state['agree_buttons'] - initial_state['agree_buttons']
        }
        
        print("🔄 PAGE STRUCTURE CHANGES:")
        print(f"   • URL changed: {changes['url_changed']}")
        if changes['url_changed']:
            print(f"     OLD: {initial_state['url']}")
            print(f"     NEW: {final_state['url']}")
        
        print(f"   • Title changed: {changes['title_changed']}")
        if changes['title_changed']:
            print(f"     OLD: {initial_state['title']}")
            print(f"     NEW: {final_state['title']}")
        
        print(f"   • HTML length change: {changes['html_length_diff']} chars")
        print(f"   • Body text change: {changes['body_text_diff']} chars")
        print(f"   • Form count change: {changes['form_count_diff']}")
        print(f"   • Input count change: {changes['input_count_diff']}")
        print(f"   • Button count change: {changes['button_count_diff']}")
        print(f"   • Captcha elements change: {changes['captcha_elements_diff']}")
        print(f"   • Agree buttons change: {changes['agree_buttons_diff']}")
        
        # Detailed event analysis
        mutations = final_state['changes_detected']['mutations']
        clicks = final_state['changes_detected']['clicks']
        errors = final_state['changes_detected']['errors']
        
        print(f"\n🔄 DOM MUTATIONS: {len(mutations)} total")
        if mutations:
            print("   Recent mutations:")
            for mutation in mutations[-10:]:
                print(f"     • {mutation['type']} on {mutation['target']} at {mutation['timestamp'][-12:-4]}")
                if mutation.get('addedNodes', 0) > 0:
                    print(f"       ➕ Added {mutation['addedNodes']} nodes")
                if mutation.get('removedNodes', 0) > 0:
                    print(f"       ➖ Removed {mutation['removedNodes']} nodes")
        
        print(f"\n🖱️ CLICK EVENTS: {len(clicks)} total")
        if clicks:
            for click in clicks:
                print(f"   • {click['event_type']} on {click['target']} ({click['target_value']}) at {click['timestamp'][-12:-4]}")
        
        if errors:
            print(f"\n❌ JAVASCRIPT ERRORS: {len(errors)}")
            for error in errors:
                print(f"   • {error['message']} at {error.get('filename', 'unknown')}:{error.get('lineno', '?')}")
        
        print(f"\n🌐 NETWORK ACTIVITY: {len(network_requests)} events")
        if network_requests:
            print("   Recent network activity:")
            for req in network_requests[-10:]:
                if req['type'] == 'request':
                    print(f"     → {req['method']} {req['url'][:80]}...")
                else:
                    print(f"     ← {req['status']} {req['url'][:80]}...")
        
        # Final verdict
        print("\n🎯 FINAL VERDICT:")
        significant_changes = (
            changes['url_changed'] or 
            abs(changes['html_length_diff']) > 100 or 
            len(mutations) > 5 or 
            len(network_requests) > 2 or
            len(clicks) > 0
        )
        
        if significant_changes:
            print("   ✅ SIGNIFICANT ACTIVITY DETECTED!")
            print("   🎯 The button appears to be responsive")
            if changes['url_changed']:
                print("   🚀 Navigation occurred - button worked!")
            elif len(mutations) > 5:
                print("   🔄 Major DOM changes - page is reacting")
            elif len(network_requests) > 2:
                print("   🌐 Network activity - requests being sent")
            elif len(clicks) > 0:
                print("   🖱️ Click events detected - button is clickable")
        else:
            print("   ❌ MINIMAL OR NO ACTIVITY DETECTED")
            print("   🚫 Possible issues:")
            print("      • Button may not be properly enabled")
            print("      • reCAPTCHA validation may be failing")
            print("      • JavaScript errors preventing submission")
            print("      • Button click not registering")
            
        print(f"\n📁 Screenshots saved:")
        print(f"   • Initial: {initial_screenshot}")
        print(f"   • Final: {final_screenshot}")
        
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n🎯 Closing browser...")
        await browser.close()
        await playwright.stop()
        print("✅ Debug session complete!")

if __name__ == "__main__":
    asyncio.run(debug_html_changes()) 