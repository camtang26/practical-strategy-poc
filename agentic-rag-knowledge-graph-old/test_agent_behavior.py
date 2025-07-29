import asyncio
import httpx
import uuid
import time

async def test_with_logging():
    """Test chat with detailed logging monitoring."""
    
    # First, clear recent logs
    print("Monitoring agent behavior for complex query...")
    
    session_id = str(uuid.uuid4())
    url = "http://localhost:8058/chat"
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            # Start monitoring logs in background
            import subprocess
            log_process = subprocess.Popen(
                ["tail", "-f", "api.log"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            print(f"\nSending complex query with session: {session_id}")
            start_time = time.time()
            
            response = await client.post(
                url,
                json={
                    "message": "What are the key principles of strategic thinking and how do they apply to competitive advantage?",
                    "session_id": session_id
                }
            )
            
            duration = time.time() - start_time
            print(f"\nResponse received in {duration:.2f}s")
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"Response length: {len(result.get('response', ''))}")
                print(f"Sources: {len(result.get('sources', []))}")
            
            # Kill log monitoring
            log_process.terminate()
            
        except httpx.TimeoutException:
            print(f"\n❌ Request timed out after 15 seconds")
            print("This suggests the agent is getting stuck during tool execution")
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_with_logging())
