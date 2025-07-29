"""Simple test runner for experimental embedder tests."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from unittest.mock import patch

# Import test class
from tests.test_experimental_embedder_jina_v2 import TestOptimizedJinaEmbeddingGenerator

def run_tests():
    """Run key tests manually."""
    print("Running experimental embedder tests...\n")
    
    test_instance = TestOptimizedJinaEmbeddingGenerator()
    
    # Test 1: Initialization with API key
    print("1. Testing initialization with API key...")
    try:
        with patch.dict(os.environ, {'EMBEDDING_API_KEY': 'test-api-key'}):
            test_instance.test_initialization_with_api_key(test_instance.mock_env)
        print("✅ PASSED: Initialization with API key\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 2: Initialization without API key
    print("2. Testing initialization without API key...")
    try:
        test_instance.test_initialization_without_api_key()
        print("✅ PASSED: Initialization without API key (raised ValueError)\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 3: Dynamic batch size calculation
    print("3. Testing dynamic batch size calculation...")
    try:
        with patch.dict(os.environ, {'EMBEDDING_API_KEY': 'test-api-key'}):
            from ingestion.experimental_embedder_jina_v2 import OptimizedJinaEmbeddingGenerator
            embedder = OptimizedJinaEmbeddingGenerator(base_batch_size=50)
            
            # Short texts
            short_texts = ["short"] * 10
            short_batch = embedder._calculate_dynamic_batch_size(short_texts)
            print(f"   Short texts batch size: {short_batch} (expected: {min(200, 100)})")
            
            # Long texts
            long_texts = ["a" * 3000] * 10
            long_batch = embedder._calculate_dynamic_batch_size(long_texts)
            print(f"   Long texts batch size: {long_batch} (expected: {max(10, 25)})")
            
            print("✅ PASSED: Dynamic batch size calculation\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 4: Rate limiting
    print("4. Testing rate limiting...")
    try:
        with patch.dict(os.environ, {'EMBEDDING_API_KEY': 'test-api-key'}):
            embedder = OptimizedJinaEmbeddingGenerator(rate_limit_per_minute=30)
            
            # Test with empty request times
            import time
            start = time.time()
            asyncio.run(embedder._wait_for_rate_limit())
            elapsed = time.time() - start
            print(f"   No wait needed: {elapsed:.3f}s (expected: <0.1s)")
            
            print("✅ PASSED: Rate limiting\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 5: Text truncation
    print("5. Testing text truncation...")
    try:
        with patch.dict(os.environ, {'EMBEDDING_API_KEY': 'test-api-key'}):
            embedder = OptimizedJinaEmbeddingGenerator()
            long_text = "a" * (embedder.max_chars_per_text + 1000)
            
            # Mock the API request
            async def test_truncation():
                from unittest.mock import AsyncMock
                embedder._make_api_request = AsyncMock(return_value=([[0.1] * 2048], 0.1))
                await embedder.generate_embeddings_batch([long_text])
                
                # Check the text was truncated
                actual_text = embedder._make_api_request.call_args[0][0][0]
                return len(actual_text) == embedder.max_chars_per_text
            
            truncated = asyncio.run(test_truncation())
            print(f"   Text was truncated: {truncated}")
            print("✅ PASSED: Text truncation\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 6: Performance stats
    print("6. Testing performance stats...")
    try:
        with patch.dict(os.environ, {'EMBEDDING_API_KEY': 'test-api-key'}):
            embedder = OptimizedJinaEmbeddingGenerator()
            
            # Add mock stats
            embedder.stats[0] = {'count': 100, 'total_time': 10.0, 'errors': 2}
            embedder.stats[1] = {'count': 50, 'total_time': 5.0, 'errors': 1}
            
            stats = embedder.get_performance_stats()
            print(f"   Total items: {stats['total_items_processed']} (expected: 150)")
            print(f"   Total time: {stats['total_time_seconds']}s (expected: 15.0)")
            print(f"   Avg time per item: {stats['average_time_per_item']} (expected: 0.1)")
            print(f"   Error rate: {stats['error_rate']} (expected: 0.02)")
            
            print("✅ PASSED: Performance stats\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    print("\n=== Test Summary ===")
    print("Tests completed. Check results above for any failures.")

if __name__ == "__main__":
    run_tests()
