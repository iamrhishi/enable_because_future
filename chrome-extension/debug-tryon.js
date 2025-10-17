// Simple debug script to test just the try-on functionality
console.log('🔍 Starting debug test...');

// Test function to simulate try-on API call
async function debugTryOn() {
    console.log('🚀 debugTryOn called');
    
    try {
        // Create a simple test request to see if the API is reachable
        const response = await fetch('http://192.168.178.48:5000/api/tryon', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                test: 'connection'
            })
        });
        
        console.log('📡 API Response status:', response.status);
        console.log('📡 API Response ok:', response.ok);
        
        const text = await response.text();
        console.log('📡 API Response body:', text);
        
    } catch (error) {
        console.error('❌ API Test Error:', error);
    }
}

// Run the test
debugTryOn();