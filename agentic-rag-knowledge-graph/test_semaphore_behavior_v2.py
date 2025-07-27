"""Test semaphore behavior under various error conditions."""
import asyncio
import time
import os
from unittest.mock import Mock, patch, AsyncMock
import httpx
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

# Set required environment variables for testing
os.environ["EMBEDDING_API_KEY"] = "test_key"
os.environ["EMBEDDING_BASE_URL"] = "https://api.jina.ai/v1"

from ingestion.embedder_jina_v2_prod import OptimizedJinaEmbeddingGenerator


async def test_semaphore_release_on_exception():
    """Test that semaphore is properly released even when exceptions occur."""
    
    embedder = OptimizedJinaEmbeddingGenerator(
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
            await embedder._make_api_request(["test text"], 1)
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
            await embedder._make_api_request(["test text"], 2)
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
                embedder._make_api_request([f"text {i}"], i)
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
            await embedder._make_api_request(["test text"], 4)
        except Exception as e:
            print(f"Expected error: {type(e).__name__}: {e}")
        
        await asyncio.sleep(0.1)
        print(f"Semaphore value after JSON error: {embedder.semaphore._value}")
        assert embedder.semaphore._value == initial_value, "Semaphore not released after JSON error!"
    
    # Test 5: Test with multiple batches through public API
    print("\n=== Test 5: Multiple batches through public API ===")
    with patch.object(embedder, '_get_client') as mock_client:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 2048} for _ in range(100)]
        }
        
        mock_http = AsyncMock()
        mock_http.post.return_value = mock_response
        mock_client.return_value = mock_http
        
        # Generate embeddings for many texts (should create multiple batches)
        texts = [f"text {i}" for i in range(250)]  # Should create 3 batches
        results = await embedder.generate_embeddings_batch(texts)
        
        print(f"Generated {len(results)} embeddings")
        print(f"Final semaphore value: {embedder.semaphore._value}")
        assert embedder.semaphore._value == initial_value, "Semaphore not released after batch processing!"
    
    # Clean up
    await embedder.close()
    print("\n✅ All semaphore tests passed!")


async def test_edge_cases():
    """Test edge cases that could cause semaphore leaks."""
    
    embedder = OptimizedJinaEmbeddingGenerator(
        max_concurrent_requests=1,  # Very low to test edge cases
        max_retries=1
    )
    
    initial_value = embedder.semaphore._value
    
    print("\n=== Test: Cancellation during request ===")
    with patch.object(embedder, '_get_client') as mock_client:
        # Create a very slow response
        async def very_slow_post(*args, **kwargs):
            await asyncio.sleep(10)  # Longer than we'll wait
            
        mock_http = AsyncMock()
        mock_http.post = very_slow_post
        mock_client.return_value = mock_http
        
        # Start a request and cancel it
        task = asyncio.create_task(embedder._make_api_request(["test"], 1))
        await asyncio.sleep(0.1)  # Let it acquire semaphore
        task.cancel()
        
        try:
            await task
        except asyncio.CancelledError:
            print("Task cancelled as expected")
        
        await asyncio.sleep(0.1)
        print(f"Semaphore value after cancellation: {embedder.semaphore._value}")
        assert embedder.semaphore._value == initial_value, "Semaphore not released after cancellation!"
    
    await embedder.close()
    print("✅ Edge case tests passed!")


if __name__ == "__main__":
    print("Testing semaphore behavior in embedder...")
    asyncio.run(test_semaphore_release_on_exception())
    asyncio.run(test_edge_cases())
    print("\n🎉 All tests completed successfully!")
