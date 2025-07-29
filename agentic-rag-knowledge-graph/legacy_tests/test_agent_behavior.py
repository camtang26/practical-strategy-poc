import asyncio
from agent.agent import rag_agent, AgentDependencies
import logging

logging.basicConfig(level=logging.DEBUG)

async def test_prompt_visibility():
    # Test 1: See what the agent actually receives
    deps = AgentDependencies(
        session_id="test-123",
        search_type="graph"
    )
    
    # Simple query that should trigger graph_search
    result = await rag_agent.run(
        "What facts do you know about strategic management? Remember to check ctx.deps.search_type first!",
        deps=deps
    )
    
    print(f"\nResult: {result.output}")
    print(f"\nMessages exchanged:")
    for msg in result.messages():
        print(f"- {msg}")

asyncio.run(test_prompt_visibility())
