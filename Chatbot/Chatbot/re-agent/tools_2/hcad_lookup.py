"""
HCAD Property Lookup Tool

This tool looks up property addresses using HCAD (Harris County Appraisal District)
by searching with legal description components (subdivision, section, block, lot).
"""

import asyncio
import logging
import aiohttp
import re
from typing import Dict, Any, Optional, List
from urllib.parse import quote_plus
import json

logger = logging.getLogger(__name__)

# HCAD search URLs
HCAD_SEARCH_URL = "https://public.hcad.org/records/Real.asp"
HCAD_DETAIL_URL = "https://public.hcad.org/records/PropertyDetail.asp"

async def hcad_lookup(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Look up property address using HCAD system
    
    Args:
        legal_params: Dictionary containing:
            - subdivision: Subdivision name
            - section: Section number
            - block: Block number
            - lot: Lot number
            
    Returns:
        Dictionary containing:
            - address: Property address if found
            - parcel_id: Property account number
            - error: Error message if lookup failed
    """
    subdivision = legal_params.get('subdivision', '').strip()
    section = legal_params.get('section', '').strip() 
    block = legal_params.get('block', '').strip()
    lot = legal_params.get('lot', '').strip()
    
    logger.info(f"🏠 HCAD lookup: {subdivision} Sec:{section} Block:{block} Lot:{lot}")
    
    # Check cache first
    cache_key = f"hcad_{subdivision}_{section}_{block}_{lot}".replace(' ', '_').lower()
    
    try:
        from cache import get_cached, set_cached
        cached_result = await get_cached(cache_key)
        if cached_result:
            logger.info("⚡ HCAD cache hit")
            return cached_result
    except ImportError:
        logger.warning("Cache not available for HCAD lookup")
    
    result = {
        'address': None,
        'parcel_id': None,
        'error': None
    }
    
    # If we don't have enough info, return early
    if not any([subdivision, lot, block]):
        result['error'] = "Insufficient legal description data"
        return result
    
    try:
        # Try multiple search strategies
        strategies = [
            _search_by_subdivision_lot_block,
            _search_by_address_pattern,
            _search_by_owner_name
        ]
        
        for strategy in strategies:
            try:
                strategy_result = await strategy(legal_params)
                if strategy_result.get('address'):
                    result.update(strategy_result)
                    break
            except Exception as e:
                logger.warning(f"HCAD strategy failed: {e}")
                continue
        
        # Cache the result for 24 hours if successful, 1 hour if failed
        ttl = 24 * 60 * 60 if result.get('address') else 60 * 60
        try:
            await set_cached(cache_key, result, ttl)
        except:
            pass
        
        return result
        
    except Exception as e:
        logger.error(f"❌ HCAD lookup failed: {e}")
        result['error'] = str(e)
        return result

async def _search_by_subdivision_lot_block(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """Search HCAD by subdivision, lot, and block"""
    subdivision = legal_params.get('subdivision', '').strip()
    block = legal_params.get('block', '').strip()
    lot = legal_params.get('lot', '').strip()
    
    if not subdivision:
        raise ValueError("No subdivision provided")
    
    logger.info(f"🔍 HCAD Strategy 1: Searching by subdivision/lot/block")
    
    async with aiohttp.ClientSession() as session:
        # Try searching by owner name pattern that includes subdivision
        search_params = {
            'search': 'addr',
            'streetname': subdivision,
            'stnum': '',
            'exactaddr': 'N'
        }
        
        async with session.get(HCAD_SEARCH_URL, params=search_params) as response:
            if response.status == 200:
                html = await response.text()
                return _parse_hcad_results(html, lot, block)
    
    return {'address': None, 'parcel_id': None}

async def _search_by_address_pattern(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """Search HCAD using address-like patterns"""
    subdivision = legal_params.get('subdivision', '').strip()
    
    if not subdivision:
        raise ValueError("No subdivision for address search")
    
    logger.info(f"🔍 HCAD Strategy 2: Address pattern search")
    
    # Create search patterns based on subdivision name
    search_terms = [
        subdivision,
        subdivision.replace(' ', ''),
        f"{subdivision} SUBDIVISION",
        f"{subdivision} ESTATES",
        f"{subdivision} ADDITION"
    ]
    
    async with aiohttp.ClientSession() as session:
        for search_term in search_terms:
            try:
                search_params = {
                    'search': 'addr', 
                    'streetname': search_term[:20],  # Limit length
                    'stnum': '',
                    'exactaddr': 'N'
                }
                
                async with session.get(HCAD_SEARCH_URL, params=search_params) as response:
                    if response.status == 200:
                        html = await response.text()
                        result = _parse_hcad_results(html, 
                                                   legal_params.get('lot', ''),
                                                   legal_params.get('block', ''))
                        if result.get('address'):
                            return result
                        
                # Small delay between requests
                await asyncio.sleep(0.2)
                
            except Exception as e:
                logger.warning(f"Address search failed for '{search_term}': {e}")
                continue
    
    return {'address': None, 'parcel_id': None}

async def _search_by_owner_name(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """Search HCAD by owner name if available"""
    # This would be used if we had owner information from the lis pendens
    # For now, return empty result
    logger.info(f"🔍 HCAD Strategy 3: Owner name search (not implemented)")
    return {'address': None, 'parcel_id': None}

def _parse_hcad_results(html: str, target_lot: str = "", target_block: str = "") -> Dict[str, Any]:
    """
    Parse HCAD search results HTML to extract property information
    
    Args:
        html: HTML response from HCAD search
        target_lot: Lot number to match
        target_block: Block number to match
        
    Returns:
        Dictionary with address and parcel_id if found
    """
    result = {'address': None, 'parcel_id': None}
    
    try:
        # Look for property records in the HTML
        # HCAD typically returns results in a table format
        
        # Pattern for account numbers (typically 13 digits)
        account_pattern = r'(\d{13})'
        
        # Pattern for addresses
        address_pattern = r'(\d+\s+[A-Z0-9\s]+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|CT|COURT|PL|PLACE|WAY|BLVD|BOULEVARD))'
        
        # Find all account numbers
        accounts = re.findall(account_pattern, html)
        
        # Find all addresses  
        addresses = re.findall(address_pattern, html, re.IGNORECASE)
        
        if accounts and addresses:
            # Take the first match for now
            # In a real implementation, we'd want to match lot/block numbers
            result['parcel_id'] = accounts[0]
            result['address'] = addresses[0].strip()
            
            # If we have lot/block info, try to find a better match
            if target_lot or target_block:
                better_match = _find_best_lot_block_match(html, target_lot, target_block)
                if better_match:
                    result.update(better_match)
        
        logger.info(f"📋 HCAD parsed: {result}")
        
    except Exception as e:
        logger.warning(f"HCAD HTML parsing failed: {e}")
    
    return result

def _find_best_lot_block_match(html: str, target_lot: str, target_block: str) -> Optional[Dict[str, str]]:
    """
    Try to find the best match based on lot and block numbers in the HTML
    
    Args:
        html: HTML content to search
        target_lot: Target lot number
        target_block: Target block number
        
    Returns:
        Dictionary with matched address/parcel_id or None
    """
    try:
        # Look for lot/block patterns in the HTML
        lot_block_patterns = [
            rf'LOT\s+{re.escape(target_lot)}\s+BLOCK\s+{re.escape(target_block)}',
            rf'L\s*{re.escape(target_lot)}\s+B\s*{re.escape(target_block)}',
            rf'{re.escape(target_lot)}-{re.escape(target_block)}'
        ]
        
        for pattern in lot_block_patterns:
            matches = re.finditer(pattern, html, re.IGNORECASE)
            for match in matches:
                # Found a match, try to extract nearby address/account
                start = max(0, match.start() - 200)
                end = min(len(html), match.end() + 200)
                context = html[start:end]
                
                # Look for account number in context
                account_match = re.search(r'(\d{13})', context)
                address_match = re.search(r'(\d+\s+[A-Z0-9\s]+(?:ST|STREET|AVE|AVENUE|RD|ROAD|DR|DRIVE|LN|LANE|CT|COURT|PL|PLACE|WAY|BLVD|BOULEVARD))', context, re.IGNORECASE)
                
                if account_match and address_match:
                    return {
                        'parcel_id': account_match.group(1),
                        'address': address_match.group(1).strip()
                    }
                    
    except Exception as e:
        logger.warning(f"Lot/block matching failed: {e}")
    
    return None

# Mock implementation for testing
async def _mock_hcad_lookup(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """
    Mock HCAD lookup for testing purposes
    
    Returns mock data based on input parameters
    """
    subdivision = legal_params.get('subdivision', '')
    lot = legal_params.get('lot', '')
    block = legal_params.get('block', '')
    
    if subdivision and lot:
        # Generate mock address
        street_number = int(lot) * 100 if lot.isdigit() else 1000
        mock_address = f"{street_number} {subdivision} Drive, Houston, TX 77001"
        mock_parcel = f"001-{block or '1'}-{lot or '1'}-0001"
        
        logger.info(f"🧪 Mock HCAD result: {mock_address}")
        
        return {
            'address': mock_address,
            'parcel_id': mock_parcel,
            'error': None
        }
    
    return {
        'address': None,
        'parcel_id': None,
        'error': "Insufficient data for mock lookup"
    }

# Test function
async def test_hcad_lookup():
    """Test function for HCAD lookup"""
    logger.info("🧪 Testing HCAD lookup")
    
    test_cases = [
        {
            'subdivision': 'MOCK SUBDIVISION',
            'section': '1',
            'block': '2',
            'lot': '5'
        },
        {
            'subdivision': 'VENTANA LAKES',
            'section': '5',
            'block': '3', 
            'lot': '34'
        }
    ]
    
    for test_case in test_cases:
        try:
            logger.info(f"Testing: {test_case}")
            
            # Use mock for testing
            result = await _mock_hcad_lookup(test_case)
            
            logger.info(f"Result: {result}")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_hcad_lookup()) 