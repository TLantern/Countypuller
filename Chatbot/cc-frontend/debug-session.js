// Test session handling in different environments
async function debugSession() {
  console.log('=== SESSION DEBUG ===');
  console.log('NODE_ENV:', process.env.NODE_ENV);
  console.log('NEXTAUTH_URL:', process.env.NEXTAUTH_URL);
  
  // Test login endpoint
  try {
    console.log('\n1. Testing login page...');
    const loginResponse = await fetch('http://localhost:3000/login');
    console.log('Login page status:', loginResponse.status);
    
    console.log('\n2. Testing auth endpoint...');
    const authResponse = await fetch('http://localhost:3000/api/auth/session');
    const sessionData = await authResponse.text();
    console.log('Session status:', authResponse.status);
    console.log('Session data:', sessionData);
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

debugSession(); 