const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function testBrevardFL() {
  console.log('🧪 Testing Brevard FL Integration...\n');

  try {
    // 1. Test database connection and table existence
    console.log('1. Testing database connection and schema...');
    
    try {
      const tableCheck = await prisma.$queryRaw`
        SELECT EXISTS (
          SELECT FROM information_schema.tables 
          WHERE table_name = 'brevard_fl_filing'
        )`;
      
      const tableExists = tableCheck[0].exists;
      if (tableExists) {
        console.log('   ✅ brevard_fl_filing table exists');
      } else {
        console.log('   ❌ brevard_fl_filing table does not exist');
        return;
      }
    } catch (error) {
      console.log(`   ❌ Database connection failed: ${error.message}`);
      return;
    }

    // 2. Test table structure
    console.log('\n2. Testing table structure...');
    try {
      const columns = await prisma.$queryRaw`
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_name = 'brevard_fl_filing'
        ORDER BY ordinal_position`;
      
      console.log('   Table columns:');
      columns.forEach(col => {
        console.log(`   - ${col.column_name} (${col.data_type})`);
      });
    } catch (error) {
      console.log(`   ❌ Error checking table structure: ${error.message}`);
    }

    // 3. Test user types
    console.log('\n3. Testing user types...');
    const userTypes = await prisma.user.groupBy({
      by: ['userType'],
      _count: { userType: true }
    });
    
    console.log('   User types in database:');
    userTypes.forEach(type => {
      console.log(`   - ${type.userType}: ${type._count.userType} users`);
    });
    
    const brevardUsers = userTypes.find(type => type.userType === 'BREVARD_FL');
    if (brevardUsers) {
      console.log(`   ✅ Found ${brevardUsers._count.userType} BREVARD_FL users`);
    } else {
      console.log('   ⚠️ No BREVARD_FL users found (assign a user to test fully)');
    }

    // 4. Test API endpoints (basic structure test)
    console.log('\n4. Testing API endpoint availability...');
    try {
      const response = await fetch('http://localhost:3000/api/brevard-fl');
      if (response.status === 401) {
        console.log('   ✅ /api/brevard-fl endpoint exists (returns 401 Unauthorized as expected)');
      } else {
        console.log(`   ⚠️ /api/brevard-fl returned status: ${response.status}`);
      }
    } catch (error) {
      console.log(`   ❌ /api/brevard-fl endpoint test failed: ${error.message}`);
    }

    try {
      const response = await fetch('http://localhost:3000/api/pull-brevard-fl', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dateFilter: 7 })
      });
      if (response.status === 401) {
        console.log('   ✅ /api/pull-brevard-fl endpoint exists (returns 401 Unauthorized as expected)');
      } else {
        console.log(`   ⚠️ /api/pull-brevard-fl returned status: ${response.status}`);
      }
    } catch (error) {
      console.log(`   ❌ /api/pull-brevard-fl endpoint test failed: ${error.message}`);
    }

    // 5. Test job worker capability
    console.log('\n5. Testing job processing capability...');
    
    // Check if there are any recent BREVARD_FL_PULL jobs
    const recentJobs = await prisma.scraping_job.findMany({
      where: { 
        job_type: 'BREVARD_FL_PULL',
        created_at: {
          gte: new Date(Date.now() - 24 * 60 * 60 * 1000) // Last 24 hours
        }
      },
      orderBy: { created_at: 'desc' },
      take: 5
    });

    if (recentJobs.length > 0) {
      console.log(`   ✅ Found ${recentJobs.length} recent BREVARD_FL_PULL jobs:`);
      recentJobs.forEach((job, index) => {
        console.log(`   ${index + 1}. Job ${job.id}: ${job.status} (${job.created_at.toISOString()})`);
        if (job.error_message) {
          console.log(`      Error: ${job.error_message}`);
        }
        if (job.records_processed) {
          console.log(`      Records processed: ${job.records_processed}`);
        }
      });
    } else {
      console.log('   ℹ️ No recent BREVARD_FL_PULL jobs found');
    }

    // 6. Test data retrieval
    console.log('\n6. Testing Brevard FL records...');
    const recordCount = await prisma.brevard_fl_filing.count();
    console.log(`   📊 Total Brevard FL records in database: ${recordCount}`);

    if (recordCount > 0) {
      const sampleRecords = await prisma.brevard_fl_filing.findMany({
        take: 3,
        orderBy: { created_at: 'desc' },
        select: {
          document_number: true,
          document_type: true,
          recorded_date: true,
          grantor: true,
          grantee: true,
          county: true,
          created_at: true
        }
      });

      console.log('   Sample records:');
      sampleRecords.forEach((record, index) => {
        console.log(`   ${index + 1}. Doc: ${record.document_number}, Type: ${record.document_type}, Date: ${record.recorded_date?.toISOString().split('T')[0] || 'N/A'}`);
      });
    }

    // 7. Display database statistics
    console.log('\n7. Database statistics...');
    const counts = {
      lph: await prisma.lis_pendens_filing.count(),
      md: await prisma.md_case_search_filing.count(),
      hillsborough: await prisma.hillsborough_nh_filing.count(),
      brevard: await prisma.brevard_fl_filing.count(),
      users: await prisma.user.count(),
      jobs: await prisma.scraping_job.count()
    };
    
    console.log(`   - LPH records: ${counts.lph}`);
    console.log(`   - MD Case Search records: ${counts.md}`);
    console.log(`   - Hillsborough NH records: ${counts.hillsborough}`);
    console.log(`   - Brevard FL records: ${counts.brevard}`);
    console.log(`   - Total users: ${counts.users}`);
    console.log(`   - Total scraping jobs: ${counts.jobs}`);

    console.log('\n🎉 Brevard FL integration test completed!');
    
    console.log('\n📋 Next steps to complete testing:');
    console.log('   1. Assign a user to BREVARD_FL type via /user-settings');
    console.log('   2. Login as that user and test the dashboard');
    console.log('   3. Try clicking "Pull Records" to test the full workflow');
    console.log('   4. Verify records appear in the dashboard grid');

  } catch (error) {
    console.error('❌ Test failed:', error);
  } finally {
    await prisma.$disconnect();
  }
}

// Run the test
testBrevardFL().catch(console.error); 