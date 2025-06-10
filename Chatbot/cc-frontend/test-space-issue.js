const address = "426SOMERVILLESTAPT212 MANCHESTERNH03103561";

console.log("Address analysis:");
console.log("Full address:", address);
console.log("Has space?", address.includes(' '));
console.log("Space position:", address.indexOf(' '));

// The issue: there's a space between "426SOMERVILLESTAPT212" and "MANCHESTERNH03103561"
// Our regex needs to account for this space!

console.log("\nTesting different patterns:");

// Pattern 1: Account for the space
const pattern1 = /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)(\d+)\s+([A-Z]+)(NH)(\d{5,9})/i;
const match1 = address.match(pattern1);
console.log("Pattern 1 (with space):", match1 ? "MATCH!" : "No match");
if (match1) {
  console.log("  Groups:", match1.slice(1));
  console.log("  Result would be:");
  console.log("    street:", `${match1[1]} ${match1[2]} ST APT ${match1[3]}`);
  console.log("    city:", match1[4]);
  console.log("    state:", match1[5]);
  console.log("    zip:", match1[6]);
}

// Pattern 2: Make space optional
const pattern2 = /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)(\d+)\s*([A-Z]+)(NH)(\d{5,9})/i;
const match2 = address.match(pattern2);
console.log("Pattern 2 (optional space):", match2 ? "MATCH!" : "No match");
if (match2) {
  console.log("  Groups:", match2.slice(1));
}

// Pattern 3: More flexible
const pattern3 = /(\d+)([A-Z]+)(ST|AVE|RD|DR|LN|WAY|CT|CIR|PL|BLVD)(APT|UNIT)(\d+)\s*([A-Z]+)(NH)(\d{8,9})/i;
const match3 = address.match(pattern3);
console.log("Pattern 3 (most flexible):", match3 ? "MATCH!" : "No match");
if (match3) {
  console.log("  Groups:", match3.slice(1));
  console.log("  Result would be:");
  console.log("    street:", `${match3[1]} ${match3[2]} ${match3[3]} ${match3[4]} ${match3[5]}`);
  console.log("    city:", match3[6]);
  console.log("    state:", match3[7]);
  console.log("    zip:", match3[8]);
}

console.log("\nConclusion: The regex needs to account for the space before the city name!");
console.log("Updated pattern should be: \\s+ or \\s* before the city group");

// Test the corrected pattern that should work:
const correctedPattern = /(\d+)([A-Z]+)(ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(APT|UNIT)?(\d+)?\s*([A-Z]+)(NH)(\d{5,9})/i;
const correctedMatch = address.match(correctedPattern);
console.log("\n✅ CORRECTED PATTERN:", correctedMatch ? "SUCCESS!" : "Still failed");

if (correctedMatch) {
  const number = correctedMatch[1];
  const streetName = correctedMatch[2];
  const streetType = correctedMatch[3];
  const aptType = correctedMatch[4] || 'APT';
  const aptNum = correctedMatch[5] || '';
  const city = correctedMatch[6];
  const state = correctedMatch[7];
  const zip = correctedMatch[8];
  
  const formattedZip = zip.length >= 8 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
  
  console.log("  ✅ Final parsed result:");
  console.log("    street:", `${number} ${streetName} ${streetType}${aptNum ? ' ' + aptType + ' ' + aptNum : ''}`);
  console.log("    city:", city);
  console.log("    state:", state);
  console.log("    zip:", formattedZip);
} 