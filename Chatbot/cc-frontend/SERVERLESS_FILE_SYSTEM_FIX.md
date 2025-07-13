# Serverless File System Fix

## Problem Description

The application was experiencing "read-only file system" errors when deployed to serverless environments (like Vercel):

```
Error: EROFS: read-only file system, open '/var/task/Chatbot/cc-frontend/scripts/temp/skip_trace_input_44ce9f38-4a7b-4a4b-ad03-7236d59ed9b8_1752393180769.csv'
```

## Root Cause

In serverless environments:
- The entire file system is **read-only** except for the `/tmp` directory
- Our application was trying to write temporary files to `scripts/temp/` which is not writable
- This affected both the skip trace and hot-20 functionality

## Solution Implemented

### 1. Fixed Skip Trace Route (`src/app/api/skip-trace/route.ts`)

**Before:**
```typescript
const tempDir = path.join(scriptsDir, 'temp');
```

**After:**
```typescript
// Use /tmp for serverless environments (Vercel, etc.) or fallback to local temp
const tempDir = process.env.VERCEL || process.env.NODE_ENV === 'production' 
  ? '/tmp' 
  : path.join(scriptsDir, 'temp');
```

### 2. Fixed Hot-20 Route (`src/app/api/hot-20/route.ts`)

**Before:**
```typescript
const tempDir = path.join(process.cwd(), 'scripts', 'temp');
```

**After:**
```typescript
// Use /tmp for serverless environments (Vercel, etc.) or fallback to local temp
const tempDir = process.env.VERCEL || process.env.NODE_ENV === 'production' 
  ? '/tmp' 
  : path.join(process.cwd(), 'scripts', 'temp');
```

### 3. Created Utility Module (`src/lib/file-utils.ts`)

Added reusable utilities for consistent file handling:

```typescript
export function getTempDirectory(): string
export async function ensureTempDirectory(): Promise<string>
export function createTempFilePath(prefix: string, suffix?: string): string
export async function cleanupTempFiles(...filePaths: string[]): Promise<void>
```

## Environment Detection Logic

The fix uses this logic to determine the appropriate temp directory:

1. **Vercel Environment**: Uses `/tmp` (detected via `process.env.VERCEL`)
2. **Production Environment**: Uses `/tmp` (detected via `process.env.NODE_ENV === 'production'`)
3. **Local Development**: Uses `scripts/temp` (for easier debugging)

## Files Modified

1. `src/app/api/skip-trace/route.ts` - Fixed temp directory path
2. `src/app/api/hot-20/route.ts` - Fixed temp directory path  
3. `src/lib/file-utils.ts` - New utility module (created)
4. `SERVERLESS_FILE_SYSTEM_FIX.md` - This documentation (created)

## Testing

### Local Development
- ✅ Still uses `scripts/temp` for easy debugging
- ✅ Temp files are visible in the project directory
- ✅ No breaking changes to existing workflow

### Production/Serverless
- ✅ Uses `/tmp` directory which is writable
- ✅ Skip trace functionality works
- ✅ Hot-20 analysis works
- ✅ Temp files are properly cleaned up

## Usage Examples

### Using the New Utility Functions

```typescript
import { ensureTempDirectory, createTempFilePath, cleanupTempFiles } from '@/lib/file-utils';

// Ensure temp directory exists
const tempDir = await ensureTempDirectory();

// Create unique temp file paths
const inputFile = createTempFilePath('skip_trace_input', '.csv');
const outputFile = createTempFilePath('skip_trace_output', '.csv');

// ... do work with files ...

// Clean up when done
await cleanupTempFiles(inputFile, outputFile);
```

### Manual Temp Directory Usage

```typescript
import { getTempDirectory } from '@/lib/file-utils';

const tempDir = getTempDirectory();
// Will return '/tmp' in production, 'scripts/temp' in development
```

## Prevention

To prevent similar issues in the future:

1. **Always use the utility functions** from `src/lib/file-utils.ts` for temp file operations
2. **Never hardcode** file paths like `scripts/temp` or `/tmp`
3. **Test in production environment** or use environment variables to simulate serverless conditions
4. **Use environment detection** rather than assuming local file system structure

## Rollback Plan

If issues arise, the fix can be easily rolled back by reverting these changes:

```bash
git revert <commit-hash>
```

The application will fall back to the original behavior of using `scripts/temp` for all environments.

## Related Issues

This fix resolves:
- Skip trace "read-only file system" errors
- Hot-20 analysis file creation failures  
- Any future temporary file operations in serverless environments

## Future Considerations

1. **Database Storage**: For large files or persistent data, consider using database storage instead of temp files
2. **Cloud Storage**: For files that need to persist across requests, consider AWS S3 or similar
3. **Memory Streams**: For small data, consider using memory streams instead of temp files 