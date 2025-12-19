# Filter Configuration System
# This file stores named filter configurations for Harris County address filtering

# Filter 1: Cypress, Humble, Katy, and specific Houston areas
FILTER_1_CONFIG = {
    "name": "Cypress_Humble_Katy_Houston_Filter",
    "description": "Filter for Cypress, Humble, Katy areas and specific Houston zip codes with proximity matching",
    "allowed_cities": ['CYPRESS', 'HUMBLE', 'KATY', 'HOUSTON'],
    "allowed_zip_codes": {
        # Cypress, TX
        '77429', '77433',
        # Katy, TX  
        '77449', '77450', '77493', '77494',
        # Humble, TX
        '77338', '77339', '77345', '77346', '77396',
        # Other Misc Houston areas
        '77033', '77047', '77088',
        # Special case: 77021 only for Harris for the one record type they can pull
        '77021'
    },
    "proximity_range": 5,  # Allow zip codes within 5 of any allowed zip
    "enable_progressive_pulling": True,  # Pull more batches if no records pass filter
    "created_date": "2025-01-18",
    "notes": "Primary filter for restricted users focusing on specific suburban areas with proximity matching"
}

# User ID to Filter Configuration Mapping
USER_FILTER_ASSIGNMENTS = {
    '6b3d5d75-f440-46d3-b0a6-8c6e49b211a5': 'FILTER_1',
    '08c8ffaa-0bfb-4db3-abbb-ebe1eef036aa': 'FILTER_1', 
    '867ebb10-afd9-4892-b781-208ba8098306': 'FILTER_1'
}

# All available filter configurations
AVAILABLE_FILTERS = {
    'FILTER_1': FILTER_1_CONFIG
}

def get_filter_config(filter_name: str) -> dict:
    """Get filter configuration by name"""
    return AVAILABLE_FILTERS.get(filter_name, {})

def get_user_filter_config(user_id: str) -> dict:
    """Get filter configuration for a specific user"""
    filter_name = USER_FILTER_ASSIGNMENTS.get(user_id)
    if filter_name:
        return get_filter_config(filter_name)
    return {}

def list_available_filters() -> dict:
    """List all available filter configurations"""
    return {name: config['description'] for name, config in AVAILABLE_FILTERS.items()}

def is_zip_within_proximity(target_zip: str, allowed_zips: set, proximity_range: int) -> bool:
    """Check if a zip code is within proximity range of any allowed zip code"""
    if not target_zip or not target_zip.isdigit() or len(target_zip) != 5:
        return False
    
    target_num = int(target_zip)
    
    for allowed_zip in allowed_zips:
        if allowed_zip.isdigit() and len(allowed_zip) == 5:
            allowed_num = int(allowed_zip)
            if abs(target_num - allowed_num) <= proximity_range:
                return True
    
    return False

def check_zip_against_filter(zip_code: str, filter_config: dict) -> bool:
    """Check if a zip code passes the filter (exact match or proximity)"""
    if not filter_config:
        return True
    
    allowed_zips = filter_config.get('allowed_zip_codes', set())
    
    # Check exact match first
    if zip_code in allowed_zips:
        return True
    
    # Check proximity if enabled
    proximity_range = filter_config.get('proximity_range', 0)
    if proximity_range > 0:
        return is_zip_within_proximity(zip_code, allowed_zips, proximity_range)
    
    return False 