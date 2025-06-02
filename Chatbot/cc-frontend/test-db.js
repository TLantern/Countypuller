const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function testDb() {
  try {
    // Check all lis pendens records
    const allRecords = await prisma.lis_pendens_filing.findMany({
      select: {
        case_number: true,
        userId: true,
        created_at: true,
        property_address: true
      },
      orderBy: { created_at: 'desc' },
      take: 10
    });

    console.log('=== ALL LIS PENDENS RECORDS (Latest 10) ===');
    console.log(JSON.stringify(allRecords, null, 2));

    // Check all users
    const allUsers = await prisma.user.findMany({
      select: {
        id: true,
        email: true,
        firstName: true
      }
    });

    console.log('\n=== ALL USERS ===');
    console.log(JSON.stringify(allUsers, null, 2));

    // Check recent jobs
    const recentJobs = await prisma.scraping_job.findMany({
      orderBy: { created_at: 'desc' },
      take: 5
    });

    console.log('\n=== RECENT JOBS ===');
    console.log(JSON.stringify(recentJobs, null, 2));

  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

testDb(); 