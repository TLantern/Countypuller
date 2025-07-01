# CountyPuller Frontend Setup Guide

## Prerequisites

1. Node.js v18+ installed (currently using v22.12.0)
2. PostgreSQL database running
3. Python 3.13 installed (for job worker scripts)

## Initial Setup

1. **Create .env file**
   ```bash
   # Copy the example file
   cp .env.example .env
   ```
   Then edit `.env` with your actual configuration values.

2. **Install dependencies**
   ```bash
   # Using the provided batch file (Windows)
   dev.bat
   
   # Or manually with npm
   npm install --legacy-peer-deps
   ```

3. **Setup database**
   ```bash
   npx prisma migrate dev
   ```

## Running the Application

### Development Server
```bash
# Windows - Using batch file
dev.bat

# Or using npm
npm run dev
```
The app will be available at http://localhost:3000

### Job Worker
```bash
# Windows - Using batch file
job-worker.bat

# Or using npm
npm run job-worker
```

## NPM Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run job-worker` - Start the job worker

## Project Structure

```
cc-frontend/
├── src/                    # Source code
│   ├── app/               # Next.js app directory
│   ├── components/        # React components
│   ├── context/          # React contexts
│   ├── hooks/            # Custom hooks
│   └── lib/              # Utility functions
├── prisma/                # Database schema and migrations
├── scripts/               # Node.js scripts
├── public/                # Static assets
├── dev.bat               # Development server script
└── job-worker.bat        # Job worker script
```

## Troubleshooting

### npm install fails
- Delete `node_modules` and `package-lock.json`
- Run `npm cache clean --force`
- Try `npm install --legacy-peer-deps`

### Node.js not found
- Update the NODE_PATH in `dev.bat` and `job-worker.bat`
- Make sure Node.js is installed and in PATH

### Database connection errors
- Check your DATABASE_URL in `.env`
- Ensure PostgreSQL is running
- Run `npx prisma migrate dev` to update schema

## Cleaned Up Files

The following files were removed as they were redundant:
- `tsconfig.tsbuildinfo` - Auto-generated
- `data.sql` - Empty file
- `start-dev.bat` - Replaced by `dev.bat`
- `run-job-worker.bat` - Replaced by `job-worker.bat` 