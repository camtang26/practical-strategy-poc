#!/usr/bin/env python3
"""Working ingestion script."""
import asyncio
import logging

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

from ingestion.chunker import SimpleChunker, ChunkingConfig
from ingestion.embedder import EmbeddingGenerator
from agent.db_utils import get_db_pool
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Main function."""
    book_path = "documents/practical_strategy_book.md"
    
    logger.info("📚 Starting Practical Strategy book ingestion with Jina embeddings v4...")
    
    # Read document
    with open(book_path, 'r', encoding='utf-8') as f:
        content = f.read()
    logger.info(f"📖 Book size: {len(content):,} characters")
    
    # Create chunks
    config = ChunkingConfig(chunk_size=800, chunk_overlap=150, use_semantic_chunking=False)
    chunker = SimpleChunker(config)
    chunks = await chunker.chunk_document(content, metadata={"source": book_path})
    logger.info(f"✂️ Created {len(chunks)} chunks")
    
    # Create embeddings
    embedder = EmbeddingGenerator()
    texts = [chunk.content for chunk in chunks]
    
    logger.info("🔥 Generating embeddings with Jina v4 (2048 dimensions)...")
    embeddings = await embedder.generate_embeddings(texts)
    logger.info(f"✅ Generated {len(embeddings)} embeddings")
    
    # Store in database
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Clean existing
        await conn.execute("DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE source = $1)", book_path)
        await conn.execute("DELETE FROM documents WHERE source = $1", book_path)
        
        # Create document
        doc_id = await conn.fetchval(
            """INSERT INTO documents (source, title, content, metadata, created_at)
               VALUES ($1, $2, $3, $4, NOW()) RETURNING id""",
            book_path,
            "Practical Strategy Book",
            content[:1000],
            json.dumps({
                "type": "book",
                "embedding_model": "jina-embeddings-v4",
                "dimensions": 2048,
                "chunks": len(chunks)
            })
        )
        
        logger.info(f"📝 Created document ID: {doc_id}")
        
        # Store chunks
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            await conn.execute(
                """INSERT INTO chunks (document_id, content, embedding, chunk_index, metadata, created_at)
                   VALUES ($1, $2, $3, $4, $5, NOW())""",
                doc_id, chunk.content, embedding, i, json.dumps(chunk.metadata)
            )
            
            if (i + 1) % 50 == 0:
                logger.info(f"💾 Stored {i + 1}/{len(chunks)} chunks...")
        
        logger.info(f"✅ Stored all {len(chunks)} chunks!")
    
    await pool.close()
    logger.info("🎉 SUCCESS! The Practical Strategy book is now ingested with Jina embeddings v4!")
    logger.info("🔍 You can now search the book using the API at http://170.64.129.131:8058")

if __name__ == "__main__":
    asyncio.run(main())
