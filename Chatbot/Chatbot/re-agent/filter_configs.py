# Filter Configuration System
# This file stores named filter configurations for Harris County address filtering

# Filter 1: Cypress, Humble, Katy, and specific Houston areas
FILTER_1_CONFIG = {
    "name": "Cypress_Humble_Katy_Houston_Filter",
    "description": "Filter for Cypress, Humble, Katy areas and specific Houston zip codes",
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
    "created_date": "2025-01-18",
    "notes": "Primary filter for restricted users focusing on specific suburban areas"
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