const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkUserType() {
  try {
    const users = await prisma.user.findMany({
      select: { id: true, email: true, userType: true }
    });
    
    console.log('Current users and their types:');
    users.forEach(user => {
      console.log(`- ${user.email}: ${user.userType} (ID: ${user.id})`);
    });
    
    const mdUsers = users.filter(u => u.userType === 'MD_CASE_SEARCH');
    console.log(`\nMD_CASE_SEARCH users: ${mdUsers.length}`);
    
    if (mdUsers.length === 0) {
      console.log('No users are set to MD_CASE_SEARCH type!');
      console.log('You need to change your user type in the dashboard dropdown or user settings.');
    }
  } catch (error) {
    console.error('Error checking user types:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

checkUserType(); 