const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function testJobWorker() {
  console.log('🔄 Testing Job Worker with TEST_SCRAPE...\n');

  try {
    // Find a test user
    const testUser = await prisma.user.findFirst({
      where: { email: 'testlph@example.com' }
    });

    if (!testUser) {
      console.log('❌ No test user found. Run test-complete-system.js first.');
      return;
    }

    // Create a new TEST_SCRAPE job
    const job = await prisma.scraping_job.create({
      data: {
        job_type: 'TEST_SCRAPE',
        status: 'PENDING',
        parameters: { test: true, max_records: 10 },
        userId: testUser.id
      }
    });

    console.log(`✅ Created TEST_SCRAPE job: ${job.id}`);
    console.log('⏳ Job worker should process this within 30 seconds...');

    // Wait and check status
    for (let i = 0; i < 6; i++) {
      await new Promise(resolve => setTimeout(resolve, 10000)); // Wait 10 seconds
      
      const updatedJob = await prisma.scraping_job.findUnique({
        where: { id: job.id }
      });

      console.log(`📊 Check ${i + 1}: Job status is ${updatedJob.status}`);
      
      if (updatedJob.status === 'COMPLETED') {
        console.log('✅ Job completed successfully!');
        console.log(`📄 Result: ${JSON.stringify(updatedJob.result, null, 2)}`);
        break;
      } else if (updatedJob.status === 'FAILED') {
        console.log('❌ Job failed:');
        console.log(`📄 Error: ${updatedJob.error_message}`);
        break;
      }
    }

  } catch (error) {
    console.error('❌ Test failed:', error);
  } finally {
    await prisma.$disconnect();
  }
}

testJobWorker(); 