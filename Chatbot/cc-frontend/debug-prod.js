const { PrismaClient } = require('@prisma/client');

async function debugProdIssues() {
  console.log('=== ENVIRONMENT DIAGNOSTIC ===');
  console.log('NODE_ENV:', process.env.NODE_ENV);
  console.log('DATABASE_URL present:', !!process.env.DATABASE_URL);
  console.log('NEXTAUTH_SECRET present:', !!process.env.NEXTAUTH_SECRET);
  console.log('NEXTAUTH_URL:', process.env.NEXTAUTH_URL);
  
  // Check critical auth environment variables
  const authVars = [
    'GITHUB_ID', 'GITHUB_SECRET',
    'GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 
    'AZURE_AD_CLIENT_ID', 'AZURE_AD_CLIENT_SECRET', 'AZURE_AD_TENANT_ID'
  ];
  
  console.log('\n=== AUTH ENVIRONMENT VARIABLES ===');
  authVars.forEach(varName => {
    console.log(`${varName} present:`, !!process.env[varName]);
  });

  // Test database connection
  console.log('\n=== DATABASE CONNECTION TEST ===');
  const prisma = new PrismaClient();
  
  try {
    // Test basic connection
    await prisma.$connect();
    console.log('✅ Database connected successfully');
    
    // Test user query
    const userCount = await prisma.user.count();
    console.log(`✅ User count: ${userCount}`);
    
    // Test scraping_job table
    const jobCount = await prisma.scraping_job.count();
    console.log(`✅ Job count: ${jobCount}`);
    
  } catch (error) {
    console.error('❌ Database connection failed:', error.message);
  } finally {
    await prisma.$disconnect();
  }

  // Check if running in development vs production
  console.log('\n=== RUNTIME ENVIRONMENT ===');
  console.log('Development mode:', process.env.NODE_ENV !== 'production');
  console.log('Next.js version:', require('next/package.json').version);
  console.log('Platform:', process.platform);
  console.log('Node version:', process.version);
}

debugProdIssues().catch(console.error); 