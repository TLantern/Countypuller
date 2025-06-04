const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function clearTestData() {
  try {
    const result = await prisma.md_case_search_filing.deleteMany({
      where: {
        case_number: {
          startsWith: 'TEST'
        }
      }
    });
    
    console.log(`Cleared ${result.count} test records`);
    
    const remaining = await prisma.md_case_search_filing.count();
    console.log(`${remaining} MD records remaining in database`);
    
  } catch (error) {
    console.error('Error clearing test data:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

clearTestData(); 