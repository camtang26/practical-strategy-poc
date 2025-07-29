#!/usr/bin/env python3
import asyncio
import httpx
import json
import time
from datetime import datetime

async def test_qwen_instruct():
    """Test Qwen instruct model."""
    
    print(f"\n{'='*80}")
    print(f"Testing: qwen3-235b-a22b-instruct-2507")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"{'='*80}\n")
    
    test_queries = [
        "What is strategic planning?",
        "How does strategic planning relate to organizational culture?",
        "What are the steps to implement strategic planning in a startup?"
    ]
    
    async with httpx.AsyncClient() as client:
        for query in test_queries:
            print(f"\nQuery: {query}")
            start_time = time.time()
            first_token_time = None
            tools_used = []
            response_started = False
            response_text = []
            
            try:
                async with client.stream(
                    "POST",
                    "http://localhost:8000/chat/stream",
                    json={
                        "message": query,
                        "session_id": f"550e8400-e29b-41d4-a716-44665544{str(int(time.time()))[-4:]}"
                    },
                    timeout=120.0
                ) as response:
                    async for line in response.aiter_lines():
                        if line.strip() and line.startswith('data: '):
                            try:
                                data = json.loads(line[6:])
                                
                                # Track first token
                                if data.get("type") == "text" and not first_token_time:
                                    first_token_time = time.time()
                                    print(f"  First token: {first_token_time - start_time:.2f}s")
                                    response_started = True
                                
                                # Track tools
                                if data.get("type") == "tools":
                                    for tool in data.get("tools", []):
                                        tool_name = tool["tool_name"]
                                        tools_used.append(tool_name)
                                        timing = "AFTER response" if response_started else "BEFORE response"
                                        print(f"  Tool: {tool_name} ({timing})")
                                
                                # Collect response
                                if data.get("type") == "text":
                                    response_text.append(data.get("content", ""))
                                    
                            except:
                                pass
                                
            except Exception as e:
                print(f"  Error: {e}")
            
            end_time = time.time()
            total_time = end_time - start_time
            response_length = len("".join(response_text))
            
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Tools used: {tools_used}")
            print(f"  Response length: {response_length} chars")
            print(f"  First 200 chars: {(''.join(response_text))[:200]}...")
            
            await asyncio.sleep(3)  # Avoid rate limiting

if __name__ == "__main__":
    asyncio.run(test_qwen_instruct())
