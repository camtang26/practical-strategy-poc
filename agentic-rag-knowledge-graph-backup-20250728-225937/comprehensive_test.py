#!/usr/bin/env python3
import asyncio
import httpx
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

TEST_QUERIES = [
    {
        "id": "simple_definition",
        "query": "What is strategic planning?",
        "expected_tools": ["vector_search"],
        "complexity": "simple",
        "expected_behavior": "Should search first, then synthesize"
    },
    {
        "id": "concept_explanation",
        "query": "Explain the concept of strategic thinking and how it differs from operational thinking",
        "expected_tools": ["vector_search", "hybrid_search"],
        "complexity": "conceptual",
        "expected_behavior": "Should search for both concepts and compare"
    },
    {
        "id": "relationship_query",
        "query": "How does strategic planning relate to organizational culture and leadership?",
        "expected_tools": ["graph_search", "hybrid_search"],
        "complexity": "relationship",
        "expected_behavior": "Should explore relationships in knowledge graph"
    },
    {
        "id": "implementation_steps",
        "query": "What are the specific steps to implement strategic planning in a startup?",
        "expected_tools": ["vector_search", "hybrid_search"],
        "complexity": "procedural",
        "expected_behavior": "Should find step-by-step guidance"
    },
    {
        "id": "complex_scenario",
        "query": "Develop a strategic plan for a mid-size retail company transitioning to e-commerce during market disruption",
        "expected_tools": ["hybrid_search", "vector_search", "graph_search"],
        "complexity": "complex",
        "expected_behavior": "Should use multiple search strategies"
    }
]

class TestResult:
    def __init__(self, query_info: Dict[str, Any]):
        self.query_info = query_info
        self.start_time = None
        self.first_token_time = None
        self.end_time = None
        self.tools_used = []
        self.tool_timing = []  # (tool_name, when_called)
        self.response_chunks = []
        self.full_response = ""
        self.error = None
        self.response_started = False
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "query_id": self.query_info["id"],
            "query": self.query_info["query"],
            "expected_tools": self.query_info["expected_tools"],
            "actual_tools": self.tools_used,
            "time_to_first_token": self.first_token_time - self.start_time if self.first_token_time else None,
            "total_time": self.end_time - self.start_time if self.end_time else None,
            "tool_order": "tools_first" if self.tool_timing and self.tool_timing[0][1] == "before_response" else "tools_after",
            "response_length": len(self.full_response),
            "response_preview": self.full_response[:500] + "..." if len(self.full_response) > 500 else self.full_response,
            "error": self.error,
            "tool_match_score": self._calculate_tool_match()
        }
    
    def _calculate_tool_match(self) -> float:
        if not self.query_info["expected_tools"]:
            return 1.0
        expected_set = set(self.query_info["expected_tools"])
        actual_set = set(self.tools_used)
        if not expected_set:
            return 1.0
        intersection = expected_set & actual_set
        return len(intersection) / len(expected_set)

async def test_single_query(client: httpx.AsyncClient, query_info: Dict[str, Any], model_name: str) -> TestResult:
    """Test a single query and capture detailed metrics."""
    result = TestResult(query_info)
    result.start_time = time.time()
    
    print(f"\n{'='*60}")
    print(f"Testing: {query_info['id']} ({model_name})")
    print(f"Query: {query_info['query']}")
    print(f"Expected tools: {query_info['expected_tools']}")
    
    try:
        async with client.stream(
            "POST",
            "http://localhost:8000/chat/stream",
            json={
                "message": query_info["query"],
                "session_id": f"550e8400-e29b-41d4-a716-4466554401{query_info['id'][-2:]}"
            },
            timeout=120.0
        ) as response:
            async for line in response.aiter_lines():
                if line.strip() and line.startswith('data: '):
                    if line == 'data: [DONE]':
                        break
                    
                    try:
                        data = json.loads(line[6:])
                        
                        # Track first token time
                        if data.get("type") == "text" and not result.first_token_time:
                            result.first_token_time = time.time()
                            print(f"  First token: {result.first_token_time - result.start_time:.2f}s")
                            result.response_started = True
                        
                        # Track tool usage
                        if data.get("type") == "tools":
                            for tool in data.get("tools", []):
                                tool_name = tool["tool_name"]
                                result.tools_used.append(tool_name)
                                timing = "after_response" if result.response_started else "before_response"
                                result.tool_timing.append((tool_name, timing))
                                print(f"  Tool used ({timing}): {tool_name}")
                        
                        # Collect response text
                        if data.get("type") == "text":
                            content = data.get("content", "")
                            result.response_chunks.append(content)
                            result.full_response += content
                            
                    except Exception as e:
                        print(f"  Parse error: {e}")
                        
    except Exception as e:
        result.error = str(e)
        print(f"  Error: {e}")
    
    result.end_time = time.time()
    print(f"  Total time: {result.end_time - result.start_time:.2f}s")
    print(f"  Response length: {len(result.full_response)} chars")
    
    return result

async def test_model(model_name: str, model_display_name: str) -> List[TestResult]:
    """Test all queries with a specific model."""
    print(f"\n{'#'*80}")
    print(f"# TESTING: {model_display_name}")
    print(f"# Model: {model_name}")
    print(f"# Time: {datetime.now().isoformat()}")
    print(f"{'#'*80}")
    
    results = []
    async with httpx.AsyncClient() as client:
        for i, query_info in enumerate(TEST_QUERIES):
            result = await test_single_query(client, query_info, model_display_name)
            results.append(result)
            
            # Wait between queries to avoid rate limiting
            if i < len(TEST_QUERIES) - 1:
                await asyncio.sleep(3)
    
    return results

