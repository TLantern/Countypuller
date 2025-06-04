const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function triggerMDJob() {
  try {
    // Get the MD user
    const mdUser = await prisma.user.findFirst({
      where: { userType: 'MD_CASE_SEARCH' }
    });
    
    if (!mdUser) {
      console.log('No MD_CASE_SEARCH user found!');
      return;
    }
    
    console.log(`Found MD user: ${mdUser.email} (${mdUser.id})`);
    
    // Create a test job
    const job = await prisma.scraping_job.create({
      data: {
        job_type: 'MD_CASE_SEARCH',
        status: 'pending',
        parameters: JSON.stringify({
          limit: 5,
          source: 'maryland_case_search',
          letters: ['a', 'b', 'c']
        }),
        userId: mdUser.id,
        created_at: new Date()
      }
    });
    
    console.log(`Created MD job: ${job.id}`);
    console.log('Job parameters:', JSON.parse(job.parameters));
    
    // Check if job worker is running
    const pendingJobs = await prisma.scraping_job.count({
      where: { status: 'pending' }
    });
    
    console.log(`Total pending jobs: ${pendingJobs}`);
    console.log('Make sure your job worker is running to process this job!');
    
  } catch (error) {
    console.error('Error creating MD job:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

triggerMDJob(); 