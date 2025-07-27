"""
Unit tests for experimental_cache_manager.py
Tests LRU cache, memory limits, TTL, and cache decorators.
"""

import pytest
import asyncio
import time
import hashlib
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')

from agent.experimental_cache_manager import (
    CacheStatistics, QueryCache, EmbeddingCache,
    get_cache, cached_search, clear_cache, get_cache_stats,
    warm_cache_with_common_queries, get_embedding_cache
)


class TestCacheStatistics:
    """Test suite for cache statistics tracking."""
    
    def test_initialization(self):
        """Test statistics initialization."""
        stats = CacheStatistics()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.total_requests == 0
        assert stats.cache_saves_ms == 0.0
        assert stats.start_time > 0
    
    def test_record_hit(self):
        """Test recording cache hits."""
        stats = CacheStatistics()
        stats.record_hit(100.5)
        
        assert stats.hits == 1
        assert stats.total_requests == 1
        assert stats.cache_saves_ms == 100.5
    
    def test_record_miss(self):
        """Test recording cache misses."""
        stats = CacheStatistics()
        stats.record_miss()
        
        assert stats.misses == 1
        assert stats.total_requests == 1
        assert stats.cache_saves_ms == 0.0
    
    def test_get_stats(self):
        """Test getting comprehensive statistics."""
        stats = CacheStatistics()
        stats.record_hit(100)
        stats.record_hit(200)
        stats.record_miss()
        
        result = stats.get_stats()
        
        assert result['hits'] == 2
        assert result['misses'] == 1
        assert result['total_requests'] == 3
        assert result['hit_rate'] == pytest.approx(66.67, 0.1)
        assert result['total_time_saved_seconds'] == 0.3
        assert result['avg_time_saved_per_hit_ms'] == 150
        assert result['uptime_seconds'] > 0


