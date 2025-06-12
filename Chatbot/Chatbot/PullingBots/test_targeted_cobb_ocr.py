import os
import cv2
import numpy as np
import pytesseract
from PIL import Image
import re

# Configure Tesseract
if os.name == 'nt':
    possible_tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        'tesseract',
    ]
    
    for tesseract_path in possible_tesseract_paths:
        try:
            if os.path.exists(tesseract_path) or tesseract_path == 'tesseract':
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                pytesseract.get_tesseract_version()
                print(f"✅ Found Tesseract at: {tesseract_path}")
                break
        except Exception:
            continue

def extract_seller_address_region(image_path):
    """Extract text specifically from the seller's address region"""
    print("\n🎯 Targeting SELLER'S ADDRESS region")
    
    image = cv2.imread(image_path)
    if image is None:
        return None
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    
    # Based on the document layout, seller info is typically in the upper left area
    # Let's extract the region where "MAILING ADDRESS (STREET & NUMBER)" appears
    seller_region = gray[int(height*0.15):int(height*0.45), int(width*0.05):int(width*0.65)]
    
    # Apply different preprocessing to this region
    methods = []
    
    # Method 1: Basic grayscale
    config1 = r'--oem 3 --psm 6'
    text1 = pytesseract.image_to_string(seller_region, config=config1)
    methods.append(("basic", text1))
    
    # Method 2: Enhanced contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
    enhanced = clahe.apply(seller_region)
    text2 = pytesseract.image_to_string(enhanced, config=config1)
    methods.append(("enhanced", text2))
    
    # Method 3: Threshold
    _, thresh = cv2.threshold(seller_region, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text3 = pytesseract.image_to_string(thresh, config=config1)
    methods.append(("threshold", text3))
    
    # Method 4: Different PSM
    config4 = r'--oem 3 --psm 4'
    text4 = pytesseract.image_to_string(seller_region, config=config4)
    methods.append(("psm4", text4))
    
    # Method 5: Line-by-line PSM
    config5 = r'--oem 3 --psm 8'
    text5 = pytesseract.image_to_string(seller_region, config=config5)
    methods.append(("psm8", text5))
    
    return methods

def extract_property_info_region(image_path):
    """Extract text from the property information section"""
    print("\n🎯 Targeting PROPERTY INFORMATION region")
    
    image = cv2.imread(image_path)
    if image is None:
        return None
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    
    # Property info is typically in the middle-lower section
    property_region = gray[int(height*0.45):int(height*0.85), int(width*0.05):int(width*0.95)]
    
    methods = []
    
    # Try different approaches on property section
    config = r'--oem 3 --psm 6'
    
    # Basic
    text1 = pytesseract.image_to_string(property_region, config=config)
    methods.append(("property_basic", text1))
    
    # Enhanced
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(property_region)
    text2 = pytesseract.image_to_string(enhanced, config=config)
    methods.append(("property_enhanced", text2))
    
    return methods

def parse_cobb_addresses(text):
    """Parse addresses specifically from Cobb County PT documents"""
    addresses = []
    
    if not text:
        return addresses
    
    # Look for the specific patterns in Cobb County PT documents
    patterns = [
        # Street address pattern: number + street name + type
        r'(\d+\s+[A-Z][A-Z\s]*(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD))',
        
        # City, State ZIP pattern
        r'([A-Z][A-Z\s]+,?\s+(?:GA|GEORGIA)\s+\d{5}(?:-\d{4})?)',
        
        # Combined address pattern
        r'(\d+\s+[A-Z][A-Z\s]*(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)[,\s]+[A-Z][A-Z\s]+,?\s+(?:GA|GEORGIA)\s+\d{5}(?:-\d{4})?)',
        
        # Look for lines that contain both numbers and GA
        r'([^\n]*\d+[^\n]*(?:GA|GEORGIA)[^\n]*\d{5}[^\n]*)',
        
        # Look for mailing address sections
        r'(?:MAILING ADDRESS|ADDRESS)[^:]*:?\s*([^\n]+)',
        
        # Look for city names in Cobb County
        r'([^\n]*(?:KENNESAW|MARIETTA|SMYRNA|ACWORTH|POWDER SPRINGS|AUSTELL|MABLETON)[^\n]*)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            if isinstance(match, tuple):
                clean_address = ' '.join(str(m).strip() for m in match if m.strip())
            else:
                clean_address = str(match).strip()
            
            # Clean up
            clean_address = re.sub(r'\s+', ' ', clean_address)
            clean_address = clean_address.strip()
            
            # Filter reasonable addresses
            if len(clean_address) > 10:
                addresses.append(clean_address)
    
    # Remove duplicates and sort by length
    unique_addresses = list(set(addresses))
    unique_addresses.sort(key=len, reverse=True)
    return unique_addresses

def test_targeted_cobb_ocr(image_path):
    """Test targeted OCR specifically for Cobb County PT documents"""
    print(f"🎯 Testing targeted OCR on Cobb County document: {image_path}")
    print("=" * 80)
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return
    
    all_results = []
    
    # Test seller address region
    seller_methods = extract_seller_address_region(image_path)
    if seller_methods:
        for method_name, text in seller_methods:
            addresses = parse_cobb_addresses(text)
            result = {
                "region": "seller",
                "method": method_name,
                "text": text,
                "addresses": addresses,
                "text_length": len(text) if text else 0
            }
            all_results.append(result)
            
            print(f"\n📊 SELLER - {method_name}")
            print(f"   📝 Text length: {len(text) if text else 0} chars")
            print(f"   🏠 Addresses found: {len(addresses)}")
            
            if addresses:
                for i, addr in enumerate(addresses[:3], 1):
                    print(f"      {i}. {addr}")
            
            if text:
                preview = text.replace('\n', ' ').strip()[:150]
                print(f"   📄 Preview: {preview}...")
    
    # Test property info region
    property_methods = extract_property_info_region(image_path)
    if property_methods:
        for method_name, text in property_methods:
            addresses = parse_cobb_addresses(text)
            result = {
                "region": "property",
                "method": method_name,
                "text": text,
                "addresses": addresses,
                "text_length": len(text) if text else 0
            }
            all_results.append(result)
            
            print(f"\n📊 PROPERTY - {method_name}")
            print(f"   📝 Text length: {len(text) if text else 0} chars")
            print(f"   🏠 Addresses found: {len(addresses)}")
            
            if addresses:
                for i, addr in enumerate(addresses[:3], 1):
                    print(f"      {i}. {addr}")
            
            if text:
                preview = text.replace('\n', ' ').strip()[:150]
                print(f"   📄 Preview: {preview}...")
    
    # Find best result
    best_result = None
    max_addresses = 0
    
    for result in all_results:
        if len(result['addresses']) > max_addresses:
            max_addresses = len(result['addresses'])
            best_result = result
    
    if best_result:
        print(f"\n🏆 BEST RESULT: {best_result['region'].upper()} - {best_result['method']}")
        print(f"   🏠 Found {len(best_result['addresses'])} addresses")
        print(f"   📊 Text length: {best_result['text_length']} chars")
        
        if best_result['addresses']:
            print(f"   📍 Best address: {best_result['addresses'][0]}")
            
        # Show full text for best result
        print(f"\n📄 FULL TEXT FROM BEST METHOD:")
        print("-" * 60)
        print(best_result['text'])
        print("-" * 60)
    else:
        print(f"\n⚠️ No addresses found with any method")
    
    return all_results

if __name__ == "__main__":
    # Test on available screenshots
    screenshots_dir = "screenshots"
    if os.path.exists(screenshots_dir):
        screenshot_files = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]
        if screenshot_files:
            # Use the most recent screenshot
            test_image = os.path.join(screenshots_dir, screenshot_files[-1])
            print(f"📁 Using screenshot: {test_image}")
            test_targeted_cobb_ocr(test_image)
        else:
            print("❌ No PNG files found in screenshots directory")
    else:
        print("❌ Screenshots directory not found") 