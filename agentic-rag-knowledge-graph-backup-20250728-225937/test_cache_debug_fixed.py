"""
Fixed debug version of cache test with correct parameter order.
"""

import asyncio
import logging
import time
import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')

from agent.experimental_cache_manager import QueryCache, get_cache, cached_search

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def simple_search(query: str, **kwargs):
    """Simple search function that takes time."""
    logger.info(f"simple_search called with query: {query}")
    await asyncio.sleep(0.1)  # Simulate work
    return {"query": query, "results": ["Result 1", "Result 2"], "metadata": kwargs}

async def test_cache_functionality():
    """Test cache operations with correct parameter order."""
    cache = await get_cache()
    
    # Test direct cache operations
    logger.info("=== Testing Direct Cache Operations ===")
    
    # Set a value with correct parameter order: query_text, value, embedding, params
    test_value = {"results": ["cached result"], "score": 0.95}
    success = await cache.set("test_query", test_value, None, None)
    logger.info(f"Set cache value: {success}")
    
    # Get the value
    result = await cache.get("test_query", None, None)
    logger.info(f"Got cache value: {result}")
    
    # Test with decorator
    logger.info("\n=== Testing With Decorator ===")
    decorated_search = cached_search(ttl_seconds=60)(simple_search)
    
    # First call
    start = time.time()
    result1 = await decorated_search("decorated query", k=5, threshold=0.8)
    duration1 = time.time() - start
    logger.info(f"First call took {duration1:.3f}s")
    
    # Second call (should be cached)
    start = time.time()
    result2 = await decorated_search("decorated query", k=5, threshold=0.8)
    duration2 = time.time() - start
    logger.info(f"Second call took {duration2:.3f}s")
    
    if duration2 < duration1 * 0.5:
        logger.info(f"✓ Cache working! Speed improvement: {duration1/duration2:.1f}x")
    else:
        logger.error(f"✗ Cache not working properly. Speed improvement: {duration1/duration2:.1f}x")
    
    # Test with different parameters (should not use cache)
    start = time.time()
    result3 = await decorated_search("decorated query", k=10, threshold=0.8)
    duration3 = time.time() - start
    logger.info(f"Third call with different params took {duration3:.3f}s")
    
    # Clear cache and test again
    await cache.clear()
    logger.info("\n=== After Cache Clear ===")
    
    start = time.time()
    result4 = await decorated_search("decorated query", k=5, threshold=0.8)
    duration4 = time.time() - start
    logger.info(f"Call after clear took {duration4:.3f}s (should be slow again)")

asyncio.run(test_cache_functionality())
