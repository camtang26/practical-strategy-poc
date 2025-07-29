"""
Trace pydantic-ai agent execution to understand the dual LLM call pattern.
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import Any, Dict

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable debug logging for pydantic-ai
logging.getLogger('pydantic_ai').setLevel(logging.DEBUG)
logging.getLogger('agent').setLevel(logging.DEBUG)

# Import after logging is configured
from agent.agent import rag_agent, AgentDependencies

class CallTracer:
    """Trace LLM calls and tool usage."""
    
    def __init__(self):
        self.events = []
        self.original_run = None
        self.original_iter = None
        
    def log_event(self, event_type: str, data: Dict[str, Any]):
        """Log an event with timestamp."""
        self.events.append({
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data
        })
        print(f"\n[{event_type}] {json.dumps(data, indent=2)}")

async def trace_agent_execution():
    """Run agent with tracing to understand execution flow."""
    
    tracer = CallTracer()
    
    # Simple test query
    query = "What is practical strategy?"
    deps = AgentDependencies(
        session_id="trace-test",
        user_id="tracer"
    )
    
    print(f"\n{'='*60}")
    print(f"Testing query: {query}")
    print(f"{'='*60}")
    
    try:
        # Trace the run method
        print("\n1. Calling rag_agent.run()...")
        result = await rag_agent.run(query, deps=deps)
        
        print("\n2. Result obtained:")
        print(f"   - Type: {type(result)}")
        print(f"   - Data: {result.data[:200]}..." if hasattr(result, 'data') else "No data attribute")
        
        # Check for message history
        if hasattr(result, 'message_history'):
            print(f"\n3. Message History:")
            for i, msg in enumerate(result.message_history):
                print(f"   Message {i+1}:")
                print(f"   - Type: {type(msg)}")
                print(f"   - Content: {str(msg)[:100]}...")
        
        # Check for tool calls
        if hasattr(result, 'tool_calls'):
            print(f"\n4. Tool Calls: {result.tool_calls}")
            
        # Check result attributes
        print(f"\n5. Result attributes: {dir(result)}")
        
    except Exception as e:
        print(f"\nError during execution: {e}")
        import traceback
        traceback.print_exc()

async def trace_streaming_execution():
    """Trace streaming execution to see the flow."""
    
    query = "Explain the six stages methodology"
    deps = AgentDependencies(
        session_id="trace-stream",
        user_id="tracer"
    )
    
    print(f"\n{'='*60}")
    print(f"Testing streaming for: {query}")
    print(f"{'='*60}")
    
    try:
        print("\n1. Starting rag_agent.iter()...")
        
        async with rag_agent.iter(query, deps=deps) as run:
            node_count = 0
            
            async for node in run:
                node_count += 1
                print(f"\n   Node {node_count}:")
                print(f"   - Type: {type(node)}")
                print(f"   - Is model request: {rag_agent.is_model_request_node(node)}")
                
                if hasattr(node, '__dict__'):
                    print(f"   - Attributes: {list(node.__dict__.keys())}")
                
                # If it's a model request node, try to get more info
                if rag_agent.is_model_request_node(node):
                    print("   - This is a MODEL REQUEST node")
                    
        print(f"\n2. Total nodes processed: {node_count}")
        
        # Get final result
        if hasattr(run, 'result'):
            print(f"\n3. Final result type: {type(run.result)}")
            
    except Exception as e:
        print(f"\nError during streaming: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """Run both trace tests."""
    
    print("\n" + "="*80)
    print("TRACING PYDANTIC-AI AGENT EXECUTION")
    print("="*80)
    
    # Test 1: Regular run
    await trace_agent_execution()
    
    # Test 2: Streaming run
    await trace_streaming_execution()
    
    print("\n" + "="*80)
    print("TRACE COMPLETE")
    print("="*80)

if __name__ == "__main__":
    asyncio.run(main())
