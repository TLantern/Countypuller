# Georgia GSCCCA County Scrapers

## Overview

This document describes the county-specific scrapers created for the **Georgia Superior Court Clerks' Cooperative Authority (GSCCCA)** system at https://search.gsccca.org/Lien/namesearch.asp.

Since the GSCCCA system serves multiple Georgia counties through a single interface, we've created separate scrapers for each county to ensure proper data organization and filtering.

## Created Scrapers

### 1. **Fulton County GA** (`FultonGA.py`)
- **Configuration**: `configs/fulton_ga.json`
- **Database Table**: `fulton_ga_filing` (created via `create_fulton_table.sql`)
- **County Filter**: Automatically filters to `FULTON` county only
- **Documentation**: `README_FultonGA.md`

### 2. **Cobb County GA** (`CobbGA.py`)
- **Configuration**: `configs/cobb_ga.json`
- **Database Table**: `cobb_ga_filing` (created via `create_cobb_table.sql`)
- **County Filter**: Automatically filters to `COBB` county only

## Functional Organization

Both scrapers follow the same functional organization pattern:

```python
# 1. DATA MODELS - County-specific TypedDict
class FultonRecord(TypedDict):  # or CobbRecord
    case_number: str
    document_type: str
    filing_date: str
    debtor_name: str
    claimant_name: str
    county: str
    book_page: str
    document_link: Optional[str]

# 2. CONFIGURATION - County-specific constants
COUNTY_NAME = "Fulton GA"  # or "Cobb GA"
TAB_NAME = "FultonGA"      # or "CobbGA"

# 3. SCRAPER CLASS - County-specific implementation
class FultonScraper(SearchFormScraper):  # or CobbScraper
    async def setup_search_parameters(self, task_params):
        # Always filter to specific county
        await self.page.select_option('select[name="County"]', 'FULTON')  # or 'COBB'

# 4. DATABASE FUNCTIONS - County-specific tables
# Uses fulton_ga_filing or cobb_ga_filing tables

# 5. EXPORT FUNCTIONS - County-specific file naming
# Creates fulton_ga_TIMESTAMP.csv or cobb_ga_TIMESTAMP.csv files
```

## Usage Examples

### Fulton County
```bash
# Test run
python FultonGA.py --test --user-id "test-user" --max-records 10

# Production run
python FultonGA.py --user-id "user123" --from-date "12/01/2024" --to-date "12/28/2024"

# Specific instrument types
python FultonGA.py --user-id "user123" --instrument-types "Lien" "Lis Pendens"
```

### Cobb County
```bash
# Test run
python CobbGA.py --test --user-id "test-user" --max-records 10

# Production run
python CobbGA.py --user-id "user123" --from-date "12/01/2024" --to-date "12/28/2024"

# Specific instrument types
python CobbGA.py --user-id "user123" --instrument-types "Lien" "Lis Pendens"
```

## Database Setup

Create the database tables before running the scrapers:

```bash
# For Fulton County
psql -d your_database -f create_fulton_table.sql

# For Cobb County
psql -d your_database -f create_cobb_table.sql
```

## Key Features

### 1. **Automatic County Filtering**
- Each scraper automatically filters to its specific county
- No need to specify county in command line arguments
- Prevents cross-contamination of county data

### 2. **Separate Data Storage**
- Each county has its own database table
- Separate CSV export files with county-specific naming
- Separate Google Sheets tabs for each county

### 3. **Identical Functionality**
- Both scrapers support the same command line arguments
- Same search capabilities (date ranges, instrument types)
- Same export options (CSV, Google Sheets, database)

### 4. **Shared Infrastructure**
- Both use the same base `SearchFormScraper` class
- Same configuration schema and validation
- Same error handling and logging patterns

## Adding More Georgia Counties

To add additional Georgia counties (e.g., DeKalb, Gwinnett), follow this pattern:

1. **Copy Configuration**:
   ```bash
   cp configs/fulton_ga.json configs/dekalb_ga.json
   ```

2. **Update Configuration**:
   ```json
   {
     "name": "DeKalb County GA Lien Index",
     "description": "DeKalb County Georgia lien records via GSCCCA system"
   }
   ```

3. **Copy Scraper**:
   ```bash
   cp FultonGA.py DeKalbGA.py
   ```

4. **Update Scraper Code**:
   - Change class names (`DeKalbRecord`, `DeKalbScraper`)
   - Update county filter: `await self.page.select_option('select[name="County"]', 'DEKALB')`
   - Update database table name: `dekalb_ga_filing`
   - Update file naming and constants

5. **Create Database Table**:
   ```bash
   cp create_fulton_table.sql create_dekalb_table.sql
   # Update table name and comments in the SQL file
   ```

## Benefits of This Approach

### **Data Organization**
- Clean separation of county data
- Easy to track which records belong to which county
- Simplified reporting and analysis

### **Scalability**
- Easy to add new counties
- Each county can have different configurations if needed
- Independent deployment and monitoring

### **Reliability**
- Failure in one county scraper doesn't affect others
- Independent rate limiting and error handling
- Easier debugging and maintenance

### **Performance**
- Smaller, focused datasets per county
- Faster database queries with county-specific indexes
- Parallel execution possible for multiple counties

This approach demonstrates how your modular architecture enables efficient scaling to multiple jurisdictions while maintaining clean code organization and data integrity. 