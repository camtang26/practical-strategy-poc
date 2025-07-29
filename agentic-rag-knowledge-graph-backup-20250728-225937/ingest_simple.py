#!/usr/bin/env python3
"""Simple ingestion focused on vector embeddings only."""
import asyncio
from pathlib import Path
import logging

# Apply Jina patches
from agent.providers_jina_patch import patch_providers
patch_providers()

from ingestion.chunker import DocumentChunker
from ingestion.embedder import Embedder
from agent.db_utils import get_db_pool
from agent.models import Document, Chunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def ingest_document(file_path: str):
    """Ingest a single document."""
    logger.info(f"Reading {file_path}...")
    
    # Read document
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Initialize components
    chunker = DocumentChunker(chunk_size=800, chunk_overlap=150)
    embedder = Embedder()
    
    # Create chunks
    logger.info("Creating chunks...")
    chunks = await chunker.chunk_text(content, {"source": file_path})
    logger.info(f"Created {len(chunks)} chunks")
    
    # Create embeddings using Jina
    logger.info("Creating embeddings with Jina...")
    texts = [chunk.content for chunk in chunks]
    embeddings = await embedder.embed_texts(texts)
    logger.info(f"Created {len(embeddings)} embeddings")
    
    # Store in database
    pool = await get_db_pool()
    
    async with pool.acquire() as conn:
        # Create document
        doc = Document(
            source=file_path,
            title=Path(file_path).stem.replace('_', ' ').title(),
            metadata={"type": "book", "embedding_model": "jina-embeddings-v4"}
        )
        
        doc_id = await conn.fetchval(
            """INSERT INTO documents (source, title, content, metadata, created_at)
               VALUES ($1, $2, $3, $4, NOW()) RETURNING id""",
            doc.source, doc.title, content[:1000], doc.metadata
        )
        
        logger.info(f"Created document with ID: {doc_id}")
        
        # Store chunks with embeddings
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            await conn.execute(
                """INSERT INTO chunks (document_id, content, embedding, chunk_index, metadata, created_at)
                   VALUES ($1, $2, $3, $4, $5, NOW())""",
                doc_id, chunk.content, embedding, i, chunk.metadata
            )
        
        logger.info(f"Stored {len(chunks)} chunks with embeddings")
    
    await pool.close()

async def main():
    """Main function."""
    book_path = "documents/practical_strategy_book.md"
    
    logger.info("Starting simplified ingestion with Jina embeddings...")
    logger.info(f"Book path: {book_path}")
    
    try:
        await ingest_document(book_path)
        logger.info("✅ Ingestion completed successfully!")
    except Exception as e:
        logger.error(f"❌ Error during ingestion: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
