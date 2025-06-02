const { PrismaClient } = require('@prisma/client');

async function debugUserIdMismatch() {
  console.log('=== DEBUGGING USERID FOREIGN KEY CONSTRAINT ===');
  
  const prisma = new PrismaClient();
  
  try {
    // Get all users from database
    const allUsers = await prisma.user.findMany({
      select: {
        id: true,
        email: true,
        firstName: true,
        createdAt: true
      },
      orderBy: { createdAt: 'desc' }
    });
    
    console.log('\n=== ALL USERS IN DATABASE ===');
    allUsers.forEach((user, index) => {
      console.log(`${index + 1}. ID: "${user.id}"`);
      console.log(`   Email: ${user.email}`);
      console.log(`   Name: ${user.firstName}`);
      console.log('');
    });
    
    // Get recent failed jobs to see what userId was attempted
    const failedJobs = await prisma.scraping_job.findMany({
      where: {
        status: 'FAILED'
      },
      select: {
        id: true,
        userId: true,
        created_at: true,
        error_message: true
      },
      orderBy: { created_at: 'desc' },
      take: 5
    });
    
    console.log('=== RECENT FAILED JOBS ===');
    failedJobs.forEach((job, index) => {
      console.log(`${index + 1}. Job ID: ${job.id}`);
      console.log(`   Attempted userId: "${job.userId}"`);
      console.log(`   Created: ${job.created_at}`);
      console.log(`   Error: ${job.error_message}`);
      console.log('');
    });
    
    // Check if there are userIds that don't exist
    const allJobUserIds = await prisma.scraping_job.findMany({
      select: { userId: true },
      distinct: ['userId']
    });
    
    console.log('=== USERID VALIDATION ===');
    for (const jobUserId of allJobUserIds) {
      const userExists = allUsers.find(u => u.id === jobUserId.userId);
      if (!userExists) {
        console.log(`❌ ORPHANED USERID: "${jobUserId.userId}" (used in jobs but user doesn't exist)`);
      } else {
        console.log(`✅ Valid userId: "${jobUserId.userId}" -> ${userExists.email}`);
      }
    }
    
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

debugUserIdMismatch(); 