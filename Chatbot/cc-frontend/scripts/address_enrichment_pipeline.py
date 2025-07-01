#!/usr/bin/env python3
"""
Address Enrichment Pipeline

This script enriches a list of U.S. street addresses with ATTOM property data
including current loan balance, LTV, and available equity. Results are saved
to both CSV and optionally to a Postgres database.

Usage:
    python address_enrichment_pipeline.py input.csv [--pg-dsn postgres://...] [--calc-date 2024-01-01]

Requirements:
    - GOOGLE_MAPS_API_KEY environment variable for Google Maps Geocoding API (recommended)
      OR USPS_USER_ID environment variable for USPS API (fallback)
    - ATTOM_API_KEY environment variable for ATTOM API
    - Input CSV with 'address' column containing raw addresses
"""

import asyncio
import aiohttp
import argparse
import csv
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
import logging
import backoff
import pandas as pd
import asyncpg
from urllib.parse import quote_plus

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('address_enrichment.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RateLimiter:
    """Rate limiter for ATTOM API (10 requests/second max)"""
    def __init__(self, max_rate: float = 10.0):
        self.max_rate = max_rate
        self.min_interval = 1.0 / max_rate
        self.last_called = 0.0
    
    async def acquire(self):
        now = time.time()
        time_passed = now - self.last_called
        if time_passed < self.min_interval:
            sleep_time = self.min_interval - time_passed
            await asyncio.sleep(sleep_time)
        self.last_called = time.time()

class AddressEnrichmentPipeline:
    def __init__(self, usps_user_id: Optional[str] = None, attom_api_key: Optional[str] = None):
        # Get from environment if not provided
        self.usps_user_id = usps_user_id or os.getenv('USPS_USER_ID')
        self.attom_api_key = attom_api_key or os.getenv('ATTOM_API_KEY')
        self.rate_limiter = RateLimiter()
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=50)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def normalize_address_for_usps(self, address: str) -> Dict[str, str]:
        """Parse raw address into components for USPS validation"""
        # Basic address parsing - you might want to use a more sophisticated parser
        address = address.strip().upper()
        
        # Try to extract ZIP code
        import re
        zip_match = re.search(r'\b(\d{5}(?:-\d{4})?)\b', address)
        zip_code = zip_match.group(1) if zip_match else ""
        
        # Try to extract state (2 letter code before ZIP)
        state_match = re.search(r'\b([A-Z]{2})\s+\d{5}', address)
        state = state_match.group(1) if state_match else ""
        
        # Remove ZIP and state to get address + city
        remaining = address
        if zip_code:
            remaining = remaining.replace(zip_code, "").strip()
        if state:
            remaining = remaining.replace(state, "").strip()
        
        # Split into address and city (city is usually last part after comma)
        parts = remaining.split(',')
        if len(parts) >= 2:
            street_address = parts[0].strip()
            city = parts[1].strip() if len(parts) > 1 else ""
        else:
            # No comma, assume entire remaining is street address
            street_address = remaining.strip()
            city = ""
        
        return {
            'street_address': street_address,
            'city': city,
            'state': state,
            'zip': zip_code
        }
    
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        max_time=60
    )
    async def validate_address_google(self, raw_address: str) -> Tuple[str, str]:
        """
        Validate address using Google Maps Geocoding API
        Returns tuple of (raw_address, canonical_address)
        """
        try:
            # Use Google Maps API key instead of USPS
            google_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
            if not google_api_key:
                # Fallback to USPS if Google key not available
                if self.usps_user_id:
                    return await self.validate_address_usps_fallback(raw_address)
                else:
                    logger.warning(f"No Google Maps API key found, using raw address: '{raw_address}'")
                    return raw_address, raw_address
            
            url = "https://maps.googleapis.com/maps/api/geocode/json"
            params = {
                'address': raw_address,
                'key': google_api_key,
                'components': 'country:US'  # Restrict to US addresses
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['status'] == 'OK' and data['results']:
                        result = data['results'][0]
                        canonical_address = result['formatted_address']
                        
                        # Clean up the formatted address (remove country)
                        if ', USA' in canonical_address:
                            canonical_address = canonical_address.replace(', USA', '')
                        
                        # Also try to extract components for better formatting
                        components = result.get('address_components', [])
                        street_number = ''
                        route = ''
                        locality = ''
                        admin_area_level_1 = ''
                        postal_code = ''
                        
                        for component in components:
                            types = component.get('types', [])
                            if 'street_number' in types:
                                street_number = component['long_name']
                            elif 'route' in types:
                                route = component['long_name']
                            elif 'locality' in types:
                                locality = component['long_name']
                            elif 'administrative_area_level_1' in types:
                                admin_area_level_1 = component['short_name']
                            elif 'postal_code' in types:
                                postal_code = component['long_name']
                        
                        # Build a standardized address if we have components
                        if street_number and route and locality and admin_area_level_1:
                            standardized = f"{street_number} {route}, {locality}, {admin_area_level_1}"
                            if postal_code:
                                standardized += f" {postal_code}"
                            canonical_address = standardized
                        
                        logger.info(f"Google Maps validated: '{raw_address}' -> '{canonical_address}'")
                        return raw_address, canonical_address
                    else:
                        logger.warning(f"Google Maps validation failed for '{raw_address}': {data.get('status', 'Unknown error')}")
                        return raw_address, raw_address
                else:
                    logger.warning(f"Google Maps API error for '{raw_address}': HTTP {response.status}")
                    return raw_address, raw_address
                    
        except Exception as e:
            logger.error(f"Google Maps validation error for '{raw_address}': {str(e)}")
            return raw_address, raw_address

    async def validate_address_google_maps(self, raw_address: str) -> Optional[Dict[str, Any]]:
        """Public method to test Google Maps validation specifically"""
        try:
            raw, canonical = await self.validate_address_google(raw_address)
            return {
                'raw_address': raw,
                'canonical_address': canonical,
                'google_validated': raw != canonical
            }
        except Exception as e:
            logger.error(f"Google Maps validation failed: {str(e)}")
            return None

    async def validate_address_usps_fallback(self, raw_address: str) -> Tuple[str, str]:
        """
        Fallback USPS validation method (original implementation)
        """
        try:
            parsed = self.normalize_address_for_usps(raw_address)
            
            # Build USPS XML request
            xml_request = f"""
            <AddressValidateRequest USERID="{self.usps_user_id}">
                <Revision>1</Revision>
                <Address ID="0">
                    <Address1></Address1>
                    <Address2>{parsed['street_address']}</Address2>
                    <City>{parsed['city']}</City>
                    <State>{parsed['state']}</State>
                    <Zip5>{parsed['zip'][:5] if parsed['zip'] else ''}</Zip5>
                    <Zip4>{parsed['zip'][6:] if len(parsed['zip']) > 5 else ''}</Zip4>
                </Address>
            </AddressValidateRequest>
            """.strip()
            
            url = f"https://secure.shippingapis.com/ShippingAPI.dll?API=Verify&XML={quote_plus(xml_request)}"
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    xml_response = await response.text()
                    root = ET.fromstring(xml_response)
                    
                    # Check for errors
                    error = root.find('.//Error')
                    if error is not None:
                        error_desc = error.find('Description')
                        logger.warning(f"USPS validation error for '{raw_address}': {error_desc.text if error_desc is not None else 'Unknown error'}")
                        return raw_address, raw_address
                    
                    # Extract validated address
                    address_elem = root.find('.//Address')
                    if address_elem is not None:
                        address2 = address_elem.find('Address2')
                        city = address_elem.find('City')
                        state = address_elem.find('State')
                        zip5 = address_elem.find('Zip5')
                        zip4 = address_elem.find('Zip4')
                        
                        canonical_parts = []
                        if address2 is not None and address2.text:
                            canonical_parts.append(address2.text)
                        if city is not None and city.text:
                            canonical_parts.append(city.text)
                        if state is not None and state.text:
                            canonical_parts.append(state.text)
                        if zip5 is not None and zip5.text:
                            zip_part = zip5.text
                            if zip4 is not None and zip4.text:
                                zip_part += f"-{zip4.text}"
                            canonical_parts.append(zip_part)
                        
                        canonical_address = ', '.join(canonical_parts)
                        logger.info(f"USPS validated: '{raw_address}' -> '{canonical_address}'")
                        return raw_address, canonical_address
                
                logger.warning(f"USPS validation failed for '{raw_address}': HTTP {response.status}")
                return raw_address, raw_address
                
        except Exception as e:
            logger.error(f"USPS validation error for '{raw_address}': {str(e)}")
            return raw_address, raw_address
    
    def parse_canonical_address(self, canonical_address: str) -> Dict[str, str]:
        """Parse canonical address into components for ATTOM API
        
        ATTOM expects:
        - address1: Street address (e.g., "14119 COYOTE POINTE")  
        - address2: City, State ZIP (e.g., "CYPRESS, TX 77433")
        
        OR one-line format as single parameter
        """
        import re
        
        # Clean the address
        address = canonical_address.strip()
        
        # Try to parse into components
        # Common formats: 
        # "14119 COYOTE POINTE, CYPRESS, TX 77433"
        # "14119 Coyote Pointe, Cypress, TX 77433"
        
        parts = address.split(', ')
        
        if len(parts) >= 3:
            # Multi-part address
            street = parts[0].strip()
            city = parts[1].strip() 
            state_zip = parts[2].strip()
            
            return {
                'address1': street,
                'address2': f"{city}, {state_zip}"
            }
        elif len(parts) == 2:
            # Two parts - assume "STREET, CITY STATE ZIP"
            street = parts[0].strip()
            city_state_zip = parts[1].strip()
            
            return {
                'address1': street,
                'address2': city_state_zip
            }
        else:
            # Single line - try to split at the first number/street vs city pattern
            # Look for pattern: "NUMBER STREET_NAME, CITY ..."
            match = re.match(r'^(.+?)(?:,\s*(.+))?$', address)
            if match and match.group(2):
                return {
                    'address1': match.group(1).strip(),
                    'address2': match.group(2).strip()
                }
            else:
                # Fallback: use the whole address as a single parameter
                return {
                    'address': address  # Use single parameter format
                }
    
    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, asyncio.TimeoutError),
        max_tries=3,
        max_time=60
    )
    async def get_attom_property_data(self, canonical_address: str) -> Optional[Dict[str, Any]]:
        """Get full property data from ATTOM API including equity information
        
        According to ATTOM docs, we can use multiple approaches:
        1. address1 + address2 (street + city,state zip)
        2. Single 'address' parameter
        3. Individual components (address, locality, postalcode)
        """
        await self.rate_limiter.acquire()
        
        try:
            parsed = self.parse_canonical_address(canonical_address)
            
            # Try multiple ATTOM API parameter formats for better success
            param_sets = []
            
            if 'address' in parsed:
                # Single address parameter
                param_sets.append({'address': parsed['address']})
            else:
                # Two-part address approach
                if parsed.get('address1') and parsed.get('address2'):
                    param_sets.append({
                        'address1': parsed['address1'], 
                        'address2': parsed['address2']
                    })
                    
                    # Also try extracting city, state, zip for alternative format
                    city_state_zip = parsed['address2']
                    parts = city_state_zip.split(', ')
                    if len(parts) >= 2:
                        city = parts[0].strip()
                        state_zip = parts[1].strip()
                        
                        # Split state and zip
                        state_zip_parts = state_zip.split(' ')
                        if len(state_zip_parts) >= 2:
                            state = state_zip_parts[0].strip()
                            postal_code = state_zip_parts[1].strip()
                            
                            # Alternative format with individual components
                            param_sets.append({
                                'address': parsed['address1'],
                                'locality': city,
                                'postalcode': postal_code
                            })
            
            # Also try the full address as a single string
            param_sets.append({'address': canonical_address})
            
            headers = {
                'apikey': self.attom_api_key,
                'accept': 'application/json'
            }
            
            url = 'https://api.gateway.attomdata.com/propertyapi/v1.0.0/property/basicprofile'
            
            # Try each parameter set until we get results
            for i, params in enumerate(param_sets):
                logger.info(f"ATTOM API attempt {i+1} for '{canonical_address}': {params}")
                
                async with self.session.get(url, params=params, headers=headers) as response:
                    response_text = await response.text()
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            
                            # Handle different possible response structures
                            properties = data.get('property', [])
                            if not properties and 'Response' in data:
                                # Some ATTOM endpoints wrap data in Response object
                                properties = data.get('Response', {}).get('property', [])
                            
                            if properties and len(properties) > 0:
                                property_data = properties[0]
                                # Try different possible field names for ATTOM ID
                                attom_id = (property_data.get('attomid') or 
                                          property_data.get('attomId') or
                                          property_data.get('identifier', {}).get('attomId'))
                                
                                if attom_id:
                                    logger.info(f"Found property data for ATTOM ID {attom_id} for '{canonical_address}' using params: {params}")
                                    return property_data
                            else:
                                logger.debug(f"ATTOM API attempt {i+1} returned empty results for '{canonical_address}': {data}")
                        except:
                            logger.warning(f"Failed to parse JSON response: {response_text[:200]}")
                    
                    elif response.status == 429:
                        logger.warning(f"Rate limited on ATTOM ID lookup for '{canonical_address}'")
                        raise aiohttp.ClientError("Rate limited")
                    
                    elif response.status == 401:
                        logger.error(f"ATTOM API authentication failed - check your API key")
                        return None
                    
                    else:
                        logger.debug(f"ATTOM API attempt {i+1} failed: HTTP {response.status}, Response: {response_text[:200]}")
                
                # Small delay between attempts to avoid rate limiting
                await asyncio.sleep(0.1)
            
            logger.warning(f"All ATTOM API attempts failed for '{canonical_address}'")
            return None
                
        except Exception as e:
            logger.error(f"ATTOM property lookup error for '{canonical_address}': {str(e)}")
            return None
    
    def extract_equity_data_from_property(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract equity data from property response data"""
        result = {
            'est_balance': None,
            'available_equity': None,
            'ltv': None,
            'loans_count': 0
        }
        
        try:
            assessment = property_data.get('assessment', {})
            
            # Get market value for calculations
            market_value = None
            if 'market' in assessment and 'mktTtlValue' in assessment['market']:
                market_value = assessment['market']['mktTtlValue']
            elif 'assessed' in assessment and 'assdTtlValue' in assessment['assessed']:
                market_value = assessment['assessed']['assdTtlValue']
            
            # Get mortgage information
            mortgage_data = assessment.get('mortgage', {})
            total_loan_balance = 0
            loans_count = 0
            
            # Check first mortgage
            first_mortgage = mortgage_data.get('FirstConcurrent', {})
            if 'amount' in first_mortgage and first_mortgage['amount'] > 0:
                total_loan_balance += first_mortgage['amount']
                loans_count += 1
                result['est_balance'] = first_mortgage['amount']  # Primary loan balance
            
            # Check second mortgage
            second_mortgage = mortgage_data.get('SecondConcurrent', {})
            if 'amount' in second_mortgage and second_mortgage['amount'] > 0:
                total_loan_balance += second_mortgage['amount']
                loans_count += 1
            
            result['loans_count'] = loans_count
            
            # Calculate equity and LTV if we have both values
            if market_value and total_loan_balance:
                available_equity = market_value - total_loan_balance
                result['available_equity'] = available_equity
                
                # Calculate LTV as percentage
                ltv = (total_loan_balance / market_value) * 100
                result['ltv'] = round(ltv, 2)
                
                logger.info(f"Calculated equity: Market Value ${market_value:,.0f}, Total Loans ${total_loan_balance:,.0f}, Equity ${available_equity:,.0f}, LTV {ltv:.1f}%")
            else:
                logger.debug(f"Insufficient data for equity calculation: Market Value = {market_value}, Loan Balance = {total_loan_balance}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting equity data from property: {str(e)}")
            return result
    
    async def enrich_address(self, raw_address: str, calc_date: str = None) -> Dict[str, Any]:
        """Complete enrichment pipeline for a single address"""
        result = {
            'raw_address': raw_address,
            'canonical_address': '',
            'attomid': None,
            'est_balance': None,
            'available_equity': None,
            'ltv': None,
            'loans_count': 0,
            'processed_at': datetime.now().isoformat()
        }
        
        try:
            # Step 1: USPS validation
            raw_address, canonical_address = await self.validate_address_google(raw_address)
            result['canonical_address'] = canonical_address
            
            # Step 2: Get ATTOM property data (includes ID and equity info)
            property_data = await self.get_attom_property_data(canonical_address)
            
            if property_data:
                # Extract ATTOM ID
                attom_id = (property_data.get('attomid') or 
                          property_data.get('attomId') or
                          property_data.get('identifier', {}).get('attomId'))
                result['attomid'] = attom_id
                
                # Extract equity data from property response
                equity_data = self.extract_equity_data_from_property(property_data)
                result.update(equity_data)
            else:
                logger.warning(f"No ATTOM property data found for '{canonical_address}'")
            
            logger.info(f"Successfully enriched '{raw_address}'")
            return result
            
        except Exception as e:
            logger.error(f"Enrichment failed for '{raw_address}': {str(e)}")
            return result
    
    async def enrich_addresses_batch(self, addresses: List[str], calc_date: str = None, max_concurrent: int = 10) -> List[Dict[str, Any]]:
        """Enrich multiple addresses with concurrency control"""
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enrich_with_semaphore(address: str) -> Dict[str, Any]:
            async with semaphore:
                return await self.enrich_address(address, calc_date)
        
        logger.info(f"Starting batch enrichment of {len(addresses)} addresses with max concurrency {max_concurrent}")
        
        tasks = [enrich_with_semaphore(addr) for addr in addresses]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        enriched_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception for address {i}: {str(result)}")
                # Create a fallback result
                enriched_results.append({
                    'raw_address': addresses[i],
                    'canonical_address': addresses[i],
                    'attomid': None,
                    'est_balance': None,
                    'available_equity': None,
                    'ltv': None,
                    'loans_count': 0,
                    'processed_at': datetime.now().isoformat()
                })
            else:
                enriched_results.append(result)
        
        logger.info(f"Completed batch enrichment. {len(enriched_results)} results generated.")
        return enriched_results

    async def process_addresses_from_csv(self, input_file: str, calc_date: str = None) -> List[Dict[str, Any]]:
        """Load addresses from CSV and process them through the enrichment pipeline"""
        addresses = load_addresses_from_csv(input_file)
        if not addresses:
            logger.warning("No addresses found in CSV file")
            return []
        
        return await self.enrich_addresses_batch(addresses, calc_date=calc_date)

def save_to_csv(results: List[Dict[str, Any]], output_file: str = 'output.csv'):
    """Save enriched results to CSV file"""
    if not results:
        logger.warning("No results to save to CSV")
        return
    
    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False)
    logger.info(f"Saved {len(results)} enriched records to {output_file}")

async def save_to_postgres(results: List[Dict[str, Any]], pg_dsn: str):
    """Save enriched results to Postgres with upsert"""
    if not results:
        logger.warning("No results to save to Postgres")
        return
    
    # Filter results that have ATTOM IDs
    postgres_results = [r for r in results if r.get('attomid')]
    
    if not postgres_results:
        logger.warning("No results with ATTOM IDs to save to Postgres")
        return
    
    try:
        conn = await asyncpg.connect(pg_dsn)
        
        # Create table if not exists
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS loan_snapshot (
                attomid          BIGINT PRIMARY KEY,
                est_balance      NUMERIC,
                available_equity NUMERIC,
                ltv              NUMERIC,
                pulled_at        TIMESTAMPTZ DEFAULT now()
            )
        ''')
        
        # Prepare upsert statement
        upsert_query = '''
            INSERT INTO loan_snapshot (attomid, est_balance, available_equity, ltv, pulled_at)
            VALUES ($1, $2, $3, $4, now())
            ON CONFLICT (attomid) DO UPDATE SET
                est_balance = EXCLUDED.est_balance,
                available_equity = EXCLUDED.available_equity,
                ltv = EXCLUDED.ltv,
                pulled_at = now()
        '''
        
        # Execute upserts
        for result in postgres_results:
            await conn.execute(
                upsert_query,
                int(result['attomid']),
                Decimal(str(result['est_balance'])) if result['est_balance'] is not None else None,
                Decimal(str(result['available_equity'])) if result['available_equity'] is not None else None,
                Decimal(str(result['ltv'])) if result['ltv'] is not None else None
            )
        
        await conn.close()
        logger.info(f"Successfully upserted {len(postgres_results)} records to Postgres")
        
    except Exception as e:
        logger.error(f"Postgres save error: {str(e)}")
        raise

def load_addresses_from_csv(input_file: str) -> List[str]:
    """Load addresses from input CSV file"""
    addresses = []
    
    try:
        with open(input_file, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            # Look for address column (case insensitive)
            address_column = None
            for col in reader.fieldnames:
                if col.lower() in ['address', 'street_address', 'property_address', 'full_address']:
                    address_column = col
                    break
            
            if not address_column:
                raise ValueError("No address column found. Expected columns: 'address', 'street_address', 'property_address', or 'full_address'")
            
            for row in reader:
                address = row[address_column].strip()
                if address:
                    addresses.append(address)
        
        logger.info(f"Loaded {len(addresses)} addresses from {input_file}")
        return addresses
        
    except Exception as e:
        logger.error(f"Error loading addresses from {input_file}: {str(e)}")
        raise

async def main():
    parser = argparse.ArgumentParser(description='Enrich addresses with ATTOM property data')
    parser.add_argument('input_csv', help='Input CSV file with addresses')
    parser.add_argument('--pg-dsn', help='PostgreSQL connection string')
    parser.add_argument('--calc-date', help='Calculation date for equity data (YYYY-MM-DD)')
    parser.add_argument('--output', default='output.csv', help='Output CSV file (default: output.csv)')
    parser.add_argument('--max-concurrent', type=int, default=10, help='Max concurrent requests (default: 10)')
    parser.add_argument('--skip-csv', action='store_true', help='Skip saving to CSV file')
    
    args = parser.parse_args()
    
    # Check required environment variables
    google_api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    usps_user_id = os.getenv('USPS_USER_ID')  # Optional fallback
    attom_api_key = os.getenv('ATTOM_API_KEY')
    
    if not google_api_key and not usps_user_id:
        logger.error("Either GOOGLE_MAPS_API_KEY or USPS_USER_ID environment variable is required")
        sys.exit(1)
    
    if not attom_api_key:
        logger.error("ATTOM_API_KEY environment variable is required")
        sys.exit(1)
    
    # Validate calc_date if provided
    calc_date = args.calc_date
    if calc_date:
        try:
            datetime.strptime(calc_date, '%Y-%m-%d')
        except ValueError:
            logger.error("Invalid calc-date format. Use YYYY-MM-DD")
            sys.exit(1)
    
    try:
        # Load addresses
        addresses = load_addresses_from_csv(args.input_csv)
        
        if not addresses:
            logger.error("No addresses found in input file")
            sys.exit(1)
        
        # Run enrichment pipeline
        async with AddressEnrichmentPipeline(usps_user_id, attom_api_key) as pipeline:
            results = await pipeline.enrich_addresses_batch(
                addresses, 
                calc_date=calc_date,
                max_concurrent=args.max_concurrent
            )
        
        # Save results
        if not args.skip_csv:
            save_to_csv(results, args.output)
        
        if args.pg_dsn:
            await save_to_postgres(results, args.pg_dsn)
        
        # Print summary
        total_addresses = len(addresses)
        successful_validations = len([r for r in results if r['canonical_address'] != r['raw_address']])
        found_attom_ids = len([r for r in results if r['attomid']])
        found_equity_data = len([r for r in results if r['est_balance'] is not None])
        
        print(f"\n=== ENRICHMENT SUMMARY ===")
        print(f"Total addresses processed: {total_addresses}")
        print(f"Address validations successful: {successful_validations}")
        print(f"ATTOM IDs found: {found_attom_ids}")
        print(f"Equity data retrieved: {found_equity_data}")
        if not args.skip_csv:
            print(f"Results saved to: {args.output}")
        if args.pg_dsn:
            print(f"Results upserted to Postgres: {found_attom_ids} records")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main()) 