# Harris County Filter Configuration System

## Overview

The Harris County address filtering system has been reorganized into a named filter configuration system for better organization and maintainability.

## Current Filter Configurations

### Filter 1: Cypress_Humble_Katy_Houston_Filter
- **Status**: ✅ Active
- **Created**: 2025-01-18
- **Description**: Filter for Cypress, Humble, Katy areas and specific Houston zip codes

#### Allowed Cities:
- CYPRESS
- HUMBLE  
- KATY
- HOUSTON (specific zip codes only)

#### Allowed Zip Codes:
- **Cypress**: 77429, 77433
- **Katy**: 77449, 77450, 77493, 77494
- **Humble**: 77338, 77339, 77345, 77346, 77396
- **Houston (specific areas)**: 77033, 77047, 77088, 77021

## User Assignments

The following users are currently assigned to **Filter 1**:
- `6b3d5d75-f440-46d3-b0a6-8c6e49b211a5`
- `08c8ffaa-0bfb-4db3-abbb-ebe1eef036aa` 
- `867ebb10-afd9-4892-b781-208ba8098306`

## How It Works

1. **Configuration**: Filter settings are defined in `filter_configs.py`
2. **Assignment**: Users are mapped to specific filter configurations
3. **Filtering**: The `harris_db_saver.py` uses these configurations to filter records
4. **Flexibility**: New filters can be added without changing the main filtering logic

## Adding New Filters

To add a new filter configuration:

1. Define the filter in `filter_configs.py`:
```python
FILTER_2_CONFIG = {
    "name": "Your_Filter_Name",
    "description": "Description of what this filter does",
    "allowed_cities": ['CITY1', 'CITY2'],
    "allowed_zip_codes": {'12345', '67890'},
    "created_date": "YYYY-MM-DD",
    "notes": "Additional notes"
}
```

2. Add it to `AVAILABLE_FILTERS`:
```python
AVAILABLE_FILTERS = {
    'FILTER_1': FILTER_1_CONFIG,
    'FILTER_2': FILTER_2_CONFIG  # Add your new filter
}
```

3. Assign users to the new filter:
```python
USER_FILTER_ASSIGNMENTS = {
    'user-id-here': 'FILTER_2'
}
```

## Benefits

- ✅ **Organized**: Named configurations instead of hardcoded values
- ✅ **Flexible**: Easy to add new filter types
- ✅ **Maintainable**: All filter logic in one place
- ✅ **Documented**: Clear description of what each filter does
- ✅ **Versioned**: Can track when filters were created/modified 