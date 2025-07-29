"""
Validate performance improvements after integration.
"""

import asyncio
import time
import httpx
import logging
from statistics import mean, stdev
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8058"

async def test_hybrid_search_performance():
    """Test hybrid search performance with cache and optimizations."""
    logger.info("=== Testing Hybrid Search Performance ===")
    
    # Test queries
    test_queries = [
        "What is strategic planning?",
        "How to implement a balanced scorecard",
        "Explain organizational culture impact on strategy",
        "What are the key performance indicators",
        "Steps to develop a business strategy"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Check if API is running
        try:
            health = await client.get(f"{API_URL}/health")
            if health.status_code != 200:
                logger.error("API not healthy")
                return
            logger.info("✓ API is healthy")
        except Exception as e:
            logger.error(f"API not available: {e}")
            return
        
        # Warm up cache with first query
        logger.info("\nWarming up cache...")
        warmup_query = test_queries[0]
        await client.post(
            f"{API_URL}/search/hybrid",
            json={"query": warmup_query, "k": 5}
        )
        
        # Test each query multiple times
        results = {}
        
        for query in test_queries:
            logger.info(f"\nTesting: '{query}'")
            times = []
            
            # First call (cache miss)
            start = time.time()
            response = await client.post(
                f"{API_URL}/search/hybrid",
                json={"query": query, "k": 5}
            )
            first_time = (time.time() - start) * 1000
            times.append(first_time)
            logger.info(f"  First call (cache miss): {first_time:.1f}ms")
            
            # Subsequent calls (cache hits)
            for i in range(4):
                start = time.time()
                response = await client.post(
                    f"{API_URL}/search/hybrid",
                    json={"query": query, "k": 5}
                )
                call_time = (time.time() - start) * 1000
                times.append(call_time)
                logger.info(f"  Call {i+2} (cache hit): {call_time:.1f}ms")
            
            # Calculate statistics
            avg_time = mean(times)
            cache_hit_time = mean(times[1:])  # Exclude first call
            
            results[query] = {
                "first_call": first_time,
                "cache_hits": times[1:],
                "average": avg_time,
                "cache_hit_avg": cache_hit_time
            }
            
            logger.info(f"  Average: {avg_time:.1f}ms")
            logger.info(f"  Cache hit average: {cache_hit_time:.1f}ms")
        
        # Overall statistics
        logger.info("\n=== Overall Performance Summary ===")
        all_times = []
        cache_times = []
        
        for query, data in results.items():
            all_times.extend([data["first_call"]] + data["cache_hits"])
            cache_times.extend(data["cache_hits"])
        
        overall_avg = mean(all_times)
        cache_avg = mean(cache_times)
        
        logger.info(f"Overall average: {overall_avg:.1f}ms")
        logger.info(f"Cache hit average: {cache_avg:.1f}ms")
        logger.info(f"Performance improvement from cache: {(1 - cache_avg/overall_avg)*100:.1f}%")
        
        # Check if meets target
        if overall_avg < 100:
            logger.info("✅ PERFORMANCE TARGET MET: <100ms average")
        else:
            logger.warning(f"⚠️ PERFORMANCE TARGET MISSED: {overall_avg:.1f}ms > 100ms")
        
        return results


async def test_embedding_generation_performance():
    """Test embedding generation performance improvements."""
    logger.info("\n=== Testing Embedding Generation Performance ===")
    
    # Import the embedders for direct testing
    import sys
    sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')
    
    from ingestion.embedder_jina import JinaEmbeddingGenerator as OriginalEmbedder
    from ingestion.experimental_embedder_jina_v2 import OptimizedJinaEmbeddingGenerator as OptimizedEmbedder
    
    # Test texts of varying lengths
    test_texts = [
        "Short text for embedding",
        "Medium length text that contains more words and might benefit from optimization strategies " * 5,
        "Long text for comprehensive testing of embedding generation performance " * 20
    ]
    
    # Test batch sizes
    batch_sizes = [1, 10, 50]
    
    logger.info("\nComparing Original vs Optimized Embedder:")
    
    # Initialize embedders
    original = OriginalEmbedder()
    optimized = OptimizedEmbedder()
    
    results = {}
    
    for batch_size in batch_sizes:
        logger.info(f"\n--- Batch size: {batch_size} ---")
        
        # Create batch
        batch = []
        for text in test_texts:
            batch.extend([text] * (batch_size // len(test_texts)))
        batch = batch[:batch_size]
        
        # Test original embedder
        start = time.time()
        try:
            original_embeddings = await original.generate_embeddings(batch)
            original_time = (time.time() - start) * 1000
            logger.info(f"Original embedder: {original_time:.1f}ms")
        except Exception as e:
            logger.error(f"Original embedder failed: {e}")
            original_time = float('inf')
        
        # Test optimized embedder
        start = time.time()
        try:
            optimized_embeddings = await optimized.generate_embeddings(batch)
            optimized_time = (time.time() - start) * 1000
            logger.info(f"Optimized embedder: {optimized_time:.1f}ms")
        except Exception as e:
            logger.error(f"Optimized embedder failed: {e}")
            optimized_time = float('inf')
        
        # Calculate improvement
        if original_time > 0 and optimized_time < float('inf'):
            improvement = (1 - optimized_time/original_time) * 100
            logger.info(f"Improvement: {improvement:.1f}%")
            
            results[batch_size] = {
                "original": original_time,
                "optimized": optimized_time,
                "improvement": improvement
            }
    
    # Overall assessment
    logger.info("\n=== Embedding Performance Summary ===")
    total_improvement = 0
    valid_tests = 0
    
    for batch_size, data in results.items():
        if "improvement" in data:
            total_improvement += data["improvement"]
            valid_tests += 1
            logger.info(f"Batch {batch_size}: {data['improvement']:.1f}% faster")
    
    if valid_tests > 0:
        avg_improvement = total_improvement / valid_tests
        logger.info(f"\nAverage improvement: {avg_improvement:.1f}%")
        
        if avg_improvement >= 50:
            logger.info("✅ EMBEDDING TARGET MET: 50%+ faster")
        else:
            logger.warning(f"⚠️ EMBEDDING TARGET MISSED: {avg_improvement:.1f}% < 50%")
    else:
        logger.error("Could not calculate improvements")


async def main():
    """Run all performance validations."""
    logger.info("Starting Performance Validation Tests")
    logger.info("=" * 50)
    
    # Test hybrid search
    search_results = await test_hybrid_search_performance()
    
    # Test embeddings
    await test_embedding_generation_performance()
    
    logger.info("\n" + "=" * 50)
    logger.info("✅ Performance validation completed!")


if __name__ == "__main__":
    asyncio.run(main())
