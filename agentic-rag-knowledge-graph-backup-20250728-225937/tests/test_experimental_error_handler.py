"""
Unit tests for experimental_error_handler.py
Tests circuit breakers, retry logic, error categorization, and fallback handlers.
"""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')

from agent.experimental_error_handler import (
    ErrorCategory, ServiceStatus, AgenticRAGException, TransientError,
    DatabaseConnectionError, EmbeddingGenerationError, GraphSearchError,
    RateLimitError, PermanentError, InvalidRequestError, AuthenticationError,
    CircuitBreaker, CircuitBreakerRegistry, get_circuit_breaker,
    retry_with_backoff, ErrorHandler, handle_error, get_error_stats,
    FallbackHandler, ServiceHealth, check_system_health
)


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_base_exception(self):
        """Test base AgenticRAGException."""
        exc = AgenticRAGException("Test error", {"key": "value"})
        assert str(exc) == "Test error"
        assert exc.details == {"key": "value"}
        assert exc.category == ErrorCategory.PERMANENT
    
    def test_transient_error(self):
        """Test transient error category."""
        exc = TransientError()
        assert exc.category == ErrorCategory.TRANSIENT
        assert "temporarily unavailable" in exc.user_message
    
    def test_database_connection_error(self):
        """Test database error."""
        exc = DatabaseConnectionError()
        assert exc.category == ErrorCategory.TRANSIENT
        assert "database" in exc.user_message.lower()
    
    def test_rate_limit_error(self):
        """Test rate limit error with retry_after."""
        exc = RateLimitError(retry_after=30)
        assert exc.retry_after == 30
        assert exc.category == ErrorCategory.TRANSIENT
    
    def test_permanent_errors(self):
        """Test permanent error types."""
        invalid = InvalidRequestError()
        auth = AuthenticationError()
        
        assert invalid.category == ErrorCategory.PERMANENT
        assert auth.category == ErrorCategory.PERMANENT
        assert "invalid" in invalid.user_message.lower()
        assert "authentication" in auth.user_message.lower()


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    def test_initialization(self):
        """Test circuit breaker initialization."""
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=30)
        assert cb.name == "test"
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30
        assert cb.status == ServiceStatus.CLOSED
        assert cb.failure_count == 0
    
    def test_successful_call(self):
        """Test successful function calls."""
        cb = CircuitBreaker("test", failure_threshold=2)
        
        def test_func(x):
            return x * 2
        
        result = cb.call(test_func, 5)
        assert result == 10
        assert cb.status == ServiceStatus.CLOSED
        assert cb.failure_count == 0
    
    def test_failure_tracking(self):
        """Test failure counting and circuit opening."""
        cb = CircuitBreaker("test", failure_threshold=2, expected_exception=ValueError)
        
        def failing_func():
            raise ValueError("Test error")
        
        # First failure
        with pytest.raises(ValueError):
            cb.call(failing_func)
        assert cb.failure_count == 1
        assert cb.status == ServiceStatus.CLOSED
        
        # Second failure - should open circuit
        with pytest.raises(ValueError):
            cb.call(failing_func)
        assert cb.failure_count == 2
        assert cb.status == ServiceStatus.OPEN
    
    def test_open_circuit_rejection(self):
        """Test that open circuit rejects calls."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60)
        
        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError()))
        
        assert cb.status == ServiceStatus.OPEN
        
        # Should reject new calls
        with pytest.raises(TransientError) as exc_info:
            cb.call(lambda: "success")
        
        assert "Circuit breaker is open" in str(exc_info.value)
    
    def test_circuit_recovery(self):
        """Test circuit breaker recovery after timeout."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        
        # Open the circuit
        with pytest.raises(ValueError):
            cb.call(lambda: (_ for _ in ()).throw(ValueError()))
        
        # Wait for recovery timeout
        time.sleep(0.2)
        
        # Should enter half-open and succeed
        result = cb.call(lambda: "recovered")
        assert result == "recovered"
        assert cb.status == ServiceStatus.CLOSED
        assert cb.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_async_circuit_breaker(self):
        """Test circuit breaker with async functions."""
        cb = CircuitBreaker("test", failure_threshold=2)
        
        async def async_func(x):
            return x * 2
        
        result = await cb.async_call(async_func, 5)
        assert result == 10
        
        async def failing_async():
            raise ValueError("Async error")
        
        # Test failures
        with pytest.raises(ValueError):
            await cb.async_call(failing_async)
        with pytest.raises(ValueError):
            await cb.async_call(failing_async)
        
        assert cb.status == ServiceStatus.OPEN
    
    def test_get_status(self):
        """Test status reporting."""
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60)
        
        status = cb.get_status()
        assert status["name"] == "test"
        assert status["status"] == "closed"
        assert status["failure_count"] == 0
        assert status["time_until_reset"] is None
        
        # Open circuit
        cb.status = ServiceStatus.OPEN
        cb.last_failure_time = datetime.now()
        
        status = cb.get_status()
        assert status["status"] == "open"
        assert status["time_until_reset"] is not None
        assert status["time_until_reset"] <= 60


