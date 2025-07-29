"""
Unit tests for experimental_embedder_jina_v2.py
Tests dynamic batching, concurrent processing, rate limiting, and error handling.
"""

import pytest
import asyncio
import httpx
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import os
import time
from datetime import datetime
import json

import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')

from ingestion.experimental_embedder_jina_v2 import OptimizedJinaEmbeddingGenerator
from ingestion.chunker import DocumentChunk


class TestOptimizedJinaEmbeddingGenerator:
    """Test suite for the optimized Jina embedding generator."""
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment variables."""
        with patch.dict(os.environ, {'EMBEDDING_API_KEY': 'test-api-key'}):
            yield
    
    @pytest.fixture
    def embedder(self, mock_env):
        """Create embedder instance with mocked environment."""
        return OptimizedJinaEmbeddingGenerator(
            base_batch_size=50,
            max_concurrent_requests=2,
            rate_limit_per_minute=30
        )
    
    def test_initialization_with_api_key(self, mock_env):
        """Test successful initialization with API key."""
        embedder = OptimizedJinaEmbeddingGenerator()
        assert embedder.api_key == 'test-api-key'
        assert embedder.dimensions == 2048
        assert embedder.max_tokens == 8191
        assert embedder.model == "jina-embeddings-v4"
    
    def test_initialization_without_api_key(self):
        """Test initialization fails without API key."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="EMBEDDING_API_KEY not found"):
                OptimizedJinaEmbeddingGenerator()
    
    def test_calculate_dynamic_batch_size_short_texts(self, embedder):
        """Test batch size calculation for short texts."""
        texts = ["short text"] * 100
        batch_size = embedder._calculate_dynamic_batch_size(texts)
        assert batch_size == min(embedder.max_batch_size, embedder.base_batch_size * 2)
    
    def test_calculate_dynamic_batch_size_long_texts(self, embedder):
        """Test batch size calculation for long texts."""
        texts = ["a" * 3000] * 10  # Very long texts
        batch_size = embedder._calculate_dynamic_batch_size(texts)
        assert batch_size == max(embedder.min_batch_size, embedder.base_batch_size // 2)
    
    def test_calculate_dynamic_batch_size_with_rate_limiting(self, embedder):
        """Test batch size reduction when approaching rate limit."""
        # Simulate many recent requests
        embedder.request_times = [time.time() - i for i in range(25)]  # 25 recent requests
        texts = ["medium text"] * 50
        batch_size = embedder._calculate_dynamic_batch_size(texts)
        # Should reduce batch size due to rate limiting
        assert batch_size < embedder.base_batch_size
    
    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_no_wait(self, embedder):
        """Test rate limiting when under limit."""
        embedder.request_times = []
        start_time = time.time()
        await embedder._wait_for_rate_limit()
        elapsed = time.time() - start_time
        assert elapsed < 0.1  # Should not wait
        assert len(embedder.request_times) == 1
    
    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_with_wait(self, embedder):
        """Test rate limiting when at limit."""
        # Fill up rate limit
        current_time = time.time()
        embedder.request_times = [current_time - 30 + i for i in range(30)]  # 30 requests in last 30 seconds
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await embedder._wait_for_rate_limit()
            mock_sleep.assert_called_once()
            wait_time = mock_sleep.call_args[0][0]
            assert wait_time > 0  # Should wait
    
    @pytest.mark.asyncio
    async def test_make_api_request_success(self, embedder):
        """Test successful API request."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 2048},
                {"embedding": [0.2] * 2048}
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_response
            
            embeddings, elapsed = await embedder._make_api_request(["text1", "text2"], 0)
            
            assert len(embeddings) == 2
            assert len(embeddings[0]) == 2048
            assert embeddings[0][0] == 0.1
            assert embeddings[1][0] == 0.2
            assert elapsed > 0
    
    @pytest.mark.asyncio
    async def test_make_api_request_rate_limit(self, embedder):
        """Test API request with rate limiting response."""
        mock_response_429 = Mock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {'Retry-After': '5'}
        
        mock_response_200 = Mock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "data": [{"embedding": [0.1] * 2048}]
        }
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            # First call returns 429, second returns 200
            mock_client.post.side_effect = [mock_response_429, mock_response_200]
            
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                embeddings, _ = await embedder._make_api_request(["text1"], 0)
                
                assert len(embeddings) == 1
                mock_sleep.assert_called_with(5)  # Should wait for retry-after
    
    @pytest.mark.asyncio
    async def test_make_api_request_retry_on_error(self, embedder):
        """Test API request retry on error."""
        embedder.max_retries = 3
        
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client.post.side_effect = Exception("Network error")
            
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(Exception, match="Network error"):
                    await embedder._make_api_request(["text1"], 0)
                
                # Should have tried max_retries times
                assert mock_client.post.call_count == embedder.max_retries
    
    @pytest.mark.asyncio
    async def test_generate_embedding_single_text(self, embedder):
        """Test generating embedding for single text."""
        with patch.object(embedder, 'generate_embeddings_batch', 
                         new_callable=AsyncMock) as mock_batch:
            mock_batch.return_value = [[0.1] * 2048]
            
            embedding = await embedder.generate_embedding("test text")
            
            assert len(embedding) == 2048
            assert embedding[0] == 0.1
            mock_batch.assert_called_once_with(["test text"])
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty(self, embedder):
        """Test generating embeddings for empty batch."""
        embeddings = await embedder.generate_embeddings_batch([])
        assert embeddings == []
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_text_truncation(self, embedder):
        """Test text truncation for too-long texts."""
        long_text = "a" * (embedder.max_chars_per_text + 1000)
        
        with patch.object(embedder, '_make_api_request', 
                         new_callable=AsyncMock) as mock_request:
            mock_request.return_value = ([[0.1] * 2048], 0.1)
            
            embeddings = await embedder.generate_embeddings_batch([long_text])
            
            # Check that text was truncated
            actual_text = mock_request.call_args[0][0][0]
            assert len(actual_text) == embedder.max_chars_per_text
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_concurrent_processing(self, embedder):
        """Test concurrent batch processing."""
        # Create enough texts to trigger multiple batches
        texts = ["text"] * 150  # With base_batch_size=50, this creates 3 batches
        
        call_count = 0
        async def mock_api_request(batch_texts, batch_id):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Simulate API delay
            return [[0.1] * 2048] * len(batch_texts), 0.1
        
        with patch.object(embedder, '_make_api_request', side_effect=mock_api_request):
            start_time = time.time()
            embeddings = await embedder.generate_embeddings_batch(texts)
            elapsed = time.time() - start_time
            
            assert len(embeddings) == 150
            assert call_count == 3  # 3 batches
            # Should be faster than sequential (0.3s) due to concurrency
            assert elapsed < 0.25
    
    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_error_handling(self, embedder):
        """Test handling of failed batches."""
        texts = ["text1", "text2", "text3"]
        
        async def mock_process_batch(texts, indices, batch_id):
            if batch_id == 0:
                raise Exception("Batch failed")
            return [[0.1] * 2048] * len(texts), indices
        
        with patch.object(embedder, '_process_batch_with_indices', 
                         side_effect=mock_process_batch):
            with patch.object(embedder, '_calculate_dynamic_batch_size', return_value=1):
                embeddings = await embedder.generate_embeddings_batch(texts)
                
                # First text should have zero vector due to error
                assert embeddings[0] == [0.0] * 2048
                # Other texts should have embeddings
                assert embeddings[1][0] == 0.1
                assert embeddings[2][0] == 0.1
    
    @pytest.mark.asyncio
    async def test_embed_chunks(self, embedder):
        """Test embedding document chunks."""
        chunks = [
            DocumentChunk(
                content=f"chunk {i}",
                index=i,
                start_char=i*100,
                end_char=(i+1)*100,
                metadata={"source": "test"},
                token_count=10
            )
            for i in range(3)
        ]
        
        with patch.object(embedder, '_embed_with_progress', 
                         new_callable=AsyncMock) as mock_embed:
            mock_embed.return_value = [[0.1] * 2048] * 3
            
            embedded_chunks = await embedder.embed_chunks(chunks)
            
            assert len(embedded_chunks) == 3
            for i, chunk in enumerate(embedded_chunks):
                assert chunk.embedding == [0.1] * 2048
                assert chunk.metadata["embedding_model"] == "jina-embeddings-v4"
                assert chunk.metadata["embedding_dimensions"] == 2048
                assert "embedding_generated_at" in chunk.metadata
    
    @pytest.mark.asyncio
    async def test_embed_chunks_with_progress_callback(self, embedder):
        """Test progress callback during chunk embedding."""
        chunks = [DocumentChunk(content=f"chunk {i}", index=i, start_char=0, 
                               end_char=100, metadata={}, token_count=10) 
                 for i in range(10)]
        
        progress_updates = []
        def progress_callback(data):
            progress_updates.append(data)
        
        with patch.object(embedder, 'generate_embeddings_batch', 
                         new_callable=AsyncMock) as mock_batch:
            mock_batch.return_value = [[0.1] * 2048] * 5  # Return 5 embeddings per batch
            with patch.object(embedder, '_calculate_dynamic_batch_size', return_value=5):
                await embedder.embed_chunks(chunks, progress_callback)
        
        # Should have progress updates for 2 batches
        assert len(progress_updates) == 2
        assert progress_updates[0]['current_batch'] == 1
        assert progress_updates[0]['total_batches'] == 2
        assert progress_updates[1]['current_batch'] == 2
        assert progress_updates[1]['percentage'] == 100
    
    def test_get_performance_stats(self, embedder):
        """Test performance statistics calculation."""
        # Add some stats
        embedder.stats[0] = {'count': 100, 'total_time': 10.0, 'errors': 2}
        embedder.stats[1] = {'count': 50, 'total_time': 5.0, 'errors': 1}
        
        stats = embedder.get_performance_stats()
        
        assert stats['total_items_processed'] == 150
        assert stats['total_time_seconds'] == 15.0
        assert stats['average_time_per_item'] == 0.1
        assert stats['total_errors'] == 3
        assert stats['error_rate'] == 0.02  # 3/150
    
    def test_create_optimized_embedder_jina(self, mock_env):
        """Test factory function for Jina embedder."""
        from ingestion.experimental_embedder_jina_v2 import create_optimized_embedder
        
        with patch.dict(os.environ, {'EMBEDDING_MODEL': 'jina-embeddings-v4'}):
            embedder = create_optimized_embedder(base_batch_size=100)
            assert isinstance(embedder, OptimizedJinaEmbeddingGenerator)
            assert embedder.base_batch_size == 100
    
    def test_create_optimized_embedder_fallback(self, mock_env):
        """Test factory function fallback for non-Jina models."""
        from ingestion.experimental_embedder_jina_v2 import create_optimized_embedder
        
        with patch.dict(os.environ, {'EMBEDDING_MODEL': 'openai-ada-002'}):
            with patch('ingestion.experimental_embedder_jina_v2.EmbeddingGenerator') as mock_generator:
                embedder = create_optimized_embedder()
                mock_generator.assert_called_once_with(model='openai-ada-002')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
