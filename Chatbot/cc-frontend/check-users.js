const { PrismaClient } = require('@prisma/client');

async function main() {
  const prisma = new PrismaClient();
  
  try {
    const users = await prisma.user.findMany({
      select: {
        email: true,
        userType: true,
        createdAt: true
      },
      orderBy: { createdAt: 'desc' }
    });
    
    console.log(`\n📊 Total users in database: ${users.length}\n`);
    
    if (users.length === 0) {
      console.log('❌ No users found in database');
    } else {
      console.log('📋 All users:');
      users.forEach((user, index) => {
        console.log(`  ${index + 1}. ${user.email} (${user.userType}) - Created: ${user.createdAt.toDateString()}`);
      });
    }
    
    // Count by user type
    const userTypeCounts = {};
    users.forEach(user => {
      userTypeCounts[user.userType] = (userTypeCounts[user.userType] || 0) + 1;
    });
    
    console.log('\n📈 User type breakdown:');
    Object.entries(userTypeCounts).forEach(([type, count]) => {
      console.log(`  - ${type}: ${count} users`);
    });
    
  } catch (error) {
    console.error('❌ Error checking users:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main(); 