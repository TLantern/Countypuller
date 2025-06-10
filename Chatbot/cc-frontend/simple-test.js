const address = "426SOMERVILLESTAPT212 MANCHESTERNH03103561";
console.log("Testing address:", address);

// Let's break this down step by step
console.log("\nStep 1: Basic regex test");
const basicPattern = /(\d+)([A-Z]+)ST(APT)(\d+)([A-Z]+)NH(\d+)/i;
const match = address.match(basicPattern);
console.log("Basic match:", match);

console.log("\nStep 2: Test the actual utils.ts pattern");
const utilsPattern = /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?([A-Z]+)(NH)(\d{5}(?:\d{4})?)/i;
const utilsMatch = address.match(utilsPattern);
console.log("Utils pattern match:", utilsMatch);

if (utilsMatch) {
  console.log("  Group 1 (number):", utilsMatch[1]);
  console.log("  Group 2 (street):", utilsMatch[2]);
  console.log("  Group 3 (apt num):", utilsMatch[3]);
  console.log("  Group 4 (city):", utilsMatch[4]);
  console.log("  Group 5 (state):", utilsMatch[5]);
  console.log("  Group 6 (zip):", utilsMatch[6]);
}

console.log("\nStep 3: What should the result be?");
console.log("Expected result:");
console.log("  street: '426 SOMERVILLE ST APT 212'");
console.log("  city: 'MANCHESTER'");
console.log("  state: 'NH'");
console.log("  zip: '03103-5561'"); 