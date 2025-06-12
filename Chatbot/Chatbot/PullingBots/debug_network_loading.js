// 🔍 COMPREHENSIVE NETWORK LOADING DEBUGGER
// Run this in the browser console to find why the page won't stop loading

console.log("🚀 Starting comprehensive network loading analysis...");

// 1. Check basic loading states
const basicInfo = {
    readyState: document.readyState,
    url: window.location.href,
    timestamp: new Date().toISOString()
};
console.log("📊 Basic Info:", basicInfo);

// 2. Analyze all resources
const resourceAnalysis = {
    totalImages: 0,
    loadingImages: 0,
    totalScripts: 0,
    loadingScripts: 0,
    totalStylesheets: 0,
    loadingStylesheets: 0,
    totalIframes: 0,
    loadingIframes: 0,
    pendingResources: []
};

// Check images
document.querySelectorAll('img').forEach((img, index) => {
    resourceAnalysis.totalImages++;
    if (!img.complete) {
        resourceAnalysis.loadingImages++;
        resourceAnalysis.pendingResources.push({
            type: 'image',
            index: index,
            src: img.src,
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight
        });
        console.log(`🖼️ Loading image ${index}:`, img.src);
    }
});

// Check scripts
document.querySelectorAll('script[src]').forEach((script, index) => {
    resourceAnalysis.totalScripts++;
    if (script.readyState && script.readyState !== 'complete') {
        resourceAnalysis.loadingScripts++;
        resourceAnalysis.pendingResources.push({
            type: 'script',
            index: index,
            src: script.src,
            readyState: script.readyState
        });
        console.log(`🔧 Loading script ${index}:`, script.src, script.readyState);
    }
});

// Check stylesheets
document.querySelectorAll('link[rel="stylesheet"]').forEach((link, index) => {
    resourceAnalysis.totalStylesheets++;
    // Stylesheets don't have a clear loading state, but we can check if they're loaded
    try {
        if (link.sheet && link.sheet.cssRules.length === 0) {
            resourceAnalysis.loadingStylesheets++;
            resourceAnalysis.pendingResources.push({
                type: 'stylesheet',
                index: index,
                href: link.href
            });
            console.log(`🎨 Potentially loading stylesheet ${index}:`, link.href);
        }
    } catch(e) {
        // Cross-origin stylesheets can't be checked
        console.log(`🎨 Cross-origin stylesheet ${index}:`, link.href);
    }
});

// Check iframes
document.querySelectorAll('iframe').forEach((iframe, index) => {
    resourceAnalysis.totalIframes++;
    try {
        if (iframe.contentDocument && iframe.contentDocument.readyState !== 'complete') {
            resourceAnalysis.loadingIframes++;
            resourceAnalysis.pendingResources.push({
                type: 'iframe',
                index: index,
                src: iframe.src,
                readyState: iframe.contentDocument.readyState
            });
            console.log(`🖼️ Loading iframe ${index}:`, iframe.src, iframe.contentDocument.readyState);
        }
    } catch(e) {
        // Cross-origin iframe
        resourceAnalysis.pendingResources.push({
            type: 'iframe-crossorigin',
            index: index,
            src: iframe.src,
            error: e.message
        });
        console.log(`🖼️ Cross-origin iframe ${index}:`, iframe.src, e.message);
    }
});

console.log("📊 Resource Analysis:", resourceAnalysis);

// 3. Check for ASP.NET specific issues
const aspNetAnalysis = {
    hasViewState: !!document.querySelector('input[name="__VIEWSTATE"]'),
    viewStateSize: document.querySelector('input[name="__VIEWSTATE"]')?.value?.length || 0,
    hasEventValidation: !!document.querySelector('input[name="__EVENTVALIDATION"]'),
    hasScriptManager: !!document.getElementById('ToolkitScriptManager1'),
    hasUpdatePanels: document.querySelectorAll('[id*="update"], [id*="Update"]').length,
    hasAjaxFramework: !!window.Sys && !!window.Sys.WebForms,
    postBackTarget: document.querySelector('input[name="__EVENTTARGET"]')?.value || 'none'
};

console.log("🏛️ ASP.NET Analysis:", aspNetAnalysis);

// 4. Check for ongoing AJAX/fetch requests
let activeRequests = 0;
let requestLog = [];

// Monitor XMLHttpRequest
const originalXHROpen = XMLHttpRequest.prototype.open;
const originalXHRSend = XMLHttpRequest.prototype.send;

XMLHttpRequest.prototype.open = function(...args) {
    this._url = args[1];
    this._method = args[0];
    return originalXHROpen.apply(this, args);
};

