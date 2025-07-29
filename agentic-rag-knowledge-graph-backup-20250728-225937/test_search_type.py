import asyncio
from agent.agent import rag_agent, AgentDependencies

async def test_context():
    deps = AgentDependencies(
        session_id="test-123",
        search_type="graph"
    )
    
    # Create a test tool to inspect context
    @rag_agent.tool
    async def debug_context(ctx):
        """Debug tool to inspect context"""
        print(f"Context type: {type(ctx)}")
        print(f"Context deps: {ctx.deps}")
        print(f"Search type: {ctx.deps.search_type}")
        return {"context_info": str(ctx.deps)}
    
    result = await rag_agent.run("Use the debug_context tool", deps=deps)
    print(f"Result: {result}")

asyncio.run(test_context())
