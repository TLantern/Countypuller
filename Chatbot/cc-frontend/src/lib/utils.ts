import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import parseAddress from "parse-address"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const US_STATES = [
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
  "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut","Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa","Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan","Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada","New Hampshire","New Jersey","New Mexico","New York","North Carolina","North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island","South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont","Virginia","Washington","West Virginia","Wisconsin","Wyoming"
];

/**
 * Normalize user input into ATTOM API parameters.
 * Uses enhanced address parsing to handle various formats including condensed OCR output.
 * If any required field is missing, attempts to fetch property data using available fields and fill in the missing ones.
 */
export async function normalizeAttomParams(input: string, fetchPropertyData?: (params: any) => Promise<any>): Promise<{ street: string, city?: string, state?: string, zip?: string, county?: string }> {
  let street = '', city = '', state = '', zip = '', county = '';

  // Enhanced address parsing with multiple strategies
  const addressResult = parseAddressEnhanced(input);
  street = addressResult.street;
  city = addressResult.city;
  state = addressResult.state;
  zip = addressResult.zip;

  // If any required field is missing, try to fetch property data to fill in
  if ((!street || !city || !state || !zip) && fetchPropertyData) {
    const propertyData = await fetchPropertyData({ street, city, state, zip });
    if (propertyData) {
      street = street || propertyData.street || '';
      city = city || propertyData.city || '';
      state = state || propertyData.state || '';
      zip = zip || propertyData.zip || '';
      county = county || propertyData.county || '';
    }
  }

  if (!county) {
    county = 'US';
  }

  // Ensure all fields are uppercase
  street = street.toUpperCase();
  city = city.toUpperCase();
  state = state.toUpperCase();
  zip = zip.toUpperCase();
  county = county.toUpperCase();

  return { street, city, state, zip, county };
}

/**
 * Create a better search query for SERP API when address parsing fails
 */
export function createFallbackSearchQuery(input: string): string {
  // Try to extract readable components from malformed addresses
  const cleanedInput = input.replace(/[^\w\s]/g, ' ').replace(/\s+/g, ' ').trim();
  
  // Handle condensed address formats - enhanced to cover all variations
  const condensedPatterns = [
    // Pattern 1: With directional prefix like "722EIndustrialPar"
    {
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]*)(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard|Park|Par|Industrial|Industr|Tree|Stree)(?:Unit|Apt|Suite|Ste)?(\d+[A-Z]?)?$/i,
      handler: (match: RegExpMatchArray) => {
        const [full, number, direction, streetName, streetType, unitNumber] = match;
        
        // Handle truncated street types
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
        
        let result = `${number} ${direction ? direction + ' ' : ''}${streetName} ${fullStreetType}`;
        if (unitNumber) {
          result += ` Unit ${unitNumber}`;
        }
        return result.trim();
      }
    },
    // Pattern 2: With units like "459KimballStreetUnit1"
    {
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]*?)(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard)(Unit|Apt|Apartment|Suite|Ste)(\d+[A-Z]?)$/i,
      handler: (match: RegExpMatchArray) => {
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
    },
    // Pattern 3: Simple condensed without clear street type like "426SOMERVILLE"
    {
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]{4,20})$/i,
      handler: (match: RegExpMatchArray) => {
        const [full, number, direction, streetName] = match;
        return `${number} ${direction ? direction + ' ' : ''}${streetName}`.trim();
      }
    }
  ];
  
  // Try condensed patterns first
  for (const pattern of condensedPatterns) {
    const match = input.match(pattern.regex);
    if (match) {
      return pattern.handler(match);
    }
  }
  
  // Look for NH addresses specifically
  if (/NH/i.test(input)) {
    // Try to extract components manually
    const patterns = [
      // Pattern for: NumberStreetSTAPTNumberCityNH...
      {
        regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?\s*([A-Z]+)NH/i,
        handler: (match: RegExpMatchArray) => {
          const number = match[1];
          const streetName = match[2];
          const aptNum = match[3] || '';
          const city = match[4];
          return `${number} ${streetName} Street ${aptNum ? 'Apartment ' + aptNum : ''} ${city} NH`;
        }
      }
    ];
    
    for (const pattern of patterns) {
      const match = input.match(pattern.regex);
      if (match) {
        return pattern.handler(match);
      }
    }
    
    // Fallback: just add spaces to make it more readable
    return input.replace(/([A-Z])([A-Z][a-z])/g, '$1 $2')
                .replace(/([a-z])([A-Z])/g, '$1 $2')
                .replace(/([A-Z]+)(ST|AVE|RD|DR|LN|WAY|CT|CIR|PL|BLVD)/gi, '$1 $2')
                .replace(/(ST|AVE|RD|DR|LN|WAY|CT|CIR|PL|BLVD)(APT|UNIT)/gi, '$1 $2')
                .replace(/(APT|UNIT)(\d+)/gi, '$1 $2')
                .replace(/([A-Z]+)(NH)/gi, '$1 $2')
                .replace(/\s+/g, ' ')
                .trim();
  }
  
  // General fallback: Add spaces to condensed formats
  let readable = input;
  
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
  
  return readable || cleanedInput;
}

