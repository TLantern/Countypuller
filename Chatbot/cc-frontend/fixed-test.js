const address = "426SOMERVILLESTAPT212 MANCHESTERNH03103561";
console.log("Testing address:", address);
console.log("Address length:", address.length);

// Let's manually identify the pattern
console.log("\nManual breakdown:");
console.log("Expected components:");
console.log("  Number: 426");
console.log("  Street: SOMERVILLE");  
console.log("  Type: ST");
console.log("  Apt: APT 212");
console.log("  City: MANCHESTER");
console.log("  State: NH");
console.log("  ZIP: 03103561 (8 digits - unusual!)");

// Test different patterns to find what works
const patterns = [
  {
    name: "Pattern 1 - Handle 8-digit ZIP",
    regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?\s+([A-Z]+)(NH)(\d{8,9})/i
  },
  {
    name: "Pattern 2 - More specific for this address", 
    regex: /(\d+)(SOMERVILLE)(ST)(APT)(\d+)\s+(MANCHESTER)(NH)(\d{8})/i
  },
  {
    name: "Pattern 3 - Generic with space before city",
    regex: /(\d+)([A-Z]+)(ST|AVE|RD|DR|LN|WAY|CT|CIR|PL|BLVD)(APT|UNIT)(\d+)\s+([A-Z]+)(NH)(\d{8,9})/i
  },
  {
    name: "Pattern 4 - Most flexible",
    regex: /^(\d+)([A-Z]+)(ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(APT|UNIT)?(\d+)?\s*([A-Z]+)(NH)(\d{5,9})$/i
  }
];

patterns.forEach((pattern, index) => {
  console.log(`\n${pattern.name}:`);
  const match = address.match(pattern.regex);
  console.log("Match:", match ? "YES" : "NO");
  
  if (match) {
    console.log("Groups:", match.slice(1));
    
    // Try to construct the result
    if (match.length >= 8) {
      let street, city, state, zip;
      
      if (pattern.name.includes("Pattern 2")) {
        street = `${match[1]} ${match[2]} ${match[3]} ${match[4]} ${match[5]}`;
        city = match[6];
        state = match[7];
        zip = match[8];
      } else if (pattern.name.includes("Pattern 4")) {
        const number = match[1];
        const streetName = match[2];
        const streetType = match[3];
        const aptType = match[4] || 'APT';
        const aptNum = match[5] || '';
        city = match[6];
        state = match[7]; 
        zip = match[8];
        
        street = `${number} ${streetName} ${streetType}${aptNum ? ' ' + aptType + ' ' + aptNum : ''}`;
      } else {
        // Generic handling
        street = `${match[1]} ${match[2]} ${match[3] || 'ST'}${match[5] ? ' APT ' + match[5] : ''}`;
        city = match[6];
        state = match[7];
        zip = match[8];
      }
      
      // Format ZIP if it's 8 or 9 digits
      if (zip && zip.length >= 8) {
        const formattedZip = zip.length === 9 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : 
                            zip.length === 8 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
        zip = formattedZip;
      }
      
      console.log("  Constructed result:");
      console.log(`    street: "${street}"`);
      console.log(`    city: "${city}"`);
      console.log(`    state: "${state}"`);
      console.log(`    zip: "${zip}"`);
    }
  }
});

// Test what the current utils.ts pattern expects
console.log("\n" + "=".repeat(50));
console.log("Current utils.ts pattern analysis:");
const currentPattern = /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?([A-Z]+)(NH)(\d{5}(?:\d{4})?)/i;
console.log("Pattern:", currentPattern);
console.log("Issue: The pattern expects ZIP to be exactly 5 digits OR 5+4=9 digits");
console.log("But our address has 8 digits:", "03103561");
console.log("This suggests a data quality issue in your OCR/scraping process");

console.log("\nRecommended fixes:");
console.log("1. Update regex to handle 8-digit ZIPs: (\\d{5,9}) instead of (\\d{5}(?:\\d{4})?)");
console.log("2. Add data cleaning to fix malformed ZIPs before parsing");
console.log("3. Implement better SERP search that doesn't rely on perfect address parsing"); 