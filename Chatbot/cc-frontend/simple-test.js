async function testApi() {
  console.log('Testing production API...');
  
  try {
    const response = await fetch('http://localhost:3000/api/pull-lph', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ test: 'data' })
    });
    
    const result = await response.text();
    console.log('Status:', response.status);
    console.log('Response:', result);
    
  } catch (error) {
    console.error('Error:', error.message);
  }
}

testApi(); 