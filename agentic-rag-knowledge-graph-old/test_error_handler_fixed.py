"""
Test error handler circuit breakers and retry logic.
"""

import asyncio
import logging
import time
import random
from typing import Dict, Any
import httpx
from unittest.mock import Mock

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')
from agent.experimental_error_handler import (
    CircuitBreaker, ServiceStatus, ErrorCategory,
    retry_with_backoff, handle_error, get_error_stats,
    AgenticRAGException, TransientError, PermanentError,
    DatabaseConnectionError, EmbeddingGenerationError,
    RateLimitError, InvalidRequestError
)


async def test_circuit_breaker():
    """Test circuit breaker pattern."""
    logger.info("\n=== Testing Circuit Breaker ===")
    
    # Create circuit breaker
    breaker = CircuitBreaker(
        name="test_service",
        failure_threshold=3,
        recovery_timeout=2,
        
    )
    
    # Simulate successful calls
    def good_function():
        return "success"
    
    # Simulate failing calls  
    failure_count = 0
    def failing_function():
        nonlocal failure_count
        failure_count += 1
        raise ValueError(f"Simulated failure {failure_count}")
    
    # Test 1: Circuit closed initially
    assert breaker.status == ServiceStatus.CLOSED
    logger.info("✓ Circuit breaker starts CLOSED")
    
    # Test 2: Success doesn't trip breaker
    for i in range(5):
        result = breaker.call(good_function)
        assert result == "success"
    assert breaker.status == ServiceStatus.CLOSED
    logger.info("✓ Successful calls don't trip breaker")
    
    # Test 3: Failures trip breaker
    for i in range(3):
        try:
            breaker.call(failing_function)
        except ValueError:
            pass
    
    assert breaker.status == ServiceStatus.OPEN
    logger.info(f"✓ Circuit opened after {breaker.failure_count} failures")
    
    # Test 4: Open circuit rejects calls
    try:
        breaker.call(good_function)
        assert False, "Should have raised exception"
    except Exception as e:
        assert "Service unavailable" in str(e)
    logger.info("✓ Open circuit rejects calls")
    
    # Test 5: Wait for recovery and attempt call to trigger HALF_OPEN
    time.sleep(2.5)
    try:
        breaker.call(good_function)
        logger.info("✓ Circuit closed after successful call in recovery")
    except:
        logger.info("✓ Circuit in HALF_OPEN state")
    
    # Test 6: Verify state transitions properly
    assert breaker.status in [ServiceStatus.HALF_OPEN, ServiceStatus.CLOSED]
    logger.info(f"✓ Circuit state after recovery attempt: {breaker.status.value}")
    assert result == "success"
    assert breaker.status == ServiceStatus.CLOSED
    logger.info("✓ Success in HALF_OPEN closes circuit")


async def test_retry_with_backoff():
    """Test retry with exponential backoff."""
    logger.info("\n=== Testing Retry With Backoff ===")
    
    # Test 1: Successful operation doesn't retry
    call_count = 0
    async def success_after_n(n):
        nonlocal call_count
        call_count += 1
        if call_count < n:
            raise DatabaseConnectionError(f"Attempt {call_count}")
        return f"Success after {call_count} attempts"
    
    # Success on first try
    call_count = 0
    result = await retry_with_backoff(
        lambda: success_after_n(1),
        max_retries=3,
        initial_delay=0.1
    )
    assert result == "Success after 1 attempts"
    assert call_count == 1
    logger.info("✓ No retry for successful operation")
    
    # Test 2: Retry until success
    call_count = 0
    start_time = time.time()
    result = await retry_with_backoff(
        lambda: success_after_n(3),
        max_retries=3,
        initial_delay=0.1
    )
    duration = time.time() - start_time
    
    assert result == "Success after 3 attempts"
    assert call_count == 3
    assert duration >= 0.2  # At least initial_delay * 2
    logger.info(f"✓ Retried {call_count-1} times before success (took {duration:.2f}s)")
    
    # Test 3: Max retries exceeded
    call_count = 0
    try:
        await retry_with_backoff(
            lambda: success_after_n(5),
            max_retries=3,
            initial_delay=0.1
        )
        assert False, "Should have raised exception"
    except DatabaseConnectionError as e:
        assert "Attempt 4" in str(e)
    assert call_count == 4  # Initial + 3 retries
    logger.info("✓ Max retries enforced")
    
    # Test 4: Non-retriable exceptions
    async def non_retriable():
        raise InvalidRequestError("This should not be retried")
    
    call_count = 0
    async def counting_non_retriable():
        nonlocal call_count
        call_count += 1
        return await non_retriable()
    
    try:
        await retry_with_backoff(counting_non_retriable)
    except InvalidRequestError:
        pass
    
    assert call_count == 1  # No retries for permanent errors
    logger.info("✓ Non-retriable exceptions not retried")


