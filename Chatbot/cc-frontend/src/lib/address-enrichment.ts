/**
 * Address Enrichment for Serverless Environments
 * 
 * This module provides address validation and property data enrichment
 * using external APIs, designed to work in serverless environments
 * where Python might not be available.
 */

interface AddressValidationResult {
  raw_address: string;
  canonical_address: string;
  success: boolean;
  error?: string;
}

interface AttomPropertyData {
  attomid?: string;
  est_balance?: number;
  available_equity?: number;
  ltv?: number;
  market_value?: number;
  loans_count?: number;
  owner_name?: string;
  processed_at: string;
}

interface EnrichmentResult extends AddressValidationResult, AttomPropertyData {}

/**
 * Validate address using Google Maps Geocoding API
 */
export async function validateAddressGoogle(rawAddress: string, apiKey: string): Promise<AddressValidationResult> {
  try {
    const encodedAddress = encodeURIComponent(rawAddress);
    const url = `https://maps.googleapis.com/maps/api/geocode/json?address=${encodedAddress}&key=${apiKey}`;
    
    const response = await fetch(url);
    const data = await response.json();
    
    if (data.status === 'OK' && data.results && data.results.length > 0) {
      const result = data.results[0];
      const canonicalAddress = result.formatted_address;
      
      return {
        raw_address: rawAddress,
        canonical_address: canonicalAddress,
        success: true
      };
    } else {
      return {
        raw_address: rawAddress,
        canonical_address: rawAddress, // fallback to original
        success: false,
        error: `Google Maps API error: ${data.status}`
      };
    }
  } catch (error) {
    return {
      raw_address: rawAddress,
      canonical_address: rawAddress, // fallback to original
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error'
    };
  }
}

/**
 * Parse address components for ATTOM API
 */
function parseAddressComponents(address: string): { [key: string]: string } {
  // Simple address parsing - can be enhanced
  const parts = address.split(',').map(p => p.trim());
  
  if (parts.length >= 3) {
    const streetAddress = parts[0];
    const city = parts[1];
    const stateZip = parts[2];
    
    // Extract state and zip
    const stateZipMatch = stateZip.match(/^(.+?)\s+(\d{5}(?:-\d{4})?)$/);
    const state = stateZipMatch ? stateZipMatch[1] : stateZip;
    const zip = stateZipMatch ? stateZipMatch[2] : '';
    
    return {
      address1: streetAddress,
      locality: city,
      countrySubd: state,
      postal1: zip.substring(0, 5)
    };
  }
  
  return { address1: address };
}

/**
 * Get property data from ATTOM API
 */
export async function getAttomPropertyData(canonicalAddress: string, apiKey: string): Promise<AttomPropertyData> {
  try {
    const addressComponents = parseAddressComponents(canonicalAddress);
    
    // Build ATTOM API URL
    const params = new URLSearchParams();
    Object.entries(addressComponents).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });
    
    const url = `https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile?${params.toString()}`;
    
    const response = await fetch(url, {
      headers: {
        'Accept': 'application/json',
        'apikey': apiKey
      }
    });
    
    if (!response.ok) {
      throw new Error(`ATTOM API error: ${response.status} ${response.statusText}`);
    }
    
    const data = await response.json();
    
    if (data.status && data.status.code === 0 && data.property && data.property.length > 0) {
      const property = data.property[0];
      
      // Extract basic property info
      const attomid = property.identifier?.attomId?.toString();
      const assessment = property.assessment;
      const lot = property.lot;
      
      // Calculate estimated values
      const marketValue = assessment?.market?.mktTtlValue || lot?.lotSize1 || 0;
      const assessedValue = assessment?.assessed?.assdTtlValue || 0;
      
      // For now, we'll use simplified calculations
      // In a full implementation, you'd make additional API calls for loan data
      const estimatedBalance = marketValue * 0.7; // Rough estimate
      const availableEquity = Math.max(0, marketValue - estimatedBalance);
      const ltv = marketValue > 0 ? estimatedBalance / marketValue : 0;
      
      return {
        attomid,
        est_balance: estimatedBalance,
        available_equity: availableEquity,
        ltv,
        market_value: marketValue,
        loans_count: 1, // Simplified
        owner_name: property.owner?.owner1?.lastName || null,
        processed_at: new Date().toISOString()
      };
    } else {
      // No property found
      return {
        processed_at: new Date().toISOString()
      };
    }
  } catch (error) {
    console.error('ATTOM API error:', error);
    return {
      processed_at: new Date().toISOString()
    };
  }
}

/**
 * Main address enrichment function
 */
export async function enrichAddress(rawAddress: string): Promise<EnrichmentResult> {
  const googleApiKey = process.env.GOOGLE_MAPS_API_KEY;
  const attomApiKey = process.env.ATTOM_API_KEY;
  
  if (!googleApiKey) {
    throw new Error('GOOGLE_MAPS_API_KEY environment variable is required');
  }
  
  if (!attomApiKey) {
    throw new Error('ATTOM_API_KEY environment variable is required');
  }
  
  // Step 1: Validate and normalize address
  const addressResult = await validateAddressGoogle(rawAddress, googleApiKey);
  
  // Step 2: Get property data from ATTOM
  const propertyData = await getAttomPropertyData(addressResult.canonical_address, attomApiKey);
  
  // Combine results
  return {
    ...addressResult,
    ...propertyData
  };
}

/**
 * Fallback enrichment for when Python pipeline is not available
 */
export async function enrichAddressFallback(rawAddress: string): Promise<EnrichmentResult> {
  console.log('🔄 Using Node.js fallback for address enrichment');
  
  try {
    return await enrichAddress(rawAddress);
  } catch (error) {
    console.error('❌ Node.js enrichment failed:', error);
    
    // Return minimal result
    return {
      raw_address: rawAddress,
      canonical_address: rawAddress,
      success: false,
      error: error instanceof Error ? error.message : 'Enrichment failed',
      processed_at: new Date().toISOString()
    };
  }
} 