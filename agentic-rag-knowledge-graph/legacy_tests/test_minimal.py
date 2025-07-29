import asyncio
import httpx
import uuid

async def test_minimal():
    """Test with minimal query to avoid token limits."""
    
    # First, test vector search alone
    print("1. Testing Vector Search...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8058/search/vector",
            json={"query": "What is strategy?", "k": 2}  # Only 2 results
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Vector search works: {data['total_results']} results")
        else:
            print(f"❌ Vector search failed: {response.status_code}")
    
    # Now test chat with a very simple query
    print("\n2. Testing Chat with minimal query...")
    session_id = str(uuid.uuid4())
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "http://localhost:8058/chat",
            json={
                "message": "What is strategy in one sentence?",
                "session_id": session_id
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Chat responded")
            print(f"Response length: {len(result.get('response', ''))} chars")
            
            resp_text = result.get('response', '')
            if resp_text:
                print(f"\nActual response: {resp_text}")
            else:
                print("\n⚠️  Still empty response")
                
            # Check metadata
            if 'metadata' in result:
                print(f"\nMetadata: {result['metadata']}")
        else:
            print(f"❌ Chat failed: {response.status_code}")
            print(f"Error: {response.text}")

if __name__ == "__main__":
    asyncio.run(test_minimal())
