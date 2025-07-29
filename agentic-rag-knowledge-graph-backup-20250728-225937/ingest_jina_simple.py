#!/usr/bin/env python3
"""Simple ingestion script for Jina embeddings."""
import asyncio
import logging
from datetime import datetime
import json
import os
import psycopg2
from psycopg2.extras import execute_values
import numpy as np

# Apply Jina patches
from agent.providers_jina_patch import patch_providers
patch_providers()

from agent.embeddings import get_embedding_function
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

async def main():
    """Main ingestion function."""
    logging.info("🚀 Starting Practical Strategy book ingestion with Jina embeddings")
    
    # Database connection
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        db_url = "postgresql://postgres:temporalrocks123@localhost:5432/strategy_rag"
    
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    
    # Create tables if needed
    cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id SERIAL PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cur.execute("""
        CREATE EXTENSION IF NOT EXISTS vector;
        CREATE TABLE IF NOT EXISTS document_chunks (
            id SERIAL PRIMARY KEY,
            document_id INTEGER REFERENCES documents(id),
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(2048),
            metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Create index for similarity search
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_chunks_embedding 
        ON document_chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    
    conn.commit()
    
    # Load book
    with open('documents/practical_strategy_book.md', 'r', encoding='utf-8') as f:
        content = f.read()
    
    logging.info(f"📖 Loaded book: {len(content):,} characters")
    
    # Insert document
    cur.execute("""
        INSERT INTO documents (title, content, metadata)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (
        "Practical Strategy",
        content,
        json.dumps({
            "author": "Business Strategy Expert",
            "source": "documents/practical_strategy_book.md",
            "embedding_model": "jina-embeddings-v4"
        })
    ))
    doc_id = cur.fetchone()[0]
    conn.commit()
    
    logging.info(f"📄 Created document with ID: {doc_id}")
    
    # Simple chunking
    chunk_size = 3000  # Characters
    chunk_overlap = 500
    chunks = []
    
    for i in range(0, len(content), chunk_size - chunk_overlap):
        chunk_text = content[i:i + chunk_size]
        if chunk_text.strip():
            chunks.append(chunk_text)
    
    logging.info(f"📄 Created {len(chunks)} chunks")
    
    # Generate embeddings
    embed_func = get_embedding_function()
    logging.info("🧮 Generating Jina embeddings...")
    
    batch_size = 5
    all_chunk_data = []
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        try:
            embeddings = await embed_func(batch)
            
            for j, (chunk_text, embedding) in enumerate(zip(batch, embeddings)):
                all_chunk_data.append((
                    doc_id,
                    i + j,
                    chunk_text,
                    embedding,
                    json.dumps({"chunk_method": "simple", "model": "jina-embeddings-v4"})
                ))
            
            logging.info(f"  Embedded {min(i+batch_size, len(chunks))}/{len(chunks)} chunks...")
            
        except Exception as e:
            logging.error(f"Error embedding batch: {e}")
            continue
    
    # Store chunks
    logging.info("💾 Storing chunks in PostgreSQL...")
    
    execute_values(
        cur,
        """
        INSERT INTO document_chunks (document_id, chunk_index, content, embedding, metadata)
        VALUES %s
        """,
        all_chunk_data,
        template="(%s, %s, %s, %s::vector, %s::jsonb)"
    )
    conn.commit()
    
    logging.info(f"✅ Stored {len(all_chunk_data)} chunks with embeddings")
    
    # Test similarity search
    test_query = "What are the key principles of business strategy?"
    logging.info(f"\n🔍 Testing similarity search: '{test_query}'")
    
    query_embedding = await embed_func([test_query])
    query_vec = query_embedding[0]
    
    cur.execute("""
        SELECT chunk_index, content, 1 - (embedding <=> %s::vector) as similarity
        FROM document_chunks
        WHERE document_id = %s
        ORDER BY embedding <=> %s::vector
        LIMIT 3
    """, (query_vec, doc_id, query_vec))
    
    results = cur.fetchall()
    logging.info(f"Found {len(results)} similar chunks:")
    for idx, (chunk_idx, chunk_content, similarity) in enumerate(results):
        preview = chunk_content[:100].replace('\n', ' ')
        logging.info(f"  {idx+1}. Chunk {chunk_idx} (similarity: {similarity:.4f}): {preview}...")
    
    # Clean up
    cur.close()
    conn.close()
    
    logging.info("\n✅ Ingestion complete! Jina embeddings successfully stored.")

if __name__ == "__main__":
    asyncio.run(main())
