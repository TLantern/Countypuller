const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkJobStatus() {
  try {
    // Check job status
    const jobs = await prisma.scraping_job.findMany({
      orderBy: { created_at: 'desc' },
      take: 5,
      select: {
        id: true,
        job_type: true,
        status: true,
        created_at: true,
        completed_at: true,
        records_processed: true,
        error_message: true
      }
    });
    
    console.log('Recent jobs:');
    jobs.forEach(job => {
      console.log(`- ${job.job_type}: ${job.status} (${job.records_processed || 0} records)`);
      if (job.error_message) {
        console.log(`  Error: ${job.error_message}`);
      }
    });
    
    // Check MD data count
    const mdCount = await prisma.md_case_search_filing.count();
    console.log(`\nMD Case Search records in DB: ${mdCount}`);
    
    if (mdCount > 0) {
      const sample = await prisma.md_case_search_filing.findMany({ 
        take: 3,
        orderBy: { created_at: 'desc' }
      });
      console.log('Latest MD records:');
      sample.forEach((record, i) => {
        console.log(`  ${i+1}. ${record.case_number} - ${record.party_name}`);
      });
    }
    
  } catch (error) {
    console.error('Error checking status:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

checkJobStatus(); 