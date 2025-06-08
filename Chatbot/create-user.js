const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function createUser() {
  try {
    // Check if user already exists
    const existingUser = await prisma.user.findUnique({
      where: { id: '80dc4c44-f591-40c9-9af8-e1205489cb8d' }
    });
    
    if (existingUser) {
      console.log('User already exists:', existingUser.email);
      return;
    }
    
    // Create the user
    const user = await prisma.user.create({
      data: {
        id: '80dc4c44-f591-40c9-9af8-e1205489cb8d',
        email: 'test@brevardfl.com',
        firstName: 'Test User',
        password: 'hashedpassword', // In real app, this should be properly hashed
        userType: 'BREVARD_FL'
      }
    });
    
    console.log('✅ Created user:', user.email, 'with type:', user.userType);
    
  } catch (error) {
    console.error('❌ Error creating user:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

createUser(); 