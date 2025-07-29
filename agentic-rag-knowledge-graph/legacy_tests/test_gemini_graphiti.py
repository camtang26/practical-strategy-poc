#!/usr/bin/env python3
"""
Test Gemini client initialization for Graphiti.
"""

import asyncio
import logging
from agent.graph_utils import GraphitiClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """Test Graphiti initialization with Gemini clients."""
    
    logger.info("Testing Graphiti initialization with Gemini clients...")
    
    # Initialize Graphiti client
    graph_client = GraphitiClient()
    
    try:
        # Initialize connection
        await graph_client.initialize()
        logger.info("✅ Graphiti initialized successfully!")
        
        # Check health
        health = await graph_client.health_check()
        logger.info(f"Health status: {health}")
        
        if health['status'] == 'healthy':
            logger.info("✅ Graphiti is healthy and ready!")
            logger.info(f"  - LLM Provider: {health['llm_provider']}")
            logger.info(f"  - Embedding Provider: {health['embedding_provider']}")
            logger.info(f"  - Embedding Dimensions: {health['embedding_dimensions']}")
        else:
            logger.error(f"❌ Graphiti is unhealthy: {health.get('error', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize Graphiti: {e}", exc_info=True)
    finally:
        # Close the connection
        await graph_client.close()
        logger.info("Graphiti connection closed")

if __name__ == "__main__":
    asyncio.run(main())
