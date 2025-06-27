"""
HCAD Property Lookup Tool

This tool looks up property addresses using HCAD's ArcGIS REST API
by querying the undocumented FeatureServer directly.
"""

import asyncio
import logging
import requests
import urllib.parse as ul
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# HCAD ArcGIS REST API endpoints
HCAD_BASE_URL = "https://www.gis.hctx.net/arcgis/rest/services/HCAD/Parcels/MapServer"
HCAD_QUERY_URL = f"{HCAD_BASE_URL}/0/query"

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
    Look up property address using HCAD's ArcGIS REST API
    
    Args:
        legal_params: Dictionary containing:
            - subdivision: Subdivision name
            - section: Section number
            - block: Block number
            - lot: Lot number
            - owner_name: Owner name
            
    Returns:
        Dictionary containing:
            - address: Property address if found
            - owner_name: Owner name if found
            - parcel_id: Property account number
            - impr_sqft: Improvement square footage (if available)
            - market_value: Market value (if available)
            - appraised_value: Appraised value (if available)
            - error: Error message if lookup failed
    """
    # Handle both string and list values
    def safe_extract(value):
        if isinstance(value, list):
            return value[0] if value else ''
        return str(value) if value else ''
    
    subdivision = safe_extract(legal_params.get('subdivision', '')).strip()
    section = safe_extract(legal_params.get('section', '')).strip() 
    block = safe_extract(legal_params.get('block', '')).strip()
    lot = safe_extract(legal_params.get('lot', '')).strip()
    owner_name = (safe_extract(legal_params.get('owner_name', '')) or 
                  safe_extract(legal_params.get('grantee', ''))).strip()
    
    logger.info(f"🏠 HCAD ArcGIS lookup: {subdivision} Sec:{section} Block:{block} Lot:{lot} Owner:{owner_name}")
    
    # Check cache first
    cache_key = f"hcad_{subdivision}_{section}_{block}_{lot}_{owner_name}".replace(' ', '_').lower()
    
    try:
        from cache import get_cached, set_cached
        cached_result = await get_cached(cache_key)
        if cached_result:
            logger.info(f"⚡ HCAD cache hit – returning {cached_result}")
            return cached_result
    except ImportError:
        logger.warning("Cache not available for HCAD lookup")
    
    # Use explicit Optional[str] typing for result values
    result: Dict[str, Optional[str]] = {
        'address': None,
        'parcel_id': None,
        'error': None,
        'owner_name': owner_name,
        'impr_sqft': None,
        'market_value': None,
        'appraised_value': None
    }
    
    # If we don't have an owner name, return early
    if not owner_name:
        result['error'] = "No owner name provided for HCAD lookup"
        return result
    
    try:
        # Use ArcGIS REST API search with timeout
        strategy_result = await asyncio.wait_for(
            _search_arcgis_api(legal_params),
            timeout=60.0  # 60 second timeout
        )
        if strategy_result.get('address'):
            from typing import cast
            result.update(cast(Dict[str, Optional[str]], strategy_result))
        
        # Cache the result for 24 hours if successful, 1 hour if failed
        ttl = 24 * 60 * 60 if result.get('address') else 60 * 60
        try:
            await set_cached(cache_key, result, ttl)
        except:
            pass
        
        return result
        
    except asyncio.TimeoutError:
        logger.warning(f"⚠️ HCAD ArcGIS lookup timed out for {owner_name}")
        result['error'] = "HCAD lookup timed out"
        return result
    except Exception as e:
        logger.error(f"❌ HCAD ArcGIS lookup failed: {e}")
        result['error'] = str(e)
        return result

def _extract_section_from_description(description: str) -> str:
    """Extract section number from Harris County description field"""
    import re
    if not description:
        return ""
    
    # Look for patterns like "Sec: 22" or "Section: 22"
    section_match = re.search(r'Sec(?:tion)?:\s*(\d+)', description, re.IGNORECASE)
    if section_match:
        return section_match.group(1)
    return ""

def _generate_name_variations(full_name: str) -> List[str]:
    """Generate name variations for better matching"""
    if not full_name:
        return []
    
    parts = full_name.strip().upper().split()
    if not parts:
        return []
    
    variations = [full_name.upper()]  # Original full name
    
    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        
        # Common variations
        variations.extend([
            f"{first} {last}",  # First + Last only
            f"{last} {first}",  # Last + First
            f"{last}, {first}",  # Last, First (formal format)
            last,  # Last name only
            first,  # First name only
        ])
        
        # Middle initial handling
        if len(parts) >= 3:
            middle = parts[1]
            variations.extend([
                f"{first} {middle[0]} {last}",  # First MI Last
                f"{last}, {first} {middle[0]}",  # Last, First MI
                f"{first} {middle} {last}",  # First Middle Last
            ])
    
    # Remove duplicates while preserving order
    seen = set()
    unique_variations = []
    for variation in variations:
        if variation not in seen:
            seen.add(variation)
            unique_variations.append(variation)
    
    return unique_variations

def _clean_subdivision_for_search(subdivision: str) -> List[str]:
    """Clean and generate subdivision variations for better matching"""
    if not subdivision:
        return []
    
    variations = [subdivision.upper()]
    
    # Handle condo units - remove "UNIT:" prefix
    if "UNIT:" in subdivision:
        base_subdivision = subdivision.split("UNIT:")[0].strip()
        variations.extend([
            base_subdivision,
            f"{base_subdivision} CONDO",
            f"{base_subdivision} CONDOMINIUM",
        ])
    
    # Handle common subdivision suffixes
    base = subdivision.upper()
    for suffix in [" SEC", " SECTION", " SUB", " SUBDIVISION"]:
        if base.endswith(suffix):
            base_without_suffix = base[:-len(suffix)].strip()
            variations.append(base_without_suffix)
    
    # Remove duplicates
    return list(set(variations))

async def _search_arcgis_api(legal_params: Dict[str, str]) -> Dict[str, Any]:
    """Search HCAD using ArcGIS REST API with multi-strategy approach.
    
    This uses the undocumented ArcGIS FeatureServer which is much more reliable
    than browser automation and doesn't require dealing with captchas.
    """
    # Handle both string and list values for owner_name
    owner_name_raw = legal_params.get('owner_name', '')
    if isinstance(owner_name_raw, list):
        full_name = owner_name_raw[0] if owner_name_raw else ''
    else:
        full_name = str(owner_name_raw) if owner_name_raw else ''
    
    full_name = full_name.strip().upper()

    if not full_name:
        raise ValueError("No owner name provided for ArcGIS search")

    logger.info(f"🔍 HCAD ArcGIS API search for owner: '{full_name}'")
    
    # Try multiple search strategies
    strategies = [
        "exact_match",      # Strategy 1: Exact owner + subdivision + lot/block
        "subdivision_only", # Strategy 2: Subdivision + lot/block (ignore owner mismatch)
        "owner_area",       # Strategy 3: Owner name variations in subdivision area
        "fuzzy_subdivision" # Strategy 4: Fuzzy subdivision matching
    ]
    
    for strategy in strategies:
        try:
            result = await _try_search_strategy(legal_params, full_name, strategy)
            if result and result.get('address'):
                logger.info(f"✅ ArcGIS search successful with strategy: {strategy}")
                return result
        except Exception as e:
            logger.warning(f"⚠️ Strategy {strategy} failed: {e}")
            continue
    
    # If all strategies fail, return empty result
    logger.info("🔍 No records found in ArcGIS with any strategy")
    return _build_empty_hcad_result(legal_params, "No records found with any search strategy")

async def _try_search_strategy(legal_params: Dict[str, str], full_name: str, strategy: str) -> Dict[str, Any]:
    """Try a specific search strategy"""
    logger.info(f"🎯 Trying strategy: {strategy}")
    
    try:
        # Extract legal description components
        def safe_extract(value):
            if isinstance(value, list):
                return value[0] if value else ''
            return str(value) if value else ''
        
        subdivision = safe_extract(legal_params.get('subdivision', '')).strip()
        section = safe_extract(legal_params.get('section', '')).strip() 
        block = safe_extract(legal_params.get('block', '')).strip()
        lot = safe_extract(legal_params.get('lot', '')).strip()
        
        # Enhanced section extraction from description if not provided
        if not section:
            description = safe_extract(legal_params.get('description', ''))
            section = _extract_section_from_description(description)
            if section:
                logger.info(f"📋 Extracted section {section} from description")
        
        # Build WHERE clause based on strategy
        where_conditions = []
        
        if strategy == "exact_match":
            # Strategy 1: Exact owner + subdivision + lot/block
            name_variations = _generate_name_variations(full_name)
            owner_conditions = []
            for name_var in name_variations[:5]:  # Limit to top 5 variations
                owner_conditions.append(f"owner_name_1 LIKE '%{name_var}%'")
            
            if owner_conditions:
                where_conditions.append(f"({' OR '.join(owner_conditions)})")
                
        elif strategy == "subdivision_only":
            # Strategy 2: Subdivision + lot/block only (ignore owner for now)
            pass  # We'll add subdivision/lot/block conditions below
            
        elif strategy == "owner_area":
            # Strategy 3: Owner name variations in subdivision area
            name_variations = _generate_name_variations(full_name)
            owner_conditions = []
            for name_var in name_variations:
                owner_conditions.append(f"owner_name_1 LIKE '%{name_var}%'")
            
            if owner_conditions:
                where_conditions.append(f"({' OR '.join(owner_conditions)})")
                
        elif strategy == "fuzzy_subdivision":
            # Strategy 4: Fuzzy subdivision matching with owner
            name_variations = _generate_name_variations(full_name)
            owner_conditions = []
            for name_var in name_variations[:3]:  # Just top 3 for fuzzy
                owner_conditions.append(f"owner_name_1 LIKE '%{name_var}%'")
            
            if owner_conditions:
                where_conditions.append(f"({' OR '.join(owner_conditions)})")
        
        # Add legal description conditions based on strategy
        legal_conditions = []
        
        if subdivision:
            subdivision_variations = _clean_subdivision_for_search(subdivision)
            
            if strategy == "fuzzy_subdivision":
                # Strategy 4: Try partial matches and word combinations
                subdivision_conditions = []
                for sub_var in subdivision_variations:
                    # Split subdivision into words for partial matching
                    words = sub_var.split()
                    for word in words:
                        if len(word) > 3:  # Skip short words
                            subdivision_conditions.append(
                                f"(legal_dscr_1 LIKE '%{word}%' OR "
                                f"legal_dscr_2 LIKE '%{word}%' OR "
                                f"legal_dscr_3 LIKE '%{word}%' OR "
                                f"legal_dscr_4 LIKE '%{word}%')"
                            )
                
                if subdivision_conditions:
                    # For fuzzy matching, use OR between word conditions
                    legal_conditions.append(f"({' OR '.join(subdivision_conditions)})")
            else:
                # Standard subdivision matching for other strategies
                subdivision_conditions = []
                for sub_var in subdivision_variations:
                    subdivision_conditions.append(
                        f"(legal_dscr_1 LIKE '%{sub_var}%' OR "
                        f"legal_dscr_2 LIKE '%{sub_var}%' OR "
                        f"legal_dscr_3 LIKE '%{sub_var}%' OR "
                        f"legal_dscr_4 LIKE '%{sub_var}%')"
                    )
                
                if subdivision_conditions:
                    # Use OR between subdivision variations
                    legal_conditions.append(f"({' OR '.join(subdivision_conditions)})")
        
        if block:
            # Search block info primarily in legal_dscr_1, but also other fields
            block_condition = (
                f"(legal_dscr_1 LIKE '%BLK {block}%' OR "
                f"legal_dscr_1 LIKE '%BLOCK {block}%' OR "
                f"legal_dscr_2 LIKE '%BLK {block}%' OR "
                f"legal_dscr_2 LIKE '%BLOCK {block}%')"
            )
            legal_conditions.append(block_condition)
        
        if lot:
            # Search lot info primarily in legal_dscr_1, but also other fields
            lot_condition = (
                f"(legal_dscr_1 LIKE '%LOT {lot}%' OR "
                f"legal_dscr_1 LIKE '%LT {lot}%' OR "
                f"legal_dscr_2 LIKE '%LOT {lot}%' OR "
                f"legal_dscr_2 LIKE '%LT {lot}%')"
            )
            legal_conditions.append(lot_condition)
        
        if section:
            # Search section info across all fields
            section_condition = (
                f"(legal_dscr_1 LIKE '%SEC {section}%' OR "
                f"legal_dscr_2 LIKE '%SEC {section}%' OR "
                f"legal_dscr_3 LIKE '%SEC {section}%' OR "
                f"legal_dscr_4 LIKE '%SEC {section}%')"
            )
            legal_conditions.append(section_condition)
        
        # Combine all conditions based on strategy
        if legal_conditions:
            where_conditions.extend(legal_conditions)
        
        if not where_conditions:
            if strategy == "subdivision_only":
                raise ValueError("Subdivision_only strategy requires subdivision info")
            else:
                raise ValueError("No search criteria provided")
        
        # Build final WHERE clause based on strategy
        if strategy == "subdivision_only":
            # For subdivision_only, use OR logic to be more permissive
            where_clause = ' OR '.join(where_conditions) if len(where_conditions) > 1 else where_conditions[0]
        elif strategy == "fuzzy_subdivision":
            # For fuzzy, also use OR logic
            where_clause = ' OR '.join(where_conditions) if len(where_conditions) > 1 else where_conditions[0]
        else:
            # For exact and owner_area, use AND logic
            where_clause = ' AND '.join(where_conditions)
            
        logger.info(f"🔍 ArcGIS WHERE clause ({strategy}): {where_clause}")
        
        # URL encode the WHERE clause
        where_encoded = ul.quote(where_clause)
        
        # Build the query URL with comprehensive field list
        query_url = (
            f"{HCAD_QUERY_URL}"
            f"?where={where_encoded}"
            f"&outFields=acct_num,site_str_name,site_str_num,site_city,site_zip,owner_name_1,owner_name_2,legal_dscr_1,legal_dscr_2,legal_dscr_3,legal_dscr_4,total_appraised_val,total_market_val,land_sqft,bld_value,impr_value"
            f"&f=json&returnGeometry=false&orderByFields=acct_num"
            f"&resultRecordCount=50"  # Limit to 50 results
        )
        
        logger.debug(f"📡 ArcGIS Query URL: {query_url}")
        
        # Make the API request
        response = requests.get(query_url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'error' in data:
            raise Exception(f"ArcGIS API error: {data['error']}")
        
        features = data.get('features', [])
        logger.info(f"📊 ArcGIS returned {len(features)} features")
        
        if not features:
            logger.info(f"🔍 No records found in ArcGIS for strategy {strategy}")
            return _build_empty_hcad_result(legal_params, f"No records found with {strategy}")
        
        # Validate and rank results based on strategy
        best_feature = _select_best_result(features, legal_params, full_name, strategy)
        if not best_feature:
            logger.info(f"🔍 No valid results after filtering for strategy {strategy}")
            return _build_empty_hcad_result(legal_params, f"No valid results with {strategy}")
        
        # Process the best result
        attrs = best_feature.get('attributes', {})
        
        # Build result from ArcGIS data
        result = _build_empty_hcad_result(legal_params)
        
        # Extract address components
        street_num = attrs.get('site_str_num', '')
        street_name = attrs.get('site_str_name', '').strip()
        city = attrs.get('site_city', '').strip()
        zip_code = attrs.get('site_zip', '').strip()
        
        # Build full address
        address_parts = []
        if street_num and street_name:
            address_parts.append(f"{street_num} {street_name}")
        elif street_name:
            address_parts.append(street_name)
        
        if city:
            address_parts.append(city)
        if zip_code:
            address_parts.append(zip_code)
        
        if address_parts:
            result['address'] = ', '.join(address_parts)
            logger.info(f"📍 ArcGIS found address: {result['address']}")
        
        # Extract account number (parcel ID)
        if attrs.get('acct_num'):
            result['parcel_id'] = str(attrs['acct_num'])
            logger.info(f"🏷️ ArcGIS found account: {result['parcel_id']}")
        
        # Extract owner name (try owner_name_1 first, then owner_name_2)
        if attrs.get('owner_name_1'):
            result['owner_name'] = attrs['owner_name_1'].strip()
        elif attrs.get('owner_name_2'):
            result['owner_name'] = attrs['owner_name_2'].strip()
        
        # Extract property values and metrics
        if attrs.get('land_sqft'):
            result['impr_sqft'] = str(int(attrs['land_sqft']))
        
        if attrs.get('total_market_val'):
            result['market_value'] = f"${attrs['total_market_val']:,.0f}"
        
        if attrs.get('total_appraised_val'):
            result['appraised_value'] = f"${attrs['total_appraised_val']:,.0f}"
        
        # Mark as successful if we got an address or parcel ID
        if result['address'] or result['parcel_id']:
            result['error'] = None
            logger.info("✅ ArcGIS HCAD search successful")
            
            # Log additional results if multiple found
            if len(features) > 1:
                logger.info(f"📋 Found {len(features)} total results, using first match")
        else:
            result['error'] = "No property data found in ArcGIS results"
            logger.info("🔍 ArcGIS search completed but no usable data found")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ HCAD ArcGIS search failed for strategy {strategy}: {e}")
        return _build_empty_hcad_result(legal_params, f"{strategy} failed: {str(e)}")

def _select_best_result(features: List[Dict], legal_params: Dict[str, str], full_name: str, strategy: str) -> Optional[Dict]:
    """Select the best result from multiple features based on strategy and validation"""
    
    def safe_extract(value):
        if isinstance(value, list):
            return value[0] if value else ''
        return str(value) if value else ''
    
    subdivision = safe_extract(legal_params.get('subdivision', '')).strip().upper()
    block = safe_extract(legal_params.get('block', '')).strip()
    lot = safe_extract(legal_params.get('lot', '')).strip()
    
    scored_features = []
    
    for feature in features:
        attrs = feature.get('attributes', {})
        score = 0
        
        # Score based on owner name match
        owner_name = attrs.get('owner_name_1', '').upper()
        if owner_name:
            name_variations = _generate_name_variations(full_name)
            for variation in name_variations:
                if variation.upper() in owner_name:
                    score += 10
                    break
            
            # Boost score for exact last name match
            if full_name.split()[-1] in owner_name:
                score += 5
        
        # Score based on legal description matches
        legal_fields = [
            str(attrs.get('legal_dscr_1', '') or ''),
            str(attrs.get('legal_dscr_2', '') or ''),
            str(attrs.get('legal_dscr_3', '') or ''),
            str(attrs.get('legal_dscr_4', '') or '')
        ]
        legal_text = ' '.join(legal_fields).upper()
        
        # Subdivision match
        if subdivision:
            subdivision_variations = _clean_subdivision_for_search(subdivision)
            for sub_var in subdivision_variations:
                if sub_var.upper() in legal_text:
                    score += 20
                    break
        
        # Block match
        if block:
            if f"BLK {block}" in legal_text or f"BLOCK {block}" in legal_text:
                score += 15
        
        # Lot match  
        if lot:
            if f"LOT {lot}" in legal_text or f"LT {lot}" in legal_text:
                score += 15
        
        # Address validation - boost score if we have a real address
        address_score = 0
        if attrs.get('site_str_name') and attrs.get('site_city'):
            address_score += 10
        if attrs.get('site_str_num'):
            address_score += 5
        
        score += address_score
        
        # Strategy-specific scoring
        if strategy == "exact_match":
            # Require high confidence for exact match
            if score < 25:
                continue
        elif strategy == "subdivision_only":
            # More lenient, just need subdivision match
            if score < 15:
                continue
        elif strategy == "owner_area":
            # Need at least owner match
            if score < 10:
                continue
        # fuzzy_subdivision is most lenient
        
        scored_features.append((score, feature))
        logger.info(f"🏆 Feature scored {score}: {owner_name} - {legal_text[:100]}")
    
    if not scored_features:
        return None
    
    # Sort by score (highest first) and return best
    scored_features.sort(key=lambda x: x[0], reverse=True)
    best_score, best_feature = scored_features[0]
    
    logger.info(f"✅ Selected best result with score {best_score}")
    return best_feature

def _build_empty_hcad_result(legal_params: Dict[str, str], error: str = None) -> Dict[str, Any]:
    """Build empty result structure."""
    return {
        'address': None,
        'parcel_id': None,
        'error': error,
        'owner_name': legal_params.get('owner_name', ''),
        'impr_sqft': None,
        'market_value': None,
        'appraised_value': None
    }