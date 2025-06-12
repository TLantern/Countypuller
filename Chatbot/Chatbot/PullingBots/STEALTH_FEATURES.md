# Ultra-Stealth Browser Configuration

## Overview

The Cobb GA scraper has been enhanced with the most comprehensive stealth browser configuration available to bypass advanced anti-bot detection systems, including captcha challenges and page refreshing issues.

## Stealth Features Implemented

### 1. Browser Launch Arguments (50+ Stealth Flags)

```bash
# Core Anti-Detection
--disable-blink-features=AutomationControlled
--exclude-switches=enable-automation

# Extension & Plugin Control
--disable-extensions-except=/path/to/extension
--disable-plugins-discovery
--disable-default-apps

# Background Process Control
--disable-sync
--disable-translate
--disable-background-timer-throttling
--disable-renderer-backgrounding
--disable-backgrounding-occluded-windows

# Security & Detection Avoidance
--disable-client-side-phishing-detection
--disable-crash-reporter
--disable-oopr-debug-crash-dump
--no-crash-upload

# Performance & Memory
--disable-dev-shm-usage
--disable-gpu-sandbox
--disable-software-rasterizer
--disable-low-res-tiling

# Network & Features
--disable-background-networking
--disable-device-discovery-notifications
--disable-domain-reliability
--enable-features=NetworkService,NetworkServiceLogging
--disable-features=VizDisplayCompositor,TranslateUI,BlinkGenPropertyTrees

# Security Overrides (for testing)
--ignore-certificate-errors
--ignore-ssl-errors
--disable-web-security
--allow-running-insecure-content
--disable-site-isolation-trials

# Additional Stealth
--no-sandbox
--disable-setuid-sandbox
--disable-infobars
--disable-notifications
--disable-popup-blocking
--disable-save-password-bubble
```

### 2. Browser Context Configuration

```javascript
{
  user_agent: "Realistic Chrome 131 UA",
  viewport: {width: 1366, height: 768},
  locale: 'en-US',
  timezone_id: 'America/New_York',
  permissions: [],
  geolocation: null,
  color_scheme: 'light'
}
```

### 3. HTTP Headers (Chrome 131 Compatible)

```http
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7
Accept-Language: en-US,en;q=0.9
Accept-Encoding: gzip, deflate, br, zstd
Connection: keep-alive
Upgrade-Insecure-Requests: 1
Sec-Fetch-Dest: document
Sec-Fetch-Mode: navigate
Sec-Fetch-Site: none
Sec-Fetch-User: ?1
Sec-Ch-Ua: "Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"
Sec-Ch-Ua-Mobile: ?0
Sec-Ch-Ua-Platform: "Windows"
Sec-Ch-Ua-Platform-Version: "15.0.0"
Cache-Control: max-age=0
DNT: 1
```

### 4. JavaScript Fingerprint Evasion

#### Navigator Properties
- Removes `navigator.webdriver`
- Mocks realistic `navigator.plugins`
- Sets `navigator.languages` to `['en-US', 'en']`
- Overrides permissions API

#### Canvas Fingerprint Protection
```javascript
// Adds minimal noise to canvas data
HTMLCanvasElement.prototype.toDataURL = function(...args) {
    const context = this.getContext('2d');
    if (context) {
        const imageData = context.getImageData(0, 0, this.width, this.height);
        for (let i = 0; i < imageData.data.length; i += 100) {
            imageData.data[i] = Math.max(0, Math.min(255, 
                imageData.data[i] + (Math.random() - 0.5)));
        }
        context.putImageData(imageData, 0, 0);
    }
    return originalToDataURL.apply(this, args);
};
```

#### WebGL Fingerprint Protection
```javascript
// Standardizes WebGL renderer/vendor
gl.getParameter = function(parameter) {
    if (parameter === gl.RENDERER) return 'Intel Iris OpenGL Engine';
    if (parameter === gl.VENDOR) return 'Intel Inc.';
    if (parameter === gl.VERSION) return 'OpenGL ES 3.0 (WebGL 2.0)';
    return originalGetParameter.call(this, parameter);
};
```

#### Audio Fingerprint Protection
```javascript
// Adds minimal noise to audio frequency data
analyser.getFloatFrequencyData = function(array) {
    originalGetFloatFrequencyData.call(this, array);
    for (let i = 0; i < array.length; i++) {
        array[i] += (Math.random() - 0.5) * 0.0001;
    }
};
```

### 5. Automation Detection Removal

```javascript
// Remove all Chrome DevTools Protocol indicators
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Object;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_JSON;
delete window.cdc_adoQpoasnfa76pfcZLmcfl_Function;
```

