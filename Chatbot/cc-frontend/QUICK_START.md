# CountyPuller Frontend - Quick Start

## Current Status

The project has been cleaned up and reorganized:

### ✅ Completed
1. **Updated package.json** - Removed hardcoded paths, updated to compatible versions
2. **Fixed dependencies** - Downgraded to stable versions (Next.js 14, MUI 5, etc.)
3. **Created helper scripts**:
   - `Start-Dev.ps1` - PowerShell script to run dev server
   - `Start-JobWorker.ps1` - PowerShell script to run job worker
   - `dev.bat` - Batch file for Windows
   - `job-worker.bat` - Batch file for job worker
4. **Added configuration files**:
   - `.npmrc` - NPM configuration for legacy peer deps
   - `tailwind.config.js` - Tailwind CSS configuration
5. **Cleaned up unnecessary files**:
   - Removed empty `data.sql`
   - Removed redundant batch files
   - Removed documentation files from root (should be in docs/)

### ⚠️ Known Issues
1. **npm scripts issue** - The `npm run dev` command has PATH issues on Windows
2. **Prisma installation** - Had to install with `--ignore-scripts` flag

## Quick Start

### Option 1: PowerShell (Recommended)
```powershell
# Install dependencies (if not done)
npm install --legacy-peer-deps

# Run development server
./Start-Dev.ps1

# In another terminal, run job worker
./Start-JobWorker.ps1
```

### Option 2: Direct Commands
```powershell
# Install dependencies
npm install --legacy-peer-deps --ignore-scripts

# Install Prisma separately if needed
npm install --save-dev prisma@5.20.0 --ignore-scripts
npm install @prisma/client@5.20.0 --ignore-scripts

# Run dev server directly
node_modules\.bin\next.cmd dev

# Run job worker
node start-job-worker.js
```

### Option 3: Fix npm run dev
To fix the npm scripts, you may need to:
1. Add Node.js to your system PATH
2. Or use npx: `npx next dev`

## Required Environment Variables

Create a `.env` file with:
```env
DATABASE_URL=postgresql://user:password@localhost:5432/dbname
NEXTAUTH_SECRET=your-secret-key
NEXTAUTH_URL=http://localhost:3000
```

## Next Steps

1. Create `.env` file with your configuration
2. Run `npx prisma generate` to generate Prisma client
3. Run `npx prisma migrate dev` if you have pending migrations
4. Start the dev server using one of the methods above

## Troubleshooting

If you encounter issues:
1. Delete `node_modules` and reinstall: `npm install --legacy-peer-deps`
2. Make sure Node.js is in your PATH
3. Check that PostgreSQL is running
4. Verify your `.env` file has correct database credentials 