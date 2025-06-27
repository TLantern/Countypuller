const { PrismaClient } = require('@prisma/client');
require('dotenv').config();

const prisma = new PrismaClient();

async function checkJobs() {
  try {
    console.log('Checking job status...\n');
    
    // Get all jobs ordered by creation date
    const allJobs = await prisma.scraping_job.findMany({
      orderBy: { created_at: 'desc' },
      take: 10
    });
    
    console.log(`Found ${allJobs.length} recent jobs:\n`);
    
    for (const job of allJobs) {
      console.log(`Job ID: ${job.id}`);
      console.log(`Type: ${job.job_type}`);
      console.log(`Status: ${job.status}`);
      console.log(`User: ${job.userId}`);
      console.log(`Created: ${job.created_at}`);
      console.log(`Parameters: ${JSON.stringify(job.parameters)}`);
      if (job.error_message) {
        console.log(`Error: ${job.error_message}`);
      }
      console.log('---');
    }
    
    // Count jobs by status
    const statusCounts = await prisma.scraping_job.groupBy({
      by: ['status'],
      _count: true
    });
    
    console.log('\nJob counts by status:');
    for (const status of statusCounts) {
      console.log(`${status.status}: ${status._count}`);
    }
    
    // Check for pending jobs specifically
    const pendingJobs = await prisma.scraping_job.findMany({
      where: { status: 'PENDING' },
      orderBy: { created_at: 'asc' }
    });
    
    console.log(`\nPending jobs: ${pendingJobs.length}`);
    for (const job of pendingJobs) {
      console.log(`- Job ${job.id} (${job.job_type}) created at ${job.created_at}`);
    }
    
  } catch (error) {
    console.error('Error checking jobs:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkJobs(); 