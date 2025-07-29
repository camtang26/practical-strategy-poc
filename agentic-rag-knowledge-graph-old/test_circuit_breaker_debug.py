import time
import sys
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')
from agent.experimental_error_handler import CircuitBreaker, ServiceStatus

# Create circuit breaker with short timeout
breaker = CircuitBreaker("test", failure_threshold=2, recovery_timeout=2)

# Test failures
def failing():
    raise ValueError("fail")

print(f"Initial state: {breaker.status.value}")

# Trigger failures
for i in range(2):
    try:
        breaker.call(failing)
    except:
        pass
    print(f"After failure {i+1}: {breaker.status.value}, failures: {breaker.failure_count}")

# Check if open
print(f"\nCircuit should be OPEN: {breaker.status.value}")

# Wait and check for half-open
print("\nWaiting 3 seconds...")
time.sleep(3)

# Try to call - this should trigger half-open
try:
    breaker.call(lambda: "test")
    print(f"After successful call: {breaker.status.value}")
except Exception as e:
    print(f"Still failing: {e}")
    print(f"Current state: {breaker.status.value}")

# Check internal state
print(f"\nBreaker details:")
print(f"- last_failure_time: {breaker.last_failure_time}")
print(f"- _should_attempt_reset(): {breaker._should_attempt_reset()}")
print(f"- _time_until_reset(): {breaker._time_until_reset()}")
