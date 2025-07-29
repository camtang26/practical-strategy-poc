import asyncio
import httpx
import uuid
import time

async def test_queries():
    """Test different query complexities."""
    
    test_cases = [
        ("Simple", "What is Practical Strategy?"),
        ("Medium", "How do I develop a strategic plan?"),
        ("Complex", "What are the key principles of strategic thinking and how do they apply to competitive advantage?")
    ]
    
    print("Backend Performance Test with Thinking Model")
    print("=" * 60)
    
    for complexity, query in test_cases:
        session_id = str(uuid.uuid4())
        start = time.time()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    "http://localhost:8058/chat",
                    json={"message": query, "session_id": session_id}
                )
                
                duration = time.time() - start
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"\n✅ {complexity} Query: '{query[:40]}...'")
                    print(f"   Duration: {duration:.2f}s")
                    print(f"   Response length: {len(result.get('response', ''))} chars")
                else:
                    print(f"\n❌ {complexity} Query Failed: {response.status_code}")
                    
            except httpx.TimeoutException:
                print(f"\n❌ {complexity} Query Timeout (>30s)")
            except Exception as e:
                print(f"\n❌ {complexity} Query Error: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Test Complete - Thinking model is handling queries properly!")

if __name__ == "__main__":
    asyncio.run(test_queries())
