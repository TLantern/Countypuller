import os
from CobbGA import extract_text_from_screenshot, parse_addresses_from_ocr_text

def test_updated_ocr():
    """Test the updated OCR implementation"""
    screenshots_dir = 'screenshots'
    
    if not os.path.exists(screenshots_dir):
        print("❌ Screenshots directory not found")
        return
    
    screenshot_files = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]
    
    if not screenshot_files:
        print("❌ No PNG files found in screenshots directory")
        return
    
    print(f"✅ Found {len(screenshot_files)} screenshot files")
    
    # Test on the most recent screenshot
    test_file = os.path.join(screenshots_dir, screenshot_files[-1])
    print(f"🧪 Testing updated OCR on: {test_file}")
    
    # Create dummy record data for testing
    record_data = {
        'case_number': 'TEST-2025-001',
        'document_type': 'DEED - FORECLOSURE',
        'filing_date': '2025-06-11',
        'debtor_name': 'TEST DEBTOR',
        'claimant_name': 'TEST CLAIMANT'
    }
    
    try:
        # Test the extract_text_from_screenshot function
        ocr_text_file = extract_text_from_screenshot(test_file, record_data)
        
        if ocr_text_file and os.path.exists(ocr_text_file):
            print(f"✅ OCR text file created: {ocr_text_file}")
            
            # Read the OCR text
            with open(ocr_text_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Extract just the OCR text (after the metadata)
            if "=== FULL OCR TEXT ===" in content:
                ocr_text = content.split("=== FULL OCR TEXT ===")[1]
                if "=== END OCR TEXT ===" in ocr_text:
                    ocr_text = ocr_text.split("=== END OCR TEXT ===")[0]
                ocr_text = ocr_text.strip()
            else:
                ocr_text = content
            
            print(f"📝 OCR text length: {len(ocr_text)} characters")
            print(f"📄 Word count: {len(ocr_text.split())} words")
            
            # Test address parsing
            addresses = parse_addresses_from_ocr_text(ocr_text)
            
            print(f"🏠 Addresses found: {len(addresses)}")
            if addresses:
                for i, addr in enumerate(addresses[:3], 1):
                    print(f"   {i}. {addr}")
            
            # Show first 300 chars of OCR text
            print(f"\n📄 OCR Text Preview:")
            print("-" * 60)
            print(ocr_text[:300] + "..." if len(ocr_text) > 300 else ocr_text)
            print("-" * 60)
            
        else:
            print("❌ OCR text file was not created")
            
    except Exception as e:
        print(f"❌ Error during OCR test: {e}")

if __name__ == "__main__":
    test_updated_ocr() 