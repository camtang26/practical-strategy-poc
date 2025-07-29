"""
Test ACTUAL performance of the integrated optimizations.
"""

import asyncio
import time
import httpx
import logging
from statistics import mean, stdev
import json
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8061"

async def measure_hybrid_search_performance():
    """Measure actual hybrid search performance with real API calls."""
    logger.info("=== MEASURING HYBRID SEARCH PERFORMANCE ===")
    
    test_queries = [
        "What is strategic planning?",
        "How to implement a balanced scorecard",
        "Explain organizational culture impact on strategy",
        "What are the key performance indicators for business success",
        "Steps to develop a comprehensive business strategy",
        "Define competitive advantage in modern markets",
        "How does digital transformation affect strategy",
        "What are Porter's five forces",
        "Explain SWOT analysis methodology",
        "Best practices for strategic implementation"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Verify API health
        health = await client.get(f"{API_URL}/health")
        if health.status_code != 200:
            logger.error(f"API not healthy: {health.text}")
            return None
        logger.info(f"✓ API healthy: {health.json()}")
        
        results = {}
        all_times = []
        cache_miss_times = []
        cache_hit_times = []
        
        # Test each query
        for i, query in enumerate(test_queries):
            logger.info(f"\nQuery {i+1}/10: '{query[:50]}...'")
            query_times = []
            
            # First call - cache miss
            start = time.time()
            try:
                response = await client.post(
                    f"{API_URL}/search/hybrid",
                    json={"query": query, "k": 5}
                )
                elapsed = (time.time() - start) * 1000
                
                if response.status_code == 200:
                    query_times.append(elapsed)
                    cache_miss_times.append(elapsed)
                    all_times.append(elapsed)
                    logger.info(f"  First call (cache miss): {elapsed:.1f}ms")
                else:
                    logger.error(f"  Error: {response.status_code} - {response.text}")
                    continue
                    
            except Exception as e:
                logger.error(f"  Request failed: {e}")
                continue
            
            # Subsequent calls - should hit cache
            for j in range(3):
                start = time.time()
                try:
                    response = await client.post(
                        f"{API_URL}/search/hybrid",
                        json={"query": query, "k": 5}
                    )
                    elapsed = (time.time() - start) * 1000
                    
                    if response.status_code == 200:
                        query_times.append(elapsed)
                        cache_hit_times.append(elapsed)
                        all_times.append(elapsed)
                        logger.info(f"  Call {j+2} (cache hit): {elapsed:.1f}ms")
                    
                except Exception as e:
                    logger.error(f"  Request {j+2} failed: {e}")
            
            if query_times:
                avg = mean(query_times)
                logger.info(f"  Average for this query: {avg:.1f}ms")
                results[query] = {
                    "times": query_times,
                    "average": avg,
                    "first_call": query_times[0] if query_times else None
                }
        
        # Calculate overall statistics
        if all_times:
            logger.info("\n" + "=" * 60)
            logger.info("PERFORMANCE SUMMARY")
            logger.info("=" * 60)
            
            overall_avg = mean(all_times)
            logger.info(f"Overall average: {overall_avg:.1f}ms (n={len(all_times)})")
            
            if cache_miss_times:
                miss_avg = mean(cache_miss_times)
                logger.info(f"Cache miss average: {miss_avg:.1f}ms (n={len(cache_miss_times)})")
            
            if cache_hit_times:
                hit_avg = mean(cache_hit_times)
                logger.info(f"Cache hit average: {hit_avg:.1f}ms (n={len(cache_hit_times)})")
                
                if cache_miss_times:
                    improvement = (1 - hit_avg/miss_avg) * 100
                    logger.info(f"Cache improvement: {improvement:.1f}%")
            
            # Check against target
            logger.info("\nPERFORMANCE TARGET CHECK:")
            if overall_avg < 100:
                logger.info(f"✅ TARGET MET: {overall_avg:.1f}ms < 100ms")
            else:
                logger.warning(f"❌ TARGET MISSED: {overall_avg:.1f}ms > 100ms")
                
            # Additional statistics
            if len(all_times) > 1:
                std_dev = stdev(all_times)
                logger.info(f"\nAdditional stats:")
                logger.info(f"  Min time: {min(all_times):.1f}ms")
                logger.info(f"  Max time: {max(all_times):.1f}ms")
                logger.info(f"  Std dev: {std_dev:.1f}ms")
                
        return results


async def measure_embedding_performance():
    """Measure actual embedding generation performance."""
    logger.info("\n\n=== MEASURING EMBEDDING GENERATION PERFORMANCE ===")
    
    # Test different text sizes
    test_texts = {
        "short": ["Strategic planning", "Business model", "Market analysis"],
        "medium": [
            "Strategic planning involves setting goals and determining actions to achieve those goals. " * 3,
            "Business model innovation requires understanding customer needs and market dynamics. " * 3,
            "Competitive advantage comes from unique value propositions and operational excellence. " * 3
        ],
        "long": [
            "The comprehensive strategic planning process encompasses multiple phases including environmental scanning, " * 10,
            "Digital transformation fundamentally changes how organizations create and deliver value to customers, " * 10,
            "Organizational culture plays a critical role in strategy implementation and long-term success, " * 10
        ]
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        results = {}
        
        for size, texts in test_texts.items():
            logger.info(f"\nTesting {size} texts ({len(texts[0])} chars each):")
            
            # Test different batch sizes
            for batch_size in [1, 10, 50]:
                if batch_size > len(texts):
                    batch = texts * (batch_size // len(texts) + 1)
                    batch = batch[:batch_size]
                else:
                    batch = texts[:batch_size]
                
                logger.info(f"\n  Batch size: {batch_size}")
                
                # Time the embedding generation
                start = time.time()
                try:
                    # Call the ingest endpoint which uses the embedder
                    response = await client.post(
                        f"{API_URL}/ingest/text",
                        json={
                            "texts": batch,
                            "source": "performance_test",
                            "metadata": {"test": True}
                        }
                    )
                    elapsed = (time.time() - start) * 1000
                    
                    if response.status_code == 200:
                        per_text = elapsed / len(batch)
                        logger.info(f"    Total time: {elapsed:.1f}ms")
                        logger.info(f"    Per text: {per_text:.1f}ms")
                        
                        key = f"{size}_{batch_size}"
                        results[key] = {
                            "total_ms": elapsed,
                            "per_text_ms": per_text,
                            "batch_size": batch_size
                        }
                    else:
                        logger.error(f"    Failed: {response.status_code}")
                        
                except Exception as e:
                    logger.error(f"    Error: {e}")
        
        # Calculate improvements (comparing single vs batch)
        logger.info("\n" + "=" * 60)
        logger.info("EMBEDDING PERFORMANCE SUMMARY")
        logger.info("=" * 60)
        
        for size in ["short", "medium", "long"]:
            single_key = f"{size}_1"
            batch_key = f"{size}_50"
            
            if single_key in results and batch_key in results:
                single_time = results[single_key]["per_text_ms"]
                batch_time = results[batch_key]["per_text_ms"]
                improvement = (1 - batch_time/single_time) * 100
                
                logger.info(f"\n{size.upper()} texts:")
                logger.info(f"  Single: {single_time:.1f}ms per text")
                logger.info(f"  Batch (50): {batch_time:.1f}ms per text")
                logger.info(f"  Improvement: {improvement:.1f}%")
        
        # Check target
        improvements = []
        for size in ["short", "medium", "long"]:
            single_key = f"{size}_1"
            batch_key = f"{size}_50"
            if single_key in results and batch_key in results:
                improvement = (1 - results[batch_key]["per_text_ms"]/results[single_key]["per_text_ms"]) * 100
                improvements.append(improvement)
        
        if improvements:
            avg_improvement = mean(improvements)
            logger.info(f"\nAverage improvement: {avg_improvement:.1f}%")
            
            if avg_improvement >= 50:
                logger.info(f"✅ EMBEDDING TARGET MET: {avg_improvement:.1f}% >= 50%")
            else:
                logger.warning(f"❌ EMBEDDING TARGET MISSED: {avg_improvement:.1f}% < 50%")


async def main():
    """Run all performance measurements."""
    logger.info("STARTING ACTUAL PERFORMANCE MEASUREMENTS")
    logger.info("=" * 60)
    logger.info("Using API at: " + API_URL)
    logger.info("=" * 60)
    
    # Measure hybrid search
    search_results = await measure_hybrid_search_performance()
    
    # Measure embeddings
    await measure_embedding_performance()
    
    logger.info("\n" + "=" * 60)
    logger.info("✅ PERFORMANCE MEASUREMENTS COMPLETED")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
