"""
Test cache manager with various query patterns and failure scenarios.
"""

import asyncio
import logging
import time
import random
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')
from agent.experimental_cache_manager import (
    QueryCache, get_cache, cached_search, get_cache_stats,
    clear_cache, warm_cache_with_common_queries, get_embedding_cache,
    ErrorHandlingMode, CacheError
)


async def simulate_search_function(query: str, embedding: List[float] = None, **kwargs):
    """Simulate a search function that takes time to execute."""
    # Simulate processing time based on query length
    processing_time = 0.6  # 600ms to trigger caching
    await asyncio.sleep(processing_time)
    
    # Return mock search results
    return {
        "query": query,
        "results": [f"Result {i} for '{query}'" for i in range(5)],
        "processing_time": processing_time
    }


async def test_basic_caching():
    """Test basic cache operations."""
    logger.info("\n=== Testing Basic Cache Operations ===")
    
    cache = await get_cache()
    
    # Test 1: Cache miss and set
    query = "What is strategic planning?"
    embedding = [random.random() for _ in range(128)]
    
    result1 = await cache.get(query, embedding)
    assert result1 is None, "Cache should be empty initially"
    logger.info("✓ Initial cache miss confirmed")
    
    # Store result
    mock_result = {"answer": "Strategic planning is..."}
    success = await cache.set(query, mock_result, embedding)
    assert success, "Cache set should succeed"
    logger.info("✓ Cache set successful")
    
    # Test 2: Cache hit
    result2 = await cache.get(query, embedding)
    assert result2 == mock_result, "Cached result should match"
    logger.info("✓ Cache hit successful")
    
    # Test 3: Different query = cache miss
    result3 = await cache.get("Different query", embedding)
    assert result3 is None, "Different query should miss"
    logger.info("✓ Different query causes cache miss")
    
    # Test 4: Clear cache
    success = await cache.clear()
    assert success, "Cache clear should succeed"
    result4 = await cache.get(query, embedding)
    assert result4 is None, "Cache should be empty after clear"
    logger.info("✓ Cache cleared successfully")


async def test_cache_decorator():
    """Test the @cached_search decorator."""
    logger.info("\n=== Testing Cache Decorator ===")
    
    # Apply decorator to test function
    cached_search_func = cached_search()(simulate_search_function)
    
    # First call - should execute function
    start = time.time()
    result1 = await cached_search_func("test query for caching")
    duration1 = time.time() - start
    logger.info(f"First call took {duration1:.3f}s")
    
    # Second call - should use cache
    start = time.time()
    result2 = await cached_search_func("test query for caching")
    duration2 = time.time() - start
    logger.info(f"Second call took {duration2:.3f}s")
    
    # Verify caching worked
    assert result1 == result2, "Results should match"
    assert duration2 < duration1 * 0.1, "Cached call should be much faster"
    logger.info("✓ Decorator caching working correctly")


