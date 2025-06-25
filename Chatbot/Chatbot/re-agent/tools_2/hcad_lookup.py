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
HCAD_ADVANCED_URL = "https://public.hcad.org/records/Real/Advanced.asp"

# ---------------------------------------------------------------------------
# 🏗️  Utility: canonical legal-description builder
# ---------------------------------------------------------------------------

def build_hcad_legal(subdivision: str | None = None,
                     section: str | int | None = None,
                     block: str | int | None = None,
                     lot: str | int | None = None) -> str:
    """Return canonical HCAD legal-description string using available parts only.

    Parts order: LT <lot> BLK <block> <SUBDIVISION> SEC <section>
    Any element that is ``None``/empty is omitted.
    """
    parts: list[str] = []

    if lot not in (None, ""):
        parts.append(f"LT {int(lot)}")
    if block not in (None, ""):
        parts.append(f"BLK {int(block)}")

    if subdivision not in (None, ""):
        subdivision_clean = " ".join(str(subdivision).upper().split())
        parts.append(subdivision_clean)

    if section not in (None, ""):
        parts.append(f"SEC {int(section)}")

    return " ".join(parts)

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
    
    # Use explicit Optional[str] typing for result values to satisfy static type checkers
    result: Dict[str, Optional[str]] = {
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
        # Only two strategies: (1) canonical legal-description search, (2) full owner-name search
        strategies = [
            _search_by_legal_description,
            _search_by_owner_name
        ]
        
        for strategy in strategies:
            try:
                strategy_result = await strategy(legal_params)
                if strategy_result.get('address'):
                    from typing import cast
                    result.update(cast(Dict[str, Optional[str]], strategy_result))
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

async def _search_by_legal_description(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """Search HCAD using the full legal-description string (LT/BLK/SEC)."""
    subdivision = legal_params.get('subdivision', '').strip()
    section = legal_params.get('section', '').strip()
    block = legal_params.get('block', '').strip()
    lot = legal_params.get('lot', '').strip()

    if not any([subdivision, section, block, lot]):
        raise ValueError("No usable legal description components provided")

    legal_string = build_hcad_legal(subdivision, section, block, lot)
    logger.info(f"🔍 HCAD Strategy 0: Legal description search – '{legal_string}'")

    async with aiohttp.ClientSession() as session:
        try:
            # STEP 1: Load Advanced search page to establish session cookies
            async with session.get(HCAD_ADVANCED_URL) as resp_init:
                if resp_init.status != 200:
                    logger.warning("Advanced page request failed – falling back")
            # STEP 2: Submit the form with the legal description.
            # The Advanced form uses HTTP GET; field id & name are `LegalDscr`.
            search_params = {
                'search': 'legal',      # tells backend we are searching legal description
                'LegalDscr': legal_string,
                'exact': 'Y'            # request exact match where available
            }
            async with session.get(HCAD_SEARCH_URL, params=search_params) as response:
                if response.status == 200:
                    html = await response.text()
                    return _parse_hcad_results(html, lot, block)
        except Exception as e:
            logger.warning(f"Legal description search failed: {e}")

    return {
        'address': None,
        'parcel_id': None,
        'error': None
    }

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
    
    return {
        'address': None,
        'parcel_id': None,
        'error': None
    }

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
    
    return {
        'address': None,
        'parcel_id': None,
        'error': None
    }

async def _search_by_owner_name(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """Search HCAD by owner / grantee name as fallback.

    The heuristic is: take the first two words of the name and append the
    initial of the *last* word (e.g. "GRAY JAMES H" → "GRAY JAMES H").
    """
    full_name = legal_params.get('owner_name', '').strip().upper()

    if not full_name:
        raise ValueError("No owner name provided for owner-name search")

    search_name = full_name  # Use full name exactly as provided
    logger.info(f"🔍 HCAD Strategy 2: Owner name search – '{search_name}'")

    async with aiohttp.ClientSession() as session:
        search_params = {
            'search': 'name',  # owner name search option
            'ownername': search_name,
            'exact': 'N'
        }
        try:
            async with session.get(HCAD_SEARCH_URL, params=search_params) as response:
                if response.status == 200:
                    html = await response.text()
                    return _parse_hcad_results(html)
        except Exception as e:
            logger.warning(f"Owner name search failed: {e}")

    return {
        'address': None,
        'parcel_id': None,
        'error': None
    }

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
    # Use explicit Optional[str] typing for result values to satisfy static type checkers
    result: Dict[str, Optional[str]] = {
        'address': None,
        'parcel_id': None,
        'error': None
    }
    
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
                    # Cast to satisfy type checkers that better_match is not None
                    from typing import cast
                    result.update(cast(Dict[str, Optional[str]], better_match))
        
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
            
            result = await hcad_lookup(test_case)
            
            logger.info(f"Result: {result}")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_hcad_lookup()) 