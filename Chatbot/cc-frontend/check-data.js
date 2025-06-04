const { PrismaClient } = require('@prisma/client');
const prisma = new PrismaClient();

async function checkData() {
  try {
    const mdCount = await prisma.md_case_search_filing.count();
    const lphCount = await prisma.lis_pendens_filing.count();
    
    console.log('Database record counts:');
    console.log('- MD Case Search records:', mdCount);
    console.log('- LPH records:', lphCount);
    
    if (mdCount > 0) {
      const sample = await prisma.md_case_search_filing.findMany({ take: 2 });
      console.log('Sample MD records:');
      sample.forEach((record, i) => {
        console.log(`  ${i+1}. ${record.case_number} - ${record.party_name} (${record.created_at})`);
      });
    } else {
      console.log('No MD Case Search records found in database');
    }
  } catch (error) {
    console.error('Database check error:', error.message);
  } finally {
    await prisma.$disconnect();
  }
}

checkData(); 