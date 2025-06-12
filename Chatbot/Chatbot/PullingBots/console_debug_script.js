// 🔍 QUICK CONSOLE DEBUG SCRIPT
// Copy and paste this entire script into the browser console on Georgia Public Notice page

console.log("🚀 Quick loading debug started...");

// Quick analysis function
function quickLoadingAnalysis() {
    const analysis = {
        basicInfo: {
            readyState: document.readyState,
            url: window.location.href.substring(0, 80),
            timestamp: new Date().toLocaleTimeString()
        },
        images: {
            total: document.querySelectorAll('img').length,
            loading: Array.from(document.querySelectorAll('img')).filter(img => !img.complete).length
        },
        scripts: {
            total: document.querySelectorAll('script[src]').length,
            loading: Array.from(document.querySelectorAll('script[src]')).filter(script => 
                script.readyState && script.readyState !== 'complete').length
        },
        iframes: {
            total: document.querySelectorAll('iframe').length,
            crossOrigin: 0
        },
        aspNet: {
            hasViewState: !!document.querySelector('input[name="__VIEWSTATE"]'),
            hasScriptManager: !!document.getElementById('ToolkitScriptManager1'),
            updatePanels: document.querySelectorAll('[id*="update"], [id*="Update"]').length,
            hasAjaxFramework: !!window.Sys && !!window.Sys.WebForms
        }
    };
    
    // Check iframes
    document.querySelectorAll('iframe').forEach(iframe => {
        try {
            if (iframe.contentDocument) {
                // Can access - check if loading
            } else {
                analysis.iframes.crossOrigin++;
            }
        } catch(e) {
            analysis.iframes.crossOrigin++;
        }
    });
    
    return analysis;
}

// Detect what's keeping the page loading
function detectLoadingBlockers() {
    const blockers = [];
    
    // Check images
    const loadingImages = Array.from(document.querySelectorAll('img')).filter(img => !img.complete);
    if (loadingImages.length > 0) {
        blockers.push(`${loadingImages.length} images still loading`);
        loadingImages.slice(0, 3).forEach(img => {
            console.log(`🖼️ Loading image: ${img.src.substring(0, 80)}`);
        });
    }
    
    // Check scripts
    const loadingScripts = Array.from(document.querySelectorAll('script[src]'))
        .filter(script => script.readyState && script.readyState !== 'complete');
    if (loadingScripts.length > 0) {
        blockers.push(`${loadingScripts.length} scripts still loading`);
        loadingScripts.slice(0, 3).forEach(script => {
            console.log(`🔧 Loading script: ${script.src.substring(0, 80)}`);
        });
    }
    
    // Check for ASP.NET specific issues
    if (window.Sys && window.Sys.WebForms) {
        blockers.push("ASP.NET AJAX framework active");
        
        if (window.Sys.WebForms.PageRequestManager) {
            const prm = window.Sys.WebForms.PageRequestManager.getInstance();
            if (prm && prm.get_isInAsyncPostBack && prm.get_isInAsyncPostBack()) {
                blockers.push("ASP.NET async postback in progress");
            }
        }
    }
    
    // Check for timers (approximate)
    if (window.setInterval.toString().includes('native code')) {
        // Normal - no custom intervals detected
    } else {
        blockers.push("Custom intervals detected");
    }
    
    return blockers;
}

// Main analysis
const result = quickLoadingAnalysis();
const blockers = detectLoadingBlockers();

console.log("📊 QUICK ANALYSIS RESULTS:");
console.log("========================");
console.log("🔍 Basic Info:", result.basicInfo);
console.log("🖼️ Images:", result.images);
console.log("🔧 Scripts:", result.scripts);
console.log("📄 Iframes:", result.iframes);
console.log("🏛️ ASP.NET:", result.aspNet);

if (blockers.length > 0) {
    console.log("⚠️ POTENTIAL LOADING BLOCKERS:");
    blockers.forEach(blocker => console.log(`  - ${blocker}`));
} else {
    console.log("✅ No obvious loading blockers detected");
}

// Set up monitoring
let monitorCount = 0;
const monitorInterval = setInterval(() => {
    monitorCount++;
    const currentStatus = quickLoadingAnalysis();
    const currentBlockers = detectLoadingBlockers();
    
    console.log(`📊 Monitor ${monitorCount}: Loading images: ${currentStatus.images.loading}, Scripts: ${currentStatus.scripts.loading}, Blockers: ${currentBlockers.length}`);
    
    if (currentBlockers.length === 0) {
        console.log("🎉 All loading appears complete!");
        clearInterval(monitorInterval);
    }
    
    if (monitorCount >= 10) { // Stop after 10 checks (20 seconds)
        console.log("⏰ Monitoring timeout reached");
        clearInterval(monitorInterval);
    }
}, 2000);

console.log("🔄 Monitoring started (will run for 20 seconds or until complete)");
console.log("💡 Check above for specific loading blockers");

// Add a manual check function
window.checkLoading = function() {
    const status = quickLoadingAnalysis();
    const blockers = detectLoadingBlockers();
    console.log("📊 Manual check:", status);
    console.log("⚠️ Blockers:", blockers);
    return {status, blockers};
};

console.log("💡 Run window.checkLoading() anytime for an updated status"); 