/**
 * Enhanced address parsing that handles various formats including condensed OCR output
 */
function parseAddressEnhanced(input: string): { street: string, city: string, state: string, zip: string } {
  // Clean up input
  const cleanInput = input.trim();
  
  // Strategy 1: Extract address from phrases like "tell me about property ADDRESS"
  let addressText = cleanInput;
  
  // First try to extract full addresses with NH cities
  const fullAddressMatch = cleanInput.match(/(?:property|address|about|for)\s+([A-Z0-9][A-Z0-9\s]+(?:NH|MANCHESTER|NASHUA|PELHAM|DERRY|CONCORD)[A-Z0-9\s\-]*)/i);
  if (fullAddressMatch) {
    addressText = fullAddressMatch[1].trim();
  } else {
    // Try to extract partial addresses at the beginning of the input - enhanced to match all condensed formats
              const partialAddressPatterns = [
       // Pattern 1: With clear street type - "459KimballStreetUnit1", "170SEWALLST", "722EIndustrialPar"  
       /^(\d+[NSEW]?[A-Z][a-zA-Z]*(?:St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard|Park|Par|Industrial|Industr|Tree|Stree)(?:Unit|Apt|Suite|Ste)?\d*[A-Z]?)/i,
       // Pattern 2: Without clear street type - "426SOMERVILLE" (at least 4 chars for street name)
       /^(\d+[NSEW]?[A-Z][a-zA-Z]{4,})/i
     ];
    
    for (const pattern of partialAddressPatterns) {
      const match = cleanInput.match(pattern);
      if (match) {
        // Additional validation for pattern 2 to avoid false positives
        if (pattern === partialAddressPatterns[1]) {
          const extracted = match[1];
          // Skip if it looks like it might be something else (contains common non-address words)
          const nonAddressPatterns = /^(\d+)(whats?|what|tell|about|info|details|property|address)/i;
          if (nonAddressPatterns.test(extracted)) {
            continue;
          }
        }
        addressText = match[1].trim();
        break;
      }
    }
  }
  
  // Strategy 2: Enhanced regex patterns for different address formats
  const addressPatterns = [
    // Pattern 0: Condensed addresses - with directional prefix like "722EIndustrialPar"
    {
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]*)(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard|Park|Par|Industrial|Industr|Tree|Stree)(?:Unit|Apt|Suite|Ste)?(\d+[A-Z]?)?$/i,
      handler: (match: RegExpMatchArray) => {
        const [full, number, direction, streetName, streetType, unitNumber] = match;
        
        // Handle truncated street types
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
        else fullStreetType = streetType; // Keep original if no mapping
        
        let street = `${number} ${direction ? direction + ' ' : ''}${streetName} ${fullStreetType}`;
        if (unitNumber) {
          street += ` Unit ${unitNumber}`;
        }
        
        return {
          street: street.trim(),
          city: '',
          state: '',
          zip: ''
        };
      }
    },
    
    // Pattern 0b: Simple condensed addresses without clear street type like "426SOMERVILLE"
    {
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]{3,})$/i,
      handler: (match: RegExpMatchArray) => {
        const [full, number, direction, streetName] = match;
        
        // Only match if it looks like a street name (reasonable length)
        if (streetName.length < 4 || streetName.length > 20) {
          return { street: '', city: '', state: '', zip: '' };
        }
        
        let street = `${number} ${direction ? direction + ' ' : ''}${streetName}`;
        
        return {
          street: street.trim(),
          city: '',
          state: '',
          zip: ''
        };
      }
    },
    
    // Pattern 0c: Condensed addresses with units like "459KimballStreetUnit1"
    {
      regex: /^(\d+)([NSEW]?)([A-Z][a-zA-Z]*)(St|Street|Ave|Avenue|Rd|Road|Dr|Drive|Ln|Lane|Way|Court|Ct|Circle|Cir|Place|Pl|Blvd|Boulevard)(Unit|Apt|Apartment|Suite|Ste)(\d+[A-Z]?)$/i,
      handler: (match: RegExpMatchArray) => {
        const [full, number, direction, streetName, streetType, unitType, unitNumber] = match;
        
        // Normalize street type
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
        
        // Normalize unit type
        let fullUnitType = unitType.toLowerCase();
        if (fullUnitType === 'apt') fullUnitType = 'Apartment';
        else if (fullUnitType === 'ste') fullUnitType = 'Suite';
        else fullUnitType = unitType;
        
        let street = `${number} ${direction ? direction + ' ' : ''}${streetName} ${fullStreetType} ${fullUnitType} ${unitNumber}`;
        
        return {
          street: street.trim(),
          city: '',
          state: '',
          zip: ''
        };
      }
    },
    
    // Pattern 1: Condensed format like "426SOMERVILLESTAPT212 MANCHESTERNH03103561" (FIXED to handle space and 8-digit ZIP)
    {
      regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?\s*([A-Z]+)(NH)(\d{5,9})/i,
      handler: (match: RegExpMatchArray) => {
        const number = match[1];
        const streetName = match[2];
        const aptNum = match[3] || '';
        const city = match[4];
        const state = match[5];
        const zip = match[6];
        
        // Format ZIP code properly - handle 8-digit malformed ZIPs
        let formattedZip = zip;
        if (zip.length === 9) {
          formattedZip = `${zip.slice(0, 5)}-${zip.slice(5)}`;
        } else if (zip.length === 8) {
          // Assume first 5 digits are ZIP, last 3 are partial ZIP+4
          formattedZip = `${zip.slice(0, 5)}-${zip.slice(5)}`;
        }
        
        return {
          street: `${number} ${streetName} ST${aptNum ? ' APT ' + aptNum : ''}`,
          city: city,
          state: state,
          zip: formattedZip
        };
      }
    },
    
    // Pattern 2: Slightly spaced condensed format like "747 SILVERSTAPT1 MANCHESTER NH 031034401"
    {
      regex: /(\d+)\s+([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?\s+([A-Z]+)\s+(NH)\s+(\d{5,9})/i,
      handler: (match: RegExpMatchArray) => {
        const number = match[1];
        const streetName = match[2];
        const aptNum = match[3] || '';
        const city = match[4];
        const state = match[5];
        const zip = match[6];
        
        let formattedZip = zip;
        if (zip.length === 9) {
          formattedZip = `${zip.slice(0, 5)}-${zip.slice(5)}`;
        } else if (zip.length === 8) {
          formattedZip = `${zip.slice(0, 5)}-${zip.slice(5)}`;
        }
        
        return {
          street: `${number} ${streetName} ST${aptNum ? ' APT ' + aptNum : ''}`,
          city: city,
          state: state,
          zip: formattedZip
        };
      }
    },
    
    // Pattern 3: Traditional spaced format like "747 SILVER ST APT 1 MANCHESTER NH 03103-4401"
    {
      regex: /(\d+[A-Z]?)\s+([A-Z][A-Z\s]+?)\s+(ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:\s+(?:APT|UNIT)\s*(\d+[A-Z]?))?\s+([A-Z\s]+?)\s+(NH|[A-Z]{2})\s+(\d{5}(?:-\d{4})?)/i,
      handler: (match: RegExpMatchArray) => {
        return {
          street: `${match[1]} ${match[2].trim()} ${match[3]}${match[4] ? ' APT ' + match[4] : ''}`,
          city: match[5].trim(),
          state: match[6],
          zip: match[7]
        };
      }
    },
    
    // Pattern 4: Handle addresses with extra text like "400WILLOWSTSTE1 MANCHESTERNH031036300" (with space)
    {
      regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:STE|SUITE)?(\d+)?\s*([A-Z]+)(NH)(\d{5,9})/i,
      handler: (match: RegExpMatchArray) => {
        const number = match[1];
        const streetName = match[2];
        const suiteNum = match[3] || '';
        const city = match[4];
        const state = match[5];
        const zip = match[6];
        
        let formattedZip = zip;
        if (zip.length === 9) {
          formattedZip = `${zip.slice(0, 5)}-${zip.slice(5)}`;
        } else if (zip.length === 8) {
          formattedZip = `${zip.slice(0, 5)}-${zip.slice(5)}`;
        }
        
        return {
          street: `${number} ${streetName} ST${suiteNum ? ' STE ' + suiteNum : ''}`,
          city: city,
          state: state,
          zip: formattedZip
        };
      }
    }
  ];
  
  // Try each pattern
  for (const pattern of addressPatterns) {
    const match = addressText.match(pattern.regex);
    if (match) {
      const result = pattern.handler(match);
      // Accept result if it has at least a street (for partial addresses) or complete address info
      if (result.street && (result.city || (!result.city && !result.state && !result.zip))) {
        return result;
      }
    }
  }
  
  // Strategy 3: Fallback to original parse-address library for well-formatted addresses
  try {
    const parsed = parseAddress.parseLocation(addressText);
    if (parsed && parsed.number && parsed.street && parsed.city && parsed.state && parsed.zip) {
      const street = [parsed.number, parsed.prefix, parsed.street, parsed.type, parsed.suffix].filter(Boolean).join(' ').trim();
      return {
        street: street,
        city: parsed.city,
        state: parsed.state,
        zip: parsed.zip + (parsed.plus4 ? '-' + parsed.plus4 : '')
      };
    }
  } catch (e) {
    // Ignore parse errors and continue
  }
  
  // Strategy 4: Return empty if no patterns match (don't try to parse non-address queries)
  return { street: '', city: '', state: '', zip: '' };
}
