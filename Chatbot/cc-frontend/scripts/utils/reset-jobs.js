const { PrismaClient } = require('@prisma/client');
require('dotenv').config();

const prisma = new PrismaClient();

async function resetStuckJobs() {
  try {
    console.log('Resetting stuck IN_PROGRESS jobs...\n');
    
    // Find jobs that have been IN_PROGRESS for more than 30 minutes
    const thirtyMinutesAgo = new Date(Date.now() - 30 * 60 * 1000);
    
    const stuckJobs = await prisma.scraping_job.findMany({
      where: {
        status: 'IN_PROGRESS',
        created_at: {
          lt: thirtyMinutesAgo
        }
      }
    });
    
    console.log(`Found ${stuckJobs.length} stuck jobs`);
    
    if (stuckJobs.length > 0) {
      // Reset them to PENDING
      const result = await prisma.scraping_job.updateMany({
        where: {
          status: 'IN_PROGRESS',
          created_at: {
            lt: thirtyMinutesAgo
          }
        },
        data: {
          status: 'PENDING'
        }
      });
      
      console.log(`Reset ${result.count} jobs from IN_PROGRESS to PENDING`);
    }
    
    // Also reset any jobs that are IN_PROGRESS for a very long time (> 2 hours)
    const twoHoursAgo = new Date(Date.now() - 2 * 60 * 60 * 1000);
    const veryStuckJobs = await prisma.scraping_job.updateMany({
      where: {
        status: 'IN_PROGRESS',
        created_at: {
          lt: twoHoursAgo
        }
      },
      data: {
        status: 'FAILED',
        error_message: 'Job timeout - reset due to long IN_PROGRESS status',
        completed_at: new Date()
      }
    });
    
    if (veryStuckJobs.count > 0) {
      console.log(`Failed ${veryStuckJobs.count} very old stuck jobs`);
    }
    
  } catch (error) {
    console.error('Error resetting jobs:', error);
  } finally {
    await prisma.$disconnect();
  }
}

resetStuckJobs(); 