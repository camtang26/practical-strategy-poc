"""
Debug version of cache test to understand why caching isn't working.
"""

import asyncio
import logging
import time
import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')

from agent.experimental_cache_manager import QueryCache, get_cache, cached_search

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def simple_search(query: str, **kwargs):
    """Simple search function that takes time."""
    logger.debug(f"simple_search called with query: {query}")
    await asyncio.sleep(0.1)  # Simulate work
    return {"query": query, "results": ["Result 1", "Result 2"]}

async def test_cache_manually():
    """Test cache operations manually."""
    cache = await get_cache()
    
    # Test direct cache operations
    logger.info("=== Testing Direct Cache Operations ===")
    
    # Set a value
    await cache.set("test_query", None, {"results": ["cached result"]})
    logger.info("Set cache value")
    
    # Get the value
    result = await cache.get("test_query", None)
    logger.info(f"Got cache value: {result}")
    
    # Test with decorator
    logger.info("\n=== Testing With Decorator ===")
    decorated_search = cached_search()(simple_search)
    
    # First call
    start = time.time()
    result1 = await decorated_search("decorated query")
    duration1 = time.time() - start
    logger.info(f"First call took {duration1:.3f}s, result: {result1}")
    
    # Second call (should be cached)
    start = time.time()
    result2 = await decorated_search("decorated query")
    duration2 = time.time() - start
    logger.info(f"Second call took {duration2:.3f}s, result: {result2}")
    
    logger.info(f"Speed improvement: {duration1/duration2:.1f}x")
    
    # Check cache stats
    stats = await cache.get_stats()
    logger.info(f"Cache stats: {stats}")

asyncio.run(test_cache_manually())
