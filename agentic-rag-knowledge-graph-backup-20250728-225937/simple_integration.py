"""
Simple integration script to add experimental optimizations.
"""

import logging
from pathlib import Path
import shutil
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def integrate_tools():
    """Add cache decorator to tools.py hybrid_search_tool."""
    tools_path = Path("agent/tools.py")
    
    # Backup
    backup_path = tools_path.with_suffix('.py.backup_simple')
    shutil.copy(tools_path, backup_path)
    logger.info(f"Backed up tools.py to {backup_path}")
    
    # Read original from the AST backup (before the failed integration)
    original_backup = Path("agent/tools.py.backup")
    if original_backup.exists():
        content = original_backup.read_text()
    else:
        content = tools_path.read_text()
    
    # Add imports at the top
    imports = """from .experimental_cache_manager import cached_search, get_embedding_cache
from .experimental_error_handler import retry_with_backoff, handle_error
"""
    
    # Insert imports after the docstring
    lines = content.split('\n')
    insert_pos = 0
    for i, line in enumerate(lines):
        if line.strip() == '"""' and i > 0:  # End of module docstring
            insert_pos = i + 1
            break
    
    # Insert imports
    lines.insert(insert_pos, imports)
    
    # Find and decorate hybrid_search_tool
    for i, line in enumerate(lines):
        if line.strip().startswith("async def hybrid_search_tool"):
            # Add decorator
            lines.insert(i, "@cached_search(ttl_seconds=300)")
            lines.insert(i, "@retry_with_backoff(max_retries=3)")
            break
    
    # Write back
    tools_path.write_text('\n'.join(lines))
    logger.info("✓ Updated tools.py with cache and retry decorators")

def integrate_api():
    """Add error handling to api.py."""
    api_path = Path("agent/api.py")
    
    # Backup
    backup_path = api_path.with_suffix('.py.backup_simple')
    shutil.copy(api_path, backup_path)
    logger.info(f"Backed up api.py to {backup_path}")
    
    # Read original
    content = api_path.read_text()
    
    # Add error handler import
    if "from .experimental_error_handler import GlobalErrorHandler" not in content:
        lines = content.split('\n')
        # Find imports section
        for i, line in enumerate(lines):
            if line.startswith("from .") and "error" not in line:
                lines.insert(i+1, "from .experimental_error_handler import GlobalErrorHandler")
                break
        
        # Initialize error handler after app creation
        for i, line in enumerate(lines):
            if "app = FastAPI" in line:
                lines.insert(i+2, "\n# Initialize global error handler")
                lines.insert(i+3, "error_handler = GlobalErrorHandler()")
                break
        
        api_path.write_text('\n'.join(lines))
        logger.info("✓ Updated api.py with error handler")

def integrate_embedder():
    """Update ingest.py to use optimized embedder."""
    ingest_path = Path("ingestion/ingest.py")
    
    # Backup
    backup_path = ingest_path.with_suffix('.py.backup_simple')
    shutil.copy(ingest_path, backup_path)
    logger.info(f"Backed up ingest.py to {backup_path}")
    
    # Read content
    content = ingest_path.read_text()
    
    # Replace JinaEmbeddingGenerator import
    content = content.replace(
        "from ingestion.embedder_jina import JinaEmbeddingGenerator",
        "from ingestion.experimental_embedder_jina_v2 import OptimizedJinaEmbeddingGenerator as JinaEmbeddingGenerator"
    )
    
    # Write back
    ingest_path.write_text(content)
    logger.info("✓ Updated ingest.py to use optimized embedder")

def main():
    logger.info("Starting simple integration...")
    
    try:
        integrate_tools()
        integrate_api()
        integrate_embedder()
        
        logger.info("\n✅ Integration completed successfully!")
        logger.info("\nTo run tests:")
        logger.info("  python3 test_integration.py")
        logger.info("\nTo restore:")
        logger.info("  cp agent/tools.py.backup_simple agent/tools.py")
        logger.info("  cp agent/api.py.backup_simple agent/api.py")
        logger.info("  cp ingestion/ingest.py.backup_simple ingestion/ingest.py")
        
    except Exception as e:
        logger.error(f"Integration failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
