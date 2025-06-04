# User Type System - LPH vs Maryland Case Search

## Overview

The application now supports two different user types that determine which scraper runs when users click "Pull Records":

- **LPH**: Users who pull Lis Pendens records from Harris County
- **MD_CASE_SEARCH**: Users who pull case records from Maryland Case Search

## How It Works

### 1. Database Schema
- Added `userType` field to the `User` model (defaults to "LPH")
- Added `md_case_search_filing` table for Maryland case search records
- Both user types have their own dedicated data tables

### 2. API Endpoints

#### For LPH Users:
- `POST /api/pull-lph` - Creates LIS_PENDENS_PULL jobs
- `GET /api/lis-pendens` - Fetches Lis Pendens records
- Requires `userType = "LPH"`

#### For MD Case Search Users:
- `POST /api/pull-md-case-search` - Creates MD_CASE_SEARCH jobs  
- `GET /api/md-case-search` - Fetches Maryland case search records
- Requires `userType = "MD_CASE_SEARCH"`

#### User Management:
- `GET /api/auth/user-type` - Get current user's type
- `POST /api/auth/user-type` - Update user's type

### 3. Frontend Behavior

The dashboard automatically adapts based on user type:

#### LPH Users See:
- County/Document type selectors (Harris, Fort Bend, Montgomery)
- Lis Pendens specific columns (Filing No, Volume No, Page No, etc.)
- "Pull Records" button triggers Harris County scraper

#### MD Case Search Users See:
- Maryland Case Search specific columns (Party Name, Case Type, Defendant Info, etc.)
- No county selectors (Maryland-specific)
- "Pull Records" button triggers Maryland Case Search scraper

## Setting Up User Types

### Method 1: User Settings Page
1. Navigate to `/user-settings`
2. Select desired account type from dropdown
3. Click "Update Account Type"
4. Return to dashboard to see changes

### Method 2: Direct Database Update
```sql
-- Set user to Maryland Case Search
UPDATE "User" SET "userType" = 'MD_CASE_SEARCH' WHERE email = 'user@example.com';

-- Set user to Lis Pendens  
UPDATE "User" SET "userType" = 'LPH' WHERE email = 'user@example.com';
```

### Method 3: Test Script
Run the included test script to see current user types:
```bash
node test-user-type.js
```

## Backend Integration

### Python Scrapers
The job system creates different job types:
- `LIS_PENDENS_PULL` jobs should trigger the existing Harris County scraper
- `MD_CASE_SEARCH` jobs should trigger the `MdCaseSearch.py` script

### Job Parameters
- **LPH jobs**: `{ limit: 10, source: 'harris_county' }`
- **MD jobs**: `{ limit: 10, source: 'maryland_case_search', letters: ['a','b','c','d','e','f'] }`

## Security

- Users can only access endpoints matching their user type
- API endpoints verify user permissions before processing
- Cross-user-type access returns 403 Forbidden

## Data Isolation

- LPH users only see `lis_pendens_filing` records they created
- MD users only see `md_case_search_filing` records they created
- No cross-contamination between user types

## Testing

1. Create two test accounts
2. Set one to LPH, one to MD_CASE_SEARCH using user settings
3. Login as each user and verify:
   - Different dashboard layouts
   - Different data columns
   - Different pull endpoints called
   - Proper access restrictions

## Migration Notes

- Existing users default to LPH type
- No data migration needed for existing Lis Pendens records
- Maryland Case Search table is new and empty initially 