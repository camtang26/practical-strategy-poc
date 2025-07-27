"""
Comprehensive error handling with circuit breakers, retry logic, and graceful degradation.
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
import traceback
from collections import defaultdict

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Categories of errors for different handling strategies."""
    TRANSIENT = "transient"  # Network errors, timeouts, rate limits
    PERMANENT = "permanent"  # Bad requests, authentication errors
    DEGRADED = "degraded"   # Partial failures, fallback mode
    CRITICAL = "critical"    # System failures, data corruption


class ServiceStatus(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Service is down, fail fast
    HALF_OPEN = "half_open" # Testing if service recovered


class AgenticRAGException(Exception):
    """Base exception for all custom errors."""
    category = ErrorCategory.PERMANENT
    user_message = "An error occurred while processing your request."
    
    def __init__(self, message: str = None, details: Dict[str, Any] = None):
        self.message = message or self.user_message
        self.details = details or {}
        super().__init__(self.message)


class TransientError(AgenticRAGException):
    """Recoverable errors that should be retried."""
    category = ErrorCategory.TRANSIENT
    user_message = "The service is temporarily unavailable. Please try again."


class DatabaseConnectionError(TransientError):
    """Database connection failures."""
    user_message = "Unable to connect to the database. Please try again later."


class EmbeddingGenerationError(TransientError):
    """Embedding API failures."""
    user_message = "The AI service is temporarily unavailable. Please try again."


class GraphSearchError(TransientError):
    """Knowledge graph query failures."""
    user_message = "Unable to search the knowledge base. Please try again."


class RateLimitError(TransientError):
    """API rate limit exceeded."""
    user_message = "Request limit exceeded. Please wait a moment and try again."
    
    def __init__(self, retry_after: int = 60):
        super().__init__()
        self.retry_after = retry_after


class PermanentError(AgenticRAGException):
    """Non-recoverable errors."""
    category = ErrorCategory.PERMANENT


class InvalidRequestError(PermanentError):
    """Bad request parameters."""
    user_message = "Invalid request. Please check your input and try again."


class AuthenticationError(PermanentError):
    """Authentication/authorization failures."""
    user_message = "Authentication failed. Please check your credentials."


class CircuitBreaker:
    """Circuit breaker pattern implementation."""
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: Type[Exception] = Exception
    ):
        """Initialize circuit breaker."""
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.status = ServiceStatus.CLOSED
        
    def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection."""
        if self.status == ServiceStatus.OPEN:
            if self._should_attempt_reset():
                self.status = ServiceStatus.HALF_OPEN
            else:
                raise TransientError(
                    f"Circuit breaker is open for {self.name}. Service unavailable.",
                    {"retry_after": self._time_until_reset()}
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    async def async_call(self, func: Callable, *args, **kwargs):
        """Execute async function with circuit breaker protection."""
        if self.status == ServiceStatus.OPEN:
            if self._should_attempt_reset():
                self.status = ServiceStatus.HALF_OPEN
            else:
                raise TransientError(
                    f"Circuit breaker is open for {self.name}. Service unavailable.",
                    {"retry_after": self._time_until_reset()}
                )
        
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Reset circuit breaker on successful call."""
        self.failure_count = 0
        self.status = ServiceStatus.CLOSED
        logger.info(f"Circuit breaker {self.name} reset to CLOSED")
    
    def _on_failure(self):
        """Record failure and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            self.status = ServiceStatus.OPEN
            logger.warning(
                f"Circuit breaker {self.name} opened after {self.failure_count} failures"
            )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to retry."""
        return (
            self.last_failure_time and
            datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout)
        )
    
    def _time_until_reset(self) -> int:
        """Calculate seconds until circuit breaker resets."""
        if not self.last_failure_time:
            return 0
        
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return max(0, int(self.recovery_timeout - elapsed))
    
    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status."""
        return {
            "name": self.name,
            "status": self.status.value,
            "failure_count": self.failure_count,
            "time_until_reset": self._time_until_reset() if self.status == ServiceStatus.OPEN else None
        }


class CircuitBreakerRegistry:
    """Manage multiple circuit breakers."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def register(self, name: str, **kwargs) -> CircuitBreaker:
        """Register a new circuit breaker."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(name, **kwargs)
        return self._breakers[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._breakers.get(name)
    
    def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status of all circuit breakers."""
        return [breaker.get_status() for breaker in self._breakers.values()]


