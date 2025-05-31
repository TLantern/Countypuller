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
 * Uses parse-address to extract street, city, state, zip, and county.
 * If any required field is missing, attempts to fetch property data using available fields and fill in the missing ones.
 */
export async function normalizeAttomParams(input: string, fetchPropertyData?: (params: any) => Promise<any>): Promise<{ street: string, city?: string, state?: string, zip?: string, county?: string }> {
  let parsed: any = {};
  try {
    parsed = parseAddress.parseLocation(input);
  } catch (e) {
    parsed = {};
  }
  let street = '', city = '', state = '', zip = '', county = '';
  if (parsed) {
    street = [parsed.number, parsed.prefix, parsed.street, parsed.type, parsed.suffix].filter(Boolean).join(' ').trim();
    city = parsed.city || '';
    state = parsed.state || '';
    zip = parsed.zip || '';
    county = parsed.county || '';
  }

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
