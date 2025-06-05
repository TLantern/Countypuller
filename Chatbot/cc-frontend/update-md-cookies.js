const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function updateMdCookies() {
  console.log('🍪 Maryland Cookie Extractor');
  console.log('📝 This will help you update md_cookies.json with fresh cookies\n');
  
  const browser = await chromium.launch({
    headless: false,
    args: ['--no-first-run']
  });
  
  const context = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'
  });
  
  const page = await context.newPage();
  
  try {
    console.log('🌐 Opening Maryland Case Search...');
    await page.goto('https://casesearch.courts.state.md.us/casesearch/inquirySearch.jis');
    
    console.log('\n📋 MANUAL STEPS:');
    console.log('1. ✅ Accept disclaimers');
    console.log('2. 🤖 Complete any CAPTCHAs'); 
    console.log('3. 🔍 Verify you can see the search form');
    console.log('4. ⌨️  Press ENTER in this terminal when ready to save cookies...\n');
    
    // Wait for user input
    process.stdin.setRawMode(true);
    process.stdin.resume();
    await new Promise(resolve => {
      process.stdin.once('data', () => {
        process.stdin.setRawMode(false);
        resolve();
      });
    });
    
    // Extract cookies
    console.log('📤 Extracting cookies...');
    const cookies = await context.cookies();
    
    // Filter for Maryland court cookies
    const mdCookies = cookies.filter(cookie => 
      cookie.domain.includes('state.md.us') || 
      cookie.domain.includes('courts.state.md.us')
    );
    
    if (mdCookies.length === 0) {
      console.log('❌ No Maryland cookies found!');
      return;
    }
    
    // Save to md_cookies.json
    const cookieFile = path.join(__dirname, 'md_cookies.json');
    fs.writeFileSync(cookieFile, JSON.stringify(mdCookies, null, 2));
    
    console.log(`\n✅ SUCCESS! Updated md_cookies.json with ${mdCookies.length} cookies`);
    
    // Show cookie summary
    console.log('\n📊 Cookies saved:');
    mdCookies.forEach(cookie => {
      console.log(`   - ${cookie.name}`);
    });
    
    console.log('\n🎉 Maryland scraper should now work with these fresh cookies!');
    
  } catch (error) {
    console.error('❌ Error:', error);
  } finally {
    await browser.close();
  }
}

// Show instructions and run
console.log('🔄 Maryland Cookie Updater');
console.log('📝 Use this when cookies expire (~4 hours) and scraper gets blocked\n');
updateMdCookies().catch(console.error); 