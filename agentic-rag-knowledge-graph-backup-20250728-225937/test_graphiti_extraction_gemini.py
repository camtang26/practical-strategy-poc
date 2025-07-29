#!/usr/bin/env python3
"""
Test entity and relationship extraction from Practical Strategy book using Graphiti with Gemini.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone
from agent.graph_utils import GraphitiClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Override embedding provider for Graphiti to use Gemini
os.environ['EMBEDDING_PROVIDER'] = 'gemini'
os.environ['EMBEDDING_MODEL'] = 'embedding-001'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Test Graphiti entity extraction with book content using Gemini."""
    
    # Initialize Graphiti client
    logger.info("Initializing Graphiti client with Gemini LLM and embeddings...")
    graph_client = GraphitiClient()
    
    try:
        # Initialize connection
        await graph_client.initialize()
        logger.info("Graphiti initialized successfully")
        
        # Clear existing graph data for clean test
        logger.info("Clearing existing graph data...")
        await graph_client.clear_graph()
        logger.info("Graph cleared")
        
        # Read sample content from the book
        with open('documents/practical_strategy_book.md', 'r') as f:
            content = f.read()
        
        # Extract a meaningful section about the 6 Myths of Strategy
        start_idx = content.find("## 2.3. The 6 Myths of Strategy")
        end_idx = content.find("### Myth 2:", start_idx)
        if end_idx == -1:
            end_idx = start_idx + 2000  # Take 2000 chars if Myth 2 not found
        
        sample_content = content[start_idx:end_idx].strip()
        logger.info(f"Extracted sample content ({len(sample_content)} chars)")
        logger.info(f"Content preview: {sample_content[:200]}...")
        
        # Add the episode to the graph
        episode_id = f"practical_strategy_myths_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        logger.info(f"Adding episode: {episode_id}")
        
        await graph_client.add_episode(
            episode_id=episode_id,
            content=sample_content,
            source="Practical Strategy Book - Section 2.3: The 6 Myths of Strategy",
            timestamp=datetime.now(timezone.utc),
        )
        
        logger.info("Episode added successfully")
        
        # Give it a moment to process
        await asyncio.sleep(2)
        
        # Query the graph to see what entities were extracted
        logger.info("\n=== Testing entity extraction ===")
        
        # Search for strategy-related entities
        search_queries = [
            "strategy",
            "myths",
            "strategy development",
            "strategy implementation",
            "management"
        ]
        
        for query in search_queries:
            logger.info(f"\nSearching for: '{query}'")
            results = await graph_client.search(query)
            
            if results.get('entities'):
                logger.info(f"Found {len(results['entities'])} entities:")
                for entity in results['entities'][:3]:  # Show top 3
                    logger.info(f"  - {entity.get('name', 'Unknown')} ({entity.get('type', 'Unknown')})")
                    if entity.get('summary'):
                        logger.info(f"    Summary: {entity.get('summary')[:100]}...")
            else:
                logger.info("  No entities found")
            
            if results.get('relationships'):
                logger.info(f"Found {len(results['relationships'])} relationships:")
                for rel in results['relationships'][:3]:  # Show top 3
                    logger.info(f"  - {rel.get('type', 'Unknown')}: {rel.get('source', 'Unknown')} -> {rel.get('target', 'Unknown')}")
                    if rel.get('summary'):
                        logger.info(f"    Summary: {rel.get('summary')[:100]}...")
        
        # Get health status
        health = await graph_client.health_check()
        logger.info(f"\nGraph health status: {health}")
        
        # Get relationships for specific entities
        logger.info("\n=== Testing relationship retrieval ===")
        if results.get('entities') and len(results['entities']) > 0:
            first_entity = results['entities'][0].get('name', '')
            if first_entity:
                logger.info(f"\nGetting relationships for entity: {first_entity}")
                relationships = await graph_client.get_entity_relationships(first_entity)
                
                if relationships.get('relationships'):
                    logger.info(f"Found {len(relationships['relationships'])} relationships:")
                    for rel in relationships['relationships'][:5]:  # Show top 5
                        logger.info(f"  - {rel.get('type', 'Unknown')}: {rel.get('source', 'Unknown')} -> {rel.get('target', 'Unknown')}")
                else:
                    logger.info("  No relationships found")
        
        logger.info("\n=== Entity extraction test completed successfully! ===")
        
    except Exception as e:
        logger.error(f"Error during testing: {e}", exc_info=True)
    finally:
        # Close the connection
        await graph_client.close()
        logger.info("Graphiti connection closed")
        
        # Restore original embedding provider
        os.environ['EMBEDDING_PROVIDER'] = 'jina'
        os.environ['EMBEDDING_MODEL'] = 'jina-embeddings-v4'

if __name__ == "__main__":
    asyncio.run(main())
