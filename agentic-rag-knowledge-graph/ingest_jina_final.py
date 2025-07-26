#!/usr/bin/env python3
"""Final working ingestion script with Jina embeddings."""
import asyncio
import logging
import json
from datetime import datetime

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

from ingestion.chunker import SimpleChunker, ChunkingConfig
from ingestion.embedder import EmbeddingGenerator
from agent.db_utils import db_pool

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """Main ingestion function."""
    book_path = "documents/practical_strategy_book.md"
    
    logger.info("🚀 Starting Practical Strategy book ingestion with Jina embeddings v4")
    logger.info("📋 Configuration:")
    logger.info("  - Embedding Model: jina-embeddings-v4")
    logger.info("  - Dimensions: 2048")
    logger.info("  - Context Window: 32,768 tokens")
    logger.info("  - Chunk Size: 800 tokens")
    logger.info("  - Chunk Overlap: 150 tokens")
    
    # Initialize database
    await db_pool.initialize()
    
    # Read document
    with open(book_path, 'r', encoding='utf-8') as f:
        content = f.read()
    logger.info(f"📖 Loaded book: {len(content):,} characters")
    
    # Create chunks
    config = ChunkingConfig(chunk_size=800, chunk_overlap=150, use_semantic_splitting=False)
    chunker = SimpleChunker(config)
    chunks = await chunker.chunk_document(content, metadata={"source": book_path})
    logger.info(f"✂️ Created {len(chunks)} chunks")
    
    # Generate embeddings
    embedder = EmbeddingGenerator()
    texts = [chunk.content for chunk in chunks]
    
    logger.info("🔮 Generating Jina embeddings...")
    start_time = datetime.now()
    embeddings = await embedder.generate_embeddings(texts)
    embed_time = (datetime.now() - start_time).total_seconds()
    logger.info(f"✅ Generated {len(embeddings)} embeddings in {embed_time:.2f} seconds")
    
    # Store in database
    async with db_pool.acquire() as conn:
        # Clean existing data
        await conn.execute("DELETE FROM chunks WHERE document_id IN (SELECT id FROM documents WHERE source = $1)", book_path)
        await conn.execute("DELETE FROM documents WHERE source = $1", book_path)
        
        # Create document record
        doc_id = await conn.fetchval(
            """INSERT INTO documents (source, title, content, metadata, created_at)
               VALUES ($1, $2, $3, $4, NOW()) RETURNING id""",
            book_path,
            "Practical Strategy Book",
            content[:1000],  # Preview
            json.dumps({
                "type": "book",
                "embedding_model": "jina-embeddings-v4",
                "dimensions": 2048,
                "total_chunks": len(chunks),
                "total_characters": len(content),
                "ingestion_time": embed_time
            })
        )
        
        logger.info(f"📄 Created document record ID: {doc_id}")
        
        # Store chunks with embeddings
        logger.info("💾 Storing chunks in database...")
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            await conn.execute(
                """INSERT INTO chunks (document_id, content, embedding, chunk_index, metadata, created_at)
                   VALUES ($1, $2, $3, $4, $5, NOW())""",
                doc_id,
                chunk.content,
                embedding,
                i,
                json.dumps({**chunk.metadata, "chunk_number": i + 1, "total_chunks": len(chunks)})
            )
            
            if (i + 1) % 20 == 0:
                logger.info(f"  Progress: {i + 1}/{len(chunks)} chunks stored")
        
        logger.info(f"✅ Successfully stored all {len(chunks)} chunks!")
    
    # Close database
    await db_pool.close()
    
    logger.info("🎉 INGESTION COMPLETE!")
    logger.info("📊 Summary:")
    logger.info(f"  - Document: Practical Strategy Book")
    logger.info(f"  - Total Chunks: {len(chunks)}")
    logger.info(f"  - Embedding Model: Jina v4 (2048-dim)")
    logger.info(f"  - Processing Time: {embed_time:.2f} seconds")
    logger.info("")
    logger.info("🔍 The book is now searchable via the API!")
    logger.info("   API Endpoint: http://170.64.129.131:8058/chat")
    logger.info("   Try: 'What is practical strategy?'")

if __name__ == "__main__":
    asyncio.run(main())