class TestCircuitBreakerRegistry:
    """Test circuit breaker registry."""
    
    def test_register_and_get(self):
        """Test registering and retrieving circuit breakers."""
        registry = CircuitBreakerRegistry()
        
        cb1 = registry.register("service1", failure_threshold=5)
        cb2 = registry.register("service2", failure_threshold=3)
        
        assert registry.get("service1") is cb1
        assert registry.get("service2") is cb2
        assert registry.get("nonexistent") is None
    
    def test_no_duplicate_registration(self):
        """Test that registering same name returns existing breaker."""
        registry = CircuitBreakerRegistry()
        
        cb1 = registry.register("test", failure_threshold=5)
        cb2 = registry.register("test", failure_threshold=10)
        
        assert cb1 is cb2
        assert cb1.failure_threshold == 5  # Original settings preserved
    
    def test_get_all_status(self):
        """Test getting status of all breakers."""
        registry = CircuitBreakerRegistry()
        
        registry.register("service1")
        registry.register("service2")
        
        statuses = registry.get_all_status()
        assert len(statuses) == 2
        assert all(s["status"] == "closed" for s in statuses)
    
    def test_global_registry(self):
        """Test global circuit breaker registry."""
        cb = get_circuit_breaker("global_test", failure_threshold=3)
        assert cb.name == "global_test"
        assert cb.failure_threshold == 3
        
        # Should return same instance
        cb2 = get_circuit_breaker("global_test", failure_threshold=5)
        assert cb is cb2


