"""Simple test runner for experimental cache manager tests."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from unittest.mock import patch
import time

# Import test classes
from tests.test_experimental_cache_manager import (
    TestCacheStatistics, TestQueryCache, TestEmbeddingCache
)

async def run_async_tests():
    """Run async tests for cache manager."""
    print("Running experimental cache manager tests...\n")
    
    # Test 1: Cache Statistics
    print("1. Testing CacheStatistics...")
    try:
        stats_test = TestCacheStatistics()
        stats_test.test_initialization()
        stats_test.test_record_hit()
        stats_test.test_record_miss()
        stats_test.test_get_stats()
        print("✅ PASSED: All CacheStatistics tests\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 2: QueryCache initialization
    print("2. Testing QueryCache initialization...")
    try:
        await TestQueryCache().test_initialization()
        print("✅ PASSED: QueryCache initialization\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 3: Cache key generation
    print("3. Testing cache key generation...")
    try:
        from agent.experimental_cache_manager import QueryCache
        cache = QueryCache()
        key1 = cache._generate_cache_key("test query")
        key2 = cache._generate_cache_key("test query") 
        key3 = cache._generate_cache_key("different")
        
        assert key1 == key2, "Same query should produce same key"
        assert key1 != key3, "Different queries should produce different keys"
        assert len(key1) == 64, "SHA256 should be 64 chars"
        print("✅ PASSED: Cache key generation\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 4: Basic get/set operations
    print("4. Testing basic get/set operations...")
    try:
        cache = QueryCache()
        
        # Test miss
        result = await cache.get("test")
        assert result is None
        assert cache.stats.misses == 1
        
        # Test set
        await cache.set("test", {"data": "value"})
        
        # Test hit
        result = await cache.get("test")
        assert result == {"data": "value"}
        assert cache.stats.hits == 1
        
        print("✅ PASSED: Basic get/set operations\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 5: TTL expiration
    print("5. Testing TTL expiration...")
    try:
        cache = QueryCache(ttl_seconds=0.1)  # 100ms TTL
        
        await cache.set("test", {"data": "value"})
        
        # Immediate get should work
        result = await cache.get("test")
        assert result == {"data": "value"}
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Should be expired
        result = await cache.get("test")
        assert result is None
        
        print("✅ PASSED: TTL expiration\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 6: LRU eviction
    print("6. Testing LRU eviction...")
    try:
        cache = QueryCache(max_size=3)
        
        # Fill cache
        for i in range(5):
            await cache.set(f"query {i}", {"result": i})
        
        # Should only have 3 items
        assert len(cache._cache) == 3
        
        # Oldest should be evicted
        assert await cache.get("query 0") is None
        assert await cache.get("query 4") is not None
        
        print("✅ PASSED: LRU eviction\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 7: Memory limit eviction
    print("7. Testing memory limit eviction...")
    try:
        cache = QueryCache(max_memory_mb=0.001)  # 1KB limit
        
        large_data = "x" * 1000
        await cache.set("item1", {"data": large_data})
        await cache.set("item2", {"data": large_data})
        
        # First should be evicted
        assert await cache.get("item1") is None
        assert await cache.get("item2") is not None
        
        print("✅ PASSED: Memory limit eviction\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 8: EmbeddingCache
    print("8. Testing EmbeddingCache...")
    try:
        from agent.experimental_cache_manager import EmbeddingCache
        cache = EmbeddingCache()
        
        # Test empty get
        assert cache.get("test") is None
        
        # Test set/get
        embedding = [0.1, 0.2, 0.3]
        cache.set("test", embedding)
        assert cache.get("test") == embedding
        
        # Test clear
        cache.clear()
        assert cache.get("test") is None
        
        print("✅ PASSED: EmbeddingCache\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 9: Cache statistics
    print("9. Testing cache statistics...")
    try:
        cache = QueryCache()
        await cache.set("test1", {"data": 1})
        await cache.get("test1")  # Hit
        await cache.get("test2")  # Miss
        
        stats = cache.get_statistics()
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 50.0
        assert stats['cache_size'] == 1
        
        print("✅ PASSED: Cache statistics\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 10: Global cache functions
    print("10. Testing global cache functions...")
    try:
        from agent.experimental_cache_manager import (
            get_cache, clear_cache, get_cache_stats
        )
        
        # Test singleton
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2
        
        # Test operations
        await cache1.set("global_test", {"data": "test"})
        stats = await get_cache_stats()
        assert stats['cache_size'] >= 1
        
        await clear_cache()
        assert await cache1.get("global_test") is None
        
        print("✅ PASSED: Global cache functions\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")

def main():
    """Run all tests."""
    print("\n=== Cache Manager Test Suite ===\n")
    asyncio.run(run_async_tests())
    print("\n=== Test Summary ===")
    print("Tests completed. Check results above for any failures.")

if __name__ == "__main__":
    main()
