// Test enhanced address parsing with condensed formats
const testAddresses = [
  '170SEWALLST',
  '459KimballStreet',
  '459KimballStreetUnit1', 
  '2312GILMANST',
  '426SOMERVILLE',
  '722EIndustrialPar',
  '722ChestnutStree',
  'AssociationIncare', // This one might not be an address
  '1234NMainStreet',
  '567WashingtonAve',
  '890NorthwoodDr'
];

// Simple version of the regex patterns from utils.ts
function testAddressParsing(input) {
  console.log(`\nTesting: "${input}"`);
  
  // Test the extraction patterns
  const extractionPatterns = [
    // Pattern 1: With clear street type
    /^(\d+[NSEW]?[A-Z][a-zA-Z]*?(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard|Park|Par|Industrial|Industr|Tree|Stree)(?:Unit|Apt|Suite|Ste)?\d*[A-Z]?)/i,
    // Pattern 2: Without clear street type
    /^(\d+[NSEW]?[A-Z][a-zA-Z]{3,20})/i
  ];
  
  let extracted = input;
  for (const pattern of extractionPatterns) {
    const match = input.match(pattern);
    if (match) {
      // Additional validation for pattern 2
      if (pattern === extractionPatterns[1]) {
        const nonAddressPatterns = /^(\d+)(whats?|what|tell|about|info|details|property|address)/i;
        if (nonAddressPatterns.test(match[1])) {
          continue;
        }
      }
      extracted = match[1];
      console.log(`  Extracted: "${extracted}"`);
      break;
    }
  }
  
  // Test the parsing patterns
  const parsingPatterns = [
    // Pattern 0: With directional prefix
    {
      name: 'Directional + Street Type',
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]*?)(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard|Park|Par|Industrial|Industr|Tree|Stree)(?:Unit|Apt|Suite|Ste)?(\d+[A-Z]?)?$/i,
      handler: (match) => {
        const [full, number, direction, streetName, streetType, unitNumber] = match;
        
        let fullStreetType = streetType.toLowerCase();
        if (fullStreetType === 'par') fullStreetType = 'Park';
        else if (fullStreetType === 'industr') fullStreetType = 'Industrial';
        else if (fullStreetType === 'stree') fullStreetType = 'Street';
        else if (fullStreetType === 'st') fullStreetType = 'Street';
        else if (fullStreetType === 'ave') fullStreetType = 'Avenue';
        else if (fullStreetType === 'rd') fullStreetType = 'Road';
        else if (fullStreetType === 'dr') fullStreetType = 'Drive';
        else if (fullStreetType === 'ln') fullStreetType = 'Lane';
        else if (fullStreetType === 'ct') fullStreetType = 'Court';
        else if (fullStreetType === 'cir') fullStreetType = 'Circle';
        else if (fullStreetType === 'pl') fullStreetType = 'Place';
        else if (fullStreetType === 'blvd') fullStreetType = 'Boulevard';
        else fullStreetType = streetType;
        
        let street = `${number} ${direction ? direction + ' ' : ''}${streetName} ${fullStreetType}`;
        if (unitNumber) {
          street += ` Unit ${unitNumber}`;
        }
        return street.trim();
      }
    },
    // Pattern 1: Simple without street type
    {
      name: 'Simple Address',
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]{3,})$/i,
      handler: (match) => {
        const [full, number, direction, streetName] = match;
        
        if (streetName.length < 4 || streetName.length > 20) {
          return null;
        }
        
        return `${number} ${direction ? direction + ' ' : ''}${streetName}`.trim();
      }
    },
    // Pattern 2: With units
    {
      name: 'With Unit',
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]*?)(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard)(Unit|Apt|Apartment|Suite|Ste)(\d+[A-Z]?)$/i,
      handler: (match) => {
        const [full, number, direction, streetName, streetType, unitType, unitNumber] = match;
        
        let fullStreetType = streetType.toLowerCase();
        if (fullStreetType === 'st') fullStreetType = 'Street';
        else if (fullStreetType === 'ave') fullStreetType = 'Avenue';
        else if (fullStreetType === 'rd') fullStreetType = 'Road';
        else if (fullStreetType === 'dr') fullStreetType = 'Drive';
        else if (fullStreetType === 'ln') fullStreetType = 'Lane';
        else if (fullStreetType === 'ct') fullStreetType = 'Court';
        else if (fullStreetType === 'cir') fullStreetType = 'Circle';
        else if (fullStreetType === 'pl') fullStreetType = 'Place';
        else if (fullStreetType === 'blvd') fullStreetType = 'Boulevard';
        else fullStreetType = streetType;
        
        let fullUnitType = unitType.toLowerCase();
        if (fullUnitType === 'apt') fullUnitType = 'Apartment';
        else if (fullUnitType === 'ste') fullUnitType = 'Suite';
        else fullUnitType = unitType;
        
        return `${number} ${direction ? direction + ' ' : ''}${streetName} ${fullStreetType} ${fullUnitType} ${unitNumber}`.trim();
      }
    }
  ];
  
  let parsed = null;
  for (const pattern of parsingPatterns) {
    const match = extracted.match(pattern.regex);
    if (match) {
      const result = pattern.handler(match);
      if (result) {
        parsed = result;
        console.log(`  Matched: ${pattern.name}`);
        console.log(`  Parsed: "${result}"`);
        break;
      }
    }
  }
  
  if (!parsed) {
    console.log(`  ❌ No match found`);
  } else {
    console.log(`  ✅ Successfully parsed`);
  }
}

console.log('Testing Enhanced Address Parsing');
console.log('================================');

testAddresses.forEach(testAddressParsing);

console.log('\n\nFallback Search Query Test:');
console.log('==========================');

// Test fallback search query generation
testAddresses.forEach(address => {
  console.log(`\nInput: "${address}"`);
  
  // Simple version of createFallbackSearchQuery logic
  let readable = address;
  
  // Add space before Street/Ave/etc
  readable = readable.replace(/(Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct|Circle|Cir|Place|Pl|Boulevard|Blvd)/gi, ' $1');
  
  // Add space before Unit/Apt
  readable = readable.replace(/(Unit|Apt|Apartment|Suite|Ste)/gi, ' $1');
  
  // Add space before numbers after letters (for unit numbers)
  readable = readable.replace(/([A-Za-z])(\d)/g, '$1 $2');
  
  // Add space between number and letters at the start
  readable = readable.replace(/^(\d+)([A-Za-z])/g, '$1 $2');
  
  // Clean up multiple spaces
  readable = readable.replace(/\s+/g, ' ').trim();
  
  console.log(`Fallback: "${readable}"`);
}); 