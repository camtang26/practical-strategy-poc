#!/usr/bin/env python3
"""Ingest Practical Strategy book with Jina embeddings - vectors only."""
import asyncio
import logging
import json
from datetime import datetime
from pathlib import Path

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

from ingestion.chunker import SimpleChunker, ChunkingConfig
from ingestion.embedder import EmbeddingGenerator
from agent.db_utils import db_pool
from agent.data.models import Document, DocumentMetadata
from agent.data.document_manager import DocumentManager
from agent.embeddings import get_embedding_function

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('ingestion_vectors_only.log'),
        logging.StreamHandler()
    ]
)

async def main():
    """Main ingestion function."""
    logging.info("🚀 Starting Practical Strategy book ingestion with Jina embeddings v4 (vectors only)")
    logging.info("📋 Configuration:")
    logging.info("  - Embedding Model: jina-embeddings-v4")
    logging.info("  - Dimensions: 2048")
    logging.info("  - Context Window: 32,768 tokens")
    logging.info("  - Chunk Size: 800 tokens")
    logging.info("  - Chunk Overlap: 150 tokens")
    
    # Initialize components
    await db_pool.initialize()
    logging.info("Database connection pool initialized")
    
    # Load book
    book_path = Path("documents/practical_strategy_book.md")
    with open(book_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    logging.info(f"📖 Loaded book: {len(content):,} characters")
    
    # Configure chunking
    config = ChunkingConfig(chunk_size=800, chunk_overlap=150, use_semantic_splitting=False)
    chunker = SimpleChunker(config)
    
    # Create chunks
    logging.info("📄 Creating chunks...")
    chunks = await chunker.chunk_document(
        content=content,
        title="Practical Strategy",
        source=str(book_path),
        metadata={"book": "Practical Strategy", "author": "Business Strategy Expert"}
    )
    logging.info(f"✅ Created {len(chunks)} chunks")
    
    # Generate embeddings
    logging.info("🧮 Generating embeddings with Jina...")
    embedder = EmbeddingGenerator()
    embed_func = get_embedding_function()
    
    # Process chunks in batches
    batch_size = 10
    total_embedded = 0
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        batch_texts = [chunk['content'] for chunk in batch]
        
        try:
            # Generate embeddings for batch
            embeddings = await embed_func(batch_texts)
            
            # Add embeddings to chunks
            for j, chunk in enumerate(batch):
                chunk['embedding'] = embeddings[j]
            
            total_embedded += len(batch)
            logging.info(f"  Embedded {total_embedded}/{len(chunks)} chunks...")
            
        except Exception as e:
            logging.error(f"Error embedding batch {i//batch_size}: {e}")
            continue
    
    logging.info(f"✅ Generated embeddings for {total_embedded} chunks")
    
    # Store in database
    logging.info("💾 Storing chunks and embeddings in PostgreSQL...")
    doc_manager = DocumentManager()
    
    # Create document
    doc_metadata = DocumentMetadata(
        title="Practical Strategy",
        author="Business Strategy Expert",
        source=str(book_path),
        created_at=datetime.now(),
        tags=["business", "strategy", "management"],
        embedding_model="jina-embeddings-v4",
        embedding_dimensions=2048
    )
    
    doc = Document(
        content=content,
        metadata=doc_metadata,
        chunks=chunks
    )
    
    # Store document
    doc_id = await doc_manager.store_document(doc)
    logging.info(f"✅ Stored document with ID: {doc_id}")
    
    # Verify storage
    stored_doc = await doc_manager.get_document(doc_id)
    if stored_doc:
        logging.info(f"✅ Verified: Document has {len(stored_doc.chunks)} chunks")
        
        # Test similarity search
        test_query = "What are the key principles of business strategy?"
        logging.info(f"\n🔍 Testing similarity search with query: '{test_query}'")
        
        results = await doc_manager.search_similar_chunks(test_query, limit=3)
        logging.info(f"Found {len(results)} similar chunks:")
        for idx, (chunk, score) in enumerate(results):
            preview = chunk['content'][:100].replace('\n', ' ')
            logging.info(f"  {idx+1}. Score: {score:.4f} - {preview}...")
    
    logging.info("\n✅ Ingestion complete! Jina embeddings v4 successfully integrated.")
    
    # Clean up
    await db_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
