const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function testHillsboroughNH() {
  try {
    console.log('🧪 Testing Hillsborough NH Integration...\n');

    // 1. Check if we can create a test user with HILLSBOROUGH_NH type
    console.log('1. Creating test user with HILLSBOROUGH_NH type...');
    
    const testUser = await prisma.user.upsert({
      where: { email: 'hillsborough-test@example.com' },
      update: { userType: 'HILLSBOROUGH_NH' },
      create: {
        email: 'hillsborough-test@example.com',
        firstName: 'Hillsborough',
        password: 'test123',
        userType: 'HILLSBOROUGH_NH'
      }
    });
    
    console.log(`✅ Test user created: ${testUser.email} (${testUser.userType})`);

    // 2. Test creating a sample Hillsborough NH record
    console.log('\n2. Creating sample Hillsborough NH record...');
    
    const sampleRecord = await prisma.hillsborough_nh_filing.create({
      data: {
        document_number: 'TEST-' + Date.now(),
        document_url: 'https://example.com/doc/test',
        recorded_date: new Date('2024-12-01'),
        instrument_type: 'LIEN',
        grantor: 'TEST GRANTOR',
        grantee: 'TEST GRANTEE',
        property_address: '123 Test Street, Manchester NH 03101',
        book_page: 'Book 1234, Page 567',
        consideration: '$50,000',
        legal_description: 'Test legal description',
        county: 'Hillsborough NH',
        state: 'NH',
        filing_date: '2024-12-01',
        amount: '$50,000',
        parties: 'TEST GRANTOR / TEST GRANTEE',
        location: 'Manchester, NH',
        status: 'active',
        is_new: true,
        doc_type: 'lien',
        userId: testUser.id
      }
    });
    
    console.log(`✅ Sample record created: ${sampleRecord.document_number}`);

    // 3. Test fetching records for the user
    console.log('\n3. Fetching Hillsborough NH records for user...');
    
    const userRecords = await prisma.hillsborough_nh_filing.findMany({
      where: { userId: testUser.id },
      orderBy: { created_at: 'desc' }
    });
    
    console.log(`✅ Found ${userRecords.length} records for user`);
    
    if (userRecords.length > 0) {
      const record = userRecords[0];
      console.log(`   - Document: ${record.document_number}`);
      console.log(`   - Type: ${record.instrument_type}`);
      console.log(`   - Grantor: ${record.grantor}`);
      console.log(`   - Grantee: ${record.grantee}`);
      console.log(`   - Address: ${record.property_address}`);
      console.log(`   - Amount: ${record.consideration}`);
    }

    // 4. Test updating a record
    console.log('\n4. Testing record update (mark as not new)...');
    
    const updatedRecord = await prisma.hillsborough_nh_filing.updateMany({
      where: { 
        document_number: sampleRecord.document_number,
        userId: testUser.id
      },
      data: { is_new: false }
    });
    
    console.log(`✅ Updated ${updatedRecord.count} record(s)`);

    // 5. Test creating a scraping job
    console.log('\n5. Testing scraping job creation...');
    
    const scrapingJob = await prisma.scraping_job.create({
      data: {
        job_type: 'HILLSBOROUGH_NH_PULL',
        status: 'PENDING',
        parameters: {
          limit: 15,
          source: 'hillsborough_nh_registry',
          extract_addresses: true
        },
        userId: testUser.id
      }
    });
    
    console.log(`✅ Scraping job created: ${scrapingJob.id} (${scrapingJob.job_type})`);

    // 6. Check database counts
    console.log('\n6. Database record counts:');
    
    const counts = {
      lph: await prisma.lis_pendens_filing.count(),
      md: await prisma.md_case_search_filing.count(),
      hillsborough: await prisma.hillsborough_nh_filing.count(),
      users: await prisma.user.count(),
      jobs: await prisma.scraping_job.count()
    };
    
    console.log(`   - LPH records: ${counts.lph}`);
    console.log(`   - MD Case Search records: ${counts.md}`);
    console.log(`   - Hillsborough NH records: ${counts.hillsborough}`);
    console.log(`   - Users: ${counts.users}`);
    console.log(`   - Scraping jobs: ${counts.jobs}`);

    // 7. Test user type validation
    console.log('\n7. Testing user types in database...');
    
    const userTypes = await prisma.user.groupBy({
      by: ['userType'],
      _count: { userType: true }
    });
    
    userTypes.forEach(type => {
      console.log(`   - ${type.userType}: ${type._count.userType} users`);
    });

    console.log('\n🎉 All Hillsborough NH tests passed!');
    console.log('\n📋 Next steps:');
    console.log('   1. Set a user to HILLSBOROUGH_NH type via /user-settings');
    console.log('   2. Login as that user and test the dashboard');
    console.log('   3. Try clicking "Pull Records" to test the API endpoints');
    console.log('   4. Verify the Python scraper integration');

  } catch (error) {
    console.error('❌ Test failed:', error);
  } finally {
    await prisma.$disconnect();
  }
}

// Run the test
testHillsboroughNH(); 