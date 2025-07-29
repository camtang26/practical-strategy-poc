import asyncio
import httpx
import uuid
import time

async def test_simple_query():
    """Quick test to verify backend is working."""
    url = "http://localhost:8058/chat"
    session_id = str(uuid.uuid4())
    
    print(f"Testing backend with session: {session_id}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        start_time = time.time()
        
        response = await client.post(
            url,
            json={
                "message": "What is Practical Strategy in simple terms?",
                "session_id": session_id
            }
        )
        
        duration = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ SUCCESS in {duration:.2f}s")
            print(f"Response length: {len(result.get('response', ''))} chars")
            
            response_text = result.get('response', '')
            if response_text:
                print(f"\nResponse:\n{response_text[:500]}...")
            else:
                print("\n⚠️  Empty response!")
                
            # Check sources
            sources = result.get('sources', [])
            print(f"\nSources used: {len(sources)}")
            if sources:
                for i, source in enumerate(sources[:3]):
                    print(f"  Source {i+1}: {source.get('content', '')[:100]}...")
        else:
            print(f"\n❌ FAILED: {response.status_code}")
            print(f"Error: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_simple_query())
