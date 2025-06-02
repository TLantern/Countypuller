const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function checkUserSession() {
  try {
    // Check all users in database
    const allUsers = await prisma.user.findMany({
      select: {
        id: true,
        email: true,
        firstName: true,
        createdAt: true
      },
      orderBy: { createdAt: 'desc' }
    });

    console.log('=== ALL USERS IN DATABASE ===');
    allUsers.forEach((user, index) => {
      console.log(`${index + 1}. ID: ${user.id}`);
      console.log(`   Email: ${user.email}`);
      console.log(`   Name: ${user.firstName}`);
      console.log(`   Created: ${user.createdAt}`);
      console.log('');
    });

    // Check what userIds are being used in job attempts
    const recentJobs = await prisma.scraping_job.findMany({
      select: {
        id: true,
        userId: true,
        status: true,
        created_at: true,
        error_message: true
      },
      orderBy: { created_at: 'desc' },
      take: 5
    });

    console.log('=== RECENT JOB ATTEMPTS ===');
    recentJobs.forEach((job, index) => {
      console.log(`${index + 1}. Job ID: ${job.id}`);
      console.log(`   User ID: ${job.userId}`);
      console.log(`   Status: ${job.status}`);
      console.log(`   Created: ${job.created_at}`);
      if (job.error_message) {
        console.log(`   Error: ${job.error_message}`);
      }
      console.log('');
    });

    // The failing userId that needs to be fixed
    const failingUserId = 'e0e8ccc4-36ac-4632-ac25-5e15ea0acb02';
    const workingUserId = '51ec156c-fae9-47a8-bcfc-4146e4036a0f';

    console.log('=== ANALYSIS ===');
    console.log(`Failing User ID: ${failingUserId}`);
    console.log(`Working User ID: ${workingUserId}`);
    
    const failingUserExists = allUsers.find(u => u.id === failingUserId);
    const workingUserExists = allUsers.find(u => u.id === workingUserId);
    
    console.log(`Failing User exists in DB: ${!!failingUserExists}`);
    console.log(`Working User exists in DB: ${!!workingUserExists}`);

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

checkUserSession(); 