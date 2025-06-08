const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function main() {
  try {
    const users = await prisma.user.findMany();
    console.log('Total users:', users.length);
    
    if (users.length === 0) {
      console.log('No users found. Creating a test user...');
      
      const newUser = await prisma.user.create({
        data: {
          id: '80dc4c44-f591-40c9-9af8-e1205489cb8d', // Use the ID from your session
          email: 'test@example.com',
          firstName: 'Test',
          password: 'hashedpassword',
          userType: 'BREVARD_FL'
        }
      });
      
      console.log('Created user:', newUser.email, 'with type:', newUser.userType);
    } else {
      console.log('Users found:');
      users.forEach(u => console.log(`- ${u.email} (${u.userType})`));
    }
  } catch (error) {
    console.error('Error:', error);
  } finally {
    await prisma.$disconnect();
  }
}

main(); 