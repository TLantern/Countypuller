const parseAddress = require('parse-address');

// Test cases from the chat logs
const testCases = [
  "tell me more about the property 747SILVERSTAPT1 MANCHESTERNH031034401",
  "747SILVERSTAPT1 MANCHESTERNH031034401", 
  "747 SILVER ST APT 1 MANCHESTER NH 03103-4401",
  "191WILSONSTAPT4 MANCHESTERNH031035071",
  "191 WILSON ST APT 4 MANCHESTER NH 03103-5071"
];

console.log("Testing address parsing with parse-address library:");
console.log("=" .repeat(60));

testCases.forEach((testCase, index) => {
  console.log(`\nTest ${index + 1}: "${testCase}"`);
  
  try {
    const parsed = parseAddress.parseLocation(testCase);
    console.log("  Parsed result:", JSON.stringify(parsed, null, 2));
    
    // Simulate what normalizeAttomParams does
    let street = '', city = '', state = '', zip = '';
    if (parsed) {
      street = [parsed.number, parsed.prefix, parsed.street, parsed.type, parsed.suffix].filter(Boolean).join(' ').trim();
      city = parsed.city || '';
      state = parsed.state || '';
      zip = parsed.zip || '';
    }
    
    console.log("  Normalized result:", { street, city, state, zip });
    
  } catch (e) {
    console.log("  Error:", e.message);
    console.log("  Normalized result: { street: '', city: '', state: '', zip: '' }");
  }
});

// Test improved parsing approach
console.log("\n" + "=" .repeat(60));
console.log("Testing improved address parsing approach:");
console.log("=" .repeat(60));

function improvedAddressParsing(input) {
  // Enhanced regex patterns for addresses in various formats
  const addressPatterns = [
    // Pattern 1: Number + Street + APT/UNIT + City + State + ZIP (all concatenated)
    /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?([A-Z]+)([A-Z]{2})(\d{5}(?:-?\d{4})?)/i,
    
    // Pattern 2: Traditional spaced address format  
    /(\d+[A-Z]?)\s+([A-Z][A-Z\s]+)\s+(ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:\s+(?:APT|UNIT)\s*(\d+[A-Z]?))?\s+([A-Z\s]+)\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)/i,
    
    // Pattern 3: Just extract the address parts if present in the message
    /(?:property|address)\s+([^\s]+(?:\s+[^\s]+)*)/i
  ];
  
  // Try each pattern
  for (const pattern of addressPatterns) {
    const match = input.match(pattern);
    if (match) {
      console.log("  Pattern matched:", pattern.toString());
      console.log("  Match groups:", match);
      
      if (pattern === addressPatterns[0]) {
        // Handle concatenated format like "747SILVERSTAPT1MANCHESTERNH031034401"
        const number = match[1];
        const streetName = match[2];
        const aptNum = match[3] || '';
        const city = match[4];
        const state = match[5];
        const zip = match[6];
        
        return {
          street: `${number} ${streetName} ST${aptNum ? ' APT ' + aptNum : ''}`.trim(),
          city: city,
          state: state,
          zip: zip
        };
      } else if (pattern === addressPatterns[1]) {
        // Handle spaced format
        return {
          street: `${match[1]} ${match[2]} ${match[3]}${match[4] ? ' APT ' + match[4] : ''}`.trim(),
          city: match[5].trim(),
          state: match[6],
          zip: match[7]
        };
      }
    }
  }
  
  // Fallback to original parse-address
  try {
    const parsed = parseAddress.parseLocation(input);
    if (parsed && (parsed.number || parsed.street)) {
      let street = [parsed.number, parsed.prefix, parsed.street, parsed.type, parsed.suffix].filter(Boolean).join(' ').trim();
      return {
        street: street,
        city: parsed.city || '',
        state: parsed.state || '',
        zip: parsed.zip || ''
      };
    }
  } catch (e) {
    // Ignore parse errors
  }
  
  return { street: '', city: '', state: '', zip: '' };
}

testCases.forEach((testCase, index) => {
  console.log(`\nImproved Test ${index + 1}: "${testCase}"`);
  const result = improvedAddressParsing(testCase);
  console.log("  Result:", result);
}); 