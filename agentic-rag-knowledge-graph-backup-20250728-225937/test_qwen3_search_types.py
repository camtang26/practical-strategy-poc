import asyncio
import httpx
import uuid
import json
import time

async def test_search_type(message: str, search_type: str):
    """Test if Qwen3 respects search_type constraints."""
    url = "http://localhost:8000/chat"
    session_id = str(uuid.uuid4())
    
    payload = {
        "message": message,
        "session_id": session_id,
        "search_type": search_type
    }
    
    print(f"\n{'='*60}")
    print(f"Testing search_type: {search_type}")
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
                metadata = data.get('metadata', {})
                
                print(f"\n✅ Success in {elapsed:.2f}s")
                print(f"Tools used: {[t['tool_name'] for t in tools]}")
                print(f"Metadata search_type: {metadata.get('search_type')}")
                print(f"Response length: {len(data.get('message', ''))}")
                
                # Check if the correct search type was used
                expected_tool = f"{search_type}_search"
                actual_tools = [t['tool_name'] for t in tools]
                
                if expected_tool in actual_tools:
                    print(f"✅ CORRECT: Used {expected_tool} as requested")
                else:
                    print(f"❌ WRONG: Expected {expected_tool}, but used {actual_tools}")
                
            else:
                print(f"\n❌ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ Exception after {elapsed:.2f}s: {e}")

async def main():
    """Test all search types."""
    test_cases = [
        ("What are the key strategic themes?", "vector"),
        ("Tell me about the relationships between CEO and strategic planning", "graph"),
        ("Explain the six stages of practical strategy", "hybrid")
    ]
    
    for message, search_type in test_cases:
        await test_search_type(message, search_type)
        await asyncio.sleep(2)  # Brief pause between requests

if __name__ == "__main__":
    print("Testing Qwen3 search type constraint respect...")
    asyncio.run(main())
