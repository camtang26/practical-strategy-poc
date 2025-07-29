import asyncio
import httpx
import uuid
import time

async def test_simple_chat():
    """Test a simple chat query with proper error handling."""
    url = "http://localhost:8058/chat"
    session_id = str(uuid.uuid4())
    
    print(f"Testing chat with session ID: {session_id}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        start_time = time.time()
        
        try:
            response = await client.post(
                url,
                json={
                    "message": "What is Practical Strategy in one sentence?",
                    "session_id": session_id
                }
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\nStatus Code: {response.status_code}")
            print(f"Duration: {duration:.2f} seconds")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Response: {result.get('response', '')[:200]}...")
                print(f"Sources: {len(result.get('sources', []))}")
            else:
                print(f"Error: {response.text}")
                
        except httpx.TimeoutException:
            print(f"\n❌ Request timed out after 30 seconds")
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_simple_chat())
