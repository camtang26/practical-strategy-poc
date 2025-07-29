#!/usr/bin/env python3
import asyncio
import httpx
import json
import time
from typing import Dict, List, Any

TEST_QUERIES = [
    {
        "id": "simple_factual",
        "query": "What is the definition of strategic thinking?",
        "expected_tool": "vector_search",
        "complexity": "simple"
    },
    {
        "id": "relationship",
        "query": "How does strategic planning relate to organizational culture and leadership?",
        "expected_tool": "graph_search",
        "complexity": "relationship"
    },
    {
        "id": "complex_conceptual",
        "query": "Explain the process of developing a comprehensive strategic plan for a mid-size company facing digital transformation",
        "expected_tool": "hybrid_search",
        "complexity": "complex"
    },
    {
        "id": "implementation",
        "query": "What are the specific steps and tools needed to implement strategic planning in a startup?",
        "expected_tool": "multiple_tools",
        "complexity": "implementation"
    },
    {
        "id": "comparison",
        "query": "Compare strategic planning approaches for established corporations versus agile startups",
        "expected_tool": "hybrid_search",
        "complexity": "comparison"
    }
]

async def test_query(client: httpx.AsyncClient, query_info: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single query and capture results."""
    print(f"\nTesting: {query_info['id']}")
    print(f"Query: {query_info['query']}")
    
    start_time = time.time()
    tools_used = []
    response_content = []
    
    async with client.stream(
        "POST",
        "http://localhost:8000/chat/stream",
        json={
            "message": query_info["query"],
            "session_id": f"test-gemini-{query_info['id']}-{int(time.time())}"
        },
        timeout=60.0
    ) as response:
        async for line in response.aiter_lines():
            if line.strip() and line.startswith('data: '):
                if line == 'data: [DONE]':
                    break
                try:
                    data = json.loads(line[6:])
                    if data.get("type") == "tools":
                        for tool in data.get("tools", []):
                            tools_used.append(tool["tool_name"])
                            print(f"  Tool used: {tool['tool_name']}")
                    elif data.get("type") == "text":
                        response_content.append(data.get("content", ""))
                except Exception as e:
                    print(f"  Parse error: {e}")
    
    end_time = time.time()
    response_time = end_time - start_time
    
    result = {
        "query_id": query_info["id"],
        "query": query_info["query"],
        "expected_tool": query_info["expected_tool"],
        "actual_tools": tools_used,
        "response_time": response_time,
        "response_preview": "".join(response_content)[:500] + "..." if response_content else "No response",
        "tool_match": query_info["expected_tool"] in tools_used or (query_info["expected_tool"] == "multiple_tools" and len(tools_used) > 1)
    }
    
    print(f"  Response time: {response_time:.1f}s")
    print(f"  Tool match: {result['tool_match']}")
    
    return result

async def main():
    """Run all tests and generate report."""
    async with httpx.AsyncClient() as client:
        results = []
        for query_info in TEST_QUERIES:
            result = await test_query(client, query_info)
            results.append(result)
            await asyncio.sleep(2)  # Avoid rate limiting
        
        # Generate report
        print("\n\n=== GEMINI 2.5 PRO EVALUATION SUMMARY ===\n")
        
        print("Tool Selection Accuracy:")
        correct_tools = sum(1 for r in results if r["tool_match"])
        print(f"  {correct_tools}/{len(results)} queries used expected tools ({correct_tools/len(results)*100:.0f}%)")
        
        print("\nResponse Times:")
        avg_time = sum(r["response_time"] for r in results) / len(results)
        print(f"  Average: {avg_time:.1f}s")
        print(f"  Range: {min(r['response_time'] for r in results):.1f}s - {max(r['response_time'] for r in results):.1f}s")
        
        print("\nDetailed Results:")
        for r in results:
            print(f"\n{r['query_id']}:")
            print(f"  Expected: {r['expected_tool']}")
            print(f"  Actual: {r['actual_tools']}")
            print(f"  Match: {'✓' if r['tool_match'] else '✗'}")
            print(f"  Time: {r['response_time']:.1f}s")
            print(f"  Response preview: {r['response_preview'][:200]}...")
        
        # Save results
        with open("test_results/gemini_evaluation.json", "w") as f:
            json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