# Global circuit breaker registry
_circuit_breakers = CircuitBreakerRegistry()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Get or create a circuit breaker."""
    return _circuit_breakers.register(name, **kwargs)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Union[Type[Exception], tuple] = TransientError
):
    """Decorator for retry logic with exponential backoff."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed {func.__name__} after {max_retries} attempts: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        import random
                        delay *= (0.5 + random.random())
                    
                    # Check for rate limit headers
                    if isinstance(e, RateLimitError):
                        delay = max(delay, e.retry_after)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.1f}s delay. Error: {e}"
                    )
                    
                    await asyncio.sleep(delay)
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Failed {func.__name__} after {max_retries} attempts: {e}"
                        )
                        raise
                    
                    # Calculate delay
                    delay = min(initial_delay * (exponential_base ** attempt), max_delay)
                    
                    if jitter:
                        import random
                        delay *= (0.5 + random.random())
                    
                    if isinstance(e, RateLimitError):
                        delay = max(delay, e.retry_after)
                    
                    logger.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.1f}s delay. Error: {e}"
                    )
                    
                    time.sleep(delay)
            
            raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


class ErrorHandler:
    """Centralized error handling and reporting."""
    
    def __init__(self):
        self.error_counts = defaultdict(int)
        self.error_history = []
        self.max_history = 1000
    
    def handle_error(
        self,
        error: Exception,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process and categorize an error."""
        error_info = {
            "type": type(error).__name__,
            "message": str(error),
            "timestamp": datetime.now().isoformat(),
            "context": context or {},
            "traceback": traceback.format_exc()
        }
        
        # Categorize error
        if isinstance(error, AgenticRAGException):
            error_info["category"] = error.category.value
            error_info["user_message"] = error.user_message
            error_info["details"] = error.details
        else:
            # Categorize common errors
            error_info["category"] = self._categorize_error(error)
            error_info["user_message"] = self._get_user_message(error)
        
        # Track error
        self.error_counts[error_info["type"]] += 1
        self.error_history.append(error_info)
        
        # Trim history
        if len(self.error_history) > self.max_history:
            self.error_history = self.error_history[-self.max_history:]
        
        # Log error
        if error_info["category"] in [ErrorCategory.CRITICAL.value, ErrorCategory.PERMANENT.value]:
            logger.error(f"Error: {error_info}")
        else:
            logger.warning(f"Error: {error_info}")
        
        return error_info
    
    def _categorize_error(self, error: Exception) -> str:
        """Categorize standard exceptions."""
        error_type = type(error).__name__
        
        transient_errors = {
            "ConnectionError", "TimeoutError", "NetworkError",
            "TemporaryFailure", "ServiceUnavailable"
        }
        
        if error_type in transient_errors:
            return ErrorCategory.TRANSIENT.value
        
        if "rate" in str(error).lower() or "limit" in str(error).lower():
            return ErrorCategory.TRANSIENT.value
        
        return ErrorCategory.PERMANENT.value
    
    def _get_user_message(self, error: Exception) -> str:
        """Generate user-friendly error message."""
        error_type = type(error).__name__
        
        messages = {
            "ConnectionError": "Unable to connect to the service. Please try again.",
            "TimeoutError": "The request took too long. Please try again.",
            "ValueError": "Invalid input provided. Please check and try again.",
            "KeyError": "Required information is missing. Please provide all details.",
            "PermissionError": "You don't have permission to perform this action."
        }
        
        return messages.get(
            error_type,
            "An unexpected error occurred. Please try again or contact support."
        )
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics."""
        total_errors = sum(self.error_counts.values())
        
        # Calculate error rate by category
        category_counts = defaultdict(int)
        for error in self.error_history[-100:]:  # Last 100 errors
            category_counts[error.get("category", "unknown")] += 1
        
        return {
            "total_errors": total_errors,
            "error_counts": dict(self.error_counts),
            "category_distribution": dict(category_counts),
            "recent_errors": self.error_history[-10:]
        }


# Global error handler
_error_handler = ErrorHandler()


def handle_error(error: Exception, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Handle and categorize an error."""
    return _error_handler.handle_error(error, context)


def get_error_stats() -> Dict[str, Any]:
    """Get error statistics."""
    return _error_handler.get_error_stats()


# Fallback handlers for external services
class FallbackHandler:
    """Manage fallback strategies for failed services."""
    
    @staticmethod
    async def embedding_fallback(text: str) -> List[float]:
        """Fallback when embedding service fails."""
        logger.warning("Using zero embedding fallback")
        # Return zero vector of appropriate dimension
        return [0.0] * 2048  # Jina v4 dimensions
    
    @staticmethod
    async def llm_fallback(query: str) -> str:
        """Fallback when LLM service fails."""
        logger.warning("Using template response fallback")
        return (
            "I apologize, but I'm currently unable to process your request due to "
            "technical difficulties. Please try again in a few moments. If the issue "
            "persists, please contact support."
        )
    
    @staticmethod
    async def database_fallback(query: str) -> List[Dict[str, Any]]:
        """Fallback when database is unavailable."""
        logger.warning("Using cached/default results fallback")
        # Return cached common results or empty list
        return []
    
    @staticmethod
    async def graph_fallback(query: str) -> List[Dict[str, Any]]:
        """Fallback when graph database fails."""
        logger.warning("Using vector-only search fallback")
        # Signal to use vector search only
        return None


# Health monitoring
class ServiceHealth:
    """Monitor health of external services."""
    
    def __init__(self):
        self.health_checks = {}
        self.last_check = {}
    
    async def check_database(self, db_pool) -> bool:
        """Check database health."""
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def check_graph(self, graph_driver) -> bool:
        """Check graph database health."""
        try:
            session = graph_driver.session()
            session.run("RETURN 1").single()
            session.close()
            return True
        except Exception as e:
            logger.error(f"Graph health check failed: {e}")
            return False
    
    async def check_embedding_service(self, embedder) -> bool:
        """Check embedding service health."""
        try:
            test_embedding = await embedder.generate_embedding("test")
            return len(test_embedding) == 2048
        except Exception as e:
            logger.error(f"Embedding service health check failed: {e}")
            return False
    
    async def check_all_services(self, **services) -> Dict[str, bool]:
        """Check health of all services."""
        results = {}
        
        if "db_pool" in services:
            results["database"] = await self.check_database(services["db_pool"])
        
        if "graph_driver" in services:
            results["graph"] = await self.check_graph(services["graph_driver"])
        
        if "embedder" in services:
            results["embedding"] = await self.check_embedding_service(services["embedder"])
        
        self.health_checks = results
        self.last_check = datetime.now()
        
        return results
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return {
            "services": self.health_checks,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "overall_health": all(self.health_checks.values()) if self.health_checks else False
        }


# Global health monitor
_health_monitor = ServiceHealth()


async def check_system_health(**services) -> Dict[str, Any]:
    """Check health of all system components."""
    health_results = await _health_monitor.check_all_services(**services)
    circuit_status = _circuit_breakers.get_all_status()
    
    return {
        "health": _health_monitor.get_health_status(),
        "circuit_breakers": circuit_status,
        "errors": get_error_stats()
    }
