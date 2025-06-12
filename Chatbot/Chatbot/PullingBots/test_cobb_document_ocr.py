import os
import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import re
from pathlib import Path

# Configure Tesseract path for Windows
if os.name == 'nt':  # Windows
    possible_tesseract_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        r'C:\Users\{}\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'.format(os.getenv('USERNAME', '')),
        'tesseract',  # If in PATH
    ]
    
    tesseract_found = False
    for tesseract_path in possible_tesseract_paths:
        try:
            if os.path.exists(tesseract_path) or tesseract_path == 'tesseract':
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
                pytesseract.get_tesseract_version()
                tesseract_found = True
                print(f"✅ Found Tesseract at: {tesseract_path}")
                break
        except Exception:
            continue
    
    if not tesseract_found:
        print("❌ Tesseract not found. Please install Tesseract OCR.")
        exit(1)

def test_ocr_method_1_basic(image_path):
    """Method 1: Basic OCR with minimal preprocessing"""
    print("\n🔍 Method 1: Basic OCR (HillsboroughNH style)")
    
    image = cv2.imread(image_path)
    if image is None:
        return None, "Could not load image"
    
    # Convert to grayscale only
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # OCR with character whitelist
    custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz .,#-/()'
    text = pytesseract.image_to_string(gray, config=custom_config)
    
    if not text.strip():
        # Fallback to basic OCR
        text = pytesseract.image_to_string(gray)
    
    return text, "basic_grayscale"

def test_ocr_method_2_enhanced_preprocessing(image_path):
    """Method 2: Enhanced preprocessing for document clarity"""
    print("\n🔍 Method 2: Enhanced preprocessing")
    
    image = cv2.imread(image_path)
    if image is None:
        return None, "Could not load image"
    
    # Convert to grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(gray)
    
    # Noise reduction
    denoised = cv2.medianBlur(enhanced, 3)
    
    # Sharpening
    kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(denoised, -1, kernel)
    
    # OCR
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(sharpened, config=custom_config)
    
    return text, "enhanced_preprocessing"

def test_ocr_method_3_multiple_psm(image_path):
    """Method 3: Try multiple PSM modes"""
    print("\n🔍 Method 3: Multiple PSM modes")
    
    image = cv2.imread(image_path)
    if image is None:
        return None, "Could not load image"
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    best_text = ""
    best_method = ""
    
    psm_modes = [3, 4, 6, 8, 11, 12]
    
    for psm in psm_modes:
        try:
            config = f'--oem 3 --psm {psm}'
            text = pytesseract.image_to_string(gray, config=config)
            
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
                best_method = f"psm_{psm}"
                print(f"   PSM {psm}: {len(text)} chars")
        except Exception as e:
            print(f"   PSM {psm}: Failed - {e}")
    
    return best_text, best_method

