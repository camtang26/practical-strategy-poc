# Resource Management Patterns

This document describes the resource management patterns implemented to prevent resource leaks in the Practical Strategy POC.

## Connection Pool Management

### Problem
The OptimizedJinaEmbeddingGenerator creates an httpx.AsyncClient for connection pooling but it was never properly closed, leading to resource leaks over time.

### Solution
1. **Embedder Close Method**: The embedder has a `close()` method that properly cleans up the httpx client:
   ```python
   async def close(self):
       """Close the HTTP client connection."""
       if self._client:
           await self._client.aclose()
           self._client = None
   ```

2. **Singleton Cleanup**: Added `cleanup_embedder()` function in `providers_extended.py`:
   ```python
   async def cleanup_embedder():
       """Clean up the embedder resources."""
       global _embedder_instance
       if _embedder_instance:
           await _embedder_instance.close()
           _embedder_instance = None
   ```

3. **FastAPI Lifespan Integration**: Added cleanup to API shutdown in `api.py`:
   ```python
   async def lifespan(app: FastAPI):
       # Startup
       yield
       # Shutdown
       await cleanup_embedder()  # Clean up embedder connections
       await close_database()
       await close_graph()
   ```

### Benefits
- Prevents connection pool exhaustion
- Ensures graceful shutdown
- No orphaned connections

## Semaphore Management

### Problem
Concern that semaphores might not be released properly during exceptions, leading to eventual blocking of all embedding requests.

### Solution
The implementation already uses the correct pattern with async context managers:
```python
async with self.semaphore:  # Automatically releases even on exception
    client = await self._get_client()
    response = await client.post(...)
```

### Testing
Extensive testing confirmed that semaphores are properly released in all scenarios:
- Network errors
- API errors
- JSON parsing errors
- Concurrent requests
- Task cancellation

### Benefits
- Guaranteed semaphore release
- No manual acquire/release needed
- Exception-safe by design

## Best Practices

### 1. Always Use Context Managers
```python
# Good - automatic cleanup
async with resource:
    # use resource

# Bad - manual cleanup can be missed
resource.acquire()
try:
    # use resource
finally:
    resource.release()  # Can be missed if code changes
```

### 2. Singleton Resource Cleanup
For singleton resources, ensure cleanup in application lifecycle:
```python
# In providers
_singleton_instance = None

async def get_singleton():
    global _singleton_instance
    if not _singleton_instance:
        _singleton_instance = create_resource()
    return _singleton_instance

async def cleanup_singleton():
    global _singleton_instance
    if _singleton_instance:
        await _singleton_instance.close()
        _singleton_instance = None

# In FastAPI lifespan
async def lifespan(app):
    yield
    await cleanup_singleton()
```

### 3. Resource Monitoring
Monitor resource usage in production:
- Connection pool metrics
- Semaphore wait times
- Memory usage trends

## Testing Resource Management

### Connection Pool Tests
```bash
python3 test_connection_pool_cleanup.py
```
Tests:
- Embedder cleanup functionality
- FastAPI lifespan integration
- Singleton reset after cleanup
- Concurrent cleanup handling

### Semaphore Tests
```bash
python3 test_semaphore_behavior_v2.py
```
Tests:
- Exception scenarios
- Concurrent request limiting
- Cancellation handling
- Rate limiting interaction

## Production Monitoring

To monitor resource health in production:

1. **Check Active Connections**:
   ```bash
   netstat -an | grep ESTABLISHED | grep 443 | wc -l
   ```

2. **Monitor Memory Usage**:
   ```bash
   ps aux | grep "python3 -m agent.api" | awk '{print $6}'
   ```

3. **API Health Check**:
   ```bash
   curl http://localhost:8058/health
   ```

## Troubleshooting

### Symptoms of Resource Leaks
- Gradual memory increase
- Connection timeouts
- "Too many open files" errors
- Semaphore acquisition timeouts

### Quick Fixes
1. **Restart API**: 
   ```bash
   kill $(cat api.pid)
   APP_PORT=8058 nohup python3 -m agent.api > api.log 2>&1 & echo $! > api.pid
   ```

2. **Check for Orphaned Processes**:
   ```bash
   ps aux | grep python | grep -v grep
   ```

3. **Monitor Logs**:
   ```bash
   tail -f api.log | grep -E "error|timeout|leak"
   ```

## Future Improvements

1. **Resource Metrics Endpoint**: Add `/metrics` endpoint for Prometheus
2. **Automatic Recovery**: Implement circuit breakers for resource exhaustion
3. **Connection Pool Tuning**: Dynamic adjustment based on load
4. **Resource Leak Detection**: Automated alerts for anomalies

---

Last Updated: January 27, 2025
