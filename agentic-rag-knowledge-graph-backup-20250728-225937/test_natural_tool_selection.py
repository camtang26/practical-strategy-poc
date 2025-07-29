import asyncio
import httpx
import uuid
import json
import time

async def test_query_without_search_type(message: str):
    """Test how agent naturally selects tools without constraints."""
    url = "http://localhost:8000/chat"
    session_id = str(uuid.uuid4())
    
    payload = {
        "message": message,
        "session_id": session_id
        # Note: No search_type specified
    }
    
    print(f"\n{'='*60}")
    print(f"Query: {message}")
    print(f"Session ID: {session_id}")
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                tools = data.get('tools_used', [])
                
                print(f"\n✅ Success in {elapsed:.2f}s")
                print(f"Tools used: {[t['tool_name'] for t in tools]}")
                print(f"Response length: {len(data.get('message', ''))}")
                
                # Show first 200 chars of response
                response_preview = data.get('message', '')[:200]
                print(f"\nResponse preview:\n{response_preview}...")
                
            else:
                print(f"\n❌ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ Exception after {elapsed:.2f}s: {e}")

async def main():
    """Test natural tool selection with various queries."""
    test_cases = [
        # Should naturally use vector search
        "What is practical strategy?",
        "Explain the six stages of the practical strategy methodology",
        "What is the Hunger Busters case study about?",
        
        # Should naturally use graph search  
        "How do strategic objectives relate to measures?",
        "What are the relationships between the Four Perspectives?",
        
        # Could use either or hybrid
        "How do I implement strategic planning in my organization?",
        "What role does cause-and-effect thinking play in strategy development?"
    ]
    
    for message in test_cases:
        await test_query_without_search_type(message)
        await asyncio.sleep(2)  # Brief pause between requests

if __name__ == "__main__":
    print("Testing natural tool selection without search_type constraints...")
    asyncio.run(main())
