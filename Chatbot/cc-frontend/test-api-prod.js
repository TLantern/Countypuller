const fetch = require('node-fetch').default || require('node-fetch');

async function testApiEndpoint() {
  console.log('=== TESTING PRODUCTION API ===');
  
  // Test if the server is running
  try {
    const baseUrl = 'http://localhost:3000';
    console.log(`Testing API at: ${baseUrl}`);
    
    // First, let's try to access the endpoint without authentication
    console.log('\n1. Testing API endpoint accessibility...');
    const response = await fetch(`${baseUrl}/api/pull-lph`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ test: 'data' })
    });
    
    const result = await response.text();
    console.log('Status:', response.status);
    console.log('Response:', result);
    
    if (response.status === 401) {
      console.log('✅ API is working - got expected 401 (not authenticated)');
    } else {
      console.log('❌ Unexpected response');
    }
    
  } catch (error) {
    console.error('❌ Error testing API:', error.message);
    
    if (error.code === 'ECONNREFUSED') {
      console.log('💡 Server might not be running. Starting server...');
      console.log('   Run: npm start');
    }
  }
}

testApiEndpoint().catch(console.error); 