def generate_comparison_report(thinking_results: List[TestResult], instruct_results: List[TestResult]):
    """Generate a detailed comparison report."""
    print(f"\n{'='*80}")
    print("COMPREHENSIVE COMPARISON: QWEN3 THINKING vs INSTRUCT")
    print(f"{'='*80}\n")
    
    # Overall timing comparison
    print("### RESPONSE TIME ANALYSIS ###\n")
    
    thinking_times = [r.to_dict()["time_to_first_token"] for r in thinking_results if r.to_dict()["time_to_first_token"]]
    instruct_times = [r.to_dict()["time_to_first_token"] for r in instruct_results if r.to_dict()["time_to_first_token"]]
    
    if thinking_times:
        print(f"THINKING MODEL - Time to First Token:")
        print(f"  Average: {sum(thinking_times)/len(thinking_times):.2f}s")
        print(f"  Range: {min(thinking_times):.2f}s - {max(thinking_times):.2f}s")
    
    if instruct_times:
        print(f"\nINSTRUCT MODEL - Time to First Token:")
        print(f"  Average: {sum(instruct_times)/len(instruct_times):.2f}s")
        print(f"  Range: {min(instruct_times):.2f}s - {max(instruct_times):.2f}s")
    
    # Tool usage comparison
    print("\n### TOOL USAGE INTELLIGENCE ###\n")
    
    thinking_tool_scores = [r.to_dict()["tool_match_score"] for r in thinking_results]
    instruct_tool_scores = [r.to_dict()["tool_match_score"] for r in instruct_results]
    
    print(f"THINKING MODEL - Tool Selection Accuracy:")
    print(f"  Average match: {sum(thinking_tool_scores)/len(thinking_tool_scores)*100:.1f}%")
    thinking_tools_first = sum(1 for r in thinking_results if r.to_dict()["tool_order"] == "tools_first")
    print(f"  Tools called first: {thinking_tools_first}/{len(thinking_results)}")
    
    print(f"\nINSTRUCT MODEL - Tool Selection Accuracy:")
    print(f"  Average match: {sum(instruct_tool_scores)/len(instruct_tool_scores)*100:.1f}%")
    instruct_tools_first = sum(1 for r in instruct_results if r.to_dict()["tool_order"] == "tools_first")
    print(f"  Tools called first: {instruct_tools_first}/{len(instruct_results)}")
    
    # Query-by-query comparison
    print("\n### DETAILED QUERY COMPARISON ###\n")
    
    for i, query_info in enumerate(TEST_QUERIES):
        print(f"\n{query_info['id'].upper()}:")
        print(f"Query: {query_info['query']}")
        
        thinking = thinking_results[i].to_dict()
        instruct = instruct_results[i].to_dict()
        
        print(f"\nTHINKING MODEL:")
        print(f"  Time to first token: {thinking['time_to_first_token']:.2f}s" if thinking['time_to_first_token'] else "  No response")
        print(f"  Tools: {thinking['actual_tools']}")
        print(f"  Tool timing: {thinking['tool_order']}")
        print(f"  Response length: {thinking['response_length']} chars")
        
        print(f"\nINSTRUCT MODEL:")
        print(f"  Time to first token: {instruct['time_to_first_token']:.2f}s" if instruct['time_to_first_token'] else "  No response")
        print(f"  Tools: {instruct['actual_tools']}")
        print(f"  Tool timing: {instruct['tool_order']}")
        print(f"  Response length: {instruct['response_length']} chars")
        
        # Speed difference
        if thinking['time_to_first_token'] and instruct['time_to_first_token']:
            speedup = thinking['time_to_first_token'] / instruct['time_to_first_token']
            print(f"\nSPEED DIFFERENCE: Instruct is {speedup:.1f}x faster")

async def main():
    """Run complete comparison test."""
    # Test thinking model
    thinking_results = await test_model("qwen3-235b-a22b-thinking-2507", "QWEN3 THINKING MODEL")
    
    # Save thinking results
    with open("test_results/qwen_thinking_results.json", "w") as f:
        json.dump([r.to_dict() for r in thinking_results], f, indent=2)
    
    print("\n\nWaiting 10 seconds before testing instruct model...")
    await asyncio.sleep(10)
    
    # Update to instruct model
    import subprocess
    subprocess.run([
        "sed", "-i", 
        "s/LLM_CHOICE=qwen3-235b-a22b-thinking-2507/LLM_CHOICE=qwen3-235b-a22b-instruct-2507/g",
        ".env"
    ], cwd="/opt/practical-strategy-poc/agentic-rag-knowledge-graph")
    
    # Restart API
    subprocess.run([
        "bash", "-c",
        "kill $(cat api.pid) 2>/dev/null; sleep 3; nohup python3 -m agent.api > api.log 2>&1 & echo $! > api.pid"
    ], cwd="/opt/practical-strategy-poc/agentic-rag-knowledge-graph")
    
    print("Waiting for API restart with instruct model...")
    await asyncio.sleep(15)
    
    # Test instruct model
    instruct_results = await test_model("qwen3-235b-a22b-instruct-2507", "QWEN3 INSTRUCT MODEL")
    
    # Save instruct results
    with open("test_results/qwen_instruct_results.json", "w") as f:
        json.dump([r.to_dict() for r in instruct_results], f, indent=2)
    
    # Generate comparison report
    generate_comparison_report(thinking_results, instruct_results)

if __name__ == "__main__":
    asyncio.run(main())
