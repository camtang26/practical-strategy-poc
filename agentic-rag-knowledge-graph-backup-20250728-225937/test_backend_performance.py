import asyncio
import httpx
import time
import json
from datetime import datetime

async def test_chat_query(query: str):
    """Test a single chat query and measure performance."""
    url = "http://localhost:8058/chat"
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        start_time = time.time()
        
        try:
            response = await client.post(
                url,
                json={
                    "message": query,
                    "session_id": "test-session-" + str(int(time.time()))
                }
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ Query: '{query[:50]}...'")
                print(f"   Duration: {duration:.2f}s")
                print(f"   Response length: {len(result.get('response', ''))} chars")
                print(f"   Sources: {len(result.get('sources', []))} sources")
                print(f"   First 200 chars: {result.get('response', '')[:200]}...")
                return True, duration
            else:
                print(f"\n❌ Query failed: '{query[:50]}...'")
                print(f"   Status: {response.status_code}")
                print(f"   Error: {response.text}")
                return False, duration
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"\n❌ Query exception: '{query[:50]}...'")
            print(f"   Error: {str(e)}")
            return False, duration

async def run_performance_tests():
    """Run a series of test queries."""
    test_queries = [
        "What are the key principles of strategic thinking?",
        "How do I develop a strategic plan for my organization?",
        "What is the difference between strategy and tactics?",
        "Can you explain the concept of competitive advantage?",
        "What are the common pitfalls in strategic planning?"
    ]
    
    print("=" * 60)
    print(f"Backend Performance Test - {datetime.now()}")
    print("=" * 60)
    
    # First, test basic endpoints
    async with httpx.AsyncClient() as client:
        # Test health
        health_resp = await client.get("http://localhost:8058/health")
        print(f"\nHealth check: {health_resp.json()}")
        
        # Test welcome
        welcome_resp = await client.get("http://localhost:8058/")
        print(f"\nWelcome message: {welcome_resp.json()}")
    
    # Run chat queries
    print("\n" + "=" * 60)
    print("Running chat queries...")
    print("=" * 60)
    
    results = []
    for query in test_queries:
        success, duration = await test_chat_query(query)
        results.append((success, duration))
        await asyncio.sleep(1)  # Small delay between queries
    
    # Summary
    print("\n" + "=" * 60)
    print("Performance Summary")
    print("=" * 60)
    
    successful = sum(1 for s, _ in results if s)
    total_duration = sum(d for _, d in results)
    avg_duration = total_duration / len(results) if results else 0
    
    print(f"\nTotal queries: {len(results)}")
    print(f"Successful: {successful}/{len(results)}")
    print(f"Total time: {total_duration:.2f}s")
    print(f"Average query time: {avg_duration:.2f}s")
    
    if successful < len(results):
        print("\n⚠️  Some queries failed - backend may have issues")
    else:
        print("\n✅ All queries successful - backend is working properly")

if __name__ == "__main__":
    asyncio.run(run_performance_tests())
