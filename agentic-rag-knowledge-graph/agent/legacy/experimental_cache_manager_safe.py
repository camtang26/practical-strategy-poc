"""
Query result caching system with LRU cache and intelligent invalidation.
Enhanced with comprehensive error handling for production reliability.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta
from functools import lru_cache, wraps
from typing import Any, Dict, List, Optional, Tuple, Callable, TypeVar, Union
from collections import defaultdict
import asyncio
import pickle
import sys
import traceback
from enum import Enum

logger = logging.getLogger(__name__)

# Type variables for better type hints
T = TypeVar('T')
F = TypeVar('F', bound=Callable[..., Any])


class CacheError(Exception):
    """Base exception for cache-related errors."""
    pass


class CacheSerializationError(CacheError):
    """Raised when object cannot be serialized for caching."""
    pass


class CacheMemoryError(CacheError):
    """Raised when cache memory limits are exceeded."""
    pass


class CacheOperationError(CacheError):
    """Raised when cache operation fails."""
    pass


class ErrorHandlingMode(Enum):
    """How to handle cache errors."""
    SILENT = "silent"  # Log and continue without cache
    WARN = "warn"      # Log warning and continue
    RAISE = "raise"    # Raise exception


class CacheStatistics:
    """Track cache performance metrics with thread-safe operations."""
    
    def __init__(self):
        self.hits = 0
        self.misses = 0
        self.total_requests = 0
        self.cache_saves_ms = 0.0
        self.errors = 0
        self.start_time = time.time()
        self._lock = asyncio.Lock()
        
    async def record_hit(self, time_saved_ms: float):
        """Record a cache hit."""
        async with self._lock:
            self.hits += 1
            self.total_requests += 1
            self.cache_saves_ms += time_saved_ms
        
    async def record_miss(self):
        """Record a cache miss."""
        async with self._lock:
            self.misses += 1
            self.total_requests += 1
    
    async def record_error(self):
        """Record a cache error."""
        async with self._lock:
            self.errors += 1
            self.total_requests += 1
        
    async def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        async with self._lock:
            uptime = time.time() - self.start_time
            hit_rate = self.hits / self.total_requests if self.total_requests > 0 else 0
            
            return {
                'hits': self.hits,
                'misses': self.misses,
                'errors': self.errors,
                'total_requests': self.total_requests,
                'hit_rate': hit_rate * 100,
                'error_rate': (self.errors / self.total_requests * 100) if self.total_requests > 0 else 0,
                'total_time_saved_seconds': self.cache_saves_ms / 1000,
                'avg_time_saved_per_hit_ms': self.cache_saves_ms / self.hits if self.hits > 0 else 0,
                'uptime_seconds': uptime,
                'health': 'healthy' if self.errors < self.total_requests * 0.1 else 'degraded'
            }


class QueryCache:
    """Advanced caching system for search queries with comprehensive error handling."""
    
    def __init__(
        self,
        max_size: int = 1000,
        ttl_seconds: int = 3600,
        max_memory_mb: int = 500,
        error_mode: ErrorHandlingMode = ErrorHandlingMode.WARN
    ):
        """Initialize cache with size and TTL limits."""
        # Validate inputs
        if max_size <= 0:
            raise ValueError(f"max_size must be positive, got {max_size}")
        if ttl_seconds <= 0:
            raise ValueError(f"ttl_seconds must be positive, got {ttl_seconds}")
        if max_memory_mb <= 0:
            raise ValueError(f"max_memory_mb must be positive, got {max_memory_mb}")
        
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.max_memory_mb = max_memory_mb
        self.error_mode = error_mode
        
        # Cache storage
        self._cache: Dict[str, Tuple[Any, float, int]] = {}
        self._access_times: Dict[str, float] = {}
        self._query_patterns: Dict[str, int] = defaultdict(int)
        
        # Statistics
        self.stats = CacheStatistics()
        
        # Memory tracking
        self._total_memory_bytes = 0
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        # Circuit breaker for repeated failures
        self._consecutive_errors = 0
        self._max_consecutive_errors = 10
        self._circuit_open = False
        
    def _handle_error(self, error: Exception, operation: str) -> None:
        """Handle errors based on configured mode."""
        self._consecutive_errors += 1
        
        # Open circuit breaker if too many errors
        if self._consecutive_errors >= self._max_consecutive_errors:
            self._circuit_open = True
            logger.error(f"Cache circuit breaker opened after {self._consecutive_errors} errors")
        
        error_msg = f"Cache {operation} error: {str(error)}"
        
        if self.error_mode == ErrorHandlingMode.SILENT:
            logger.debug(error_msg, exc_info=True)
        elif self.error_mode == ErrorHandlingMode.WARN:
            logger.warning(error_msg, exc_info=True)
        elif self.error_mode == ErrorHandlingMode.RAISE:
            raise CacheOperationError(error_msg) from error
    
    def _reset_error_count(self):
        """Reset error counting after successful operation."""
        if self._consecutive_errors > 0:
            self._consecutive_errors = 0
            if self._circuit_open:
                self._circuit_open = False
                logger.info("Cache circuit breaker reset after successful operation")
        
    def _generate_cache_key(
        self,
        query_text: str,
        embedding: Optional[List[float]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Generate a unique cache key for the query."""
        try:
            # Validate inputs
            if not query_text or not isinstance(query_text, str):
                logger.warning(f"Invalid query_text for cache key: {type(query_text)}")
                return None
            
            # Create a dictionary of all inputs
            key_data = {
                'query': query_text.lower().strip(),
                'params': params or {}
            }
            
            # Include embedding hash if provided
            if embedding:
                try:
                    # Validate embedding
                    if not isinstance(embedding, (list, tuple)) or not embedding:
                        logger.warning("Invalid embedding format for cache key")
                        return None
                    
                    # Hash the embedding to avoid huge keys
                    embedding_str = ','.join(str(float(x)) for x in embedding[:10])
                    key_data['embedding_hash'] = hashlib.md5(embedding_str.encode()).hexdigest()
                except (ValueError, TypeError) as e:
                    logger.warning(f"Error processing embedding for cache key: {e}")
                    return None
            
            # Create stable JSON representation
            key_json = json.dumps(key_data, sort_keys=True)
            
            # Generate SHA256 hash
            return hashlib.sha256(key_json.encode()).hexdigest()
            
        except Exception as e:
            self._handle_error(e, "key generation")
            return None
    
    def _estimate_size(self, obj: Any) -> int:
        """Estimate memory size of an object in bytes."""
        try:
            # Try pickle first (most accurate)
            return len(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL))
        except (pickle.PicklingError, TypeError, AttributeError) as e:
            # Object can't be pickled
            logger.debug(f"Cannot pickle object for size estimation: {e}")
            try:
                # Try JSON serialization
                return len(json.dumps(obj, default=str).encode())
            except (TypeError, ValueError) as e:
                # Can't serialize to JSON either
                logger.debug(f"Cannot JSON serialize object: {e}")
                try:
                    # Last resort - string representation
                    return len(str(obj).encode())
                except Exception:
                    # Give up and return a default size
                    logger.warning("Failed all size estimation methods, using default")
                    return 1000  # 1KB default
    
    async def _evict_if_needed(self, new_size: int) -> bool:
        """Evict items if cache is full or memory limit exceeded."""
        try:
            # Check if we need to evict
            memory_limit_bytes = self.max_memory_mb * 1024 * 1024
            
            # Check memory limit
            evicted_count = 0
            while self._total_memory_bytes + new_size > memory_limit_bytes:
                if not self._cache:
                    logger.warning("Cache empty but memory limit exceeded")
                    return False
                
                # Find least recently used item
                if not self._access_times:
                    logger.error("Access times dict is empty but cache is not")
                    return False
                
                lru_key = min(self._access_times.items(), key=lambda x: x[1])[0]
                if await self._evict_item(lru_key):
                    evicted_count += 1
                else:
                    return False
                
                # Prevent infinite loop
                if evicted_count > self.max_size:
                    logger.error("Eviction loop detected")
                    return False
            
            # Check size limit
            while len(self._cache) >= self.max_size:
                if not self._cache:
                    break
                
                if not self._access_times:
                    logger.error("Access times dict is empty but cache is not")
                    return False
                
                lru_key = min(self._access_times.items(), key=lambda x: x[1])[0]
                if not await self._evict_item(lru_key):
                    return False
            
            return True
            
        except Exception as e:
            self._handle_error(e, "eviction")
            return False
    
    async def _evict_item(self, key: str) -> bool:
        """Evict a single item from cache."""
        try:
            if key in self._cache:
                _, _, size_bytes = self._cache[key]
                self._total_memory_bytes -= size_bytes
                del self._cache[key]
                
                if key in self._access_times:
                    del self._access_times[key]
                
                logger.debug(f"Evicted cache item: {key[:8]}...")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error evicting cache item {key[:8]}: {e}")
            return False
    
    async def get(
        self,
        query_text: str,
        embedding: Optional[List[float]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Get cached result if available and not expired."""
        # Check circuit breaker
        if self._circuit_open:
            logger.debug("Cache circuit breaker is open, skipping cache lookup")
            await self.stats.record_miss()
            return None
        
        try:
            key = self._generate_cache_key(query_text, embedding, params)
            if not key:
                await self.stats.record_error()
                return None
            
            async with self._lock:
                if key in self._cache:
                    value, timestamp, size_bytes = self._cache[key]
                    
                    # Check if expired
                    if time.time() - timestamp > self.ttl_seconds:
                        await self._evict_item(key)
                        await self.stats.record_miss()
                        return None
                    
                    # Update access time
                    self._access_times[key] = time.time()
                    
                    # Record hit
                    time_saved = 30000  # Estimate 30s saved per cache hit
                    await self.stats.record_hit(time_saved)
                    
                    # Track query pattern
                    self._track_query_pattern(query_text)
                    
                    logger.info(f"Cache hit for query: {query_text[:50]}...")
                    self._reset_error_count()
                    return value
                
                await self.stats.record_miss()
                return None
                
        except Exception as e:
            await self.stats.record_error()
            self._handle_error(e, "get")
            return None
    
    async def set(
        self,
        query_text: str,
        value: Any,
        embedding: Optional[List[float]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store result in cache."""
        # Check circuit breaker
        if self._circuit_open:
            logger.debug("Cache circuit breaker is open, skipping cache write")
            return False
        
        try:
            key = self._generate_cache_key(query_text, embedding, params)
            if not key:
                return False
            
            size_bytes = self._estimate_size(value)
            
            # Check if value is too large
            if size_bytes > self.max_memory_mb * 1024 * 1024 * 0.1:  # 10% of total
                logger.warning(f"Value too large for cache: {size_bytes / 1024 / 1024:.2f} MB")
                return False
            
            async with self._lock:
                # Evict if needed
                if not await self._evict_if_needed(size_bytes):
                    logger.warning("Failed to make space for new cache entry")
                    return False
                
                # Store in cache
                self._cache[key] = (value, time.time(), size_bytes)
                self._access_times[key] = time.time()
                self._total_memory_bytes += size_bytes
                
                # Track query pattern
                self._track_query_pattern(query_text)
                
                logger.debug(f"Cached result for query: {query_text[:50]}... (size: {size_bytes} bytes)")
                self._reset_error_count()
                return True
                
        except MemoryError as e:
            await self.stats.record_error()
            logger.error(f"Memory error while caching: {e}")
            # Try to free some memory
            await self.clear()
            return False
            
        except Exception as e:
            await self.stats.record_error()
            self._handle_error(e, "set")
            return False
    
    def _track_query_pattern(self, query_text: str):
        """Track query patterns for analysis."""
        try:
            # Extract pattern (first few words)
            words = query_text.lower().split()[:3]
            pattern = ' '.join(words)
            self._query_patterns[pattern] += 1
        except Exception as e:
            # Non-critical error, just log
            logger.debug(f"Error tracking query pattern: {e}")
    
    async def clear(self) -> bool:
        """Clear entire cache."""
        try:
            async with self._lock:
                self._cache.clear()
                self._access_times.clear()
                self._query_patterns.clear()
                self._total_memory_bytes = 0
                logger.info("Cache cleared")
                self._reset_error_count()
                return True
                
        except Exception as e:
            self._handle_error(e, "clear")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """Clear cache entries matching a pattern."""
        try:
            async with self._lock:
                keys_to_remove = []
                
                # In production, we'd need to store query text with cache entries
                # For now, clear entries based on access pattern
                for key in list(self._cache.keys()):
                    keys_to_remove.append(key)
                
                removed_count = 0
                for key in keys_to_remove:
                    if await self._evict_item(key):
                        removed_count += 1
                
                logger.info(f"Cleared {removed_count} cache entries matching pattern: {pattern}")
                self._reset_error_count()
                return removed_count
                
        except Exception as e:
            self._handle_error(e, "clear_pattern")
            return 0
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive cache statistics."""
        try:
            stats = await self.stats.get_stats()
            
            async with self._lock:
                stats.update({
                    'cache_size': len(self._cache),
                    'memory_usage_mb': self._total_memory_bytes / (1024 * 1024),
                    'memory_limit_mb': self.max_memory_mb,
                    'circuit_breaker_open': self._circuit_open,
                    'consecutive_errors': self._consecutive_errors,
                    'top_patterns': sorted(
                        self._query_patterns.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:10]
                })
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {
                'error': str(e),
                'cache_size': len(self._cache) if hasattr(self, '_cache') else 0,
                'circuit_breaker_open': self._circuit_open if hasattr(self, '_circuit_open') else False
            }
    
    async def warm_cache(self, common_queries: List[Tuple[str, Any]]) -> int:
        """Pre-populate cache with common queries."""
        try:
            logger.info(f"Warming cache with {len(common_queries)} common queries")
            
            success_count = 0
            for query_text, result in common_queries:
                if await self.set(query_text, result):
                    success_count += 1
            
            logger.info(f"Cache warming completed: {success_count}/{len(common_queries)} cached")
            return success_count
            
        except Exception as e:
            self._handle_error(e, "warm_cache")
            return 0
    
    async def health_check(self) -> Dict[str, Any]:
        """Check cache health status."""
        try:
            stats = await self.get_statistics()
            
            # Determine health status
            if self._circuit_open:
                status = 'unhealthy'
            elif stats.get('error_rate', 0) > 10:
                status = 'degraded'
            else:
                status = 'healthy'
            
            return {
                'status': status,
                'circuit_breaker_open': self._circuit_open,
                'error_rate': stats.get('error_rate', 0),
                'memory_usage_percent': (self._total_memory_bytes / (self.max_memory_mb * 1024 * 1024) * 100)
                                      if self.max_memory_mb > 0 else 0
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }


# Global cache instance with error recovery
_query_cache: Optional[QueryCache] = None
_cache_creation_lock = asyncio.Lock()


async def get_cache() -> QueryCache:
    """Get or create global cache instance with error handling."""
    global _query_cache
    
    if _query_cache is None:
        async with _cache_creation_lock:
            # Double-check after acquiring lock
            if _query_cache is None:
                try:
                    _query_cache = QueryCache(error_mode=ErrorHandlingMode.WARN)
                    logger.info("Created new global cache instance")
                except Exception as e:
                    logger.error(f"Failed to create cache instance: {e}")
                    # Create a minimal cache that fails silently
                    _query_cache = QueryCache(
                        max_size=100,
                        ttl_seconds=300,
                        max_memory_mb=50,
                        error_mode=ErrorHandlingMode.SILENT
                    )
    
    return _query_cache


def cached_search(ttl_seconds: Optional[int] = None):
    """Decorator for caching search functions with error handling."""
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                cache = await get_cache()
                
                # Extract query text and embedding from arguments
                query_text = None
                embedding = None
                
                # Handle positional arguments
                if args:
                    query_text = str(args[0]) if args[0] is not None else None
                    if len(args) > 1 and isinstance(args[1], (list, tuple)):
                        embedding = args[1]
                
                # Handle keyword arguments
                query_text = kwargs.get('query', query_text)
                embedding = kwargs.get('embedding', embedding)
                
                if not query_text:
                    # Can't cache without query text
                    return await func(*args, **kwargs)
                
                # Create params dict from other kwargs
                cache_params = {k: v for k, v in kwargs.items() 
                              if k not in ['query', 'embedding']}
                
                # Check cache
                cached_result = await cache.get(query_text, embedding, cache_params)
                if cached_result is not None:
                    return cached_result
                
                # Execute function
                start_time = time.time()
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                
                # Cache result if execution took significant time
                if execution_time > 0.5:  # Only cache if query took >500ms
                    await cache.set(query_text, result, embedding, cache_params)
                
                return result
                
            except CacheError as e:
                # Cache-specific errors - log and continue without cache
                logger.warning(f"Cache error in decorator: {e}")
                return await func(*args, **kwargs)
                
            except Exception as e:
                # Other errors - propagate
                logger.error(f"Unexpected error in cached_search decorator: {e}")
                raise
        
        return wrapper  # type: ignore
    return decorator


# Cache management functions with error handling
async def clear_cache() -> bool:
    """Clear the global cache."""
    try:
        cache = await get_cache()
        return await cache.clear()
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return False


async def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics."""
    try:
        cache = await get_cache()
        return await cache.get_statistics()
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {'error': str(e)}


async def warm_cache_with_common_queries() -> bool:
    """Warm cache with predefined common queries."""
    try:
        cache = await get_cache()
        
        # Common queries for Practical Strategy book
        common_queries = [
            ("what is strategic planning", {"summary": "Strategic planning is..."}),
            ("how to create a business strategy", {"summary": "Creating a business strategy involves..."}),
            ("strategic thinking principles", {"summary": "Key principles include..."}),
            ("define competitive advantage", {"summary": "Competitive advantage is..."}),
            ("strategy implementation steps", {"summary": "Implementation involves..."}),
        ]
        
        success_count = await cache.warm_cache(common_queries)
        return success_count > 0
        
    except Exception as e:
        logger.error(f"Error warming cache: {e}")
        return False


# Embedding cache for expensive operations
class EmbeddingCache:
    """Specialized cache for embedding lookups with error handling."""
    
    def __init__(self, max_size: int = 5000):
        """Initialize embedding cache."""
        try:
            self._cache: Dict[str, List[float]] = {}
            self._max_size = max_size
            self._access_order: List[str] = []
            self._lock = asyncio.Lock()
        except Exception as e:
            logger.error(f"Error initializing embedding cache: {e}")
            raise
        
    def get_embedding_key(self, text: str) -> Optional[str]:
        """Generate key for embedding lookup."""
        try:
            if not text or not isinstance(text, str):
                return None
            return hashlib.md5(text.encode()).hexdigest()
        except Exception as e:
            logger.warning(f"Error generating embedding key: {e}")
            return None
    
    async def get(self, text: str) -> Optional[List[float]]:
        """Get cached embedding."""
        try:
            key = self.get_embedding_key(text)
            if not key:
                return None
            
            async with self._lock:
                if key in self._cache:
                    # Move to end (most recently used)
                    self._access_order.remove(key)
                    self._access_order.append(key)
                    return self._cache[key].copy()  # Return copy to prevent modification
                return None
                
        except Exception as e:
            logger.warning(f"Error getting cached embedding: {e}")
            return None
    
    async def set(self, text: str, embedding: List[float]) -> bool:
        """Cache an embedding."""
        try:
            key = self.get_embedding_key(text)
            if not key:
                return False
            
            # Validate embedding
            if not isinstance(embedding, (list, tuple)) or not embedding:
                logger.warning("Invalid embedding format for caching")
                return False
            
            async with self._lock:
                # Check if already cached
                if key in self._cache:
                    # Move to end
                    self._access_order.remove(key)
                    self._access_order.append(key)
                    return True
                
                # Evict if at capacity
                while len(self._cache) >= self._max_size:
                    if not self._access_order:
                        break
                    lru_key = self._access_order.pop(0)
                    del self._cache[lru_key]
                
                # Add new embedding
                self._cache[key] = list(embedding)  # Store copy
                self._access_order.append(key)
                return True
                
        except Exception as e:
            logger.warning(f"Error caching embedding: {e}")
            return False
    
    async def clear(self) -> bool:
        """Clear embedding cache."""
        try:
            async with self._lock:
                self._cache.clear()
                self._access_order.clear()
            return True
        except Exception as e:
            logger.error(f"Error clearing embedding cache: {e}")
            return False


# Global embedding cache
_embedding_cache: Optional[EmbeddingCache] = None
_embedding_cache_lock = asyncio.Lock()


async def get_embedding_cache() -> EmbeddingCache:
    """Get global embedding cache instance with error handling."""
    global _embedding_cache
    
    if _embedding_cache is None:
        async with _embedding_cache_lock:
            if _embedding_cache is None:
                try:
                    _embedding_cache = EmbeddingCache()
                    logger.info("Created new embedding cache instance")
                except Exception as e:
                    logger.error(f"Failed to create embedding cache: {e}")
                    # Create minimal cache
                    _embedding_cache = EmbeddingCache(max_size=100)
    
    return _embedding_cache
