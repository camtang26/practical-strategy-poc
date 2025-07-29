import re
from pathlib import Path

def add_embedder_cleanup():
    """Add embedder cleanup to FastAPI lifespan handler."""
    
    api_path = Path("agent/api.py")
    content = api_path.read_text()
    
    # Check if cleanup_embedder is already imported
    if "cleanup_embedder" not in content:
        # Add import after other imports
        import_line = "from .providers_extended import generate_embedding_unified, cleanup_embedder"
        content = content.replace(
            "from .providers_extended import generate_embedding_unified",
            import_line
        )
        print("✅ Added cleanup_embedder import")
    
    # Find the shutdown section and add embedder cleanup
    shutdown_pattern = r'(# Shutdown\s*\n\s*logger\.info\("Shutting down.*?"\)\s*\n\s*\n\s*try:)'
    
    match = re.search(shutdown_pattern, content, re.DOTALL)
    if match:
        # Check if cleanup_embedder is already called
        if "cleanup_embedder" not in content[match.end():match.end()+500]:
            # Add cleanup_embedder call after the try:
            shutdown_section = match.group(1)
            new_shutdown = shutdown_section + "\n        await cleanup_embedder()"
            content = content.replace(shutdown_section, new_shutdown)
            print("✅ Added cleanup_embedder() call to shutdown section")
        else:
            print("ℹ️ cleanup_embedder() already in shutdown section")
    else:
        print("❌ Could not find shutdown section")
        return False
    
    # Write the updated content
    api_path.write_text(content)
    print("✅ Updated api.py successfully")
    return True

if __name__ == "__main__":
    add_embedder_cleanup()