class TestRetryDecorator:
    """Test retry with backoff decorator."""
    
    @pytest.mark.asyncio
    async def test_async_retry_success(self):
        """Test async retry succeeds on second attempt."""
        attempt_count = 0
        
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise TransientError("Temporary failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert attempt_count == 2
    
    def test_sync_retry_success(self):
        """Test sync retry succeeds on second attempt."""
        attempt_count = 0
        
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        def flaky_function():
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count < 2:
                raise TransientError("Temporary failure")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert attempt_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test retry gives up after max attempts."""
        attempt_count = 0
        
        @retry_with_backoff(max_retries=3, initial_delay=0.01)
        async def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise TransientError("Always fails")
        
        with pytest.raises(TransientError):
            await always_fails()
        
        assert attempt_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_with_rate_limit(self):
        """Test retry respects rate limit retry_after."""
        @retry_with_backoff(max_retries=2, initial_delay=0.01)
        async def rate_limited():
            raise RateLimitError(retry_after=0.05)
        
        start_time = time.time()
        with pytest.raises(RateLimitError):
            await rate_limited()
        elapsed = time.time() - start_time
        
        # Should wait at least retry_after time
        assert elapsed >= 0.05
    
    @pytest.mark.asyncio
    async def test_retry_only_on_specific_errors(self):
        """Test retry only catches specified exceptions."""
        @retry_with_backoff(retry_on=ValueError, max_retries=3, initial_delay=0.01)
        async def raises_type_error():
            raise TypeError("Wrong type")
        
        # Should not retry TypeError
        with pytest.raises(TypeError):
            await raises_type_error()
    
    def test_exponential_backoff(self):
        """Test exponential backoff calculation."""
        delays = []
        
        @retry_with_backoff(
            max_retries=4,
            initial_delay=0.01,
            exponential_base=2,
            jitter=False
        )
        def track_delays():
            nonlocal delays
            if len(delays) < 3:
                delays.append(time.time())
                raise TransientError()
            return "done"
        
        start = time.time()
        track_delays()
        
        # Calculate actual delays
        actual_delays = []
        for i in range(1, len(delays)):
            actual_delays.append(delays[i] - delays[i-1])
        
        # Should be exponentially increasing
        assert actual_delays[0] < actual_delays[1]
        assert abs(actual_delays[1] / actual_delays[0] - 2) < 0.5  # ~2x increase


class TestErrorHandler:
    """Test centralized error handling."""
    
    def test_handle_custom_error(self):
        """Test handling custom exceptions."""
        handler = ErrorHandler()
        
        error = DatabaseConnectionError()
        info = handler.handle_error(error, {"query": "test"})
        
        assert info["type"] == "DatabaseConnectionError"
        assert info["category"] == ErrorCategory.TRANSIENT.value
        assert info["user_message"] == error.user_message
        assert info["context"]["query"] == "test"
        assert handler.error_counts["DatabaseConnectionError"] == 1
    
    def test_handle_standard_error(self):
        """Test categorizing standard exceptions."""
        handler = ErrorHandler()
        
        # Connection error should be transient
        error = ConnectionError("Network issue")
        info = handler.handle_error(error)
        assert info["category"] == ErrorCategory.TRANSIENT.value
        
        # Value error should be permanent
        error = ValueError("Bad value")
        info = handler.handle_error(error)
        assert info["category"] == ErrorCategory.PERMANENT.value
    
    def test_error_history_limit(self):
        """Test error history is limited."""
        handler = ErrorHandler()
        handler.max_history = 5
        
        # Add more errors than limit
        for i in range(10):
            handler.handle_error(ValueError(f"Error {i}"))
        
        assert len(handler.error_history) == 5
        # Should keep most recent
        assert "Error 9" in handler.error_history[-1]["message"]
    
    def test_get_error_stats(self):
        """Test error statistics."""
        handler = ErrorHandler()
        
        # Generate various errors
        handler.handle_error(TransientError())
        handler.handle_error(TransientError())
        handler.handle_error(PermanentError())
        
        stats = handler.get_error_stats()
        assert stats["total_errors"] == 3
        assert stats["error_counts"]["TransientError"] == 2
        assert stats["error_counts"]["PermanentError"] == 1
        assert len(stats["recent_errors"]) == 3
    
    def test_global_error_handler(self):
        """Test global error handler functions."""
        error = InvalidRequestError()
        info = handle_error(error)
        
        assert info["type"] == "InvalidRequestError"
        assert info["category"] == ErrorCategory.PERMANENT.value
        
        stats = get_error_stats()
        assert stats["total_errors"] > 0


class TestFallbackHandler:
    """Test fallback strategies."""
    
    @pytest.mark.asyncio
    async def test_embedding_fallback(self):
        """Test embedding service fallback."""
        embedding = await FallbackHandler.embedding_fallback("test text")
        assert len(embedding) == 2048
        assert all(x == 0.0 for x in embedding)
    
    @pytest.mark.asyncio
    async def test_llm_fallback(self):
        """Test LLM service fallback."""
        response = await FallbackHandler.llm_fallback("test query")
        assert "apologize" in response.lower()
        assert "technical difficulties" in response.lower()
    
    @pytest.mark.asyncio
    async def test_database_fallback(self):
        """Test database fallback."""
        results = await FallbackHandler.database_fallback("test query")
        assert isinstance(results, list)
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_graph_fallback(self):
        """Test graph database fallback."""
        result = await FallbackHandler.graph_fallback("test query")
        assert result is None


class TestServiceHealth:
    """Test service health monitoring."""
    
    @pytest.mark.asyncio
    async def test_database_health_check(self):
        """Test database health check."""
        health = ServiceHealth()
        
        # Mock healthy database
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        
        result = await health.check_database(mock_pool)
        assert result is True
        
        # Mock unhealthy database
        mock_pool.acquire.side_effect = Exception("Connection failed")
        result = await health.check_database(mock_pool)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_graph_health_check(self):
        """Test graph database health check."""
        health = ServiceHealth()
        
        # Mock healthy graph
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_result.single = Mock(return_value={"1": 1})
        mock_session.run = Mock(return_value=mock_result)
        mock_driver.session = Mock(return_value=mock_session)
        
        result = await health.check_graph(mock_driver)
        assert result is True
        
        # Mock unhealthy graph
        mock_driver.session.side_effect = Exception("Graph error")
        result = await health.check_graph(mock_driver)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_embedding_health_check(self):
        """Test embedding service health check."""
        health = ServiceHealth()
        
        # Mock healthy embedder
        mock_embedder = AsyncMock()
        mock_embedder.generate_embedding = AsyncMock(return_value=[0.0] * 2048)
        
        result = await health.check_embedding_service(mock_embedder)
        assert result is True
        
        # Mock unhealthy embedder
        mock_embedder.generate_embedding = AsyncMock(return_value=[0.0] * 100)
        result = await health.check_embedding_service(mock_embedder)
        assert result is False
    
    @pytest.mark.asyncio
    async def test_check_all_services(self):
        """Test checking all services."""
        health = ServiceHealth()
        
        # Mock services
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        
        results = await health.check_all_services(db_pool=mock_pool)
        
        assert "database" in results
        assert results["database"] is True
        assert health.last_check is not None
    
    def test_get_health_status(self):
        """Test health status reporting."""
        health = ServiceHealth()
        health.health_checks = {"database": True, "graph": False}
        health.last_check = datetime.now()
        
        status = health.get_health_status()
        assert status["services"]["database"] is True
        assert status["services"]["graph"] is False
        assert status["overall_health"] is False
        assert status["last_check"] is not None
    
    @pytest.mark.asyncio
    async def test_check_system_health(self):
        """Test complete system health check."""
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        
        result = await check_system_health(db_pool=mock_pool)
        
        assert "health" in result
        assert "circuit_breakers" in result
        assert "errors" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
