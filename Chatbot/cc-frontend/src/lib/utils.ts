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
 * Enhanced address parsing that handles various formats including condensed OCR output
 */
function parseAddressEnhanced(input: string): { street: string, city: string, state: string, zip: string } {
  // Clean up input
  const cleanInput = input.trim();
  
  // Strategy 1: Extract address from phrases like "tell me about property ADDRESS"
  const propertyMatch = cleanInput.match(/(?:property|address|about|for)\s+([A-Z0-9][A-Z0-9\s]+(?:NH|MANCHESTER|NASHUA|PELHAM|DERRY|CONCORD)[A-Z0-9\s\-]*)/i);
  const addressText = propertyMatch ? propertyMatch[1].trim() : cleanInput;
  
  // Strategy 2: Enhanced regex patterns for different address formats
  const addressPatterns = [
    // Pattern 1: Condensed format like "747SILVERSTAPT1MANCHESTERNH031034401"
    {
      regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?([A-Z]+)(NH)(\d{5}(?:\d{4})?)/i,
      handler: (match: RegExpMatchArray) => {
        const number = match[1];
        const streetName = match[2];
        const aptNum = match[3] || '';
        const city = match[4];
        const state = match[5];
        const zip = match[6];
        
        // Format ZIP code properly
        const formattedZip = zip.length === 9 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
        
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
      regex: /(\d+)\s+([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:APT|UNIT)?(\d+)?\s+([A-Z]+)\s+(NH)\s+(\d{5}(?:\d{4})?)/i,
      handler: (match: RegExpMatchArray) => {
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
    
    // Pattern 4: Handle addresses with extra text like "400WILLOWSTSTE1MANCHESTERNH031036300"
    {
      regex: /(\d+)([A-Z]+)(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|WAY|CT|COURT|CIR|CIRCLE|PL|PLACE|BLVD|BOULEVARD)(?:STE|SUITE)?(\d+)?([A-Z]+)(NH)(\d{5}(?:\d{4})?)/i,
      handler: (match: RegExpMatchArray) => {
        const number = match[1];
        const streetName = match[2];
        const suiteNum = match[3] || '';
        const city = match[4];
        const state = match[5];
        const zip = match[6];
        
        const formattedZip = zip.length === 9 ? `${zip.slice(0, 5)}-${zip.slice(5)}` : zip;
        
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
      if (result.street && result.city && result.state && result.zip) {
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
