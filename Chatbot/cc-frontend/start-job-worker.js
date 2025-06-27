#!/usr/bin/env node

console.log('='.repeat(50));
console.log('CountyPuller Job Worker Startup');
console.log('='.repeat(50));
console.log(`Node.js version: ${process.version}`);
console.log(`Working directory: ${process.cwd()}`);
console.log(`Environment: ${process.env.NODE_ENV || 'development'}`);
console.log('='.repeat(50));

// Load environment variables
require('dotenv').config();

// Verify required environment variables
const requiredEnvs = ['DATABASE_URL'];
for (const env of requiredEnvs) {
  if (!process.env[env]) {
    console.error(`[FATAL] Missing required environment variable: ${env}`);
    process.exit(1);
  }
}

console.log('[INFO] Environment variables loaded successfully');

// Import and start the job worker
try {
  require('./scripts/job-worker.js');
} catch (error) {
  console.error('[FATAL] Failed to start job worker:', error);
  process.exit(1);
} 