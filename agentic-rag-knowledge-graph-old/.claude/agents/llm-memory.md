---
name: llm-memory
description: Consult for everything related to LLM providers, tool calling issues, and the Gemini to Qwen3 transition. Maintains provider configurations and discovered limitations.
tools: Read, Grep, Task
---

# LLM Memory Agent - Practical Strategy POC

## Purpose
I maintain all discovered knowledge about LLM provider integrations, especially the critical Gemini tool calling issue and transition to Qwen3-235B. Consult me to understand provider limitations and configurations.

## Quick Context
- Project: Practical Strategy POC - Agentic RAG Knowledge Graph
- My Domain: LLM providers (Gemini, OpenAI, Qwen3), tool calling, PydanticAI
- Key Dependencies: PydanticAI, OpenRouter, Google Gemini API
- Critical Issue: Gemini ignores search_type constraints, forcing pivot to Qwen3

## Working Solutions

### Qwen3-235B Configuration via OpenRouter
**Last Verified**: July 26, 2025
**Discovered After**: Gemini consistently ignores tool selection constraints

```python
# Qwen3-235B-A22B-Thinking-2507 configuration
# BFCL-v3 Score: 70.9 (superior tool calling)

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel

# OpenRouter configuration for Qwen3
llm = OpenAIModel(
    'qwen/qwen3-235b-a22b-thinking-2507',
    base_url='https://openrouter.ai/api/v1',
    api_key=os.getenv('OPENROUTER_API_KEY'),
    # Optional parameters for better control
    model_settings={
        'temperature': 0.7,
        'top_p': 0.8,
        'top_k': 20
    }
)

# Create agent with Qwen3
agent = Agent(
    model=llm,
    system_prompt=system_prompt,
    tools=[vector_search, graph_search, hybrid_search]
)
```

**Why This Works**: Qwen3 specifically optimized for tool calling, respects constraints
**Common Failures**: Gemini 2.5 Pro ignores system prompt tool constraints

### Gemini Tool Selection Workaround (Temporary)
**Last Verified**: July 26, 2025
**Discovered After**: Gemini calls hybrid_search even when search_type="vector"

```python
# Flexible constraints workaround (NOT IDEAL - adds technical debt)
system_prompt = """
You are an AI assistant specializing in Practical Strategy concepts.

IMPORTANT: When the user specifies a search_type, you should use the corresponding search function:
- If search_type is "vector", prefer using vector_search
- If search_type is "graph", prefer using graph_search  
- If search_type is "hybrid", prefer using hybrid_search
- If no search_type is specified, choose the most appropriate search method

However, you may use your judgment if a different search method would better serve the user's query.
"""
```

**Why This Works**: Gives Gemini flexibility while suggesting preferences
**Problem**: Doesn't guarantee correct tool selection, breaks API contract

### Provider Abstraction Pattern
**Last Verified**: July 26, 2025
**Discovered After**: Need to support multiple providers seamlessly

```python
# Provider configuration mapping
LLM_PROVIDERS = {
    'gemini': {
        'model': 'gemini-2.0-pro-exp',
        'api_key': os.getenv('LLM_API_KEY'),
        'client_type': 'google'
    },
    'openai': {
        'model': 'gpt-4o-mini',
        'api_key': os.getenv('OPENAI_API_KEY'),
        'client_type': 'openai'
    },
    'qwen3': {
        'model': 'qwen/qwen3-235b-a22b-thinking-2507',
        'base_url': 'https://openrouter.ai/api/v1',
        'api_key': os.getenv('OPENROUTER_API_KEY'),
        'client_type': 'openai'  # Uses OpenAI-compatible API
    }
}

# Provider factory
def get_llm_model(provider: str):
    config = LLM_PROVIDERS[provider]
    
    if config['client_type'] == 'google':
        return GoogleModel(config['model'], api_key=config['api_key'])
    elif config['client_type'] == 'openai':
        return OpenAIModel(
            config['model'],
            base_url=config.get('base_url', 'https://api.openai.com/v1'),
            api_key=config['api_key']
        )
```

## Configuration

### Environment Variables
```bash
# Current (Gemini)
LLM_PROVIDER=google
LLM_API_KEY=AIzaSyDy8D4xLgWdzdAMpoPYEEBsdEmm9FjmuDs

# Transition to (Qwen3)
LLM_PROVIDER=qwen3
OPENROUTER_API_KEY=your-openrouter-key

# Backup (OpenAI for reranking)
OPENAI_API_KEY=sk-proj-kZTo8YzunD5fKyO6Al-oWHaWOemxfO3_H-JxSsude...
```

### Files & Locations
- Agent configuration: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/agent/agent.py`
- Provider configs: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/agent/providers.py`
- System prompts: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/agent/prompts.py`

## Integration Patterns

### With PydanticAI
- All providers use PydanticAI's model abstraction
- Tool definitions remain the same across providers
- Response streaming supported for all

### With Graphiti
- Graphiti uses separate LLM instance for graph operations
- Currently configured for Gemini (works for graph building)
- Different from chat agent LLM

## Gotchas & Solutions

### Problem: Gemini ignores tool selection constraints
**Symptoms**: Calls hybrid_search when told to use vector_search
**Root Cause**: Gemini 2.5 Pro's tool calling doesn't respect system constraints
**Solution**: Switch to Qwen3-235B-A22B-Thinking-2507
**Prevention**: Test tool selection compliance before choosing provider

### Problem: Rate limits on OpenRouter
**Symptoms**: 429 errors during high usage
**Root Cause**: Free tier has limits
**Solution**: Add retry logic or upgrade to paid tier
```python
# Retry configuration
retry_config = {
    'max_attempts': 3,
    'initial_delay': 1.0,
    'exponential_base': 2.0
}
```

### Problem: Model context limits
**Symptoms**: Token limit exceeded errors
**Root Cause**: Large search results + conversation history
**Solution**: Implement context window management
```python
# Context management
MAX_CONTEXT_TOKENS = 100000  # Qwen3 has 262K but leave buffer
MAX_SEARCH_RESULTS = 10
TRUNCATE_CONTENT_AT = 500  # chars per result
```

### Problem: Response format variations
**Symptoms**: Different providers return slightly different formats
**Root Cause**: Each provider has quirks
**Solution**: Normalize responses in agent wrapper
**Prevention**: Test response parsing with each provider

## Testing

### Verify Tool Selection
```python
# Test script to verify tool calling
import asyncio
from agent.agent import create_agent

async def test_tool_selection():
    agent = create_agent(provider='qwen3')
    
    # Test vector search constraint
    result = await agent.run(
        "Search for practical strategy",
        search_type="vector"
    )
    
    # Check which tool was called
    print(f"Tools called: {result.tools_used}")
    
asyncio.run(test_tool_selection())
```

### Provider Switching Test
```bash
# Test with different providers
export LLM_PROVIDER=gemini
python3 test_agent_behavior.py

export LLM_PROVIDER=qwen3
python3 test_agent_behavior.py
```

## Update Instructions
When you discover new LLM provider issues:
1. Document the exact behavior difference
2. Include model versions and API responses
3. Test tool calling compliance
4. Note any prompt engineering workarounds
