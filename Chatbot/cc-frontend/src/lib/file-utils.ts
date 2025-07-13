import path from 'path';
import fs from 'fs/promises';

/**
 * Get the appropriate temporary directory for the current environment
 * - In serverless environments (Vercel, etc.), use /tmp which is writable
 * - In local development, use the local scripts/temp directory
 */
export function getTempDirectory(): string {
  if (process.env.VERCEL || process.env.NODE_ENV === 'production') {
    return '/tmp';
  }
  return path.join(process.cwd(), 'scripts', 'temp');
}

/**
 * Ensure the temporary directory exists
 */
export async function ensureTempDirectory(): Promise<string> {
  const tempDir = getTempDirectory();
  await fs.mkdir(tempDir, { recursive: true });
  return tempDir;
}

/**
 * Create a unique temporary file path
 */
export function createTempFilePath(prefix: string, suffix: string = '.tmp'): string {
  const tempDir = getTempDirectory();
  const timestamp = Date.now();
  const randomId = Math.random().toString(36).substring(2, 15);
  return path.join(tempDir, `${prefix}_${timestamp}_${randomId}${suffix}`);
}

/**
 * Clean up temporary files safely
 */
export async function cleanupTempFiles(...filePaths: string[]): Promise<void> {
  const cleanupPromises = filePaths.map(async (filePath) => {
    try {
      await fs.unlink(filePath);
    } catch (error) {
      // Ignore errors - file might not exist or already be cleaned up
      console.warn(`Failed to cleanup temp file ${filePath}:`, error);
    }
  });
  
  await Promise.all(cleanupPromises);
} 