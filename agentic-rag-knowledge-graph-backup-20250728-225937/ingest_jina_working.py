#!/usr/bin/env python3
"""Working ingestion script for Jina embeddings."""
import asyncio
import logging
from datetime import datetime
import json

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

from agent.tools import generate_embedding
from agent.db_utils import db_pool

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
    with open('documents/practical_strategy_book.md', 'r', encoding='utf-8') as f:
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
                'index': len(chunks),
                'start_char': i,
                'end_char': i + len(chunk_text)
            })
    
    logging.info(f"📄 Created {len(chunks)} chunks")
    
    # Store document
    async with db_pool.pool.acquire() as conn:
        # Insert document
        doc_id = await conn.fetchval("""
            INSERT INTO documents (title, content, metadata, created_at)
            VALUES ($1, $2, $2, $3, $4)
            RETURNING id
        """, 
            'Practical Strategy (Jina Embeddings)',
            content,
            json.dumps({
                'author': 'Business Strategy Expert',
                'source': 'documents/practical_strategy_book.md',
                'embedding_model': 'jina-embeddings-v4',
                'embedding_dimensions': 2048,
                'ingested_at': datetime.now().isoformat()
            }),
            datetime.now()
        )
        
        logging.info(f"📄 Created document with ID: {doc_id}")
        
        # Generate embeddings and store chunks
        logging.info("🧮 Generating Jina embeddings and storing chunks...")
        
        successful_chunks = 0
        for i, chunk in enumerate(chunks):
            try:
                # Generate embedding
                embedding = await generate_embedding(chunk['content'])
                
                # Store chunk with embedding
                await conn.execute("""
                    INSERT INTO document_chunks 
                    (document_id, chunk_index, content, embedding, metadata, created_at)
                    VALUES ($1, $2, $3, $4::vector, $5, $6)
                """,
                    doc_id,
                    chunk['index'],
                    chunk['content'],
                    embedding,
                    json.dumps({
                        'start_char': chunk['start_char'],
                        'end_char': chunk['end_char'],
                        'chunk_method': 'simple',
                        'model': 'jina-embeddings-v4'
                    }),
                    datetime.now()
                )
                
                successful_chunks += 1
                
                if (i + 1) % 10 == 0:
                    logging.info(f"  Processed {i + 1}/{len(chunks)} chunks...")
                
            except Exception as e:
                logging.error(f"Error processing chunk {i}: {e}")
                continue
        
        logging.info(f"✅ Successfully stored {successful_chunks}/{len(chunks)} chunks")
        
        # Test similarity search
        test_query = "What are the key principles of business strategy?"
        logging.info(f"\n🔍 Testing similarity search: '{test_query}'")
        
        query_embedding = await generate_embedding(test_query)
        
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
            preview = row['content'][:150].replace('\n', ' ')
            logging.info(f"\n  {idx+1}. Chunk {row['chunk_index']} (similarity: {row['similarity']:.4f}):")
            logging.info(f"     {preview}...")
    
    # Clean up
    await db_pool.close()
    
    logging.info("\n✅ Ingestion complete! Jina embeddings v4 successfully integrated.")
    logging.info("📋 Summary:")
    logging.info(f"  - Model: jina-embeddings-v4")
    logging.info(f"  - Dimensions: 2048") 
    logging.info(f"  - Context Window: 32,768 tokens")
    logging.info(f"  - Document ID: {doc_id}")
    logging.info(f"  - Total chunks: {successful_chunks}")

if __name__ == "__main__":
    asyncio.run(main())
