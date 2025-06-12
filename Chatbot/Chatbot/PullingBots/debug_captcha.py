"""
Simple debug script to test HTML structure changes when clicking I Agree button
on Cobb GA captcha page
"""

import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

async def debug_html_changes():
    """Debug HTML changes when clicking I Agree button"""
    print("🚀 Starting Cobb GA HTML structure debug test...")
    
    # Launch browser
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False)  # Visible for debugging
    context = await browser.new_context()
    page = await context.new_page()
    
    try:
        # Navigate to Georgia Public Notice search page
        print("🌐 Navigating to Georgia Public Notice...")
        await page.goto("https://www.georgiapublicnotice.com/(S(tv0ve0wmyued4k422mekjrk1))/Search.aspx#searchResults")
        await page.wait_for_load_state("networkidle")
        
        print("⏳ Waiting 5 seconds for page to fully load...")
        await page.wait_for_timeout(5000)
        
        # Run a basic search to get to results/captcha
        print("🔍 Running search to trigger captcha...")
        
        # Select foreclosures
        foreclosure_js = """
        const dropdown = document.querySelector('[id*="ddlPopularSearches"]');
        if (dropdown) {
            dropdown.value = '16';
            dropdown.dispatchEvent(new Event('change', { bubbles: true }));
        }
        """
        await page.evaluate(foreclosure_js)
        await page.wait_for_timeout(2000)
        
        # Submit search
        search_js = """
        const searchBtn = document.querySelector('[id*="btnGo"]') || document.querySelector('[id*="btnSearch"]');
        if (searchBtn) {
            searchBtn.click();
        }
        """
        await page.evaluate(search_js)
        await page.wait_for_timeout(8000)
        
        print("📸 Taking initial screenshot...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        initial_screenshot = Path("data") / f"debug_initial_{timestamp}.png"
        await page.screenshot(path=initial_screenshot, full_page=True)
        print(f"✅ Initial screenshot: {initial_screenshot}")
        
        # Check for captcha
        print("🔒 Checking for captcha elements...")
        captcha_check_js = """
        (() => {
            return {
                has_recaptcha: !!document.querySelector('[data-sitekey], .g-recaptcha'),
                has_agree_button: !!document.querySelector('input[value*="I Agree" i]'),
                agree_button_name: document.querySelector('input[name*="btnViewNotice"]') ? 
                                  document.querySelector('input[name*="btnViewNotice"]').name : null,
                recaptcha_response_length: document.querySelector('textarea[name="g-recaptcha-response"]') ? 
                                         document.querySelector('textarea[name="g-recaptcha-response"]').value.length : 0,
                url: window.location.href
            };
        })()
        """
        
        captcha_info = await page.evaluate(captcha_check_js)
        print(f"🔍 Captcha check: {captcha_info}")
        
        if captcha_info['has_agree_button']:
            print("🎯 Found I Agree button! Starting HTML structure monitoring...")
            
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
                    agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length,
                    specific_elements: {
                        recaptcha_panel: !!document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha'),
                        agree_button: !!document.querySelector('input[name*="btnViewNotice"]'),
                        viewstate: !!document.querySelector('input[name="__VIEWSTATE"]'),
                        eventvalidation: !!document.querySelector('input[name="__EVENTVALIDATION"]')
                    }
                };
            })()
            """
            
            initial_state = await page.evaluate(initial_state_js)
            print("\n📊 INITIAL HTML STATE:")
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
                    errors: []
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
            print("✅ DOM mutation observer set up")
            
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
            print("✅ Network monitoring set up")
            
            print("\n🔥 MANUAL INTERVENTION REQUIRED:")
            print("   1. Please manually solve the reCAPTCHA challenge if present")
            print("   2. Then click the 'I Agree, View Notice' button")
            print("   3. The script will monitor HTML changes for 30 seconds")
            print("   4. Press Enter when you're ready to start monitoring...")
            
            input("Press Enter to start monitoring...")
            
            print("🎯 MONITORING STARTED - Click 'I Agree, View Notice' button now!")
            print("⏳ Monitoring for 30 seconds...")
            
            # Monitor for 30 seconds
            await page.wait_for_timeout(30000)
            
            # Capture final state
            final_state_js = """
            (() => {
                const finalState = {
                    url: window.location.href,
                    title: document.title,
                    html_length: document.documentElement.outerHTML.length,
                    body_text_length: document.body.textContent.length,
                    form_count: document.querySelectorAll('form').length,
                    input_count: document.querySelectorAll('input').length,
                    button_count: document.querySelectorAll('button, input[type="submit"], input[type="button"]').length,
                    captcha_elements: document.querySelectorAll('[data-sitekey], .g-recaptcha').length,
                    agree_buttons: document.querySelectorAll('input[value*="I Agree" i]').length,
                    specific_elements: {
                        recaptcha_panel: !!document.querySelector('#ctl00_ContentPlaceHolder1_PublicNoticeDetailsBody1_pnlRecaptcha'),
                        agree_button: !!document.querySelector('input[name*="btnViewNotice"]'),
                        viewstate: !!document.querySelector('input[name="__VIEWSTATE"]'),
                        eventvalidation: !!document.querySelector('input[name="__EVENTVALIDATION"]')
                    },
                    changes_detected: window.debugData
                };
                
                return finalState;
            })()
            """
            
            final_state = await page.evaluate(final_state_js)
            
            # Take final screenshot
            final_screenshot = Path("data") / f"debug_final_{timestamp}.png"
            await page.screenshot(path=final_screenshot, full_page=True)
            print(f"📸 Final screenshot: {final_screenshot}")
            
            # Analyze changes
            print("\n🔄 ANALYZING HTML CHANGES:")
            
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
            
            print("📊 DETECTED CHANGES:")
            print(f"   • URL changed: {changes['url_changed']}")
            if changes['url_changed']:
                print(f"     OLD: {initial_state['url'][:100]}...")
                print(f"     NEW: {final_state['url'][:100]}...")
            
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
            
            # Log specific element changes
            print("\n🔍 SPECIFIC ELEMENT CHANGES:")
            for key, value in initial_state['specific_elements'].items():
                final_value = final_state['specific_elements'][key]
                if value != final_value:
                    print(f"   • {key}: {value} → {final_value}")
                else:
                    print(f"   • {key}: {value} (no change)")
            
            # Log DOM mutations
            mutations = final_state['changes_detected']['mutations']
            print(f"\n🔄 DOM MUTATIONS: {len(mutations)} detected")
            for mutation in mutations[-20:]:  # Last 20 mutations
                print(f"   • {mutation['type']} on {mutation['target']} at {mutation['timestamp'][-12:-4]}")
                if mutation.get('addedNodes', 0) > 0:
                    print(f"     Added {mutation['addedNodes']} nodes")
                if mutation.get('removedNodes', 0) > 0:
                    print(f"     Removed {mutation['removedNodes']} nodes")
                if mutation.get('attributeName'):
                    print(f"     Attribute changed: {mutation['attributeName']}")
            
            # Log errors
            errors = final_state['changes_detected']['errors']
            if errors:
                print(f"\n❌ JAVASCRIPT ERRORS: {len(errors)}")
                for error in errors[-5:]:
                    print(f"   • {error['message']} at {error.get('filename', 'unknown')}:{error.get('lineno', '?')}")
            
            # Log network activity
            print(f"\n🌐 NETWORK ACTIVITY: {len(network_requests)} requests/responses")
            for req in network_requests[-10:]:  # Last 10 network events
                if req['type'] == 'request':
                    print(f"   → {req['method']} {req['url'][:100]}...")
                else:
                    print(f"   ← {req['status']} {req['url'][:100]}...")
            
            # Summary
            print("\n📋 SUMMARY:")
            if any(changes.values()):
                print("   ✅ HTML structure changes were detected!")
                print("   🔍 This suggests the button click is having some effect")
                if changes['url_changed']:
                    print("   🚀 Page navigation occurred - this is a good sign!")
                if changes['html_length_diff'] != 0:
                    print(f"   📏 HTML content changed by {changes['html_length_diff']} characters")
                if len(mutations) > 0:
                    print(f"   🔄 {len(mutations)} DOM mutations detected")
                if len(network_requests) > 0:
                    print(f"   🌐 {len(network_requests)} network requests made")
            else:
                print("   ❌ No HTML structure changes detected")
                print("   🚫 The button click may not be working properly")
                print("   🔍 Check if reCAPTCHA was solved correctly")
                
        else:
            print("⚠️ No I Agree button found - may not have reached captcha page")
            
    except Exception as e:
        print(f"❌ Error during debugging: {e}")
        
    finally:
        print("\n🎯 Closing browser...")
        await browser.close()
        await playwright.stop()
        print("✅ Debug session complete!")

if __name__ == "__main__":
    asyncio.run(debug_html_changes()) 