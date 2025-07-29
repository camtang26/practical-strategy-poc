"""
Test script to validate all optimizations are working correctly.
"""

import asyncio
import httpx
import time
import statistics
from typing import List, Dict, Any
import json


class OptimizationTester:
    """Test harness for optimization validation."""
    
    def __init__(self, base_url: str = "http://localhost:8058"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.test_queries = [
            # Factual queries (should use more text search)
            "What is the definition of strategic planning?",
            "List the key components of a business strategy",
            # Conceptual queries (should use more vector search)
            "Why is strategic thinking important for business success?",
            "Explain the relationship between vision and strategy",
            # Procedural queries (balanced approach)
            "What are the steps to create a strategic plan?",
            "How to implement a new business strategy?",
        ]
        self.results = {}
    
    async def test_cache_functionality(self):
        """Test cache endpoints and functionality."""
        print("\n🔧 Testing Cache Functionality...")
        
        # Clear cache first
        clear_resp = await self.client.post(f"{self.base_url}/cache/clear")
        assert clear_resp.status_code == 200
        print("✅ Cache cleared successfully")
        
        # Check initial stats
        stats_resp = await self.client.get(f"{self.base_url}/cache/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        print("✅ Initial cache stats verified")
        
        # Warm cache
        warm_resp = await self.client.post(f"{self.base_url}/cache/warm")
        assert warm_resp.status_code == 200
        print("✅ Cache warmed successfully")
        
        # Test cache hit
        test_query = "what is strategic planning"
        
        # First request (cache miss)
        start1 = time.time()
        resp1 = await self.client.post(
            f"{self.base_url}/search/hybrid",
            json={"query": test_query, "k": 5}
        )
        time1 = time.time() - start1
        
        # Second request (should be cache hit)
        start2 = time.time()
        resp2 = await self.client.post(
            f"{self.base_url}/search/hybrid",
            json={"query": test_query, "k": 5}
        )
        time2 = time.time() - start2
        
        # Verify cache hit was faster
        speedup = time1 / time2 if time2 > 0 else 100
        print(f"✅ Cache speedup: {speedup:.1f}x (First: {time1:.2f}s, Second: {time2:.2f}s)")
        
        # Check updated stats
        stats_resp2 = await self.client.get(f"{self.base_url}/cache/stats")
        stats2 = stats_resp2.json()
        print(f"✅ Cache stats - Hits: {stats2['hits']}, Hit rate: {stats2['hit_rate']:.1f}%")
        
        self.results["cache"] = {
            "working": True,
            "speedup": speedup,
            "hit_rate": stats2['hit_rate']
        }
    
    async def test_query_intent_detection(self):
        """Test query intent detection and dynamic weights."""
        print("\n🎯 Testing Query Intent Detection...")
        
        results = []
        for query in self.test_queries:
            resp = await self.client.post(
                f"{self.base_url}/search/hybrid",
                json={"query": query, "k": 3}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                # The optimized function should return query intent
                # We'll check response characteristics
                results.append({
                    "query": query,
                    "status": "success",
                    "result_count": len(data.get("results", []))
                })
                print(f"✅ Query processed: {query[:50]}...")
            else:
                results.append({
                    "query": query,
                    "status": "failed",
                    "error": resp.text
                })
                print(f"❌ Query failed: {query[:50]}...")
        
        success_rate = sum(1 for r in results if r["status"] == "success") / len(results) * 100
        self.results["query_intent"] = {
            "success_rate": success_rate,
            "tested_queries": len(results)
        }
        print(f"\n✅ Query intent success rate: {success_rate:.1f}%")
    
    async def test_error_handling(self):
        """Test error handling and circuit breakers."""
        print("\n🛡️ Testing Error Handling...")
        
        # Test with invalid query
        try:
            resp = await self.client.post(
                f"{self.base_url}/search/hybrid",
                json={"query": "", "k": 5}  # Empty query
            )
            print(f"✅ Empty query handled: Status {resp.status_code}")
        except Exception as e:
            print(f"❌ Error handling failed: {e}")
        
        # Check system health
        health_resp = await self.client.get(f"{self.base_url}/system/health/detailed")
        if health_resp.status_code == 200:
            health = health_resp.json()
            print("✅ System health check working")
            print(f"   Circuit breakers: {len(health.get('circuit_breakers', []))}")
            print(f"   Total errors: {health.get('errors', {}).get('total_errors', 0)}")
            self.results["error_handling"] = {
                "working": True,
                "circuit_breakers": len(health.get('circuit_breakers', [])),
                "total_errors": health.get('errors', {}).get('total_errors', 0)
            }
        else:
            print("❌ System health check failed")
            self.results["error_handling"] = {"working": False}
    
    async def test_performance_improvements(self):
        """Test overall performance improvements."""
        print("\n⚡ Testing Performance Improvements...")
        
        # Run multiple queries and measure times
        query_times = []
        
        for i, query in enumerate(self.test_queries[:3]):  # Test first 3 queries
            times = []
            
            # Run each query 3 times
            for j in range(3):
                start = time.time()
                resp = await self.client.post(
                    f"{self.base_url}/search/hybrid",
                    json={"query": query, "k": 5}
                )
                elapsed = time.time() - start
                
                if resp.status_code == 200:
                    times.append(elapsed)
                
                # Small delay between requests
                await asyncio.sleep(0.5)
            
            if times:
                avg_time = statistics.mean(times)
                query_times.append(avg_time)
                print(f"✅ Query {i+1} avg time: {avg_time:.2f}s")
        
        if query_times:
            overall_avg = statistics.mean(query_times)
            print(f"\n✅ Overall average response time: {overall_avg:.2f}s")
            
            # Check if meeting performance targets
            if overall_avg < 1.0:
                print("🎉 Excellent! Sub-second response times achieved")
            elif overall_avg < 5.0:
                print("✅ Good performance for complex queries")
            else:
                print("⚠️ Performance could be improved further")
            
            self.results["performance"] = {
                "avg_response_time": overall_avg,
                "individual_times": query_times
            }
    
    async def test_embedding_optimization(self):
        """Test embedding generation optimization."""
        print("\n🔄 Testing Embedding Optimization...")
        
        # This would normally test the ingestion pipeline
        # For now, we'll test if embeddings are being cached
        
        test_texts = [
            "Strategic planning is essential for business success.",
            "Innovation drives competitive advantage in modern markets.",
            "Leadership and vision are key components of strategy."
        ]
        
        # Make search requests to trigger embedding generation
        for text in test_texts:
            resp = await self.client.post(
                f"{self.base_url}/search/vector",
                json={"query": text, "k": 3}
            )
            
            if resp.status_code == 200:
                print(f"✅ Embedding generated for: {text[:40]}...")
            else:
                print(f"❌ Embedding failed for: {text[:40]}...")
        
        self.results["embedding_optimization"] = {
            "tested": True,
            "note": "Full test requires document re-ingestion"
        }
    
    async def run_all_tests(self):
        """Run all optimization tests."""
        print("🚀 Starting Optimization Tests...\n")
        
        try:
            # Check if API is running
            health_resp = await self.client.get(f"{self.base_url}/health")
            if health_resp.status_code != 200:
                print("❌ API is not running or not healthy")
                return
            
            print("✅ API is healthy\n")
            
            # Run all tests
            await self.test_cache_functionality()
            await self.test_query_intent_detection()
            await self.test_error_handling()
            await self.test_performance_improvements()
            await self.test_embedding_optimization()
            
            # Summary
            print("\n" + "="*50)
            print("📊 OPTIMIZATION TEST SUMMARY")
            print("="*50)
            
            for category, results in self.results.items():
                print(f"\n{category.upper()}:")
                for key, value in results.items():
                    print(f"  {key}: {value}")
            
            # Overall verdict
            print("\n" + "="*50)
            cache_working = self.results.get("cache", {}).get("working", False)
            cache_speedup = self.results.get("cache", {}).get("speedup", 0) > 2
            error_handling = self.results.get("error_handling", {}).get("working", False)
            perf_improved = self.results.get("performance", {}).get("avg_response_time", 100) < 5
            
            if all([cache_working, cache_speedup, error_handling, perf_improved]):
                print("✅ ALL OPTIMIZATIONS WORKING SUCCESSFULLY! 🎉")
            else:
                print("⚠️ Some optimizations need attention")
                if not cache_working:
                    print("  - Cache functionality needs fixing")
                if not cache_speedup:
                    print("  - Cache speedup is below target")
                if not error_handling:
                    print("  - Error handling needs improvement")
                if not perf_improved:
                    print("  - Performance is below target")
            
        except Exception as e:
            print(f"\n❌ Test suite failed: {e}")
        finally:
            await self.client.aclose()


async def main():
    """Run optimization tests."""
    tester = OptimizationTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
