import asyncio
import httpx
import uuid
import time
import json
from datetime import datetime

async def test_query(query_type: str, query: str, session_id: str):
    """Test a single query and return detailed metrics."""
    url = "http://localhost:8058/chat"
    
    print(f"\n{'='*60}")
    print(f"Testing {query_type} Query")
    print(f"{'='*60}")
    print(f"Query: {query}")
    print(f"Session: {session_id}")
    
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
            
            end_time = time.time()
            duration = end_time - start_time
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"\n✅ SUCCESS")
                print(f"Duration: {duration:.2f} seconds")
                print(f"Response length: {len(result.get('response', ''))} characters")
                print(f"Sources used: {len(result.get('sources', []))} sources")
                
                # Print first 300 chars of response
                response_text = result.get('response', '')
                print(f"\nResponse preview:")
                print(f"{response_text[:300]}..." if len(response_text) > 300 else response_text)
                
                # Print tool usage if available
                if 'metadata' in result and 'tool_calls' in result['metadata']:
                    print(f"\nTools used: {result['metadata']['tool_calls']}")
                
                return True, duration, result
            else:
                print(f"\n❌ FAILED")
                print(f"Status Code: {response.status_code}")
                print(f"Error: {response.text}")
                return False, duration, None
                
        except httpx.TimeoutException:
            duration = time.time() - start_time
            print(f"\n❌ TIMEOUT (>{duration:.0f}s)")
            return False, duration, None
        except Exception as e:
            duration = time.time() - start_time
            print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
            return False, duration, None

async def check_tool_usage():
    """Check the API logs for tool usage patterns."""
    print("\n" + "="*60)
    print("Analyzing Tool Usage from Logs")
    print("="*60)
    
    # Get last 500 lines of log
    import subprocess
    result = subprocess.run(
        ["tail", "-n", "500", "api.log"],
        capture_output=True,
        text=True
    )
    
    # Count tool calls
    tool_counts = {}
    for line in result.stdout.split('\n'):
        if 'tool_name=' in line:
            # Extract tool name
            start = line.find('tool_name=') + 10
            end = line.find('\n', start) if '\n' in line[start:] else len(line)
            tool_name = line[start:end].strip()
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
    
    print("\nTool usage in recent queries:")
    for tool, count in sorted(tool_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {tool}: {count} calls")

async def run_comprehensive_tests():
    """Run a comprehensive test suite."""
    print(f"\n{'='*60}")
    print(f"COMPREHENSIVE BACKEND TEST SUITE")
    print(f"Started at: {datetime.now()}")
    print(f"{'='*60}")
    
    # First check system health
    async with httpx.AsyncClient() as client:
        health = await client.get("http://localhost:8058/health")
        print(f"\nSystem Health: {health.json()}")
    
    # Test queries of varying complexity
    test_cases = [
        # Simple queries
        ("SIMPLE-1", "What is Practical Strategy?"),
        ("SIMPLE-2", "Define strategic thinking"),
        
        # Medium queries
        ("MEDIUM-1", "What are the six steps of the Practical Strategy methodology?"),
        ("MEDIUM-2", "How do I create a balanced scorecard?"),
        ("MEDIUM-3", "Explain the difference between strategy and tactics"),
        
        # Complex queries
        ("COMPLEX-1", "How do I develop a comprehensive strategic plan for my organization using the Practical Strategy framework, including the key principles and common pitfalls to avoid?"),
        ("COMPLEX-2", "What are the relationships between the Four Perspectives in the Balanced Scorecard and how do they create competitive advantage?"),
        ("COMPLEX-3", "Can you walk me through the complete process of implementing Practical Strategy in a mid-sized company, including examples from the Hunger Busters case study?")
    ]
    
    results = []
    session_id = str(uuid.uuid4())
    
    for query_type, query in test_cases:
        success, duration, result = await test_query(query_type, query, session_id)
        results.append((query_type, success, duration))
        
        # Small delay between queries
        await asyncio.sleep(2)
    
    # Summary statistics
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    successful = sum(1 for _, success, _ in results if success)
    total_time = sum(duration for _, _, duration in results)
    
    print(f"\nTotal queries: {len(results)}")
    print(f"Successful: {successful}/{len(results)} ({successful/len(results)*100:.1f}%)")
    print(f"Total time: {total_time:.2f}s")
    print(f"Average response time: {total_time/len(results):.2f}s")
    
    print("\nBreakdown by query type:")
    for query_type, success, duration in results:
        status = "✅" if success else "❌"
        print(f"  {query_type}: {status} {duration:.2f}s")
    
    # Analyze tool usage
    await check_tool_usage()
    
    # Final verdict
    print("\n" + "="*60)
    if successful == len(results):
        print("✅ BACKEND IS FULLY FUNCTIONAL!")
        print("All queries completed successfully with reasonable response times.")
    elif successful >= len(results) * 0.7:
        print("⚠️  BACKEND IS MOSTLY FUNCTIONAL")
        print(f"Some queries failed or timed out ({len(results) - successful} failures)")
    else:
        print("❌ BACKEND HAS SIGNIFICANT ISSUES")
        print(f"Many queries failed ({len(results) - successful} failures)")

if __name__ == "__main__":
    asyncio.run(run_comprehensive_tests())
