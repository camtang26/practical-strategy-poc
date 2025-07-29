#!/usr/bin/env python3
"""Ingest book with Jina embeddings using existing infrastructure."""
import asyncio
import logging
from datetime import datetime
import json
from pathlib import Path

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

from agent.tools import generate_embedding
from agent.db_utils import db_pool
from agent.db_utils import store_document_with_chunks

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

async def main():
    """Main ingestion function."""
    logging.info("🚀 Starting Practical Strategy book ingestion with Jina embeddings v4")
    
    # Initialize database
    await db_pool.initialize()
    logging.info("Database connection pool initialized")
    
    # Load book
    book_path = Path("documents/practical_strategy_book.md")
    with open(book_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    logging.info(f"📖 Loaded book: {len(content):,} characters")
    
    # Simple chunking
    chunk_size = 3000  # Characters
    chunk_overlap = 500
    chunks = []
    
    for i in range(0, len(content), chunk_size - chunk_overlap):
        chunk_text = content[i:i + chunk_size]
        if chunk_text.strip():
            chunks.append({
                'content': chunk_text,
                'index': i // (chunk_size - chunk_overlap),
                'metadata': {
                    'start_char': i,
                    'end_char': i + len(chunk_text),
                    'chunk_method': 'simple',
                    'chunk_size': chunk_size,
                    'chunk_overlap': chunk_overlap
                }
            })
    
    logging.info(f"📄 Created {len(chunks)} chunks")
    
    # Generate embeddings
    logging.info("🧮 Generating Jina embeddings...")
    
    for i, chunk in enumerate(chunks):
        try:
            # Generate embedding using the patched function
            embedding = await generate_embedding(chunk['content'])
            chunk['embedding'] = embedding
            
            if (i + 1) % 10 == 0:
                logging.info(f"  Embedded {i + 1}/{len(chunks)} chunks...")
            
        except Exception as e:
            logging.error(f"Error embedding chunk {i}: {e}")
            chunk['embedding'] = None
    
    # Filter out chunks without embeddings
    valid_chunks = [c for c in chunks if c.get('embedding') is not None]
    logging.info(f"✅ Generated embeddings for {len(valid_chunks)} chunks")
    
    # Store document and chunks
    document_data = {
        'title': 'Practical Strategy',
        'content': content,
        'metadata': {
            'author': 'Business Strategy Expert',
            'source': str(book_path),
            'ingested_at': datetime.now().isoformat(),
            'embedding_model': 'jina-embeddings-v4',
            'embedding_dimensions': 2048,
            'total_chunks': len(valid_chunks)
        }
    }
    
    logging.info("💾 Storing document and chunks in PostgreSQL...")
    
    try:
        doc_id = await store_document_with_chunks(
            title=document_data['title'],
            content=document_data['content'],
            chunks=valid_chunks,
            metadata=document_data['metadata']
        )
        
        logging.info(f"✅ Stored document with ID: {doc_id}")
        
        # Test similarity search
        test_query = "What are the key principles of business strategy?"
        logging.info(f"\n🔍 Testing similarity search: '{test_query}'")
        
        query_embedding = await generate_embedding(test_query)
        
        # Perform vector search
        async with db_pool.pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT 
                    chunk_index,
                    content,
                    1 - (embedding <=> $1::vector) as similarity
                FROM document_chunks
                WHERE document_id = $2
                ORDER BY embedding <=> $1::vector
                LIMIT 3
            """, query_embedding, doc_id)
            
            logging.info(f"Found {len(results)} similar chunks:")
            for idx, row in enumerate(results):
                preview = row['content'][:100].replace('\n', ' ')
                logging.info(f"  {idx+1}. Chunk {row['chunk_index']} (similarity: {row['similarity']:.4f}): {preview}...")
        
    except Exception as e:
        logging.error(f"Error storing document: {e}")
        raise
    
    # Clean up
    await db_pool.close()
    
    logging.info("\n✅ Ingestion complete! Jina embeddings v4 successfully integrated.")
    logging.info("📋 Summary:")
    logging.info(f"  - Model: jina-embeddings-v4")
    logging.info(f"  - Dimensions: 2048")
    logging.info(f"  - Document chunks: {len(valid_chunks)}")
    logging.info(f"  - Book size: {len(content):,} characters")

if __name__ == "__main__":
    asyncio.run(main())
