const testAddress = "426SOMERVILLESTAPT212 MANCHESTERNH03103561";

console.log("Testing specific problematic address:", testAddress);
console.log("=".repeat(60));

// Test the enhanced regex pattern from utils.ts
const addressPatterns = [
  // Pattern 1: Condensed format like "426SOMERVILLESTAPT212MANCHESTERNH03103561"
  {
    name: "Pattern 1 - Original utils.ts pattern",
    regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?([A-Z]+)(NH)(\d{5}(?:\d{4})?)/i,
    handler: (match) => {
      const number = match[1];
      const streetName = match[2];
      const aptNum = match[3] || '';
      const city = match[4];
      const state = match[5];
      const zip = match[6];
      
      const formattedZip = zip.length === 9 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
      
      return {
        street: `${number} ${streetName} ST${aptNum ? ' APT ' + aptNum : ''}`,
        city: city,
        state: state,
        zip: formattedZip
      };
    }
  },
  
  // Pattern 2: Fixed pattern for SOMERVILLE with potential OCR issues
  {
    name: "Pattern 2 - Fixed for SOMERVILLE", 
    regex: /(\d+)([A-Z]+?)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)(\d+)([A-Z]+?)(NH)(\d{5,9})/i,
    handler: (match) => {
      const number = match[1];
      const streetName = match[2]; 
      const aptNum = match[3];
      const city = match[4];
      const state = match[5];
      const zip = match[6];
      
      const formattedZip = zip.length === 9 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
      
      return {
        street: `${number} ${streetName} ST APT ${aptNum}`,
        city: city,
        state: state,
        zip: formattedZip
      };
    }
  },
  
  // Pattern 3: More aggressive pattern to catch the issue
  {
    name: "Pattern 3 - Most permissive",
    regex: /^(\d+)([A-Z]+)(ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(APT|UNIT)?(\d+)?([A-Z]+)(NH)(\d{5,9})$/i,
    handler: (match) => {
      const number = match[1];
      const streetName = match[2];
      const streetType = match[3];
      const aptType = match[4] || 'APT';
      const aptNum = match[5] || '';
      const city = match[6];
      const state = match[7];
      const zip = match[8];
      
      const formattedZip = zip.length === 9 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
      
      return {
        street: `${number} ${streetName} ${streetType}${aptNum ? ' ' + aptType + ' ' + aptNum : ''}`,
        city: city,
        state: state,
        zip: formattedZip
      };
    }
  },
  
  // Pattern 4: Manual breakdown for this specific address
  {
    name: "Pattern 4 - Specific manual breakdown",
    regex: /^426SOMERVILLE(ST|STREET)(APT|UNIT)(\d+)MANCHESTER(NH)(\d{9})$/i,
    handler: (match) => {
      return {
        street: `426 SOMERVILLE ST APT ${match[3]}`,
        city: 'MANCHESTER',
        state: 'NH',
        zip: `${match[5].slice(0, 5)}-${match[5].slice(5)}`
      };
    }
  }
];

addressPatterns.forEach((pattern, index) => {
  console.log(`\n${pattern.name}:`);
  console.log(`Regex: ${pattern.regex}`);
  
  const match = testAddress.match(pattern.regex);
  console.log(`Match result:`, match);
  
  if (match) {
    try {
      const result = pattern.handler(match);
      console.log(`✅ Parsed result:`, result);
      console.log(`   Has all fields: ${result.street && result.city && result.state && result.zip ? 'YES' : 'NO'}`);
    } catch (e) {
      console.log(`❌ Handler error:`, e.message);
    }
  } else {
    console.log(`❌ No match`);
  }
});

// Also test what the SERP query would be
console.log("\n" + "=".repeat(60));
console.log("SERP Search Query Test:");
console.log("Original message:", testAddress);
console.log("Search query used:", testAddress); // This is the problematic part!

// Better SERP search would be:
console.log("Better search query would be: '426 Somerville Street Manchester NH'"); 