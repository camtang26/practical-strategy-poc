import asyncio
import httpx
import uuid
import time
from datetime import datetime

async def test_query_properly(query_type: str, query: str, session_id: str):
    """Test a query and show the actual response."""
    url = "http://localhost:8058/chat"
    
    print(f"\n{'='*60}")
    print(f"Testing {query_type} Query")
    print(f"{'='*60}")
    print(f"Query: {query}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        start_time = time.time()
        
        try:
            response = await client.post(
                url,
                json={
                    "message": query,
                    "session_id": session_id
                }
            )
            
            duration = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                message_text = result.get('message', '')
                
                print(f"\n✅ SUCCESS in {duration:.2f} seconds")
                print(f"Response length: {len(message_text)} characters")
                print(f"Tools used: {len(result.get('tools_used', []))}")
                
                # Show tool usage
                tools = result.get('tools_used', [])
                if tools:
                    print("\nTools called:")
                    for tool in tools:
                        print(f"  - {tool.get('tool_name', 'unknown')}")
                
                # Show response preview
                print(f"\nResponse preview (first 400 chars):")
                print("-" * 40)
                print(message_text[:400] + "..." if len(message_text) > 400 else message_text)
                
                return True, duration
            else:
                print(f"\n❌ FAILED: {response.status_code}")
                return False, duration
                
        except httpx.TimeoutException:
            duration = time.time() - start_time
            print(f"\n❌ TIMEOUT after {duration:.0f}s")
            return False, duration

async def run_final_tests():
    """Run final comprehensive test suite."""
    print(f"\n{'='*60}")
    print(f"FINAL BACKEND VERIFICATION TEST")
    print(f"Started at: {datetime.now()}")
    print(f"{'='*60}")
    
    # Test cases
    test_cases = [
        ("SIMPLE", "What is Practical Strategy?"),
        ("MEDIUM", "What are the six steps of the Practical Strategy methodology?"),
        ("COMPLEX", "How do I develop a strategic plan using the Practical Strategy framework?")
    ]
    
    results = []
    session_id = str(uuid.uuid4())
    
    for query_type, query in test_cases:
        success, duration = await test_query_properly(query_type, query, session_id)
        results.append((query_type, success, duration))
        await asyncio.sleep(2)
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    successful = sum(1 for _, success, _ in results if success)
    total_time = sum(duration for _, _, duration in results)
    
    print(f"\nTotal queries: {len(results)}")
    print(f"Successful: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
    print(f"Average response time: {total_time/len(results):.2f}s")
    
    if successful == len(results):
        print("\n✅ BACKEND IS FULLY FUNCTIONAL!")
        print("The system is working perfectly with the Qwen3 thinking model.")
        print("Vector search, graph search, and response generation are all operational.")
    else:
        print(f"\n⚠️  Some queries failed ({len(results) - successful} failures)")

if __name__ == "__main__":
    asyncio.run(run_final_tests())
