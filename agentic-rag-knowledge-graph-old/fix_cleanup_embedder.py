import asyncio
from pathlib import Path

async def fix_cleanup_embedder():
    """Fix the cleanup_embedder function to use the proper close() method."""
    
    providers_path = Path("agent/providers_extended.py")
    content = providers_path.read_text()
    
    # Find and replace the cleanup_embedder function
    old_cleanup = """async def cleanup_embedder():
    \"\"\"Clean up the embedder resources.\"\"\"
    global _embedder_instance
    if _embedder_instance and hasattr(_embedder_instance, '_client') and _embedder_instance._client:
        await _embedder_instance._client.aclose()
        _embedder_instance = None"""
    
    new_cleanup = """async def cleanup_embedder():
    \"\"\"Clean up the embedder resources.\"\"\"
    global _embedder_instance
    if _embedder_instance:
        await _embedder_instance.close()
        _embedder_instance = None"""
    
    if old_cleanup in content:
        content = content.replace(old_cleanup, new_cleanup)
        providers_path.write_text(content)
        print("✅ Updated cleanup_embedder to use proper close() method")
    else:
        print("❌ Could not find the old cleanup_embedder function")
        print("Checking current implementation...")
        # Find the current implementation
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if 'async def cleanup_embedder' in line:
                print(f"Found at line {i+1}:")
                for j in range(i, min(i+10, len(lines))):
                    print(f"{j+1}: {lines[j]}")
                break

if __name__ == "__main__":
    asyncio.run(fix_cleanup_embedder())
