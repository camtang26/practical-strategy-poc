#!/usr/bin/env python3
"""
Continue building knowledge graph from existing chunks in database.
Designed to run in background and pick up where previous ingestion left off.
"""

import asyncio
import logging
import sys
from datetime import datetime
import os
from dotenv import load_dotenv
import asyncpg

# Add the agent module to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from agent.graph_utils import GraphitiClient, initialize_graph, close_graph
from agent.db_utils import initialize_database, close_database

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('graph_building.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


async def get_unprocessed_chunks(conn):
    """Get chunks that haven't been added to the knowledge graph yet."""
    # We know that 32 chunks were processed, so start from chunk 33 (index 32)
    query = """
    SELECT c.id, c.content, c.chunk_index, d.title, d.source
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE c.chunk_index >= 32
    ORDER BY c.chunk_index
    """
    
    rows = await conn.fetch(query)
    return rows


async def continue_graph_building():
    """Continue building the knowledge graph from existing chunks."""
    logger.info("Starting knowledge graph building continuation...")
    
    # Initialize database
    await initialize_database()
    
    # Get database connection
    conn = await asyncpg.connect(
        host=os.getenv('POSTGRES_HOST'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        user=os.getenv('POSTGRES_USER'),
        password=os.getenv('POSTGRES_PASSWORD'),
        database=os.getenv('POSTGRES_DB')
    )
    
    try:
        # Initialize graph
        await initialize_graph()
        
        # Initialize graph client
        graph_client = GraphitiClient()
        
        # Get unprocessed chunks
        chunks = await get_unprocessed_chunks(conn)
        total_chunks = len(chunks)
        logger.info(f"Found {total_chunks} chunks to process into knowledge graph")
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            chunk_index = chunk['chunk_index']
            content = chunk['content']
            doc_title = chunk['title']
            doc_source = chunk['source']
            
            try:
                start_time = datetime.now()
                
                # Create episode ID
                episode_id = f"{doc_source}_{chunk_index}_{start_time.timestamp()}"
                
                logger.info(f"Processing chunk {chunk_index} ({i+1}/{total_chunks})")
                
                # Add to knowledge graph using the same method as ingestion
                result = await graph_client.add_episode(
                    episode_id=episode_id,
                    content=content,
                    source=f"{doc_title} - Chunk {chunk_index}",
                    timestamp=start_time,
                    metadata={
                        "document_title": doc_title,
                        "chunk_index": chunk_index,
                        "document_source": doc_source
                    }
                )
                
                elapsed = (datetime.now() - start_time).total_seconds()
                logger.info(f"✓ Processed chunk {chunk_index} in {elapsed:.1f}s ({i+1}/{total_chunks})")
                
                # Log progress every 10 chunks
                if (i + 1) % 10 == 0:
                    progress = ((i + 1) / total_chunks) * 100
                    logger.info(f"Progress: {progress:.1f}% complete ({i+1}/{total_chunks} chunks)")
                    
            except Exception as e:
                logger.error(f"Error processing chunk {chunk_index}: {e}")
                # Continue with next chunk
                continue
        
        # Final summary
        logger.info(f"Knowledge graph building complete! Processed {total_chunks} chunks.")
        
        # Get final stats
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        
        with driver.session() as session:
            entity_count = session.run('MATCH (n:Entity) RETURN COUNT(n) as count').single()['count']
            rel_count = session.run('MATCH ()-[r:RELATES_TO]->() RETURN COUNT(r) as count').single()['count']
            episode_count = session.run('MATCH (e:Episodic) RETURN COUNT(e) as count').single()['count']
            
            logger.info(f"Final graph stats: {entity_count} entities, {rel_count} relationships, {episode_count} episodes")
        
        driver.close()
        
    except Exception as e:
        logger.error(f"Fatal error in graph building: {e}")
        raise
    finally:
        await conn.close()
        await close_graph()
        await close_database()


if __name__ == "__main__":
    logger.info("Knowledge graph building script started")
    asyncio.run(continue_graph_building())
