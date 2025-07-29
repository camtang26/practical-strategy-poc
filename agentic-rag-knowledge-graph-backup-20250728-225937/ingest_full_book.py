#!/usr/bin/env python3
"""
Comprehensive ingestion script for both vector database and knowledge graph.
"""
import asyncio
import logging
from datetime import datetime, timezone
import sys
from pathlib import Path

# Apply Jina patches first
from agent.providers_jina_patch import patch_providers
patch_providers()

from agent.tools import generate_embedding
from agent.db_utils import db_pool, initialize_database
from agent.graph_utils import GraphitiClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def ingest_to_vector_db():
    """Ingest book into vector database with Jina embeddings."""
    logger.info("🚀 Starting vector database ingestion...")
    
    # Load book
    book_path = Path('documents/practical_strategy_book.md')
    if not book_path.exists():
        logger.error(f"Book file not found: {book_path}")
        return False
        
    with open(book_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    logger.info(f"📖 Loaded book: {len(content):,} characters")
    
    # Chunking configuration
    chunk_size = 2000  # Characters
    chunk_overlap = 400
    chunks = []
    
    # Create chunks
    for i in range(0, len(content), chunk_size - chunk_overlap):
        chunk_text = content[i:i + chunk_size]
        if chunk_text.strip():
            chunks.append({
                'content': chunk_text,
                'index': len(chunks),
                'start_char': i,
                'end_char': i + len(chunk_text)
            })
    
    logger.info(f"📄 Created {len(chunks)} chunks")
    
    async with db_pool.acquire() as conn:
        # First, clear existing chunks for this document
        logger.info("Clearing existing chunks...")
        await conn.execute("""
            DELETE FROM chunks 
            WHERE document_id IN (
                SELECT id FROM documents 
                WHERE title = 'Practical Strategy Book'
            )
        """)
        
        # Create document record
        doc_id = await conn.fetchval("""
            INSERT INTO documents (title, source, content)
            VALUES ($1, $2, $3)
            RETURNING id
        """, 'Practical Strategy Book', 'documents/practical_strategy_book.md', content[:1000])
        
        logger.info(f"📚 Created document record: {doc_id}")
        
        # Process chunks in batches
        batch_size = 10
        for batch_start in range(0, len(chunks), batch_size):
            batch_end = min(batch_start + batch_size, len(chunks))
            batch = chunks[batch_start:batch_end]
            
            logger.info(f"Processing chunks {batch_start + 1}-{batch_end}/{len(chunks)}")
            
            # Generate embeddings for batch
            embeddings = []
            for chunk in batch:
                try:
                    embedding = await generate_embedding(chunk['content'])
                    embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"Error generating embedding: {e}")
                    embeddings.append(None)
            
            # Insert chunks with embeddings
            for chunk, embedding in zip(batch, embeddings):
                if embedding is not None:
                    await conn.execute("""
                        INSERT INTO chunks (
                            document_id, 
                            content, 
                            chunk_index, 
                            embedding_jina,
                            embedding_provider
                        )
                        VALUES ($1, $2, $3, $4, 'jina_v4')
                    """, doc_id, chunk['content'], chunk['index'], embedding)
            
            # Small delay to avoid rate limits
            await asyncio.sleep(1)
    
    logger.info("✅ Vector database ingestion complete!")
    return True

async def build_knowledge_graph():
    """Build knowledge graph from ingested chunks."""
    logger.info("🌐 Starting knowledge graph construction...")
    
    # Initialize graph client
    graph_client = GraphitiClient()
    await graph_client.initialize()
    
    async with db_pool.acquire() as conn:
        # Get all chunks
        chunks = await conn.fetch("""
            SELECT 
                c.id, 
                c.content, 
                c.chunk_index,
                d.title as document_title,
                d.source as document_source
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.title = 'Practical Strategy Book'
            ORDER BY c.chunk_index
        """)
        
        logger.info(f"📊 Found {len(chunks)} chunks to process for graph")
        
        # Process chunks in smaller batches for graph
        batch_size = 5
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i+batch_size]
            logger.info(f"Processing graph batch {i//batch_size + 1}/{(len(chunks) + batch_size - 1)//batch_size}")
            
            for chunk in batch:
                try:
                    # Create episode content
                    episode_content = f"""
{chunk['document_title']} - Section {chunk['chunk_index']}

{chunk['content']}
"""
                    
                    # Add to graph
                    episode = await graph_client.client.add_episode(
                        name=f"practical_strategy_chunk_{chunk['chunk_index']}",
                        episode_body=episode_content,
                        source=chunk['document_source'],
                        reference_time=datetime.now(timezone.utc),
                        source_description=f"Chunk {chunk['chunk_index']} from {chunk['document_title']}",
                        group_id="practical_strategy_book"
                    )
                    
                    logger.info(f"✓ Added chunk {chunk['chunk_index']} to graph")
                    
                except Exception as e:
                    logger.error(f"Error processing chunk {chunk['chunk_index']}: {str(e)}")
                    continue
            
            # Delay between batches
            await asyncio.sleep(2)
    
    await graph_client.close()
    logger.info("✅ Knowledge graph construction complete!")

async def main():
    """Run the complete ingestion pipeline."""
    try:
        # Initialize database
        await initialize_database()
        
        # Step 1: Ingest to vector database
        success = await ingest_to_vector_db()
        if not success:
            logger.error("Vector database ingestion failed")
            return
        
        # Step 2: Build knowledge graph
        await build_knowledge_graph()
        
        # Verify results
        async with db_pool.acquire() as conn:
            chunk_count = await conn.fetchval("SELECT COUNT(*) FROM chunks")
            logger.info(f"\n📊 Final statistics:")
            logger.info(f"  - Total chunks in database: {chunk_count}")
        
        # Check Neo4j
        from neo4j import GraphDatabase
        import os
        from dotenv import load_dotenv
        load_dotenv()
        
        driver = GraphDatabase.driver(
            os.getenv("NEO4J_URI", "bolt://localhost:7688"),
            auth=(os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD"))
        )
        
        with driver.session() as session:
            node_count = session.run("MATCH (n) RETURN count(n) as count").single()["count"]
            fact_count = session.run("MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count").single()["count"]
            logger.info(f"  - Total nodes in graph: {node_count}")
            logger.info(f"  - Total facts in graph: {fact_count}")
        
        driver.close()
        
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        raise
    finally:
        await db_pool.close()

if __name__ == "__main__":
    asyncio.run(main())
