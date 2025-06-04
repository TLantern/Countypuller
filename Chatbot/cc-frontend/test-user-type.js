const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

async function testUserTypes() {
  try {
    console.log('🔍 Testing user type functionality...');
    
    // Get all users
    const users = await prisma.user.findMany({
      select: { id: true, email: true, userType: true }
    });
    
    console.log(`📊 Found ${users.length} users:`);
    users.forEach(user => {
      console.log(`  - ${user.email}: ${user.userType || 'NULL'}`);
    });
    
    // Update users without userType to LPH (default)
    const usersWithoutType = users.filter(user => !user.userType);
    if (usersWithoutType.length > 0) {
      console.log(`\n🔧 Updating ${usersWithoutType.length} users to default LPH type...`);
      
      for (const user of usersWithoutType) {
        await prisma.user.update({
          where: { id: user.id },
          data: { userType: 'LPH' }
        });
        console.log(`  ✅ Updated ${user.email} to LPH`);
      }
    }
    
    // Show final state
    const updatedUsers = await prisma.user.findMany({
      select: { id: true, email: true, userType: true }
    });
    
    console.log(`\n📊 Final user types:`);
    updatedUsers.forEach(user => {
      console.log(`  - ${user.email}: ${user.userType}`);
    });
    
    console.log('\n✅ User type test completed successfully!');
    
  } catch (error) {
    console.error('❌ Error testing user types:', error);
  } finally {
    await prisma.$disconnect();
  }
}

testUserTypes(); 