class TestQueryCache:
    """Test suite for the query cache system."""
    
    @pytest.fixture
    def cache(self):
        """Create a test cache instance."""
        return QueryCache(max_size=10, ttl_seconds=60, max_memory_mb=1)
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test cache initialization."""
        cache = QueryCache(max_size=100, ttl_seconds=3600, max_memory_mb=50)
        assert cache.max_size == 100
        assert cache.ttl_seconds == 3600
        assert cache.max_memory_mb == 50
        assert len(cache._cache) == 0
        assert cache._total_memory_bytes == 0
    
    def test_generate_cache_key_basic(self, cache):
        """Test basic cache key generation."""
        key1 = cache._generate_cache_key("test query")
        key2 = cache._generate_cache_key("test query")
        key3 = cache._generate_cache_key("different query")
        
        assert key1 == key2  # Same query produces same key
        assert key1 != key3  # Different queries produce different keys
        assert len(key1) == 64  # SHA256 hex digest length
    
    def test_generate_cache_key_with_embedding(self, cache):
        """Test cache key generation with embeddings."""
        embedding = [0.1, 0.2, 0.3] * 10  # 30 values
        key1 = cache._generate_cache_key("test", embedding=embedding)
        key2 = cache._generate_cache_key("test", embedding=embedding)
        key3 = cache._generate_cache_key("test")  # No embedding
        
        assert key1 == key2
        assert key1 != key3  # With vs without embedding
    
    def test_generate_cache_key_with_params(self, cache):
        """Test cache key generation with parameters."""
        params1 = {"k": 5, "threshold": 0.7}
        params2 = {"k": 5, "threshold": 0.7}
        params3 = {"k": 10, "threshold": 0.7}
        
        key1 = cache._generate_cache_key("test", params=params1)
        key2 = cache._generate_cache_key("test", params=params2)
        key3 = cache._generate_cache_key("test", params=params3)
        
        assert key1 == key2
        assert key1 != key3  # Different params
    
    def test_estimate_size(self, cache):
        """Test object size estimation."""
        # Small object
        small_obj = {"key": "value"}
        small_size = cache._estimate_size(small_obj)
        assert small_size > 0
        assert small_size < 1000
        
        # Large object
        large_obj = {"data": "x" * 10000}
        large_size = cache._estimate_size(large_obj)
        assert large_size > small_size
        assert large_size > 10000
    
    @pytest.mark.asyncio
    async def test_get_set_basic(self, cache):
        """Test basic get/set operations."""
        # Initially empty
        result = await cache.get("test query")
        assert result is None
        assert cache.stats.misses == 1
        
        # Set value
        await cache.set("test query", {"result": "test"})
        
        # Get value
        result = await cache.get("test query")
        assert result == {"result": "test"}
        assert cache.stats.hits == 1
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, cache):
        """Test TTL-based expiration."""
        cache.ttl_seconds = 0.1  # 100ms TTL
        
        await cache.set("test query", {"result": "test"})
        
        # Immediate get should work
        result = await cache.get("test query")
        assert result == {"result": "test"}
        
        # Wait for expiration
        await asyncio.sleep(0.2)
        
        # Should be expired
        result = await cache.get("test query")
        assert result is None
        assert len(cache._cache) == 0  # Should be evicted
    
    @pytest.mark.asyncio
    async def test_size_limit_eviction(self, cache):
        """Test eviction based on cache size limit."""
        cache.max_size = 3
        
        # Fill cache
        for i in range(5):
            await cache.set(f"query {i}", {"result": i})
        
        # Should only have 3 items (LRU eviction)
        assert len(cache._cache) == 3
        
        # Oldest items should be evicted
        assert await cache.get("query 0") is None
        assert await cache.get("query 1") is None
        assert await cache.get("query 4") is not None
    
    @pytest.mark.asyncio
    async def test_memory_limit_eviction(self, cache):
        """Test eviction based on memory limit."""
        cache.max_memory_mb = 0.001  # 1KB limit
        
        # Add large objects
        large_data = "x" * 1000  # ~1KB
        await cache.set("query 1", {"data": large_data})
        await cache.set("query 2", {"data": large_data})
        
        # First should be evicted due to memory pressure
        assert await cache.get("query 1") is None
        assert await cache.get("query 2") is not None
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self, cache):
        """Test LRU eviction policy."""
        cache.max_size = 3
        
        # Fill cache
        await cache.set("query 1", {"result": 1})
        await cache.set("query 2", {"result": 2})
        await cache.set("query 3", {"result": 3})
        
        # Access query 1 to make it recently used
        await cache.get("query 1")
        
        # Add new item - should evict query 2 (least recently used)
        await cache.set("query 4", {"result": 4})
        
        assert await cache.get("query 1") is not None
        assert await cache.get("query 2") is None  # Evicted
        assert await cache.get("query 3") is not None
        assert await cache.get("query 4") is not None
    
    @pytest.mark.asyncio
    async def test_clear_cache(self, cache):
        """Test clearing entire cache."""
        # Add items
        await cache.set("query 1", {"result": 1})
        await cache.set("query 2", {"result": 2})
        
        assert len(cache._cache) == 2
        assert cache._total_memory_bytes > 0
        
        # Clear
        await cache.clear()
        
        assert len(cache._cache) == 0
        assert cache._total_memory_bytes == 0
        assert len(cache._access_times) == 0
    
    @pytest.mark.asyncio
    async def test_query_pattern_tracking(self, cache):
        """Test query pattern tracking."""
        await cache.set("what is strategic planning", {"result": 1})
        await cache.set("what is business strategy", {"result": 2})
        await cache.set("how to implement strategy", {"result": 3})
        
        # Check patterns
        assert cache._query_patterns["what is strategic"] == 1
        assert cache._query_patterns["what is business"] == 1
        assert cache._query_patterns["how to implement"] == 1
    
    @pytest.mark.asyncio
    async def test_get_statistics(self, cache):
        """Test comprehensive statistics."""
        await cache.set("query 1", {"result": 1})
        await cache.get("query 1")  # Hit
        await cache.get("query 2")  # Miss
        
        stats = cache.get_statistics()
        
        assert stats['hits'] == 1
        assert stats['misses'] == 1
        assert stats['hit_rate'] == 50.0
        assert stats['cache_size'] == 1
        assert stats['memory_usage_mb'] >= 0
        assert stats['memory_limit_mb'] == 1
        assert len(stats['top_patterns']) >= 0
    
    @pytest.mark.asyncio
    async def test_warm_cache(self, cache):
        """Test cache warming."""
        common_queries = [
            ("query 1", {"result": 1}),
            ("query 2", {"result": 2}),
            ("query 3", {"result": 3})
        ]
        
        await cache.warm_cache(common_queries)
        
        assert len(cache._cache) == 3
        assert await cache.get("query 1") == {"result": 1}
        assert await cache.get("query 2") == {"result": 2}
        assert await cache.get("query 3") == {"result": 3}


class TestGlobalCache:
    """Test global cache instance and functions."""
    
    def test_get_cache_singleton(self):
        """Test global cache is a singleton."""
        cache1 = get_cache()
        cache2 = get_cache()
        assert cache1 is cache2
    
    @pytest.mark.asyncio
    async def test_clear_cache_global(self):
        """Test global cache clearing."""
        cache = get_cache()
        await cache.set("test", {"result": "test"})
        
        await clear_cache()
        
        assert await cache.get("test") is None
    
    @pytest.mark.asyncio
    async def test_get_cache_stats_global(self):
        """Test getting global cache stats."""
        cache = get_cache()
        await cache.set("test", {"result": "test"})
        
        stats = await get_cache_stats()
        
        assert 'cache_size' in stats
        assert stats['cache_size'] >= 1
    
    @pytest.mark.asyncio
    async def test_warm_cache_with_common_queries_global(self):
        """Test warming global cache with common queries."""
        cache = get_cache()
        await cache.clear()
        
        await warm_cache_with_common_queries()
        
        # Should have some common queries cached
        assert len(cache._cache) > 0
        assert await cache.get("what is strategic planning") is not None


class TestCachedSearchDecorator:
    """Test the cached_search decorator."""
    
    @pytest.mark.asyncio
    async def test_cached_search_basic(self):
        """Test basic caching with decorator."""
        call_count = 0
        
        @cached_search()
        async def search_function(query: str):
            nonlocal call_count
            call_count += 1
            return {"result": f"Result for {query}"}
        
        # First call - should execute
        result1 = await search_function("test query")
        assert call_count == 1
        assert result1 == {"result": "Result for test query"}
        
        # Second call - should use cache
        result2 = await search_function("test query")
        assert call_count == 1  # Not incremented
        assert result2 == result1
    
    @pytest.mark.asyncio
    async def test_cached_search_with_embedding(self):
        """Test caching with embeddings."""
        @cached_search()
        async def search_with_embedding(query: str, embedding: list):
            return {"query": query, "embedding_len": len(embedding)}
        
        embedding = [0.1, 0.2, 0.3]
        
        # These should use different cache keys
        result1 = await search_with_embedding("test", embedding)
        result2 = await search_with_embedding("test", [0.4, 0.5, 0.6])
        
        assert result1 != result2
    
    @pytest.mark.asyncio
    async def test_cached_search_slow_queries_only(self):
        """Test that only slow queries are cached."""
        call_count = 0
        
        @cached_search()
        async def fast_search(query: str):
            nonlocal call_count
            call_count += 1
            # Fast query - should not be cached
            return {"result": query}
        
        @cached_search()
        async def slow_search(query: str):
            nonlocal call_count
            call_count += 1
            # Slow query - should be cached
            await asyncio.sleep(0.6)
            return {"result": query}
        
        # Fast queries should not be cached
        await fast_search("fast")
        await fast_search("fast")
        assert call_count == 2  # Called twice
        
        # Reset counter
        call_count = 0
        
        # Slow queries should be cached
        await slow_search("slow")
        await slow_search("slow")
        assert call_count == 1  # Called only once


class TestEmbeddingCache:
    """Test the embedding cache system."""
    
    def test_embedding_cache_initialization(self):
        """Test embedding cache initialization."""
        cache = EmbeddingCache(max_size=100)
        assert len(cache._cache) == 0
    
    def test_get_embedding_key(self):
        """Test embedding key generation."""
        cache = EmbeddingCache()
        key1 = cache.get_embedding_key("test text")
        key2 = cache.get_embedding_key("test text")
        key3 = cache.get_embedding_key("different text")
        
        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 32  # MD5 hex digest
    
    def test_get_set_embedding(self):
        """Test getting and setting embeddings."""
        cache = EmbeddingCache()
        embedding = [0.1, 0.2, 0.3]
        
        # Initially not cached
        assert cache.get("test text") is None
        
        # Set embedding
        cache.set("test text", embedding)
        
        # Should be cached
        assert cache.get("test text") == embedding
    
    def test_clear_embedding_cache(self):
        """Test clearing embedding cache."""
        cache = EmbeddingCache()
        cache.set("test", [0.1, 0.2])
        
        cache.clear()
        
        assert cache.get("test") is None
        assert len(cache._cache) == 0
    
    def test_get_embedding_cache_global(self):
        """Test global embedding cache instance."""
        cache1 = get_embedding_cache()
        cache2 = get_embedding_cache()
        assert cache1 is cache2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
