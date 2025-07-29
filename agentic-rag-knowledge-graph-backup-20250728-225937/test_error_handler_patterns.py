"""
Test error handler circuit breakers and retry logic.
"""

import asyncio
import logging
import time
import random
from typing import List, Dict, Any
from unittest.mock import AsyncMock, Mock, patch
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')
from agent.experimental_error_handler import (
    CircuitBreaker, CircuitState, RetryHandler, ErrorRecovery,
    DatabaseErrorRecovery, EmbeddingErrorRecovery, SearchErrorRecovery,
    GlobalErrorHandler
)


async def test_circuit_breaker():
    """Test circuit breaker pattern."""
    logger.info("\n=== Testing Circuit Breaker ===")
    
    # Create circuit breaker with low thresholds for testing
    breaker = CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=2.0,
        expected_exception=ValueError
    )
    
    # Simulate successful calls
    async def good_function():
        return "success"
    
    # Simulate failing calls
    failure_count = 0
    async def failing_function():
        nonlocal failure_count
        failure_count += 1
        raise ValueError(f"Simulated failure {failure_count}")
    
    # Test 1: Circuit closed initially
    assert breaker.state == CircuitState.CLOSED
    logger.info("✓ Circuit breaker starts CLOSED")
    
    # Test 2: Success doesn't trip breaker
    for i in range(5):
        result = await breaker.call(good_function)
        assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    logger.info("✓ Successful calls don't trip breaker")
    
    # Test 3: Failures trip breaker
    for i in range(3):
        try:
            await breaker.call(failing_function)
        except ValueError:
            pass
    
    assert breaker.state == CircuitState.OPEN
    assert breaker.failure_count == 3
    logger.info(f"✓ Circuit opened after {breaker.failure_count} failures")
    
    # Test 4: Open circuit rejects calls
    try:
        await breaker.call(good_function)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Circuit breaker is OPEN" in str(e)
    logger.info("✓ Open circuit rejects calls")
    
    # Test 5: Wait for recovery timeout
    await asyncio.sleep(2.5)
    assert breaker.state == CircuitState.HALF_OPEN
    logger.info("✓ Circuit moves to HALF_OPEN after timeout")
    
    # Test 6: Success in HALF_OPEN closes circuit
    result = await breaker.call(good_function)
    assert result == "success"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
    logger.info("✓ Success in HALF_OPEN closes circuit")
    
    # Test 7: Failure in HALF_OPEN reopens circuit
    for i in range(3):
        try:
            await breaker.call(failing_function)
        except ValueError:
            pass
    
    assert breaker.state == CircuitState.OPEN
    await asyncio.sleep(2.5)
    assert breaker.state == CircuitState.HALF_OPEN
    
    try:
        await breaker.call(failing_function)
    except ValueError:
        pass
    
    assert breaker.state == CircuitState.OPEN
    logger.info("✓ Failure in HALF_OPEN reopens circuit")


async def test_retry_handler():
    """Test retry handler with exponential backoff."""
    logger.info("\n=== Testing Retry Handler ===")
    
    # Create retry handler with short intervals for testing
    retry_handler = RetryHandler(
        max_retries=3,
        base_delay=0.1,
        max_delay=1.0,
        exponential_base=2
    )
    
    # Test 1: Successful operation doesn't retry
    call_count = 0
    async def success_after_n(n):
        nonlocal call_count
        call_count += 1
        if call_count < n:
            raise ValueError(f"Attempt {call_count}")
        return f"Success after {call_count} attempts"
    
    # Success on first try
    call_count = 0
    result = await retry_handler.execute(lambda: success_after_n(1))
    assert result == "Success after 1 attempts"
    assert call_count == 1
    logger.info("✓ No retry for successful operation")
    
    # Test 2: Retry until success
    call_count = 0
    start_time = time.time()
    result = await retry_handler.execute(lambda: success_after_n(3))
    duration = time.time() - start_time
    
    assert result == "Success after 3 attempts"
    assert call_count == 3
    assert duration >= 0.2  # At least base_delay * 2 (0.1 + 0.2)
    logger.info(f"✓ Retried {call_count-1} times before success (took {duration:.2f}s)")
    
    # Test 3: Max retries exceeded
    call_count = 0
    try:
        await retry_handler.execute(lambda: success_after_n(5))
        assert False, "Should have raised exception"
    except ValueError as e:
        assert "Attempt 4" in str(e)
    assert call_count == 4  # Initial + 3 retries
    logger.info("✓ Max retries enforced")
    
    # Test 4: Test jitter (multiple runs should have different timings)
    timings = []
    for _ in range(3):
        call_count = 0
        start_time = time.time()
        try:
            await retry_handler.execute(lambda: success_after_n(10))
        except:
            pass
        timings.append(time.time() - start_time)
    
    # Timings should vary due to jitter
    assert len(set(timings)) > 1
    logger.info(f"✓ Jitter working: timings = {[f'{t:.3f}' for t in timings]}")
    
    # Test 5: Non-retriable exceptions
    async def non_retriable():
        raise TypeError("This should not be retried")
    
    call_count = 0
    async def counting_non_retriable():
        nonlocal call_count
        call_count += 1
        await non_retriable()
    
    try:
        await retry_handler.execute(counting_non_retriable, retriable_exceptions=(ValueError,))
    except TypeError:
        pass
    
    assert call_count == 1  # No retries
    logger.info("✓ Non-retriable exceptions not retried")