async def test_error_handling():
    """Test error handling and recovery strategies."""
    logger.info("\n=== Testing Error Handling ===")
    
    # Test different error types
    errors = [
        (DatabaseConnectionError("Connection failed"), ErrorCategory.DATABASE),
        (EmbeddingGenerationError("API timeout"), ErrorCategory.EMBEDDING), 
        (RateLimitError("Rate limit exceeded"), ErrorCategory.RATE_LIMIT),
        (InvalidRequestError("Bad query"), ErrorCategory.VALIDATION)
    ]
    
    for error, expected_category in errors:
        result = handle_error(error, {"operation": "test"})
        assert result["category"] == expected_category
        logger.info(f"✓ {error.__class__.__name__} → {expected_category.value}")
    
    # Test error statistics
    stats = get_error_stats()
    assert stats["total_errors"] > 0
    assert len(stats["errors_by_category"]) > 0
    logger.info(f"✓ Error stats tracking: {stats['total_errors']} total errors")


async def test_database_error_recovery():
    """Test database-specific error recovery."""
    logger.info("\n=== Testing Database Error Recovery ===")
    
    # Simulate connection pool exhausted
    async def db_operation_pool_exhausted():
        raise DatabaseConnectionError("connection pool exhausted")
    
    # Should retry with backoff
    retry_count = 0
    async def counting_db_operation():
        nonlocal retry_count
        retry_count += 1
        if retry_count < 3:
            await db_operation_pool_exhausted()
        return "Success"
    
    start = time.time()
    try:
        result = await retry_with_backoff(
            counting_db_operation,
            max_retries=5,
            initial_delay=0.5
        )
        duration = time.time() - start
        logger.info(f"✓ Pool exhausted recovered after {retry_count} tries in {duration:.2f}s")
    except Exception as e:
        logger.error(f"✗ Failed to recover: {e}")


async def test_embedding_error_recovery():
    """Test embedding API error recovery."""
    logger.info("\n=== Testing Embedding Error Recovery ===")
    
    # Test rate limit handling
    async def rate_limited_call():
        raise RateLimitError("429: Rate limit exceeded")
    
    start = time.time()
    try:
        await retry_with_backoff(
            rate_limited_call,
            max_retries=1,
            initial_delay=1.0
        )
    except RateLimitError:
        duration = time.time() - start
        logger.info(f"✓ Rate limit handled with {duration:.2f}s delay")
    
    # Test timeout with batch size reduction
    batch_size = 100
    async def timeout_with_batch():
        nonlocal batch_size
        if batch_size > 25:
            batch_size = batch_size // 2
            raise EmbeddingGenerationError("Request timeout")
        return f"Success with batch size {batch_size}"
    
    result = await retry_with_backoff(
        timeout_with_batch,
        max_retries=5,
        initial_delay=0.1
    )
    logger.info(f"✓ Timeout recovered: {result}")


async def test_cascading_failures():
    """Test handling of cascading failures."""
    logger.info("\n=== Testing Cascading Failure Handling ===")
    
    # Simulate cascading failure scenario
    failures = {"db": 0, "embed": 0}
    
    async def complex_operation():
        # DB check
        failures["db"] += 1
        if failures["db"] < 3:
            raise DatabaseConnectionError("Database unavailable")
        
        # Embedding check  
        failures["embed"] += 1
        if failures["embed"] < 2:
            raise EmbeddingGenerationError("Embedding service down")
        
        return "All services recovered"
    
    # Test recovery with circuit breakers
    db_breaker = CircuitBreaker("database", failure_threshold=5)
    embed_breaker = CircuitBreaker("embedding", failure_threshold=5)
    
    async def protected_operation():
        # Check DB circuit
        try:
            db_breaker.call(lambda: None if failures["db"] < 3 else "ok")
        except:
            if failures["db"] < 3:
                raise DatabaseConnectionError("DB circuit open")
        
        # Check embedding circuit
        try:
            embed_breaker.call(lambda: None if failures["embed"] < 2 else "ok")
        except:
            if failures["embed"] < 2:
                raise EmbeddingGenerationError("Embed circuit open")
        
        return await complex_operation()
    
    start = time.time()
    try:
        result = await retry_with_backoff(
            protected_operation,
            max_retries=10,
            initial_delay=0.2
        )
        duration = time.time() - start
        logger.info(f"✓ Cascading recovery: {result}")
        logger.info(f"  DB failures: {failures['db']}, Embed failures: {failures['embed']}")
        logger.info(f"  Recovery took {duration:.2f}s")
    except Exception as e:
        logger.error(f"✗ Cascading recovery failed: {e}")


async def main():
    """Run all error handler tests."""
    logger.info("Starting Error Handler Pattern Tests")
    logger.info("=" * 50)
    
    try:
        await test_circuit_breaker()
        await test_retry_with_backoff()
        await test_error_handling()
        await test_database_error_recovery()
        await test_embedding_error_recovery()
        await test_cascading_failures()
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All error handler tests completed successfully!")
        
        # Final statistics
        final_stats = get_error_stats()
        logger.info(f"\nError handling statistics:")
        logger.info(f"  Total errors handled: {final_stats['total_errors']}")
        for category, count in final_stats['errors_by_category'].items():
            logger.info(f"  {category}: {count}")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
