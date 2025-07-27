"""
Analyze the dual LLM call pattern in pydantic-ai by intercepting the actual calls.
"""

import asyncio
import json
from typing import Any, Dict, List
from datetime import datetime

# Monkey patch to intercept OpenAI calls
original_create = None
call_count = 0
calls_log = []

def log_llm_call(messages: List[Dict], tools: List[Dict] = None, **kwargs):
    """Log details of each LLM call."""
    global call_count
    call_count += 1
    
    call_info = {
        'call_number': call_count,
        'timestamp': datetime.now().isoformat(),
        'messages': messages,
        'tools_provided': len(tools) if tools else 0,
        'has_tool_calls': any(msg.get('tool_calls') for msg in messages),
        'has_tool_responses': any(msg.get('role') == 'tool' for msg in messages)
    }
    
    calls_log.append(call_info)
    
    print(f"\n{'='*60}")
    print(f"LLM CALL #{call_count}")
    print(f"{'='*60}")
    print(f"Timestamp: {call_info['timestamp']}")
    print(f"Tools provided: {call_info['tools_provided']}")
    print(f"Has tool calls: {call_info['has_tool_calls']}")
    print(f"Has tool responses: {call_info['has_tool_responses']}")
    print(f"\nMessages ({len(messages)} total):")
    
    for i, msg in enumerate(messages):
        print(f"\n  Message {i+1}:")
        print(f"    Role: {msg.get('role')}")
        
        if msg.get('role') == 'system':
            print(f"    Content: {msg.get('content', '')[:200]}...")
        elif msg.get('role') == 'user':
            print(f"    Content: {msg.get('content', '')}")
        elif msg.get('role') == 'assistant':
            content = msg.get('content', '')
            if content:
                print(f"    Content: {content[:200]}...")
            if msg.get('tool_calls'):
                print(f"    Tool calls: {[tc['function']['name'] for tc in msg['tool_calls']]}")
        elif msg.get('role') == 'tool':
            print(f"    Tool call ID: {msg.get('tool_call_id')}")
            print(f"    Content length: {len(msg.get('content', ''))}")
    
    if tools:
        print(f"\n  Tools available: {[t['function']['name'] for t in tools[:5]]}...")

async def analyze_agent_pattern():
    """Run agent and analyze the LLM call pattern."""
    
    # Import after defining the monkey patch function
    import openai
    from openai import AsyncOpenAI
    
    # Store original
    global original_create
    original_create = AsyncOpenAI.chat.completions.create
    
    # Create wrapper
    async def create_wrapper(self, **kwargs):
        messages = kwargs.get('messages', [])
        tools = kwargs.get('tools', [])
        
        # Log the call
        log_llm_call(messages, tools)
        
        # Call original
        result = await original_create(self, **kwargs)
        return result
    
    # Apply monkey patch
    AsyncOpenAI.chat.completions.create = create_wrapper
    
    # Now import and use the agent
    from agent.agent import rag_agent, AgentDependencies
    
    # Test query
    query = "What are the six stages of practical strategy?"
    deps = AgentDependencies(
        session_id="analysis-test",
        user_id="analyzer"
    )
    
    print("\n" + "="*80)
    print("ANALYZING PYDANTIC-AI LLM CALL PATTERN")
    print("="*80)
    
    # Run the agent
    result = await rag_agent.run(query, deps=deps)
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nTotal LLM calls made: {call_count}")
    print(f"Final response length: {len(result.output)}")
    
    # Analyze the pattern
    print("\n" + "="*80)
    print("CALL PATTERN ANALYSIS")
    print("="*80)
    
    for i, call in enumerate(calls_log):
        print(f"\nCall {i+1}:")
        print(f"  - Has tools: {'Yes' if call['tools_provided'] > 0 else 'No'}")
        print(f"  - Has tool responses: {'Yes' if call['has_tool_responses'] else 'No'}")
        print(f"  - Purpose: ", end="")
        
        if i == 0 and call['tools_provided'] > 0:
            print("Tool selection (deciding which tools to use)")
        elif call['has_tool_responses']:
            print("Response generation (using tool results)")
        else:
            print("Unknown")

if __name__ == "__main__":
    asyncio.run(analyze_agent_pattern())