async def test_error_recovery_strategies():
    """Test various error recovery strategies."""
    logger.info("\n=== Testing Error Recovery Strategies ===")
    
    # Test Database Error Recovery
    logger.info("\nTesting Database Recovery:")
    db_recovery = DatabaseErrorRecovery()
    
    # Test connection pool exhausted
    error = Exception("connection pool exhausted")
    strategy = await db_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "retry"
    assert strategy["wait_time"] == 1.0
    logger.info("✓ Pool exhausted → retry strategy")
    
    # Test deadlock
    error = Exception("deadlock detected")
    strategy = await db_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "retry"
    assert "jitter" in strategy
    logger.info("✓ Deadlock → retry with jitter")
    
    # Test syntax error
    error = Exception("syntax error at or near")
    strategy = await db_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "fail"
    logger.info("✓ Syntax error → fail fast")
    
    # Test Embedding Error Recovery
    logger.info("\nTesting Embedding Recovery:")
    embed_recovery = EmbeddingErrorRecovery()
    
    # Test rate limit
    error = httpx.HTTPStatusError("429", request=Mock(), response=Mock(status_code=429))
    strategy = await embed_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "retry"
    assert strategy["wait_time"] == 60
    logger.info("✓ Rate limit → backoff 60s")
    
    # Test timeout
    error = httpx.TimeoutException("Request timeout")
    strategy = await embed_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "retry"
    assert strategy["reduce_batch_size"] == True
    logger.info("✓ Timeout → retry with smaller batch")
    
    # Test server error
    error = httpx.HTTPStatusError("500", request=Mock(), response=Mock(status_code=500))
    strategy = await embed_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "fallback"
    assert strategy["fallback_provider"] == "openai"
    logger.info("✓ Server error → fallback provider")
    
    # Test Search Error Recovery
    logger.info("\nTesting Search Recovery:")
    search_recovery = SearchErrorRecovery()
    
    # Test timeout
    error = asyncio.TimeoutError()
    strategy = await search_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "retry"
    assert strategy["simplify_query"] == True
    logger.info("✓ Timeout → simplify query")
    
    # Test no results
    error = ValueError("No results found")
    strategy = await search_recovery.get_recovery_strategy(error)
    assert strategy["action"] == "fallback"
    assert strategy["broaden_search"] == True
    logger.info("✓ No results → broaden search")


async def test_global_error_handler():
    """Test global error handler coordination."""
    logger.info("\n=== Testing Global Error Handler ===")
    
    handler = GlobalErrorHandler()
    
    # Test 1: Register handlers
    db_recovery = DatabaseErrorRecovery()
    embed_recovery = EmbeddingErrorRecovery()
    search_recovery = SearchErrorRecovery()
    
    handler.register_handler("database", db_recovery)
    handler.register_handler("embedding", embed_recovery)
    handler.register_handler("search", search_recovery)
    logger.info("✓ Handlers registered")
    
    # Test 2: Database error handling
    async def db_operation():
        raise Exception("connection pool exhausted")
    
    start = time.time()
    try:
        await handler.handle_with_recovery(db_operation, "database", max_retries=2)
    except Exception:
        pass
    duration = time.time() - start
    
    # Should have retried with delays
    assert duration >= 1.0  # At least one retry with 1s delay
    logger.info(f"✓ Database retry took {duration:.2f}s")
    
    # Test 3: Circuit breaker integration
    # Force circuit to open
    for _ in range(5):
        try:
            await handler.handle_with_recovery(
                lambda: asyncio.create_task(db_operation()),
                "database"
            )
        except:
            pass
    
    # Circuit should be open
    breaker_open = False
    try:
        await handler.handle_with_recovery(lambda: 1/0, "database")
    except Exception as e:
        if "Circuit breaker is OPEN" in str(e):
            breaker_open = True
    
    logger.info(f"✓ Circuit breaker integration: {'OPEN' if breaker_open else 'CLOSED'}")
    
    # Test 4: Get system health
    health = await handler.get_system_health()
    logger.info(f"System health: {health}")
    assert "database" in health
    assert "embedding" in health
    assert "search" in health
    logger.info("✓ Health monitoring working")


async def test_cascading_failures():
    """Test handling of cascading failures."""
    logger.info("\n=== Testing Cascading Failure Handling ===")
    
    handler = GlobalErrorHandler()
    
    # Simulate cascading failure scenario
    failures = {"db": 0, "embed": 0, "search": 0}
    
    async def failing_db():
        failures["db"] += 1
        if failures["db"] < 10:
            raise Exception("Database connection failed")
        return "DB recovered"
    
    async def failing_embed():
        failures["embed"] += 1
        if failures["embed"] < 5:
            raise httpx.TimeoutException("Embedding timeout")
        return "Embed recovered"
    
    async def complex_operation():
        # This simulates an operation that needs both DB and embeddings
        db_result = await failing_db()
        embed_result = await failing_embed()
        return f"{db_result}, {embed_result}"
    
    # Register recovery handlers
    handler.register_handler("database", DatabaseErrorRecovery())
    handler.register_handler("embedding", EmbeddingErrorRecovery())
    
    # Test cascading recovery
    start = time.time()
    try:
        # This will fail multiple times before succeeding
        result = await handler.handle_with_recovery(
            complex_operation,
            "database",
            max_retries=15
        )
        logger.info(f"✓ Cascading recovery succeeded: {result}")
        logger.info(f"  DB failures: {failures['db']}, Embed failures: {failures['embed']}")
    except Exception as e:
        logger.error(f"✗ Cascading recovery failed: {e}")
    
    duration = time.time() - start
    logger.info(f"✓ Recovery took {duration:.2f}s")


async def main():
    """Run all error handler tests."""
    logger.info("Starting Error Handler Pattern Tests")
    logger.info("=" * 50)
    
    try:
        await test_circuit_breaker()
        await test_retry_handler()
        await test_error_recovery_strategies()
        await test_global_error_handler()
        await test_cascading_failures()
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All error handler tests completed successfully!")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
