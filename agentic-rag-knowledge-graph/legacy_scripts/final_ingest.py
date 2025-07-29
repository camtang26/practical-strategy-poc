#!/usr/bin/env python3
"""Final ingestion script with correct imports."""
import asyncio
from pathlib import Path
import logging

# Apply Jina patches
from agent.providers_jina_patch import patch_providers
patch_providers()

from ingestion.chunker import SimpleChunker, ChunkingConfig
from ingestion.embedder import Embedder
from agent.db_utils import get_db_pool
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Main ingestion function."""
    book_path = "documents/practical_strategy_book.md"
    
    logger.info("Starting Jina embeddings ingestion...")
    logger.info(f"Book: {book_path}")
    
    # Read document
    with open(book_path, 'r', encoding='utf-8') as f:
        content = f.read()
    logger.info(f"Document size: {len(content)} characters")
    
    # Configure chunking
    config = ChunkingConfig(
        chunk_size=800,
        chunk_overlap=150,
        use_semantic_chunking=False  # Simple chunking for now
    )
    
    # Create chunks
    chunker = SimpleChunker(config)
    chunks = await chunker.chunk_document(content, metadata={"source": book_path})
    logger.info(f"Created {len(chunks)} chunks")
    
    # Create embeddings
    embedder = Embedder()
    texts = [chunk.content for chunk in chunks]
    
    logger.info("Creating embeddings with Jina v4...")
    embeddings = await embedder.embed_texts(texts)
    logger.info(f"Created {len(embeddings)} embeddings (dimension: {len(embeddings[0]) if embeddings else 0})")
    
    # Store in database
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Clear existing data
        await conn.execute("DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE source = $1)", book_path)
        await conn.execute("DELETE FROM documents WHERE source = $1", book_path)
        
        # Create document
        doc_id = await conn.fetchval(
            """INSERT INTO documents (source, title, content, metadata, created_at)
               VALUES ($1, $2, $3, $4, NOW()) RETURNING id""",
            book_path,
            "Practical Strategy Book",
            content[:1000],  # Store first 1000 chars as preview
            json.dumps({"type": "book", "embedding_model": "jina-embeddings-v4", "dimensions": len(embeddings[0]) if embeddings else 0})
        )
        
        logger.info(f"Created document ID: {doc_id}")
        
        # Store chunks
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            await conn.execute(
                """INSERT INTO chunks (document_id, content, embedding, chunk_index, metadata, created_at)
                   VALUES ($1, $2, $3, $4, $5, NOW())""",
                doc_id,
                chunk.content,
                embedding,
                i,
                json.dumps(chunk.metadata)
            )
        
        logger.info(f"✅ Successfully stored {len(chunks)} chunks!")
    
    await pool.close()
    logger.info("🎉 Ingestion complete! The book is now searchable with Jina embeddings.")

if __name__ == "__main__":
    asyncio.run(main())
