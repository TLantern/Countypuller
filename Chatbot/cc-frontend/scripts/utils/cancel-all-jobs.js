const { PrismaClient } = require('@prisma/client');
require('dotenv').config();

const prisma = new PrismaClient();

async function cancelAllJobs() {
  try {
    console.log('Canceling all pending and in-progress jobs...\n');
    
    // Cancel all PENDING jobs
    const cancelPending = await prisma.scraping_job.updateMany({
      where: {
        status: 'PENDING'
      },
      data: {
        status: 'FAILED',
        error_message: 'Job cancelled by admin',
        completed_at: new Date()
      }
    });
    
    console.log(`Cancelled ${cancelPending.count} PENDING jobs`);
    
    // Cancel all IN_PROGRESS jobs
    const cancelInProgress = await prisma.scraping_job.updateMany({
      where: {
        status: 'IN_PROGRESS'
      },
      data: {
        status: 'FAILED',
        error_message: 'Job cancelled by admin - was in progress',
        completed_at: new Date()
      }
    });
    
    console.log(`Cancelled ${cancelInProgress.count} IN_PROGRESS jobs`);
    
    // Show current status
    const statusCounts = await prisma.scraping_job.groupBy({
      by: ['status'],
      _count: true
    });
    
    console.log('\nFinal job counts by status:');
    for (const status of statusCounts) {
      console.log(`${status.status}: ${status._count}`);
    }
    
  } catch (error) {
    console.error('Error canceling jobs:', error);
  } finally {
    await prisma.$disconnect();
  }
}

cancelAllJobs(); 