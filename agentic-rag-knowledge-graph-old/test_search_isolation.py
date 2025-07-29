import asyncio
import httpx
import time
import json

async def test_search_endpoints():
    """Test each search endpoint independently."""
    
    print("=" * 60)
    print("Testing Search Endpoints Independently")
    print("=" * 60)
    
    # Test 1: Vector Search
    print("\n1. Testing Vector Search...")
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "http://localhost:8058/search/vector",
                json={"query": "strategic planning principles", "k": 3}
            )
            duration = time.time() - start
            print(f"   Status: {response.status_code}")
            print(f"   Duration: {duration:.2f}s")
            if response.status_code == 200:
                data = response.json()
                print(f"   Results: {data.get('total_results', 0)} chunks found")
                print(f"   Query time: {data.get('query_time_ms', 0)/1000:.2f}s")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   Exception: {type(e).__name__}: {str(e)}")
    
    # Test 2: Graph Search
    print("\n2. Testing Graph Search...")
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "http://localhost:8058/search/graph",
                json={"query": "strategic planning"}
            )
            duration = time.time() - start
            print(f"   Status: {response.status_code}")
            print(f"   Duration: {duration:.2f}s")
            if response.status_code == 200:
                data = response.json()
                print(f"   Results: {data.get('total_results', 0)} graph results")
                print(f"   Query time: {data.get('query_time_ms', 0)/1000:.2f}s")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   Exception: {type(e).__name__}: {str(e)}")
    
    # Test 3: Hybrid Search
    print("\n3. Testing Hybrid Search...")
    start = time.time()
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "http://localhost:8058/search/hybrid",
                json={"query": "competitive advantage", "k": 5, "text_weight": 0.3}
            )
            duration = time.time() - start
            print(f"   Status: {response.status_code}")
            print(f"   Duration: {duration:.2f}s")
            if response.status_code == 200:
                data = response.json()
                print(f"   Results: {data.get('total_results', 0)} results")
                print(f"   Query time: {data.get('query_time_ms', 0)/1000:.2f}s")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   Exception: {type(e).__name__}: {str(e)}")
    
    # Test 4: Documents listing
    print("\n4. Testing Documents Endpoint...")
    start = time.time()
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get("http://localhost:8058/documents")
            duration = time.time() - start
            print(f"   Status: {response.status_code}")
            print(f"   Duration: {duration:.2f}s")
            if response.status_code == 200:
                docs = response.json()
                print(f"   Documents: {len(docs)} found")
                if docs:
                    print(f"   First doc: {docs[0].get('title', 'Unknown')}")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   Exception: {type(e).__name__}: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_search_endpoints())