def test_ocr_method_4_region_specific(image_path):
    """Method 4: Focus on specific regions where addresses typically appear"""
    print("\n🔍 Method 4: Region-specific extraction")
    
    image = cv2.imread(image_path)
    if image is None:
        return None, "Could not load image"
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape
    
    # Define regions where addresses typically appear in Cobb County docs
    regions = [
        ("top_half", gray[0:height//2, :]),
        ("middle_section", gray[height//4:3*height//4, :]),
        ("left_half", gray[:, 0:width//2]),
        ("right_half", gray[:, width//2:]),
        ("seller_section", gray[height//6:height//2, :]),  # Where seller info typically is
    ]
    
    all_text = []
    
    for region_name, region in regions:
        try:
            config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(region, config=config)
            if text.strip():
                all_text.append(f"=== {region_name.upper()} ===\n{text}\n")
        except Exception as e:
            print(f"   {region_name}: Failed - {e}")
    
    combined_text = "\n".join(all_text)
    return combined_text, "region_specific"

def test_ocr_method_5_threshold_variations(image_path):
    """Method 5: Different thresholding techniques"""
    print("\n🔍 Method 5: Threshold variations")
    
    image = cv2.imread(image_path)
    if image is None:
        return None, "Could not load image"
    
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    # Different thresholding methods
    threshold_methods = [
        ("binary", cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)[1]),
        ("binary_inv", cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)[1]),
        ("adaptive_mean", cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)),
        ("adaptive_gaussian", cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)),
        ("otsu", cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1])
    ]
    
    best_text = ""
    best_method = ""
    
    for method_name, processed_image in threshold_methods:
        try:
            config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(processed_image, config=config)
            
            if len(text.strip()) > len(best_text.strip()):
                best_text = text
                best_method = f"threshold_{method_name}"
                print(f"   {method_name}: {len(text)} chars")
        except Exception as e:
            print(f"   {method_name}: Failed - {e}")
    
    return best_text, best_method

def extract_addresses_from_text(text):
    """Extract addresses from OCR text using Georgia-specific patterns"""
    addresses = []
    
    if not text:
        return addresses
    
    # Georgia address patterns for Cobb County
    patterns = [
        # Standard format: Number Street Type City State ZIP
        r'\b(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+[A-Z\s]+\s+GA\s+\d{5}(?:-\d{4})?)\b',
        
        # Cobb County cities
        r'\b(\d+[A-Z]?\s+[A-Z][A-Z\s]+\s+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)\s+(?:MARIETTA|KENNESAW|SMYRNA|ACWORTH|POWDER SPRINGS|AUSTELL|MABLETON)\s+(?:GA|GEORGIA)\s+\d{5}(?:-\d{4})?)\b',
        
        # More flexible patterns
        r'(\d+[A-Z]?\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Way|Circle|Cir|Court|Ct|Place|Pl)[,\s]+[A-Za-z\s]+[,\s]+(?:GA|Georgia)\s+\d{5}(?:-\d{4})?)',
        
        # Address lines with Georgia
        r'([A-Za-z0-9\s,]+(?:MARIETTA|KENNESAW|SMYRNA|ACWORTH|POWDER SPRINGS|AUSTELL|MABLETON|GA|GEORGIA)[,\s]*\d{5}(?:-\d{4})?)',
        
        # Look for mailing address sections
        r'(?:MAILING ADDRESS|ADDRESS|STREET)[^:]*:?\s*([^\n]+(?:GA|GEORGIA)[^\n]*)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            if isinstance(match, tuple):
                clean_address = ' '.join(str(m).strip() for m in match if m.strip())
            else:
                clean_address = str(match).strip()
            
            # Clean up the address
            clean_address = re.sub(r'\s+', ' ', clean_address)
            clean_address = clean_address.strip()
            
            # Filter reasonable addresses
            if len(clean_address) > 15 and ('GA' in clean_address.upper() or 'GEORGIA' in clean_address.upper()):
                addresses.append(clean_address)
    
    # Remove duplicates and sort by length (longer addresses first)
    unique_addresses = list(set(addresses))
    unique_addresses.sort(key=len, reverse=True)
    return unique_addresses

def analyze_ocr_quality(text):
    """Analyze OCR quality metrics"""
    if not text:
        return {"chars": 0, "words": 0, "lines": 0, "noise_ratio": 100}
    
    chars = len(text)
    words = len(text.split())
    lines = len(text.split('\n'))
    
    # Calculate noise ratio (single character "words")
    single_chars = len([word for word in text.split() if len(word) == 1 and word.isalpha()])
    noise_ratio = (single_chars / words * 100) if words > 0 else 0
    
    return {
        "chars": chars,
        "words": words, 
        "lines": lines,
        "noise_ratio": noise_ratio
    }

def test_cobb_document_ocr(image_path):
    """Test all OCR methods on a Cobb County document"""
    print(f"🧪 Testing OCR methods on: {image_path}")
    print("=" * 80)
    
    if not os.path.exists(image_path):
        print(f"❌ Image file not found: {image_path}")
        return
    
    methods = [
        test_ocr_method_1_basic,
        test_ocr_method_2_enhanced_preprocessing,
        test_ocr_method_3_multiple_psm,
        test_ocr_method_4_region_specific,
        test_ocr_method_5_threshold_variations
    ]
    
    results = []
    
    for i, method in enumerate(methods, 1):
        try:
            text, method_name = method(image_path)
            quality = analyze_ocr_quality(text)
            addresses = extract_addresses_from_text(text)
            
            result = {
                "method": f"Method {i}: {method_name}",
                "text": text,
                "quality": quality,
                "addresses": addresses
            }
            results.append(result)
            
            print(f"\n📊 {result['method']}")
            print(f"   📝 Text: {quality['chars']} chars, {quality['words']} words, {quality['lines']} lines")
            print(f"   🔍 Noise ratio: {quality['noise_ratio']:.1f}%")
            print(f"   🏠 Addresses found: {len(addresses)}")
            
            if addresses:
                for j, addr in enumerate(addresses[:3], 1):  # Show first 3 addresses
                    print(f"      {j}. {addr}")
            
            # Show first 200 chars of text
            if text:
                preview = text.replace('\n', ' ').strip()[:200]
                print(f"   📄 Preview: {preview}...")
            
        except Exception as e:
            print(f"\n❌ Method {i} failed: {e}")
    
    # Find best method based on address extraction
    best_method = None
    max_addresses = 0
    
    for result in results:
        if len(result['addresses']) > max_addresses:
            max_addresses = len(result['addresses'])
            best_method = result
    
    if best_method:
        print(f"\n🏆 BEST METHOD: {best_method['method']}")
        print(f"   🏠 Found {len(best_method['addresses'])} addresses")
        print(f"   📊 Quality: {best_method['quality']['chars']} chars, {best_method['quality']['noise_ratio']:.1f}% noise")
        
        if best_method['addresses']:
            print(f"   📍 Best address: {best_method['addresses'][0]}")
    else:
        print(f"\n⚠️ No addresses found with any method")
    
    return results

if __name__ == "__main__":
    # Test on the specific Cobb County document
    test_image = "cobb_ga_unknown_unknown_20250611_185202.png"
    
    # Also check screenshots directory
    if not os.path.exists(test_image):
        screenshots_dir = "screenshots"
        if os.path.exists(screenshots_dir):
            screenshot_files = [f for f in os.listdir(screenshots_dir) if f.endswith('.png')]
            if screenshot_files:
                test_image = os.path.join(screenshots_dir, screenshot_files[0])
                print(f"📁 Using screenshot: {test_image}")
    
    if os.path.exists(test_image):
        test_cobb_document_ocr(test_image)
    else:
        print(f"❌ No test image found. Please ensure {test_image} exists or add PNG files to screenshots/ directory") 