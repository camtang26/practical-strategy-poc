#!/usr/bin/env python3
"""Ingest the Practical Strategy book with Jina embeddings."""
import asyncio
import sys
from pathlib import Path

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

# Import ingestion modules
from ingestion.ingest import ingest_documents

async def main():
    """Ingest the book."""
    print("Starting ingestion of Practical Strategy book...")
    print("Using Jina embeddings v4 (2048 dimensions)")
    print("This will take advantage of:")
    print("- 32K token context window")
    print("- Better semantic representations")
    print("- Cost efficiency")
    print()
    
    # Define the book path
    book_path = Path("documents/practical_strategy_book.md")
    
    if not book_path.exists():
        print(f"Error: Book file not found at {book_path}")
        return
    
    print(f"Found book at: {book_path}")
    print(f"File size: {book_path.stat().st_size / 1024:.2f} KB")
    print()
    
    try:
        # Ingest the document
        print("Starting ingestion process...")
        result = await ingest_documents(
            file_paths=[str(book_path)],
            chunk_size=800,  # Good size for semantic coherence
            chunk_overlap=150  # Ensure context continuity
        )
        
        print(f"\n✅ Ingestion completed successfully!")
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"\n❌ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
