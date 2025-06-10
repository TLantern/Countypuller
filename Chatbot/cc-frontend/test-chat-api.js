const fetch = require('node-fetch');

async function testChatAPI() {
  try {
    console.log('Testing chat API...');
    
    const response = await fetch('http://localhost:3000/api/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message: 'Hello, can you help me find property information?',
        chatHistory: []
      }),
    });

    console.log('Response status:', response.status);
    console.log('Response headers:', Object.fromEntries(response.headers));
    
    if (!response.ok) {
      const errorText = await response.text();
      console.log('Error response:', errorText);
      return;
    }

    const data = await response.json();
    console.log('Response data:', JSON.stringify(data, null, 2));
    
    // Check if response has expected structure
    if (data.message) {
      console.log('✅ Chat API is working - got message:', data.message.substring(0, 100) + '...');
    } else {
      console.log('❌ Chat API response missing message field');
      console.log('Available fields:', Object.keys(data));
    }
    
  } catch (error) {
    console.error('❌ Error testing chat API:', error.message);
  }
}

testChatAPI(); 