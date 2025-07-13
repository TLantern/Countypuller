# User ID Mapping Issue Fix

## Problem Description

The Harris County data pulling system was experiencing a user ID mapping issue where:

1. **Symptom**: User `44ce9f38-4a7b-4a4b-ad03-7236d59ed9b8` (James Harden, jayoving@gmail.com) was successfully authenticated and could trigger scraping jobs
2. **Issue**: The Harris County records were being saved to the database with the wrong user ID (`867ebb10-afd9-4892-b781-208ba8098306`)
3. **Result**: The user could not see their scraped data because the API only returns records matching their user ID

## Root Cause Analysis

The issue was in the `harris_db_saver.py` UPSERT logic:

```sql
-- BEFORE (INCORRECT)
ON CONFLICT (case_number) DO UPDATE
SET
    filing_date = EXCLUDED.filing_date,
    doc_type = EXCLUDED.doc_type,
    -- ... other fields ...
    updated_at = EXCLUDED.updated_at
    -- ❌ Missing: "userId" = EXCLUDED."userId"
```

When a Harris County record already existed in the database (same case_number), the UPSERT would update all fields **except** the `userId`. This meant:
- New records got the correct user ID
- Existing records kept their old (incorrect) user ID

## Solution Implemented

### 1. Fixed the UPSERT Logic
Updated `Chatbot/Chatbot/re-agent/harris_db_saver.py`:

```sql
-- AFTER (CORRECT)
ON CONFLICT (case_number) DO UPDATE
SET
    filing_date = EXCLUDED.filing_date,
    doc_type = EXCLUDED.doc_type,
    -- ... other fields ...
    updated_at = EXCLUDED.updated_at,
    "userId" = EXCLUDED."userId"  -- ✅ Now updates user ID too
```

### 2. Fixed Existing Records
Updated 20 existing Harris County records to have the correct user ID:

```javascript
// Updated records from wrong user ID to correct user ID
const wrongUserId = '867ebb10-afd9-4892-b781-208ba8098306';
const correctUserId = '44ce9f38-4a7b-4a4b-ad03-7236d59ed9b8';
// 20 records updated successfully
```

### 3. Created Validation Tools
Created `Chatbot/Chatbot/re-agent/validate_user_mapping.py` to:
- Validate user ID mapping for recent records
- Fix any mismatches (with dry-run option)
- Prevent future occurrences

## Verification

After the fix:
- ✅ All 20 Harris County records now correctly mapped to user `44ce9f38-4a7b-4a4b-ad03-7236d59ed9b8`
- ✅ User validation script passes: `User mapping validation PASSED`
- ✅ Harris County API now returns the correct records for the user
- ✅ Future scraping jobs will correctly maintain user ID mapping

## Prevention Measures

### 1. Validation Script
Run this periodically to check for user ID mapping issues:

```bash
cd Chatbot/cc-frontend
export DATABASE_URL="your_database_url"
python3 ../Chatbot/re-agent/validate_user_mapping.py --user-id USER_ID_TO_CHECK
```

### 2. Fix Script
If issues are found, fix them with:

```bash
# Dry run (shows what would be fixed)
python3 ../Chatbot/re-agent/validate_user_mapping.py --user-id USER_ID --fix --dry-run

# Actual fix
python3 ../Chatbot/re-agent/validate_user_mapping.py --user-id USER_ID --fix
```

### 3. Code Review Checklist
When modifying database save operations:
- ✅ Ensure UPSERT logic updates ALL relevant fields including `userId`
- ✅ Test with existing records to verify user ID is preserved/updated correctly
- ✅ Run validation script after changes

## Files Modified

1. `Chatbot/Chatbot/re-agent/harris_db_saver.py` - Fixed UPSERT logic
2. `Chatbot/Chatbot/re-agent/validate_user_mapping.py` - New validation tool
3. Database records - Updated 20 Harris County records

## Testing

To verify the fix is working:

1. **Check user can see their records**:
   ```bash
   # Should return records for the user
   curl -H "Authorization: Bearer USER_TOKEN" /api/harris-county
   ```

2. **Run validation script**:
   ```bash
   python3 validate_user_mapping.py --user-id 44ce9f38-4a7b-4a4b-ad03-7236d59ed9b8
   # Should show: "✅ User mapping validation PASSED"
   ```

3. **Test new scraping jobs**:
   - Create a new scraping job
   - Verify records are saved with correct user ID
   - Verify user can see the new records

## Impact

- **Users**: Can now see their scraped Harris County data
- **System**: Improved data integrity and user isolation
- **Future**: Preventive measures in place to avoid similar issues 