XMLHttpRequest.prototype.send = function(...args) {
    activeRequests++;
    requestLog.push({
        type: 'XHR',
        method: this._method,
        url: this._url,
        timestamp: new Date().toISOString(),
        status: 'sent'
    });
    
    this.addEventListener('loadend', () => {
        activeRequests--;
        console.log(`📡 XHR completed: ${this._method} ${this._url} (${this.status})`);
    });
    
    return originalXHRSend.apply(this, args);
};

// Monitor fetch requests
const originalFetch = window.fetch;
window.fetch = function(...args) {
    activeRequests++;
    const url = args[0];
    requestLog.push({
        type: 'fetch',
        url: url,
        timestamp: new Date().toISOString(),
        status: 'sent'
    });
    
    return originalFetch.apply(this, args).finally(() => {
        activeRequests--;
        console.log(`📡 Fetch completed: ${url}`);
    });
};

console.log(`📡 Active requests at analysis time: ${activeRequests}`);
console.log("📡 Request log:", requestLog);

// 5. Check for timers and intervals
const timerAnalysis = {
    timeoutCount: 0,
    intervalCount: 0
};

// This is approximate - we can't directly count existing timers
// But we can monitor new ones
const originalSetTimeout = window.setTimeout;
const originalSetInterval = window.setInterval;

window.setTimeout = function(...args) {
    timerAnalysis.timeoutCount++;
    console.log(`⏰ New timeout set: ${args[1]}ms`);
    return originalSetTimeout.apply(this, args);
};

window.setInterval = function(...args) {
    timerAnalysis.intervalCount++;
    console.log(`⏰ New interval set: ${args[1]}ms`);
    return originalSetInterval.apply(this, args);
};

console.log("⏰ Timer monitoring setup complete");

// 6. Check for event listeners that might be preventing completion
const eventListenerAnalysis = {
    totalListeners: 0,
    listenerTypes: {}
};

// We can't directly enumerate existing listeners, but we can monitor new ones
const originalAddEventListener = EventTarget.prototype.addEventListener;
EventTarget.prototype.addEventListener = function(type, listener, options) {
    eventListenerAnalysis.totalListeners++;
    eventListenerAnalysis.listenerTypes[type] = (eventListenerAnalysis.listenerTypes[type] || 0) + 1;
    console.log(`🎧 New event listener: ${type} on`, this.constructor.name);
    return originalAddEventListener.call(this, type, listener, options);
};

// 7. Continuous monitoring function
function continuousMonitor() {
    const status = {
        timestamp: new Date().toISOString(),
        readyState: document.readyState,
        activeRequests: activeRequests,
        pendingImages: Array.from(document.querySelectorAll('img')).filter(img => !img.complete).length,
        pendingScripts: Array.from(document.querySelectorAll('script[src]')).filter(script => 
            script.readyState && script.readyState !== 'complete').length,
        networkActivity: performance.getEntriesByType('navigation')[0]?.loadEventEnd > 0 ? 'complete' : 'ongoing'
    };
    
    console.log("📊 Current status:", status);
    
    // Check if anything is still loading
    if (status.activeRequests > 0 || status.pendingImages > 0 || status.pendingScripts > 0) {
        console.log("⚠️ Still loading resources...");
        return false; // Still loading
    } else {
        console.log("✅ All known resources loaded");
        return true; // Appears complete
    }
}

// 8. Set up periodic monitoring
console.log("🔄 Starting periodic monitoring (every 2 seconds)...");
const monitorInterval = setInterval(() => {
    const isComplete = continuousMonitor();
    if (isComplete) {
        console.log("🎉 Page appears to be fully loaded!");
        clearInterval(monitorInterval);
    }
}, 2000);

// 9. Manual check function you can call anytime
window.debugLoadingStatus = function() {
    console.log("🔍 Manual loading status check:");
    continuousMonitor();
    
    // Additional manual checks
    console.log("📊 Resource Summary:");
    console.log(`- Images: ${resourceAnalysis.totalImages} total, ${resourceAnalysis.loadingImages} loading`);
    console.log(`- Scripts: ${resourceAnalysis.totalScripts} total, ${resourceAnalysis.loadingScripts} loading`);
    console.log(`- Stylesheets: ${resourceAnalysis.totalStylesheets} total, ${resourceAnalysis.loadingStylesheets} loading`);
    console.log(`- Iframes: ${resourceAnalysis.totalIframes} total, ${resourceAnalysis.loadingIframes} loading`);
    console.log(`- Active AJAX/Fetch: ${activeRequests}`);
    
    return {
        resourceAnalysis,
        aspNetAnalysis,
        activeRequests,
        requestLog: requestLog.slice(-10) // Last 10 requests
    };
};

console.log("✅ Network loading debugger initialized!");
console.log("💡 Call window.debugLoadingStatus() anytime for a status update");
console.log("💡 Check the console for ongoing monitoring messages");

// 10. Initial comprehensive report
console.log("📋 INITIAL COMPREHENSIVE REPORT:");
console.log("================================");
window.debugLoadingStatus(); 