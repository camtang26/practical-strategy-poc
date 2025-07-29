import asyncio
import httpx
import uuid
import json
import time

async def test_query(message: str, expected_tool: str):
    """Test a specific query and check which tool is selected."""
    url = "http://localhost:8000/chat"
    session_id = str(uuid.uuid4())
    
    payload = {
        "message": message,
        "session_id": session_id
    }
    
    print(f"\n{'='*60}")
    print(f"Expected tool: {expected_tool}")
    print(f"Query: {message}")
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                tools = data.get('tools_used', [])
                tools_used = [t['tool_name'] for t in tools]
                
                print(f"\n✅ Success in {elapsed:.2f}s")
                print(f"Tools used: {tools_used}")
                
                # Check if expected tool was used
                if expected_tool in tools_used:
                    print(f"✅ CORRECT: {expected_tool} was used as expected")
                else:
                    print(f"❌ UNEXPECTED: Expected {expected_tool}, but got {tools_used}")
                
                # Show first 150 chars of response
                response_preview = data.get('message', '')[:150]
                print(f"\nResponse preview: {response_preview}...")
                
            else:
                print(f"\n❌ Error {response.status_code}: {response.text}")
                
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ Exception after {elapsed:.2f}s: {e}")

async def main():
    """Test targeted queries for specific tool selection."""
    
    # VECTOR SEARCH - Simple definitional/content queries
    vector_queries = [
        ("What are the exact words used to define 'strategy' in the Practical Strategy guide?", "vector_search"),
        ("List the 6 myths of strategy mentioned in Chapter 2", "vector_search"),
        ("What specific example is given for a global technology company's strategy levels?", "vector_search"),
        ("Quote the Chinese proverb mentioned in the introduction", "vector_search"),
        ("What does Section 1 of the Project Plan template contain?", "vector_search")
    ]
    
    # GRAPH SEARCH - Relationship/connection queries
    graph_queries = [
        ("Show me all entities connected to 'CEO' in the knowledge graph", "graph_search"),
        ("What entities have a RELATES_TO relationship with 'Strategic Planning'?", "graph_search"),
        ("Find all relationships between 'Financial Perspective' and other perspectives", "graph_search"),
        ("Which entities are most connected in the strategic framework?", "graph_search"),
        ("Map the connections between 'Balanced Scorecard' and other strategic concepts", "graph_search")
    ]
    
    # HYBRID SEARCH - Complex queries needing both content and relationships
    hybrid_queries = [
        ("Explain how the Hunger Busters case study demonstrates the relationships between strategy development and implementation across all four perspectives", "hybrid_search"),
        ("How does cause-and-effect thinking connect strategic objectives to measures, and provide specific examples from the guide", "hybrid_search"),
        ("Analyze the complete strategic planning process including all relationships between stages, stakeholders, and expected outcomes", "hybrid_search"),
        ("Compare traditional vs contemporary strategy approaches and show how they impact organizational relationships", "hybrid_search"),
        ("Design a strategy implementation plan showing how all six stages interconnect with specific examples", "hybrid_search")
    ]
    
    print("Testing VECTOR SEARCH queries...")
    for query, expected in vector_queries:
        await test_query(query, expected)
        await asyncio.sleep(2)
    
    print("\n\nTesting GRAPH SEARCH queries...")
    for query, expected in graph_queries:
        await test_query(query, expected)
        await asyncio.sleep(2)
    
    print("\n\nTesting HYBRID SEARCH queries...")
    for query, expected in hybrid_queries:
        await test_query(query, expected)
        await asyncio.sleep(2)

if __name__ == "__main__":
    print("Testing targeted tool selection with specific query types...")
    asyncio.run(main())