async def test_concurrent_access():
    """Test cache behavior under concurrent access."""
    logger.info("\n=== Testing Concurrent Access ===")
    
    cache = await get_cache()
    
    async def concurrent_operation(query_id: int):
        query = f"Concurrent query {query_id}"
        value = f"Result for query {query_id}"
        
        # Try to set and get concurrently
        await cache.set(query, value)
        result = await cache.get(query)
        return result == value
    
    # Run many concurrent operations
    tasks = [concurrent_operation(i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    
    # All operations should succeed
    success_rate = sum(results) / len(results)
    logger.info(f"Concurrent success rate: {success_rate * 100:.1f}%")
    assert success_rate == 1.0, "All concurrent operations should succeed"
    logger.info("✓ Concurrent access handled correctly")


async def test_memory_limits():
    """Test cache memory limit enforcement."""
    logger.info("\n=== Testing Memory Limits ===")
    
    # Create cache with small memory limit
    cache = QueryCache(max_size=10, max_memory_mb=1)  # 1MB limit
    
    # Try to fill cache beyond memory limit
    large_value = "x" * 100000  # ~100KB per entry
    
    added_count = 0
    for i in range(20):  # Try to add 2MB worth
        query = f"Large query {i}"
        success = await cache.set(query, large_value)
        if success:
            added_count += 1
    
    logger.info(f"Added {added_count} entries before hitting memory limit")
    
    # Check memory usage
    stats = await cache.get_statistics()
    logger.info(f"Memory usage: {stats['memory_usage_mb']:.2f} MB")
    assert stats['memory_usage_mb'] <= 1.1, "Memory limit should be enforced"
    logger.info("✓ Memory limits enforced correctly")


async def test_ttl_expiration():
    """Test TTL expiration of cached items."""
    logger.info("\n=== Testing TTL Expiration ===")
    
    # Create cache with short TTL
    cache = QueryCache(ttl_seconds=1)  # 1 second TTL
    
    # Add item
    query = "Expiring query"
    value = "This will expire"
    await cache.set(query, value)
    
    # Immediate get should work
    result1 = await cache.get(query)
    assert result1 == value, "Immediate get should work"
    logger.info("✓ Item retrieved before expiration")
    
    # Wait for expiration
    await asyncio.sleep(1.5)
    
    # Should be expired now
    result2 = await cache.get(query)
    assert result2 is None, "Item should be expired"
    logger.info("✓ Item expired after TTL")


async def test_error_handling():
    """Test cache error handling and circuit breaker."""
    logger.info("\n=== Testing Error Handling ===")
    
    # Test with different error modes
    for mode in [ErrorHandlingMode.SILENT, ErrorHandlingMode.WARN]:
        logger.info(f"\nTesting {mode.value} mode:")
        cache = QueryCache(error_mode=mode)
        
        # Test with invalid inputs
        result = await cache.get(None)  # Invalid query
        assert result is None, "Should handle None gracefully"
        
        result = await cache.get("")  # Empty query
        assert result is None, "Should handle empty string gracefully"
        
        # Test with unpicklable object
        class UnpicklableClass:
            def __reduce__(self):
                raise TypeError("Cannot pickle this")
        
        obj = UnpicklableClass()
        success = await cache.set("test", obj)
        # Should handle gracefully based on mode
        logger.info(f"✓ {mode.value} mode handled errors gracefully")


async def test_circuit_breaker():
    """Test circuit breaker functionality."""
    logger.info("\n=== Testing Circuit Breaker ===")
    
    cache = QueryCache(error_mode=ErrorHandlingMode.WARN)
    
    # Force many errors to trip circuit breaker
    # We'll use an internal method to simulate errors
    for i in range(15):  # More than max_consecutive_errors (10)
        cache._handle_error(Exception("Simulated error"), "test operation")
    
    # Check circuit breaker state
    assert cache._circuit_open, "Circuit breaker should be open"
    logger.info("✓ Circuit breaker opened after repeated errors")
    
    # Operations should fail fast when circuit is open
    result = await cache.get("any query")
    assert result is None, "Should fail fast when circuit is open"
    logger.info("✓ Circuit breaker prevents operations when open")
    
    # Successful operation should reset
    cache._reset_error_count()
    assert not cache._circuit_open, "Circuit breaker should reset"
    logger.info("✓ Circuit breaker resets after success")


async def test_cache_statistics():
    """Test cache statistics tracking."""
    logger.info("\n=== Testing Cache Statistics ===")
    
    cache = await get_cache()
    await cache.clear()  # Start fresh
    
    # Perform various operations
    queries = [
        "What is strategy?"
        "How to plan?"
        "What is strategy?",  # Duplicate for hit
        "Implementation steps"
    ]
    
    for query in queries:
        # First time miss, second time hit
        await cache.get(query)
        await cache.set(query, f"Answer to: {query}")
        await cache.get(query)
    
    # Get statistics
    stats = await cache.get_statistics()
    
    logger.info(f"Cache statistics:")
    logger.info(f"  Hits: {stats['hits']}")
    logger.info(f"  Misses: {stats['misses']}")
    logger.info(f"  Hit rate: {stats['hit_rate']:.1f}%")
    logger.info(f"  Cache size: {stats['cache_size']}")
    logger.info(f"  Memory usage: {stats['memory_usage_mb']:.3f} MB")
    
    assert stats['hits'] > 0, "Should have cache hits"
    assert stats['misses'] > 0, "Should have cache misses"
    assert stats['cache_size'] > 0, "Should have cached items"
    logger.info("✓ Statistics tracking working correctly")


async def test_embedding_cache():
    """Test the specialized embedding cache."""
    logger.info("\n=== Testing Embedding Cache ===")
    
    emb_cache = await get_embedding_cache()
    
    # Test basic operations
    text = "Sample text for embedding"
    embedding = [random.random() for _ in range(128)]
    
    # Initially empty
    result = await emb_cache.get(text)
    assert result is None, "Should be empty initially"
    
    # Set embedding
    success = await emb_cache.set(text, embedding)
    assert success, "Should set successfully"
    
    # Get embedding
    result = await emb_cache.get(text)
    assert result == embedding, "Should retrieve same embedding"
    logger.info("✓ Embedding cache working correctly")
    
    # Test LRU eviction
    for i in range(5100):  # More than max_size (5000)
        await emb_cache.set(f"Text {i}", [i] * 128)
    
    # Original should be evicted
    result = await emb_cache.get(text)
    assert result is None, "Original should be evicted"
    logger.info("✓ LRU eviction working")


async def test_cache_warming():
    """Test cache warming functionality."""
    logger.info("\n=== Testing Cache Warming ===")
    
    cache = await get_cache()
    await cache.clear()
    
    # Warm cache with common queries
    success = await warm_cache_with_common_queries()
    assert success, "Cache warming should succeed"
    
    # Check that common queries are cached
    stats_before = await cache.get_statistics()
    
    # Try a common query
    result = await cache.get("what is strategic planning")
    assert result is not None, "Common query should be cached"
    
    stats_after = await cache.get_statistics()
    assert stats_after['hits'] > stats_before['hits'], "Should have cache hit"
    logger.info("✓ Cache warming successful")


async def test_pattern_tracking():
    """Test query pattern tracking."""
    logger.info("\n=== Testing Pattern Tracking ===")
    
    cache = await get_cache()
    await cache.clear()
    
    # Generate queries with patterns
    patterns = [
        "what is strategic planning"
        "what is business strategy"
        "what is competitive advantage"
        "how to implement strategy"
        "how to measure success"
        "define strategic goals"
        "define key metrics"
    ]
    
    # Cache these queries
    for query in patterns:
        await cache.set(query, f"Answer to: {query}")
        await cache.get(query)  # Access to track pattern
    
    # Get statistics with patterns
    stats = await cache.get_statistics()
    top_patterns = stats.get('top_patterns', [])
    
    logger.info("Top query patterns:")
    for pattern, count in top_patterns[:5]:
        logger.info(f"  '{pattern}': {count} times")
    
    assert len(top_patterns) > 0, "Should track patterns"
    logger.info("✓ Pattern tracking working")


async def test_health_check():
    """Test cache health check functionality."""
    logger.info("\n=== Testing Health Check ===")
    
    cache = await get_cache()
    
    # Check health when healthy
    health = await cache.health_check()
    
    logger.info(f"Cache health: {health}")
    assert health['status'] in ['healthy', 'degraded', 'unhealthy'], "Should have valid status"
    assert 'memory_usage_percent' in health, "Should report memory usage"
    logger.info("✓ Health check working")


async def main():
    """Run all cache tests."""
    logger.info("Starting Cache Manager Pattern Tests")
    logger.info("=" * 50)
    
    try:
        # Run all tests
        await test_basic_caching()
        await test_cache_decorator()
        await test_concurrent_access()
        await test_memory_limits()
        await test_ttl_expiration()
        await test_error_handling()
        await test_circuit_breaker()
        await test_cache_statistics()
        await test_embedding_cache()
        await test_cache_warming()
        await test_pattern_tracking()
        await test_health_check()
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All cache tests completed successfully!")
        
        # Final statistics
        final_stats = await get_cache_stats()
        logger.info(f"\nFinal cache statistics:")
        logger.info(f"  Total requests: {final_stats.get('total_requests', 0)}")
        logger.info(f"  Hit rate: {final_stats.get('hit_rate', 0):.1f}%")
        logger.info(f"  Error rate: {final_stats.get('error_rate', 0):.1f}%")
        logger.info(f"  Health: {final_stats.get('health', 'unknown')}")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
