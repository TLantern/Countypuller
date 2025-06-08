import asyncio
import logging
from typing import Dict, Any, List
from base_scrapers import SearchFormScraper
from config_schemas import ScrapingResult

# Set up detailed logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Tesseract path
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

class AspNetSearchFormScraper(SearchFormScraper):
    """Enhanced scraper for ASP.NET AJAX applications like Harris County"""
    
    async def fill_search_form(self, task_params: Dict[str, Any]):
        """Enhanced form filling for ASP.NET applications"""
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
        
        # Wait for ASP.NET to fully load (important for AJAX apps)
        await self.page.wait_for_load_state('networkidle')
        await self.page.wait_for_timeout(2000)  # Additional wait for ASP.NET initialization
        
        # Fill date range if provided
        date_range = task_params.get('date_range')
        if date_range and 'date_from' in search_config.search_fields:
            date_from_selector = search_config.search_fields['date_from']
            date_to_selector = search_config.search_fields.get('date_to')
            
            # Clear and fill date fields
            if date_from_selector:
                try:
                    element = await self.page.query_selector(date_from_selector)
                    if element:
                        date_value = date_range.get('from', '')
                        await self.page.fill(date_from_selector, '')
                        await self.page.fill(date_from_selector, date_value)
                        print(f"DEBUG: Filled date_from with '{date_value}'")
                        await self.page.wait_for_timeout(500)
                    else:
                        print(f"DEBUG: date_from element not found with selector '{date_from_selector}'")
                except Exception as e:
                    print(f"DEBUG: Error filling date_from: {e}")
            
            if date_to_selector:
                try:
                    element = await self.page.query_selector(date_to_selector)
                    if element:
                        date_value = date_range.get('to', '')
                        await self.page.fill(date_to_selector, '')
                        await self.page.fill(date_to_selector, date_value)
                        print(f"DEBUG: Filled date_to with '{date_value}'")
                        await self.page.wait_for_timeout(500)
                    else:
                        print(f"DEBUG: date_to element not found with selector '{date_to_selector}'")
                except Exception as e:
                    print(f"DEBUG: Error filling date_to: {e}")
        
        # Fill search terms if provided
        search_terms = task_params.get('search_terms', [])
        if search_terms and 'search_term' in search_config.search_fields:
            search_term_selector = search_config.search_fields['search_term']
            try:
                element = await self.page.query_selector(search_term_selector)
                if element:
                    search_value = ' '.join(search_terms)
                    await self.page.fill(search_term_selector, '')
                    await self.page.fill(search_term_selector, search_value)
                    print(f"DEBUG: Filled search_term with '{search_value}'")
                    await self.page.wait_for_timeout(500)
                else:
                    print(f"DEBUG: search_term element not found with selector '{search_term_selector}'")
            except Exception as e:
                print(f"DEBUG: Error filling search_term: {e}")
        
        # Fill other form fields as configured
        for field_name, selector in search_config.search_fields.items():
            if field_name in task_params and field_name not in ['date_from', 'date_to', 'search_term']:
                await self.page.fill(selector, '')
                await self.page.fill(selector, str(task_params[field_name]))
                await self.page.wait_for_timeout(500)
    
    async def submit_search_form(self):
        """Enhanced form submission for ASP.NET AJAX"""
        submit_selector = self.config.search_config.submit_button_selector
        
        print("DEBUG: Attempting to submit search form...")
        
        # Check if submit button exists
        try:
            submit_element = await self.page.query_selector(submit_selector)
            if submit_element:
                print(f"DEBUG: Submit button found with selector '{submit_selector}'")
            else:
                print(f"DEBUG: Submit button NOT found with selector '{submit_selector}'")
                # Try alternative submit button selectors
                alt_selectors = [
                    "input[type='submit']",
                    "button[type='submit']",
                    "input[value*='Search']",
                    "*[id*='Search']",
                    "*[id*='Submit']",
                    "input[name*='btnSearch']"
                ]
                for alt_selector in alt_selectors:
                    try:
                        alt_element = await self.page.query_selector(alt_selector)
                        if alt_element:
                            print(f"DEBUG: Alternative submit button found: '{alt_selector}'")
                            submit_selector = alt_selector
                            break
                    except:
                        continue
        except Exception as e:
            print(f"DEBUG: Error checking submit button: {e}")
        
        # Wait for any ongoing AJAX requests to complete
        await self.page.wait_for_load_state('networkidle')
        
        try:
            # Click the search button and wait for AJAX response
            await self.page.click(submit_selector)
            print("DEBUG: Submit button clicked successfully")
        except Exception as e:
            print(f"DEBUG: Error clicking submit button: {e}")
            return
        
        # ASP.NET AJAX typically triggers multiple requests, so we wait longer
        print("DEBUG: Waiting for ASP.NET AJAX response...")
        try:
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            print("DEBUG: Network idle state reached")
        except Exception as e:
            print(f"DEBUG: Timeout waiting for network idle: {e}")
        
        # Additional wait for DOM updates
        await self.page.wait_for_timeout(2000)
        print("DEBUG: Form submission complete")
    
    async def wait_for_search_results(self):
        """Enhanced waiting for ASP.NET AJAX results"""
        results_selector = "table"  # Default fallback
        
        # Try different selectors to find results
        alt_selectors = [
            "#itemPlaceholderContainer",
            "table.table-condensed", 
            ".table-hover",
            "table", 
            "*[id*='results']"
        ]
        
        for alt_selector in alt_selectors:
            try:
                await self.page.wait_for_selector(alt_selector, timeout=5000)
                print(f"DEBUG: Results container found: '{alt_selector}'")
                results_selector = alt_selector
                break
            except:
                continue
        
        # Wait for network activity to settle (important for AJAX)
        print("DEBUG: Waiting for network to settle...")
        try:
            await self.page.wait_for_load_state('networkidle', timeout=30000)
            print("DEBUG: Network settled")
        except Exception as e:
            print(f"DEBUG: Network timeout: {e}")
        
        # Additional wait for any remaining DOM updates
        await self.page.wait_for_timeout(3000)
        
        # Check if results actually loaded by looking for data rows
        try:
            rows = await self.page.query_selector_all(f"{results_selector} tr")
            print(f"DEBUG: Found {len(rows)} table rows")
            if len(rows) <= 1:  # Only header row
                print("DEBUG: No data rows found, results may still be loading")
                await self.page.wait_for_timeout(5000)
                # Check again
                rows = await self.page.query_selector_all(f"{results_selector} tr")
                print(f"DEBUG: After additional wait, found {len(rows)} table rows")
        except Exception as e:
            print(f"DEBUG: Error checking for rows: {e}")
            
        # Check page content for debugging
        page_content = await self.page.content()
        if "no records" in page_content.lower() or "no results" in page_content.lower():
            print("DEBUG: Page indicates no records found")
        elif "search" in page_content.lower():
            print("DEBUG: Page still contains search form")
    
    async def handle_aspnet_postback(self):
        """Handle ASP.NET postback mechanisms if needed"""
        # This method can be extended to handle specific ASP.NET postback scenarios
        # such as UpdatePanels, ScriptManager, etc.
        pass
    
    async def extract_film_code_url_proven_method(self, row_element, case_number: str) -> str:
        """Extract film code URL using proven LpH.py logic"""
        try:
            print(f"DEBUG: Using proven method to find film code URL for case: {case_number}")
            
            # Find the last TD in the row which contains the case link (from LpH.py logic)
            all_tds = await row_element.query_selector_all("td")
            
            if len(all_tds) > 0:
                last_td = all_tds[-1]
                print(f"DEBUG: Found {len(all_tds)} TDs, checking last TD for film code link")
                
                # Use proven selectors from LpH.py
                case_link = await last_td.query_selector(
                    "a[id*='HyperLinkFCEC'], a[class='doclinks'], a[href*='fComm/ViewEdoc.aspx']"
                )
                
                if case_link:
                    case_url_rel = await case_link.get_attribute("href")
                    
                    if case_url_rel and not case_url_rel.startswith(('http://', 'https://')):
                        from urllib.parse import urljoin
                        case_url = urljoin(self.config.base_url, case_url_rel)
                        print(f"DEBUG: Converted relative URL to absolute: {case_url}")
                    else:
                        case_url = case_url_rel
                    
                    print(f"DEBUG: Found case URL for {case_number}: {case_url}")
                    return case_url
                    
                else:
                    # Fallback: check for film code text when no direct link (from LpH.py logic)
                    film_code_text = await last_td.inner_text()
                    
                    if "RP-" in film_code_text:
                        film_code = None
                        for line in film_code_text.split("\n"):
                            if line.strip().startswith("RP-"):
                                film_code = line.strip().split("</a>")[0].strip() if "</a>" in line else line.strip()
                                break
                        
                        if film_code:
                            print(f"DEBUG: Found film code in text: {film_code}, but no direct link")
                            return None
                        else:
                            print(f"DEBUG: No film code found in text for {case_number}")
                            return None
                    else:
                        print(f"DEBUG: No case link found in last TD for {case_number}")
                        return None
            else:
                print(f"DEBUG: No TD elements found for {case_number}")
                return None
                
        except Exception as e:
            print(f"DEBUG: Error in proven film code URL extraction: {e}")
            return None

    async def extract_address_from_document_proven_method(self, doc_id: str, doc_url: str) -> str:
        """Extract address from document using proven LpH.py logic"""
        try:
            print(f"DEBUG: Extracting address from document using proven method for {doc_id}")
            
            # Download/screenshot the document
            file_path = await self.download_or_screenshot_document(doc_url, doc_id)
            address = ""
            extracted_text = ""
            
            if file_path:
                if file_path.lower().endswith(('.png', '.jpg', '.jpeg')):
                    try:
                        # OCR the entire image
                        extracted_text = await self.ocr_region_from_image(file_path, doc_id)
                        print(f"DEBUG: [OCR OUTPUT for {doc_id}]\n{extracted_text[:500]}...\n---")
                    except Exception as e:
                        print(f"DEBUG: ❌ Error running OCR on screenshot: {e}")
                
                if extracted_text:
                    # Save detailed address extraction debug info
                    try:
                        from pathlib import Path
                        ocr_debug_dir = Path(__file__).parent / "ocr_text_debug"
                        ocr_debug_dir.mkdir(exist_ok=True)
                        
                        import asyncio
                        timestamp = int(asyncio.get_event_loop().time())
                        address_debug_filename = f"address_extraction_{doc_id}_{timestamp}.txt"
                        address_debug_path = ocr_debug_dir / address_debug_filename
                        
                        with open(address_debug_path, 'w', encoding='utf-8') as f:
                            f.write(f"Address Extraction Debug for Document: {doc_id}\n")
                            f.write(f"Timestamp: {timestamp}\n")
                            f.write("="*70 + "\n")
                            f.write("EXTRACTED TEXT:\n")
                            f.write("="*70 + "\n")
                            f.write(extracted_text)
                            f.write("\n" + "="*70 + "\n")
                            f.write("REGEX PATTERN TESTING:\n")
                            f.write("="*70 + "\n")
                    except Exception as e:
                        print(f"DEBUG: Could not create address debug file: {e}")
                    
                    # Use exact regex patterns from LpH.py
                    patterns = [
                        r"(?:commonly known|known as|is commonly known|is commonly)(.*?)(?:this action seeks)",
                        r"(?:commonly known as|commonly known|this proceeding is|property affected:|known as|is commonly known|property located at|common address|legally described as)(.*?)(?:the instrument|this action seeks|and/or stats|by the applicable|to unpaid|this action|that the lawsuit|to whom it|parcel id|authorized|recovery of|and being legally described|and being|may concern)"
                    ]
                    
                    address = ""
                    for i, pat in enumerate(patterns):
                        import re
                        match = re.search(pat, extracted_text, re.IGNORECASE | re.DOTALL)
                        
                        # Log each pattern attempt
                        try:
                            with open(address_debug_path, 'a', encoding='utf-8') as f:
                                f.write(f"Pattern {i+1}: {pat}\n")
                                if match:
                                    f.write(f"MATCH FOUND: {match.group(1).strip()}\n")
                                else:
                                    f.write("NO MATCH\n")
                                f.write("-" * 50 + "\n")
                        except:
                            pass
                        
                        if match:
                            address = match.group(1).strip()
                            print(f"DEBUG: Found address via regex pattern {i+1}: {address}")
                            break
                    
                    if not address:
                        # Log fallback attempt
                        try:
                            with open(address_debug_path, 'a', encoding='utf-8') as f:
                                f.write("NO REGEX MATCHES FOUND - TRYING FALLBACK METHODS\n")
                                f.write("="*70 + "\n")
                        except:
                            pass
                        
                        # Fallback: use pyap to extract address (exact LpH.py logic)
                        try:
                            import pyap
                            print(f"DEBUG: [PYAP INPUT for {doc_id}]\n{extracted_text[:300]}...\n---")
                            cleaned_text = self.clean_extracted_text_lph(extracted_text)
                            
                            # Log cleaned text
                            try:
                                with open(address_debug_path, 'a', encoding='utf-8') as f:
                                    f.write("CLEANED TEXT FOR PYAP:\n")
                                    f.write(cleaned_text[:500] + "...\n")
                                    f.write("-" * 50 + "\n")
                            except:
                                pass
                            
                            addresses = pyap.parse(cleaned_text, country='US')
                            
                            if addresses:
                                address = addresses[0].full_address
                                print(f"DEBUG: [PYAP OUTPUT for {doc_id}]\n{address}\n---")
                                
                                # Log pyap result
                                try:
                                    with open(address_debug_path, 'a', encoding='utf-8') as f:
                                        f.write(f"PYAP FOUND ADDRESS: {address}\n")
                                        f.write(f"NEEDS LLM POLISH: {self.needs_llm_polish(address)}\n")
                                        f.write("-" * 50 + "\n")
                                except:
                                    pass
                                
                                # Apply LLM cleaning if needed (from LpH.py)
                                if self.needs_llm_polish(address):
                                    llm_address = self.clean_address_with_llm(address)
                                    try:
                                        with open(address_debug_path, 'a', encoding='utf-8') as f:
                                            f.write(f"LLM CLEANED ADDRESS: {llm_address}\n")
                                            f.write("-" * 50 + "\n")
                                    except:
                                        pass
                                    address = llm_address
                            else:
                                # LpH.py fallback: try LLM on cleaned text directly
                                try:
                                    with open(address_debug_path, 'a', encoding='utf-8') as f:
                                        f.write("PYAP FOUND NO ADDRESS - TRYING LLM ON FULL TEXT\n")
                                        f.write("-" * 50 + "\n")
                                except:
                                    pass
                                
                                address = self.clean_address_with_llm(cleaned_text)
                                print(f"DEBUG: [PYAP OUTPUT for {doc_id}]\nNo address found by pyap.\n---")
                                
                                try:
                                    with open(address_debug_path, 'a', encoding='utf-8') as f:
                                        f.write(f"LLM ON FULL TEXT RESULT: {address}\n")
                                        f.write("-" * 50 + "\n")
                                except:
                                    pass
                                
                        except ImportError:
                            print(f"DEBUG: pyap library not available, using basic text extraction")
                            # Simple fallback - look for common address patterns
                            try:
                                with open(address_debug_path, 'a', encoding='utf-8') as f:
                                    f.write("PYAP NOT AVAILABLE - USING BASIC EXTRACTION\n")
                                    f.write("-" * 50 + "\n")
                            except:
                                pass
                            address = self.extract_address_from_text(extracted_text)
                    
                    print(f"DEBUG: [PARSED ADDRESS for {doc_id}]\n{address}\n---")
                    
                    # Log final result
                    try:
                        with open(address_debug_path, 'a', encoding='utf-8') as f:
                            f.write("="*70 + "\n")
                            f.write("FINAL RESULT:\n")
                            f.write("="*70 + "\n")
                            f.write(f"FINAL ADDRESS: {address if address else 'NO ADDRESS FOUND'}\n")
                            f.write("="*70 + "\n")
                        print(f"DEBUG: Address extraction debug saved to: {address_debug_path}")
                    except Exception as e:
                        print(f"DEBUG: Could not save final debug result: {e}")
            
            return address if address else ""
            
        except Exception as e:
            print(f"DEBUG: ❌ Error extracting address from document {doc_id}: {e}")
            return ""

    async def extract_with_ocr(self, film_code_url: str, field_mapping, case_number: str = None) -> str:
        """Extract data using OCR from film code document"""
        import os
        import tempfile
        from pathlib import Path
        
        try:
            print(f"DEBUG: Starting OCR extraction from: {film_code_url}")
            
            # Create new context for document viewing
            context = await self.browser.new_context(
                user_agent=self.config.user_agent
            )
            doc_page = await context.new_page()
            
            # Navigate to film code document
            await doc_page.goto(film_code_url, wait_until='domcontentloaded', timeout=60000)
            await doc_page.wait_for_load_state('networkidle', timeout=60000)
            await doc_page.wait_for_timeout(2000)
            
            # Check if login is required
            print("DEBUG: Checking for login form (UserName input)...")
            login_form = await doc_page.query_selector('input[id*="Login1_UserName"]')
            if login_form:
                print("DEBUG: Login form detected. Attempting authentication...")
                
                # Check multiple possible environment variable names
                import os
                print("DEBUG: Checking environment variables...")
                print(f"DEBUG: LP_USERNAME = {'***' if os.getenv('LP_USERNAME') else 'NOT SET'}")
                print(f"DEBUG: HARRIS_USERNAME = {'***' if os.getenv('HARRIS_USERNAME') else 'NOT SET'}")
                print(f"DEBUG: LP_PASSWORD = {'***' if os.getenv('LP_PASSWORD') else 'NOT SET'}")
                print(f"DEBUG: HARRIS_PASSWORD = {'***' if os.getenv('HARRIS_PASSWORD') else 'NOT SET'}")
                
                # Try multiple environment variable names
                username = (os.getenv("LP_USERNAME") or 
                           os.getenv("HARRIS_USERNAME") or
                           os.getenv("USERNAME") or
                           os.getenv("SCRAPER_USERNAME"))
                           
                password = (os.getenv("LP_PASSWORD") or 
                           os.getenv("HARRIS_PASSWORD") or
                           os.getenv("PASSWORD") or
                           os.getenv("SCRAPER_PASSWORD"))
                
                print(f"DEBUG: Final username found: {'YES' if username else 'NO'}")
                print(f"DEBUG: Final password found: {'YES' if password else 'NO'}")
                
                if not username or not password:
                    print("DEBUG: No login credentials found in environment variables")
                    print("DEBUG: Available env vars containing 'USER' or 'PASS':")
                    for key in os.environ.keys():
                        if 'USER' in key.upper() or 'PASS' in key.upper():
                            print(f"DEBUG:   {key} = {'***' if os.environ[key] else 'EMPTY'}")
                    await context.close()
                    return None
                print("DEBUG: Filling username field...")
                await doc_page.fill('input[id*="Login1_UserName"]', username)
                print("DEBUG: Filling password field...")
                await doc_page.fill('input[id*="Login1_Password"]', password)
                print("DEBUG: Checking for 'Remember Me' checkbox...")
                remember_me = await doc_page.query_selector('input[id*="Login1_RememberMe"]')
                if remember_me:
                    print("DEBUG: 'Remember Me' checkbox found. Checking it...")
                    await doc_page.check('input[id*="Login1_RememberMe"]')
                else:
                    print("DEBUG: 'Remember Me' checkbox not found.")
                print("DEBUG: Clicking login button...")
                await doc_page.click('input[id*="Login1_LoginButton"]')
                print("DEBUG: Login button clicked. Waiting for networkidle...")
                await doc_page.wait_for_load_state('networkidle', timeout=30000)
                print("DEBUG: Login completed")
            else:
                print("DEBUG: Login form NOT detected. Continuing without login.")
            
            # Wait for document viewer to load
            await doc_page.wait_for_timeout(3000)
            
            # Look for PDF viewer or document content
            pdf_selectors = [
                'embed[type*="pdf"]',
                'iframe[src*="pdf"]',
                'object[data*="pdf"]',
                '.pdf-viewer',
                '#pdfViewer'
            ]
            
            pdf_found = False
            for selector in pdf_selectors:
                try:
                    if await doc_page.query_selector(selector):
                        print(f"DEBUG: Found PDF viewer with selector: {selector}")
                        pdf_found = True
                        break
                except:
                    continue
            
            if not pdf_found:
                print("DEBUG: No PDF viewer found, taking full page screenshot")
            
            # Take screenshot for OCR
            screenshot_dir = Path(__file__).parent / "ocr_debug"
            screenshot_dir.mkdir(exist_ok=True)
            
            # Use case number in filename if available
            filename = f"film_code_{case_number or 'unknown'}_{int(asyncio.get_event_loop().time())}.png"
            screenshot_path = screenshot_dir / filename
            
            # Set viewport to match LpH.py proven settings
            await doc_page.set_viewport_size({"width": 1414, "height": 746})
            await doc_page.evaluate("""
                () => {
                    document.body.style.margin = '0';
                    document.documentElement.style.margin = '0';
                }
            """)
            await doc_page.wait_for_timeout(2000)  # Additional wait like LpH.py
            
            # Take screenshot
            await doc_page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"DEBUG: Screenshot saved: {screenshot_path}")
            
            # Apply sharpening filter like LpH.py
            try:
                from PIL import Image, ImageFilter
                img = Image.open(screenshot_path)
                img_sharpened = img.filter(ImageFilter.SHARPEN)
                img_sharpened.save(screenshot_path)
                print(f"DEBUG: Applied sharpening filter to screenshot")
            except Exception as e:
                print(f"DEBUG: Could not apply sharpening filter: {e}")
            
            # Perform OCR on the screenshot
            ocr_result = await self.perform_ocr_on_image(str(screenshot_path), field_mapping)
            
            # Clean up
            await context.close()
            
            # Optionally remove screenshot after OCR
            # screenshot_path.unlink()
            
            return ocr_result
            
        except Exception as e:
            print(f"DEBUG: Error in OCR extraction: {e}")
            try:
                await context.close()
            except:
                pass
            return None
    
    async def download_or_screenshot_document(self, doc_url: str, doc_id: str) -> str:
        """Download or screenshot document for OCR processing"""
        try:
            print(f"DEBUG: Processing document URL: {doc_url}")
            
            # Create new context for document viewing
            context = await self.browser.new_context(
                user_agent=self.config.user_agent
            )
            doc_page = await context.new_page()
            
            # Navigate to document
            await doc_page.goto(doc_url, wait_until='domcontentloaded', timeout=60000)
            await doc_page.wait_for_load_state('networkidle', timeout=60000)
            await doc_page.wait_for_timeout(2000)  # Wait 2 seconds as requested
            
            # Check if login is required
            print("DEBUG: Checking for login form (UserName input)...")
            login_form = await doc_page.query_selector('input[id*="Login1_UserName"]')
            if login_form:
                print("DEBUG: Login form detected. Attempting authentication...")
                
                # Check multiple possible environment variable names
                import os
                print("DEBUG: Checking environment variables...")
                print(f"DEBUG: LP_USERNAME = {'***' if os.getenv('LP_USERNAME') else 'NOT SET'}")
                print(f"DEBUG: HARRIS_USERNAME = {'***' if os.getenv('HARRIS_USERNAME') else 'NOT SET'}")
                print(f"DEBUG: LP_PASSWORD = {'***' if os.getenv('LP_PASSWORD') else 'NOT SET'}")
                print(f"DEBUG: HARRIS_PASSWORD = {'***' if os.getenv('HARRIS_PASSWORD') else 'NOT SET'}")
                
                # Try multiple environment variable names
                username = (os.getenv("LP_USERNAME") or 
                           os.getenv("HARRIS_USERNAME") or
                           os.getenv("USERNAME") or
                           os.getenv("SCRAPER_USERNAME"))
                           
                password = (os.getenv("LP_PASSWORD") or 
                           os.getenv("HARRIS_PASSWORD") or
                           os.getenv("PASSWORD") or
                           os.getenv("SCRAPER_PASSWORD"))
                
                print(f"DEBUG: Final username found: {'YES' if username else 'NO'}")
                print(f"DEBUG: Final password found: {'YES' if password else 'NO'}")
                
                if not username or not password:
                    print("DEBUG: No login credentials found in environment variables")
                    print("DEBUG: Available env vars containing 'USER' or 'PASS':")
                    for key in os.environ.keys():
                        if 'USER' in key.upper() or 'PASS' in key.upper():
                            print(f"DEBUG:   {key} = {'***' if os.environ[key] else 'EMPTY'}")
                    await context.close()
                    return None
                
                # Fill login form
                await doc_page.fill('input[id*="Login1_UserName"]', username)
                await doc_page.fill('input[id*="Login1_Password"]', password)
                
                # Check remember me option
                remember_me = await doc_page.query_selector('input[id*="Login1_RememberMe"]')
                if remember_me:
                    await doc_page.check('input[id*="Login1_RememberMe"]')
                
                # Submit login
                await doc_page.click('input[id*="Login1_LoginButton"]')
                await doc_page.wait_for_load_state('networkidle', timeout=30000)
                print("DEBUG: Login completed")
            
            # Take screenshot for OCR (save to ocr_debug)
            from pathlib import Path
            screenshot_dir = Path(__file__).parent / "ocr_debug"
            screenshot_dir.mkdir(exist_ok=True)
            
            # Use case number in filename
            import asyncio
            timestamp = int(asyncio.get_event_loop().time())
            filename = f"document_{doc_id}_{timestamp}.png"
            screenshot_path = screenshot_dir / filename
            
            # Set viewport to match LpH.py proven settings
            await doc_page.set_viewport_size({"width": 1414, "height": 746})
            await doc_page.evaluate("""
                () => {
                    document.body.style.margin = '0';
                    document.documentElement.style.margin = '0';
                }
            """)
            await doc_page.wait_for_timeout(2000)  # Additional wait like LpH.py
            
            # Take screenshot
            await doc_page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"DEBUG: Screenshot saved: {screenshot_path}")
            
            # Apply sharpening filter like LpH.py
            try:
                from PIL import Image, ImageFilter
                img = Image.open(screenshot_path)
                img_sharpened = img.filter(ImageFilter.SHARPEN)
                img_sharpened.save(screenshot_path)
                print(f"DEBUG: Applied sharpening filter to screenshot")
            except Exception as e:
                print(f"DEBUG: Could not apply sharpening filter: {e}")
            
            # Clean up
            await context.close()
            
            return str(screenshot_path)
            
        except Exception as e:
            print(f"DEBUG: Error downloading/screenshotting document: {e}")
            try:
                await context.close()
            except:
                pass
            return None

    async def ocr_region_from_image(self, image_path: str, doc_id: str) -> str:
        """Perform OCR on image region using proven LpH.py logic"""
        try:
            # Try to import OCR libraries
            try:
                import pytesseract
                from PIL import Image, ImageFilter, ImageEnhance
                import cv2
                import numpy as np
            except ImportError:
                print("DEBUG: OCR libraries not available (pytesseract, PIL, cv2, numpy)")
                return ""
            
            print(f"DEBUG: Processing OCR for document using LpH.py method: {doc_id}")
            
            # Load and process image using LpH.py proven method
            img = Image.open(image_path)
            
            # Contrast Enhancement (from LpH.py)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.05)  # Reduced contrast boost for more natural result
            
            # Convert to OpenCV format (from LpH.py)
            open_cv_image = np.array(img)
            if open_cv_image.ndim == 3:
                if open_cv_image.shape[2] == 4:  # RGBA
                    open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGBA2BGR)
                else:
                    open_cv_image = cv2.cvtColor(open_cv_image, cv2.COLOR_RGB2BGR)
            
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
            
            # Denoise (from LpH.py)
            denoised = cv2.fastNlMeansDenoising(gray, h=30)
            
            # Adaptive Thresholding (replaces Otsu - from LpH.py)
            thresh = cv2.adaptiveThreshold(
                denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 12
            )
            
            # Deskew (from LpH.py)
            coords = np.column_stack(np.where(thresh > 0))
            angle = 0.0
            if coords.shape[0] > 0:
                angle = cv2.minAreaRect(coords)[-1]
                if angle < -45:
                    angle = -(90 + angle)
                else:
                    angle = -angle
            
            (h, w) = thresh.shape
            M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
            deskewed = cv2.warpAffine(thresh, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            
            # Convert back to PIL for pytesseract (from LpH.py)
            pil_img = Image.fromarray(deskewed)
            text = pytesseract.image_to_string(pil_img)
            
            print(f"DEBUG: OCR extracted text preview: {text[:200]}...")
            
            # Save OCR text to debug file
            try:
                from pathlib import Path
                ocr_debug_dir = Path(__file__).parent / "ocr_text_debug"
                ocr_debug_dir.mkdir(exist_ok=True)
                
                # Create filename with doc_id and timestamp
                import asyncio
                timestamp = int(asyncio.get_event_loop().time())
                debug_filename = f"ocr_text_{doc_id}_{timestamp}.txt"
                debug_path = ocr_debug_dir / debug_filename
                
                # Save full OCR text to file
                with open(debug_path, 'w', encoding='utf-8') as f:
                    f.write(f"OCR Debug for Document: {doc_id}\n")
                    f.write(f"Timestamp: {timestamp}\n")
                    f.write("="*50 + "\n")
                    f.write("FULL OCR TEXT:\n")
                    f.write("="*50 + "\n")
                    f.write(text)
                    f.write("\n" + "="*50 + "\n")
                    f.write("END OCR TEXT\n")
                
                print(f"DEBUG: OCR text saved to debug file: {debug_path}")
                
            except Exception as e:
                print(f"DEBUG: Could not save OCR text to debug file: {e}")
            
            return text
            
        except Exception as e:
            print(f"DEBUG: OCR processing failed for {doc_id}: {e}")
            return ""

    async def extract_field_data_custom(self, element, field_mapping) -> str:
        """Custom field extraction that doesn't add film_code_url to records"""
        try:
            # Normal extraction logic without OCR interference
            for selector_config in field_mapping.selectors:
                try:
                    if selector_config.selector_type == "css":
                        target_element = await element.query_selector(selector_config.selector)
                    else:  # xpath
                        target_element = await element.query_selector(f"xpath={selector_config.selector}")
                    
                    if target_element:
                        if selector_config.attribute:
                            if selector_config.attribute == "text":
                                value = await target_element.text_content()
                            else:
                                value = await target_element.get_attribute(selector_config.attribute)
                        else:
                            value = await target_element.text_content()
                        
                        if value:
                            value = value.strip()
                            return value
                except Exception as e:
                    print(f"DEBUG: Custom selector failed {selector_config.selector}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            print(f"DEBUG: Custom field extraction failed: {e}")
            return None

    def clean_extracted_text_lph(self, text: str) -> str:
        """Clean extracted text using proven LpH.py logic"""
        if not text:
            return ""
        
        import re
        
        # Normalize unicode quotes and dashes (from LpH.py)
        text = text.replace("'", "'").replace("'", "'").replace(""", '"').replace(""", '"')
        text = text.replace("—", "-").replace("–", "-")
        
        # Fix common OCR errors (expanded from LpH.py)
        corrections = {
            "Lx": "Ln",
            "l1": "11",
            "O0": "00",
            "Streel": "Street",
            "Slreet": "Street",
            "Streot": "Street",
            "Avonue": "Avenue",
            "Avenuo": "Avenue",
            "Comiurtt": "Community",
            "howe, ing": "housing",
            "rown as": "known as",
            "Set.": "Sec.",
            "l6": "lis",
            "LI6 PENDENS": "LIS PENDENS",
            "LI6": "LIS",
        }
        for wrong, right in corrections.items():
            text = re.sub(rf"\\b{re.escape(wrong)}\\b", right, text, flags=re.IGNORECASE)
        
        # Remove hyphenation at line breaks (from LpH.py)
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
        
        # Join lines that are split in the middle of sentences (from LpH.py)
        text = re.sub(r"\n+", " ", text)
        text = re.sub(r"\s+", " ", text)
        
        # Standardize key phrases (from LpH.py)
        key_phrases = [
            "legally described as", "known as", "property located at", "commonly known as"
        ]
        for phrase in key_phrases:
            text = re.sub(rf"{phrase}[:\s]*", f"{phrase}: ", text, flags=re.IGNORECASE)
        
        # Remove non-content lines (from LpH.py)
        text = re.sub(r"SIGNED this the.*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"RP-\d{4,}-\d{5,}", "", text)
        text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^\s*[$#@!%^&*()_+=\[\]{}|;:'\",.<>/?`~\\-]+\s*$", "", text, flags=re.MULTILINE)
        
        # Final trim
        text = text.strip()
        return text

    def needs_llm_polish(self, address: str) -> bool:
        """Check if address needs LLM polishing (from LpH.py)"""
        import re
        
        # If the address contains a likely street address and state/ZIP, do not polish unless legalese is present
        street_pattern = r"\d+\s+\w+\s+(St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Ln|Lane|Dr|Drive|Ct|Court|Pl|Place|Way|Terrace|Ter|Loop|Pkwy|Parkway)"
        state_zip_pattern = r"[A-Z]{2}\s*\d{5}(-\d{4})?"
        
        if re.search(street_pattern, address, re.IGNORECASE) and re.search(state_zip_pattern, address):
            # Only polish if legalese is present
            legalese_phrases = [
                "lot", "block", "section", "plat", "file no", "map record", "recorded in", 
                "volume", "page", "cause no", "attorney", "notary", "signed this", 
                "state of", "county of", "before me", "plaintiff", "defendant"
            ]
            for phrase in legalese_phrases:
                if phrase in address.lower():
                    return True
            return False
        
        # If no clear street/state/zip, or if too long, or contains legalese, polish
        if len(address) > 80:
            return True
            
        legalese_phrases = [
            "lot", "block", "section", "plat", "file no", "map record", "recorded in", 
            "volume", "page", "cause no", "attorney", "notary", "signed this", 
            "state of", "county of", "before me", "plaintiff", "defendant"
        ]
        for phrase in legalese_phrases:
            if phrase in address.lower():
                return True
        return False

    def clean_address_with_llm(self, address: str) -> str:
        """Use OpenAI GPT-3.5 Turbo to extract clean address (from LpH.py)"""
        try:
            import openai
            import os
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                print("DEBUG: OPENAI_API_KEY not set in environment, skipping LLM cleaning")
                return address
                
            openai.api_key = api_key
            
            prompt = (
                "Return only the US street address, city, state, and ZIP code. "
                "Do not include any names, legal phrases, suite numbers, or extra words. "
                "If no valid address is found, return an empty string.\n\n"
                f"{address}"
            )
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.0,
            )
            
            cleaned = response.choices[0].message['content'].strip()
            print(f"DEBUG: LLM cleaned address: {cleaned}")
            return cleaned
            
        except Exception as e:
            print(f"DEBUG: LLM cleaning failed: {e}")
            return address  # Fallback to original if LLM fails

    def clean_extracted_text(self, text: str) -> str:
        """Clean extracted text for better address parsing (legacy method)"""
        try:
            import re
            
            # Basic cleaning
            cleaned = text.replace('\n', ' ')
            cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
            cleaned = cleaned.strip()
            
            return cleaned
            
        except Exception as e:
            print(f"DEBUG: Error cleaning text: {e}")
            return text

    async def extract_property_address_from_screenshot(self, image_path: str) -> str:
        """Extract property address from screenshot using OCR"""
        try:
            # Try to import OCR libraries
            try:
                import pytesseract
                from PIL import Image
            except ImportError:
                print("DEBUG: OCR libraries not available (pytesseract, PIL)")
                return None
            
            print(f"DEBUG: Processing screenshot for property address: {image_path}")
            
            # Load and process image
            image = Image.open(image_path)
            
            # Perform OCR
            text = pytesseract.image_to_string(image)
            print(f"DEBUG: OCR extracted text preview: {text[:300]}...")
            
            # Extract property address using patterns
            property_address = self.extract_address_from_text(text)
            
            if property_address:
                print(f"DEBUG: Successfully extracted property address: {property_address}")
            else:
                print(f"DEBUG: No property address found in OCR text")
            
            return property_address
            
        except Exception as e:
            print(f"DEBUG: OCR processing failed: {e}")
            return None

    async def perform_ocr_on_image(self, image_path: str, field_mapping) -> str:
        """Perform OCR on image and extract relevant data"""
        try:
            # Try to import OCR libraries
            try:
                import pytesseract
                from PIL import Image
            except ImportError:
                print("DEBUG: OCR libraries not available (pytesseract, PIL)")
                return None
            
            # Load and process image
            image = Image.open(image_path)
            
            # Perform OCR
            text = pytesseract.image_to_string(image)
            print(f"DEBUG: OCR extracted text preview: {text[:200]}...")
            
            # Extract address based on field mapping type
            if field_mapping.field_name == "property_address":
                address = self.extract_address_from_text(text)
                print(f"DEBUG: Extracted address: {address}")
                return address
            
            return text
            
        except Exception as e:
            print(f"DEBUG: OCR processing failed: {e}")
            return None
    
    def extract_address_from_text(self, text: str) -> str:
        """Extract property address from OCR text"""
        import re
        
        # Common patterns for property addresses
        address_patterns = [
            r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Place|Pl|Way|Circle|Cir)\s*,?\s*[A-Za-z\s]+,?\s*[A-Z]{2}\s*\d{5}',
            r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd|Court|Ct|Place|Pl|Way|Circle|Cir)',
            r'Property Address[:\s]+([^\n]+)',
            r'Subject Property[:\s]+([^\n]+)',
            r'Located at[:\s]+([^\n]+)'
        ]
        
        for pattern in address_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Return the first match, cleaned up
                address = matches[0].strip()
                # Clean up common OCR errors
                address = re.sub(r'\s+', ' ', address)  # Multiple spaces to single
                address = re.sub(r'[^\w\s,.-]', '', address)  # Remove special chars
                if len(address) > 10:  # Reasonable minimum length
                    return address
        
        return None
    
    async def extract_nested_table_data(self, row_element, field_mapping) -> str:
        """Extract data from nested tables in specific columns"""
        try:
            # Get the selector from field mapping
            selector = field_mapping.selectors[0].selector
            print(f"DEBUG: Extracting nested table data with selector: {selector}")
            
            # Find all nested table cells
            nested_cells = await row_element.query_selector_all(selector)
            
            if not nested_cells:
                print(f"DEBUG: No nested cells found with selector: {selector}")
                return None
            
            # Extract text from all nested cells
            texts = []
            for cell in nested_cells:
                cell_text = await cell.text_content()
                if cell_text and cell_text.strip():
                    texts.append(cell_text.strip())
            
            if texts:
                result = " | ".join(texts)  # Join multiple cells with separator
                print(f"DEBUG: Nested table extracted: {result}")
                return result
            
            print(f"DEBUG: No text found in nested table cells")
            return None
            
        except Exception as e:
            print(f"DEBUG: Error extracting nested table data: {e}")
            return None
    
    async def go_to_next_results_page(self) -> bool:
        """Enhanced pagination for ASP.NET AJAX"""
        if not self.config.pagination_config:
            return False
        
        try:
            next_selector = self.config.pagination_config.next_button_selector
            if next_selector:
                next_button = await self.page.query_selector(next_selector)
                if next_button:
                    # Click and wait for AJAX postback
                    await next_button.click()
                    await self.page.wait_for_load_state('networkidle', timeout=30000)
                    await self.page.wait_for_timeout(3000)
                    
                    # Verify we actually moved to next page
                    await self.wait_for_search_results()
                    return True
        except Exception as e:
            logger.debug(f"Failed to navigate to next results page: {e}")
        
        return False
    
    async def extract_search_results(self) -> List[Dict[str, Any]]:
        """Enhanced search result extraction with debug logging"""
        results_container = self.config.search_config.results_container_selector
        
        print(f"DEBUG: Extracting results from container '{results_container}'")
        
        # Find all result rows using odd/even classes
        row_selectors = [
            f"{results_container} tr.odd, {results_container} tr.even",  # Use odd/even classes
            "tr.odd, tr.even",  # Fallback without container
            f"{results_container} tbody tr",  # General tbody rows
        ]
        
        row_elements = None
        for selector in row_selectors:
            try:
                row_elements = await self.page.query_selector_all(selector)
                if row_elements and len(row_elements) > 0:
                    print(f"DEBUG: Found {len(row_elements)} rows with selector '{selector}'")
                    break
            except Exception as e:
                print(f"DEBUG: Selector '{selector}' failed: {e}")
                continue
        
        if not row_elements:
            print("DEBUG: No result rows found")
            return []
        
        records = []
        max_records = getattr(self.config, 'max_records', None) or 10  # Default to 10 if not set
        rows_to_process = min(len(row_elements), max_records)
        
        print(f"DEBUG: Processing up to {max_records} records from {len(row_elements)} available rows...")
        
        for i, element in enumerate(row_elements[:rows_to_process]):
            try:
                print(f"DEBUG: Processing row {i+1}")
                record_data = {}
                
                # Debug: Print the HTML structure of the current row
                row_html = await element.inner_html()
                print(f"DEBUG: Row {i+1} HTML structure:")
                print(f"  {row_html[:200]}...")  # First 200 chars
                
                # Count table cells in this row
                cells = await element.query_selector_all("td")
                print(f"DEBUG: Row {i+1} has {len(cells)} cells")
                
                # Extract each configured field 
                for field_mapping in self.config.field_mappings:
                    print(f"DEBUG: Processing field '{field_mapping.field_name}' (requires_ocr: {getattr(field_mapping, 'requires_ocr', False)})")
                    
                    # Special handling for property address extraction via film code link
                    if field_mapping.field_name == "property_address":
                        print(f"DEBUG: === PROPERTY ADDRESS EXTRACTION VIA FILM CODE ===")
                        
                        # Get the case/file number first to use as search criteria
                        case_number = record_data.get('case_number')
                        if not case_number:
                            print(f"DEBUG: No case_number found yet, trying to extract it first")
                            # Try to extract case number from first cell
                            first_cell = await element.query_selector("td:first-child")
                            if first_cell:
                                case_number = await first_cell.text_content()
                                case_number = case_number.strip() if case_number else None
                                print(f"DEBUG: Extracted case_number: '{case_number}'")
                        
                        if case_number:
                            # Use proven LpH.py logic for film code URL extraction
                            case_url = await self.extract_film_code_url_proven_method(element, case_number)
                            
                            if case_url:
                                print(f"DEBUG: Found film code URL: {case_url}")
                                
                                # Use proven address extraction logic
                                property_address = await self.extract_address_from_document_proven_method(case_number, case_url)
                                
                                if property_address:
                                    record_data[field_mapping.field_name] = property_address
                                    print(f"DEBUG: Property address extracted: '{property_address}'")
                                else:
                                    print(f"DEBUG: Failed to extract property address from film code document")
                            else:
                                print(f"DEBUG: No film code URL found for case: '{case_number}'")
                        else:
                            print(f"DEBUG: No case number available for film code link matching")
                        
                        print(f"DEBUG: === END PROPERTY ADDRESS EXTRACTION ===")
                    
                    elif not getattr(field_mapping, 'requires_ocr', False):  # Handle non-OCR fields
                        print(f"DEBUG: Extracting field '{field_mapping.field_name}' with selector '{field_mapping.selectors[0].selector}'")
                        
                        # Special handling for nested table fields
                        if field_mapping.field_name in ["names_grantor_grantee", "legal_description"]:
                            value = await self.extract_nested_table_data(element, field_mapping)
                        else:
                            # Use custom field extraction instead of base class to avoid film_code_url
                            value = await self.extract_field_data_custom(element, field_mapping)
                        
                        if value:
                            record_data[field_mapping.field_name] = value
                            print(f"DEBUG: Field '{field_mapping.field_name}' = '{value}'")
                        else:
                            print(f"DEBUG: Field '{field_mapping.field_name}' = None")
                    else:
                        print(f"DEBUG: Skipping OCR field '{field_mapping.field_name}' (will be handled by property_address extraction)")
                
                # Note: Property address is now extracted immediately via film code link click
                # No separate OCR pass needed since we handle it inline
                
                # Add all records regardless of field population (max 10 records)
                records.append(record_data)
                print(f"DEBUG: Record {i+1} added to results (total: {len(records)})")
                
                # Stop if we've reached max records
                if len(records) >= max_records:
                    print(f"DEBUG: Reached maximum {max_records} records, stopping extraction")
                    break
                
            except Exception as e:
                print(f"DEBUG: Failed to extract record {i+1}: {e}")
                continue
        
        print(f"DEBUG: Successfully extracted {len(records)} valid records")
        
        # Save the records to files and database
        if records:
            await self.save_scraped_data(records)
        
        return records
    
    async def save_scraped_data(self, records: List[Dict[str, Any]]):
        """Save scraped data to JSON, CSV files and database"""
        try:
            import json
            import pandas as pd
            from datetime import datetime
            from pathlib import Path
            
            # Create data directory if it doesn't exist
            data_dir = Path(__file__).parent / "data"
            data_dir.mkdir(exist_ok=True)
            
            # Generate timestamp for filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save to JSON
            json_filename = f"harris_lis_pendens_{timestamp}.json"
            json_path = data_dir / json_filename
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, default=str, ensure_ascii=False)
            print(f"✅ Saved {len(records)} records to JSON: {json_path}")
            
            # Save to CSV
            csv_filename = f"harris_lis_pendens_{timestamp}.csv"
            csv_path = data_dir / csv_filename
            
            df = pd.DataFrame(records)
            df.to_csv(csv_path, index=False)
            print(f"✅ Saved {len(records)} records to CSV: {csv_path}")
            
            # Save to database
            await self.save_to_database(records)
            
        except Exception as e:
            print(f"❌ Error saving scraped data: {e}")
    
    async def save_to_database(self, records: List[Dict[str, Any]]):
        """Save records to database with proper Harris County schema"""
        try:
            # Import database dependencies
            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            from sqlalchemy import text
            from datetime import datetime
            import os
            
            # Database configuration - adjust as needed
            DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/database")
            
            if not DATABASE_URL or "user:password" in DATABASE_URL:
                print("⚠️ No valid DATABASE_URL found in environment variables")
                print("⚠️ Skipping database save - configure DATABASE_URL to enable")
                return
            
            engine = create_async_engine(DATABASE_URL, echo=False)
            
            # Prepare records for database insertion
            processed_records = []
            for record in records:
                processed_record = {
                    'case_number': record.get('case_number', ''),
                    'file_date': self.parse_date(record.get('file_date', '')),
                    'document_type': record.get('document_type', ''),
                    'names': record.get('names_grantor_grantee', ''),
                    'legal_description': record.get('legal_description', ''),
                    'property_address': record.get('property_address', ''),
                    'county': 'Harris',
                    'state': 'TX',
                    'created_at': datetime.now(),
                    'is_new': True,
                    'doc_type': 'L/P',
                    'userId': os.getenv('USER_ID', 1),  # Default user ID
                }
                processed_records.append(processed_record)
            
            # SQL for Harris County Lis Pendens
            insert_sql = """
            INSERT INTO lis_pendens_filing
            (case_number, file_date, document_type, names, legal_description, 
             property_address, county, state, created_at, is_new, doc_type, userId)
            VALUES
            (:case_number, :file_date, :document_type, :names, :legal_description,
             :property_address, :county, :state, :created_at, :is_new, :doc_type, :userId)
            ON CONFLICT (case_number) DO UPDATE
            SET
                file_date = EXCLUDED.file_date,
                document_type = EXCLUDED.document_type,
                names = EXCLUDED.names,
                legal_description = EXCLUDED.legal_description,
                property_address = EXCLUDED.property_address,
                created_at = EXCLUDED.created_at;
            """
            
            async with AsyncSession(engine) as session:
                await session.execute(text(insert_sql), processed_records)
                await session.commit()
                print(f"✅ Saved {len(processed_records)} records to database")
                
        except ImportError as e:
            print(f"⚠️ Database dependencies not available: {e}")
            print("⚠️ Install: pip install sqlalchemy asyncpg pandas")
        except Exception as e:
            print(f"❌ Database save error: {e}")
            print(f"⚠️ Records saved to files but not database")
    
    def parse_date(self, date_str: str):
        """Parse date string to datetime object"""
        try:
            from datetime import datetime
            
            if not date_str or date_str.strip() == '':
                return None
                
            # Try different date formats
            date_formats = [
                '%m/%d/%Y',    # 01/15/2024
                '%Y-%m-%d',    # 2024-01-15
                '%m-%d-%Y',    # 01-15-2024
                '%d/%m/%Y',    # 15/01/2024
            ]
            
            for fmt in date_formats:
                try:
                    return datetime.strptime(date_str.strip(), fmt).date()
                except ValueError:
                    continue
                    
            print(f"⚠️ Could not parse date: {date_str}")
            return None
            
        except Exception as e:
            print(f"❌ Date parsing error: {e}")
            return None