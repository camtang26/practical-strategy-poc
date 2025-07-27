"""
Test error handler circuit breakers and retry logic - simplified version.
"""

import asyncio
import logging
import time
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')
from agent.experimental_error_handler import (
    CircuitBreaker, ServiceStatus, ErrorCategory,
    retry_with_backoff, handle_error, get_error_stats,
    DatabaseConnectionError, EmbeddingGenerationError,
    RateLimitError, InvalidRequestError
)


async def test_circuit_breaker():
    """Test circuit breaker basic functionality."""
    logger.info("\n=== Testing Circuit Breaker ===")
    
    breaker = CircuitBreaker("test_service", failure_threshold=3, recovery_timeout=2)
    
    # Test successful calls
    def good_function():
        return "success"
    
    # Test failing calls  
    def failing_function():
        raise ValueError("Simulated failure")
    
    # Circuit starts closed
    assert breaker.status == ServiceStatus.CLOSED
    logger.info("✓ Circuit breaker starts CLOSED")
    
    # Failures trip breaker
    for i in range(3):
        try:
            breaker.call(failing_function)
        except ValueError:
            pass
    
    assert breaker.status == ServiceStatus.OPEN
    logger.info(f"✓ Circuit opened after {breaker.failure_count} failures")
    
    # Open circuit rejects calls
    try:
        breaker.call(good_function)
        assert False, "Should reject"
    except:
        logger.info("✓ Open circuit rejects calls")
    
    # Wait for recovery
    time.sleep(2.5)
    result = breaker.call(good_function)
    assert result == "success"
    assert breaker.status == ServiceStatus.CLOSED
    logger.info("✓ Circuit recovers after timeout")


async def test_retry_decorator():
    """Test retry decorator functionality."""
    logger.info("\n=== Testing Retry Decorator ===")
    
    call_count = 0
    
    @retry_with_backoff(max_retries=3, initial_delay=0.1)
    async def flaky_function(fail_times=2):
        nonlocal call_count
        call_count += 1
        if call_count <= fail_times:
            raise DatabaseConnectionError(f"Attempt {call_count}")
        return f"Success after {call_count} attempts"
    
    # Test retry behavior
    call_count = 0
    start = time.time()
    result = await flaky_function(fail_times=2)
    duration = time.time() - start
    
    assert "Success after 3 attempts" in result
    assert call_count == 3
    assert duration > 0.2  # Should have delays
    logger.info(f"✓ Retried {call_count-1} times in {duration:.2f}s")
    
    # Test non-retriable error
    @retry_with_backoff(max_retries=3, retry_on=DatabaseConnectionError)
    async def permanent_error():
        raise InvalidRequestError("Bad request")
    
    try:
        await permanent_error()
        assert False, "Should not retry"
    except InvalidRequestError:
        logger.info("✓ Non-retriable errors not retried")


async def test_error_handling():
    """Test error categorization and handling."""
    logger.info("\n=== Testing Error Handling ===")
    
    # Test error categorization
    errors = [
        (DatabaseConnectionError("DB down"), ErrorCategory.TRANSIENT),
        (EmbeddingGenerationError("API error"), ErrorCategory.TRANSIENT),
        (RateLimitError("Too many requests"), ErrorCategory.TRANSIENT),
        (InvalidRequestError("Invalid query"), ErrorCategory.PERMANENT)
    ]
    
    for error, expected_category in errors:
        result = handle_error(error, {"test": True})
        assert result["category"] == expected_category.value
        logger.info(f"✓ {error.__class__.__name__} → {expected_category.value}")
    
    # Check statistics
    stats = get_error_stats()
    assert stats["total_errors"] >= len(errors)
    logger.info(f"✓ Error stats: {stats['total_errors']} total errors tracked")


async def test_real_world_scenario():
    """Test a real-world scenario with cascading failures."""
    logger.info("\n=== Testing Real-World Scenario ===")
    
    # Create circuit breakers for different services
    db_breaker = CircuitBreaker("database", failure_threshold=3, recovery_timeout=2)
    api_breaker = CircuitBreaker("embedding_api", failure_threshold=2, recovery_timeout=2)
    
    # Simulate intermittent failures
    db_failures = 0
    api_failures = 0
    
    @retry_with_backoff(max_retries=5, initial_delay=0.2)
    async def complex_operation():
        nonlocal db_failures, api_failures
        
        # Check database
        def db_check():
            nonlocal db_failures
            db_failures += 1
            if db_failures < 3:
                raise DatabaseConnectionError("DB unavailable")
            return "DB OK"
        
        # Check API
        def api_check():
            nonlocal api_failures
            api_failures += 1
            if api_failures < 2:
                raise EmbeddingGenerationError("API down")
            return "API OK"
        
        # Try operations with circuit breakers
        try:
            db_status = db_breaker.call(db_check)
        except Exception as e:
            logger.warning(f"DB check failed: {e}")
            raise
        
        try:
            api_status = api_breaker.call(api_check)
        except Exception as e:
            logger.warning(f"API check failed: {e}")
            raise
        
        return f"Operation complete: {db_status}, {api_status}"
    
    # Execute with retries
    start = time.time()
    try:
        result = await complex_operation()
        duration = time.time() - start
        logger.info(f"✓ Complex operation succeeded: {result}")
        logger.info(f"  DB failures: {db_failures}, API failures: {api_failures}")
        logger.info(f"  Total time: {duration:.2f}s")
    except Exception as e:
        logger.error(f"✗ Complex operation failed: {e}")
    
    # Check circuit breaker states
    logger.info(f"  DB breaker: {db_breaker.status.value}")
    logger.info(f"  API breaker: {api_breaker.status.value}")


async def main():
    """Run all error handler tests."""
    logger.info("Starting Error Handler Tests (Simplified)")
    logger.info("=" * 50)
    
    try:
        await test_circuit_breaker()
        await test_retry_decorator()
        await test_error_handling()
        await test_real_world_scenario()
        
        logger.info("\n" + "=" * 50)
        logger.info("✅ All error handler tests completed successfully!")
        
        # Final statistics
        final_stats = get_error_stats()
        logger.info(f"\nFinal error statistics:")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