### 6. Screen & Display Properties

```javascript
// Override screen properties for consistency
Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });

// Prevent headless detection
if (window.outerWidth === 0 && window.outerHeight === 0) {
    Object.defineProperty(window, 'outerWidth', { get: () => 1366 });
    Object.defineProperty(window, 'outerHeight', { get: () => 768 });
}
```

### 7. Chrome Runtime Simulation

```javascript
// Mock Chrome extension API
if (!window.chrome) {
    window.chrome = {
        runtime: {
            onConnect: null,
            onMessage: null
        }
    };
}

// Mock battery API
if (!navigator.getBattery) {
    navigator.getBattery = () => Promise.resolve({
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1.0
    });
}
```

### 8. Event Timing Humanization

```javascript
// Add random delays to events to appear more human
EventTarget.prototype.addEventListener = function(type, listener, options) {
    if (['mousemove', 'click', 'keydown', 'scroll'].includes(type)) {
        const wrappedListener = function(e) {
            setTimeout(() => listener.call(this, e), Math.random() * 3);
        };
        return originalAddEventListener.call(this, type, wrappedListener, options);
    }
    return originalAddEventListener.call(this, type, listener, options);
};
```

### 9. Human-Like Behavior Simulation

```javascript
// Random mouse movements
for (let i = 0; i < random(2, 5); i++) {
    await page.mouse.move(random(100, 1200), random(100, 600));
    await page.wait_for_timeout(random(100, 400));
}

// Natural scrolling patterns
await page.mouse.wheel(0, random(50, 200));
await page.wait_for_timeout(random(500, 1200));
await page.mouse.wheel(0, -random(20, 80));

// Focus events and clicks
await page.focus('body');
await page.click('body', button='left');
```

### 10. Timing & Delays

- **Initial page load**: 8 seconds
- **Section expansion**: 2-5 seconds between actions
- **Form interactions**: 2-3 seconds between fields
- **Random delays**: All delays include randomization (±50%)
- **Network idle waiting**: Up to 45 seconds for AJAX completion

## How to Use

### Test Stealth Configuration
```bash
cd Chatbot/PullingBots
python test_stealth_cobb.py
```

### Run Full Scraper with Stealth
```bash
cd Chatbot/PullingBots
python CobbGA.py --test --user-id test123
```

## Detection Bypass Techniques

### 1. Captcha Bypass
- **User Agent Rotation**: Cycles through realistic Chrome 129-131 UAs
- **Realistic Headers**: Full Chrome 131 header simulation
- **Fingerprint Masking**: Canvas, WebGL, Audio protection
- **Timing Variation**: Human-like interaction timing

### 2. Page Refresh Prevention
- **Network Stability**: Waits for networkidle state
- **Progressive Loading**: Handles AJAX/dynamic content
- **Error Recovery**: Graceful handling of timeouts
- **Session Persistence**: Cookie management for state maintenance

### 3. Bot Detection Avoidance
- **CDP Removal**: Eliminates Chrome DevTools Protocol traces
- **Headless Masking**: Simulates windowed browser environment
- **Event Simulation**: Natural mouse/keyboard patterns
- **Resource Loading**: Realistic network request patterns

## Testing Results

The stealth configuration has been tested against:
- ✅ Basic bot detection
- ✅ Canvas fingerprinting
- ✅ WebGL fingerprinting  
- ✅ Audio fingerprinting
- ✅ Navigator property checks
- ✅ Headless detection
- ✅ Chrome DevTools Protocol detection
- ✅ Event timing analysis
- ⚠️ Advanced captcha systems (requires manual solving)

## Troubleshooting

### If Captcha Still Appears
1. Run with `--test` flag to see browser window
2. Manually solve captcha during 10-second wait
3. Check screenshot in `screenshots/stealth_test.png`
4. Verify all stealth patches are applied

### If Page Keeps Refreshing
1. Increase timeout values in config
2. Check network stability
3. Verify cookies are being saved/loaded
4. Enable additional logging for diagnosis

### Additional Stealth Options
- **Residential Proxies**: Use rotating IP addresses
- **Cookie Persistence**: Maintain session between runs  
- **User Interaction**: Manual captcha solving during automation
- **Rate Limiting**: Longer delays between requests

## Security Considerations

This stealth configuration is designed for legitimate web scraping of public records. It should only be used for:
- ✅ Public information access
- ✅ Research and compliance
- ✅ Data analysis and reporting
- ❌ Circumventing security measures
- ❌ Unauthorized access
- ❌ Malicious activities

Always respect website terms of service and robots.txt files. 