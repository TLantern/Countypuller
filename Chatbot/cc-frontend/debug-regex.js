// Debug regex patterns
const testAddresses = [
  "747SILVERSTAPT1MANCHESTERNH031034401",
  "191WILSONSTAPT4 MANCHESTERNH031035071", 
  "400WILLOWSTSTE1MANCHESTERNH031036300"
];

console.log("Debugging regex patterns:");
console.log("=" .repeat(60));

testAddresses.forEach((address, index) => {
  console.log(`\nTesting: "${address}"`);
  
  // Break down the patterns step by step
  const patterns = [
    {
      name: "Number only",
      regex: /^(\d+)/,
    },
    {
      name: "Number + Street name",  
      regex: /^(\d+)([A-Z]+)/,
    },
    {
      name: "Number + Street + ST",
      regex: /^(\d+)([A-Z]+)ST/,
    },
    {
      name: "Number + Street + ST + APT",
      regex: /^(\d+)([A-Z]+)ST(?:APT)?(\d+)?/,
    },
    {
      name: "Full pattern (simple)",
      regex: /^(\d+)([A-Z]+)ST(?:APT)?(\d+)?([A-Z]+)(NH)(\d{5,9})/,
    },
    {
      name: "Full pattern (with alternatives)",
      regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?([A-Z]+)(NH)(\d{5}(?:\d{4})?)/i,
    }
  ];
  
  patterns.forEach(pattern => {
    const match = address.match(pattern.regex);
    console.log(`  ${pattern.name}:`, match ? match : "NO MATCH");
  });
});

// Let's try with a more specific approach for the exact format
console.log("\n" + "=" .repeat(60));
console.log("Testing specific patterns for OCR addresses:");

function parseOCRAddress(address) {
  console.log(`\nParsing: "${address}"`);
  
  // Pattern for: NumberStreetNameSTAPTNumberCityNHZIP
  // Example: 747SILVERSTAPT1MANCHESTERNH031034401
  
  // Let's manually break it down:
  // 1. Find the number at start: \d+
  // 2. Find street name: [A-Z]+  
  // 3. Find ST/STREET/etc: (?:ST|STREET|AVE|etc)
  // 4. Find APT/UNIT + number: (?:APT|UNIT)?(\d+)?
  // 5. Find city name: ([A-Z]+)
  // 6. Find state: (NH)
  // 7. Find ZIP: (\d{9})
  
  const manualPattern = /^(\d+)([A-Z]+)(ST|AVE|RD|DR|LN|WAY|CT|CIR|PL|BLVD)(?:APT|UNIT|STE)?(\d+)?([A-Z]+)(NH)(\d{9}|\d{5})$/i;
  
  const match = address.match(manualPattern);
  console.log("  Manual pattern match:", match);
  
  if (match) {
    const number = match[1];
    const streetName = match[2]; 
    const streetType = match[3];
    const aptNum = match[4] || '';
    const city = match[5];
    const state = match[6];
    const zip = match[7];
    
    // Format ZIP properly
    const formattedZip = zip.length === 9 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
    
    const result = {
      street: `${number} ${streetName} ${streetType}${aptNum ? ' APT ' + aptNum : ''}`,
      city: city,
      state: state,
      zip: formattedZip
    };
    
    console.log("  Parsed result:", result);
    return result;
  }
  
  return { street: '', city: '', state: '', zip: '' };
}

testAddresses.forEach(parseOCRAddress); 