"""Test semaphore behavior under various error conditions."""
import asyncio
import time
from unittest.mock import Mock, patch, AsyncMock
import httpx
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from ingestion.embedder_jina_v2_prod import OptimizedJinaEmbeddingGenerator


async def test_semaphore_release_on_exception():
    """Test that semaphore is properly released even when exceptions occur."""
    
    embedder = OptimizedJinaEmbeddingGenerator(
        api_key="test_key",
        max_concurrent_requests=2,  # Low limit to test semaphore
        max_retries=1  # Reduce retries for faster testing
    )
    
    # Track semaphore state
    initial_value = embedder.semaphore._value
    print(f"Initial semaphore value: {initial_value}")
    
    # Test 1: Network error during request
    print("\n=== Test 1: Network error ===")
    with patch.object(embedder, '_get_client') as mock_client:
        mock_http = AsyncMock()
        mock_http.post.side_effect = httpx.NetworkError("Connection failed")
        mock_client.return_value = mock_http
        
        try:
            await embedder._generate_embeddings_batch(["test text"], "batch1")
        except Exception as e:
            print(f"Expected error: {type(e).__name__}: {e}")
        
        # Check semaphore was released
        await asyncio.sleep(0.1)  # Let async operations complete
        print(f"Semaphore value after error: {embedder.semaphore._value}")
        assert embedder.semaphore._value == initial_value, "Semaphore not released after network error!"
    
    # Test 2: API error response
    print("\n=== Test 2: API error response ===")
    with patch.object(embedder, '_get_client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_client.return_value = mock_http
        
        try:
            await embedder._generate_embeddings_batch(["test text"], "batch2")
        except Exception as e:
            print(f"Expected error: {type(e).__name__}: {e}")
        
        await asyncio.sleep(0.1)
        print(f"Semaphore value after API error: {embedder.semaphore._value}")
        assert embedder.semaphore._value == initial_value, "Semaphore not released after API error!"
    
    # Test 3: Concurrent requests respecting semaphore limit
    print("\n=== Test 3: Concurrent requests ===")
    with patch.object(embedder, '_get_client') as mock_client:
        # Create a slow response to test concurrency
        async def slow_post(*args, **kwargs):
            await asyncio.sleep(0.5)
            response = Mock()
            response.status_code = 200
            response.json.return_value = {
                "data": [{"embedding": [0.1] * 2048}]
            }
            return response
        
        mock_http = AsyncMock()
        mock_http.post = slow_post
        mock_client.return_value = mock_http
        
        # Start multiple concurrent requests
        start_time = time.time()
        tasks = []
        for i in range(4):  # More than semaphore limit
            task = asyncio.create_task(
                embedder._generate_embeddings_batch([f"text {i}"], f"batch{i}")
            )
            tasks.append(task)
        
        # Check that semaphore is limiting concurrent requests
        await asyncio.sleep(0.1)
        active_count = initial_value - embedder.semaphore._value
        print(f"Active requests (should be <= 2): {active_count}")
        assert active_count <= 2, "Semaphore not limiting concurrent requests!"
        
        # Wait for all to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"All requests completed in {end_time - start_time:.1f}s")
        print(f"Final semaphore value: {embedder.semaphore._value}")
        assert embedder.semaphore._value == initial_value, "Semaphore not fully released after all requests!"
    
    # Test 4: Exception during response processing
    print("\n=== Test 4: Exception during response processing ===")
    with patch.object(embedder, '_get_client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_client.return_value = mock_http
        
        try:
            await embedder._generate_embeddings_batch(["test text"], "batch4")
        except Exception as e:
            print(f"Expected error: {type(e).__name__}: {e}")
        
        await asyncio.sleep(0.1)
        print(f"Semaphore value after JSON error: {embedder.semaphore._value}")
        assert embedder.semaphore._value == initial_value, "Semaphore not released after JSON error!"
    
    # Clean up
    await embedder.close()
    print("\n✅ All semaphore tests passed!")


async def test_semaphore_with_rate_limiting():
    """Test semaphore behavior with rate limiting."""
    
    embedder = OptimizedJinaEmbeddingGenerator(
        api_key="test_key",
        max_concurrent_requests=3,
        rate_limit_per_minute=2,  # Very low for testing
        max_retries=1
    )
    
    print("\n=== Test: Semaphore with rate limiting ===")
    
    # Mock successful responses
    with patch.object(embedder, '_get_client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 2048}]
        }
        
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_client.return_value = mock_http
        
        # Send requests that should trigger rate limiting
        start_time = time.time()
        tasks = []
        for i in range(4):
            task = asyncio.create_task(
                embedder._generate_embeddings_batch([f"text {i}"], f"batch{i}")
            )
            tasks.append(task)
            await asyncio.sleep(0.1)  # Small delay between submissions
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        print(f"Completed {len(tasks)} requests in {end_time - start_time:.1f}s")
        print(f"Final semaphore value: {embedder.semaphore._value}")
        
        # Check all succeeded despite rate limiting
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            print(f"Errors: {errors}")
        
        assert embedder.semaphore._value == embedder.semaphore._initial_value, \
            "Semaphore not properly released with rate limiting!"
    
    await embedder.close()
    print("✅ Rate limiting test passed!")


if __name__ == "__main__":
    print("Testing semaphore behavior in embedder...")
    asyncio.run(test_semaphore_release_on_exception())
    asyncio.run(test_semaphore_with_rate_limiting())
