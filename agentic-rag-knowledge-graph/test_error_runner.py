"""Simple test runner for experimental error handler tests."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import time
from datetime import datetime

# Import test classes
from tests.test_experimental_error_handler import (
    TestCustomExceptions, TestCircuitBreaker, TestErrorHandler, TestFallbackHandler
)

async def run_async_tests():
    """Run async tests for error handler."""
    print("Running experimental error handler tests...\n")
    
    # Test 1: Custom Exceptions
    print("1. Testing custom exceptions...")
    try:
        test = TestCustomExceptions()
        test.test_base_exception()
        test.test_transient_error()
        test.test_database_connection_error()
        test.test_rate_limit_error()
        test.test_permanent_errors()
        print("✅ PASSED: All custom exception tests\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 2: Circuit Breaker
    print("2. Testing circuit breaker...")
    try:
        test = TestCircuitBreaker()
        test.test_initialization()
        test.test_successful_call()
        test.test_failure_tracking()
        test.test_open_circuit_rejection()
        test.test_circuit_recovery()
        test.test_get_status()
        print("✅ PASSED: All circuit breaker tests\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 3: Async Circuit Breaker
    print("3. Testing async circuit breaker...")
    try:
        from agent.experimental_error_handler import CircuitBreaker
        cb = CircuitBreaker("test", failure_threshold=2)
        
        async def test_func(x):
            return x * 2
        
        result = await cb.async_call(test_func, 5)
        assert result == 10
        
        async def failing_func():
            raise ValueError("Test error")
        
        # Should fail twice and open
        try:
            await cb.async_call(failing_func)
        except ValueError:
            pass
        try:
            await cb.async_call(failing_func)
        except ValueError:
            pass
        
        assert cb.status.value == "open"
        print("✅ PASSED: Async circuit breaker\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 4: Retry Decorator
    print("4. Testing retry decorator...")
    try:
        from agent.experimental_error_handler import retry_with_backoff, TransientError
        
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
        print("✅ PASSED: Retry decorator\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 5: Error Handler
    print("5. Testing error handler...")
    try:
        test = TestErrorHandler()
        test.test_handle_custom_error()
        test.test_handle_standard_error()
        test.test_error_history_limit()
        test.test_get_error_stats()
        print("✅ PASSED: All error handler tests\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 6: Fallback Handlers
    print("6. Testing fallback handlers...")
    try:
        from agent.experimental_error_handler import FallbackHandler
        
        # Test embedding fallback
        embedding = await FallbackHandler.embedding_fallback("test")
        assert len(embedding) == 2048
        assert all(x == 0.0 for x in embedding)
        
        # Test LLM fallback
        response = await FallbackHandler.llm_fallback("test")
        assert "apologize" in response.lower()
        
        # Test database fallback
        results = await FallbackHandler.database_fallback("test")
        assert isinstance(results, list)
        
        # Test graph fallback
        result = await FallbackHandler.graph_fallback("test")
        assert result is None
        
        print("✅ PASSED: All fallback handlers\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 7: Circuit Breaker Registry
    print("7. Testing circuit breaker registry...")
    try:
        from agent.experimental_error_handler import CircuitBreakerRegistry
        
        registry = CircuitBreakerRegistry()
        cb1 = registry.register("service1", failure_threshold=5)
        cb2 = registry.register("service2", failure_threshold=3)
        
        assert registry.get("service1") is cb1
        assert registry.get("service2") is cb2
        assert registry.get("nonexistent") is None
        
        # Test no duplicate registration
        cb3 = registry.register("service1", failure_threshold=10)
        assert cb3 is cb1  # Same instance
        assert cb1.failure_threshold == 5  # Original settings
        
        print("✅ PASSED: Circuit breaker registry\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 8: Global Functions
    print("8. Testing global functions...")
    try:
        from agent.experimental_error_handler import (
            get_circuit_breaker, handle_error, get_error_stats,
            InvalidRequestError
        )
        
        # Test global circuit breaker
        cb = get_circuit_breaker("global_test", failure_threshold=3)
        assert cb.name == "global_test"
        
        # Test global error handler
        error = InvalidRequestError()
        info = handle_error(error)
        assert info["type"] == "InvalidRequestError"
        
        stats = get_error_stats()
        assert stats["total_errors"] > 0
        
        print("✅ PASSED: Global functions\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 9: Service Health
    print("9. Testing service health...")
    try:
        from agent.experimental_error_handler import ServiceHealth
        from unittest.mock import AsyncMock
        
        health = ServiceHealth()
        
        # Mock healthy database
        mock_pool = AsyncMock()
        mock_conn = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=1)
        mock_pool.acquire = AsyncMock(return_value=mock_conn)
        
        result = await health.check_database(mock_pool)
        assert result is True
        
        # Test health status
        health.health_checks = {"database": True, "graph": False}
        health.last_check = datetime.now()
        status = health.get_health_status()
        assert status["overall_health"] is False
        
        print("✅ PASSED: Service health\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")
    
    # Test 10: Exponential Backoff
    print("10. Testing exponential backoff...")
    try:
        from agent.experimental_error_handler import retry_with_backoff, TransientError
        
        delays = []
        
        @retry_with_backoff(
            max_retries=4,
            initial_delay=0.01,
            exponential_base=2,
            jitter=False
        )
        def track_delays():
            if len(delays) < 3:
                delays.append(time.time())
                raise TransientError()
            return "done"
        
        track_delays()
        
        # Calculate actual delays
        actual_delays = []
        for i in range(1, len(delays)):
            actual_delays.append(delays[i] - delays[i-1])
        
        # Should be exponentially increasing
        assert actual_delays[0] < actual_delays[1]
        print("✅ PASSED: Exponential backoff\n")
    except Exception as e:
        print(f"❌ FAILED: {e}\n")

def main():
    """Run all tests."""
    print("\n=== Error Handler Test Suite ===\n")
    asyncio.run(run_async_tests())
    print("\n=== Test Summary ===")
    print("Tests completed. Check results above for any failures.")

if __name__ == "__main__":
    main()
