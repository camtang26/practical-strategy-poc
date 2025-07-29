"""
Build knowledge graph from existing document chunks in the database.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone
from agent.graph_utils import GraphitiClient
from agent.database import get_db_connection
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

async def build_graph_from_chunks():
    """Build knowledge graph from all chunks in the database."""
    try:
        # Initialize graph client
        logger.info("Initializing Graphiti client...")
        graph_client = GraphitiClient()
        await graph_client.initialize()
        
        # Get database connection
        logger.info("Connecting to database...")
        conn = await get_db_connection()
        
        # Get all chunks with their document info
        logger.info("Fetching chunks from database...")
        chunks = await conn.fetch("""
            SELECT 
                c.id, 
                c.content, 
                c.chunk_index,
                d.title as document_title,
                d.source as document_source
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            ORDER BY d.id, c.chunk_index
            LIMIT 10  -- Start with just 10 chunks for testing
        """)
        
        logger.info(f"Found {len(chunks)} chunks to process")
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {i+1}/{len(chunks)} from {chunk['document_title']}")
            
            # Create episode content
            episode_content = f"""
Document: {chunk['document_title']}
Source: {chunk['document_source']}
Chunk {chunk['chunk_index']}:

{chunk['content']}
"""
            
            try:
                # Add episode to graph
                episode = await graph_client.client.add_episode(
                    name=f"{chunk['document_title']}_chunk_{chunk['chunk_index']}",
                    episode_body=episode_content,
                    source=chunk['document_source'],
                    reference_time=datetime.now(timezone.utc),
                    source_description=f"Chunk {chunk['chunk_index']} from {chunk['document_title']}",
                    group_id="practical_strategy_book"
                )
                
                logger.info(f"Added episode: {episode.name}")
                
                # Small delay to avoid rate limits
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"Error processing chunk {i+1}: {str(e)}")
                continue
        
        # Close connections
        await conn.close()
        await graph_client.close()
        
        logger.info("Graph building complete!")
        
    except Exception as e:
        logger.error(f"Error building graph: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(build_graph_from_chunks())
