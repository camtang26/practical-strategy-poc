import asyncio
from agent.agent import rag_agent, AgentDependencies
import json

async def test_system_prompt():
    deps = AgentDependencies(
        session_id="test-123", 
        search_type="graph"
    )
    
    # Get the messages that would be sent to the LLM
    result = await rag_agent.run("Show me the system prompt", deps=deps)
    
    # Check the actual messages
    messages = result.messages()
    
    print("=== MESSAGES SENT TO LLM ===")
    for i, msg in enumerate(messages):
        print(f"\nMessage {i}:")
        print(f"Type: {type(msg)}")
        print(f"Content: {msg}")
        if hasattr(msg, 'model_dump'):
            print(f"Dump: {json.dumps(msg.model_dump(), indent=2)}")

asyncio.run(test_system_prompt())
