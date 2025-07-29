"""Final stress test targeting the correct API process."""
import asyncio
import time
import httpx
import psutil
import os

# Test configuration
API_URL = "http://localhost:8058"
NUM_CONCURRENT_USERS = 5  # Reduced for 1-2 user MVP
REQUESTS_PER_USER = 20    # Reduced for quick test
MONITOR_INTERVAL = 2      # More frequent monitoring

class ResourceMonitor:
    def __init__(self, pid):
        self.pid = pid
        self.process = psutil.Process(pid)
        self.samples = []
        self.start_time = time.time()
        
    def sample(self):
        """Take a resource usage sample."""
        try:
            memory_info = self.process.memory_info()
            connections = len(self.process.net_connections())  # Fixed deprecation
            threads = self.process.num_threads()
            
            sample = {
                'time': time.time() - self.start_time,
                'memory_mb': memory_info.rss / 1024 / 1024,
                'connections': connections,
                'threads': threads
            }
            self.samples.append(sample)
            return sample
        except Exception as e:
            print(f"Sampling error: {e}")
            return None
    
    def report(self):
        """Generate a resource usage report."""
        if not self.samples:
            return "No samples collected"
        
        memory_start = self.samples[0]['memory_mb']
        memory_end = self.samples[-1]['memory_mb']
        memory_max = max(s['memory_mb'] for s in self.samples)
        
        connections_start = self.samples[0]['connections']
        connections_end = self.samples[-1]['connections']
        connections_max = max(s['connections'] for s in self.samples)
        
        return f"""
Resource Usage Report:
=====================
Memory:
  Start: {memory_start:.1f} MB
  End: {memory_end:.1f} MB
  Max: {memory_max:.1f} MB
  Change: {memory_end - memory_start:.1f} MB ({(memory_end/memory_start - 1)*100:.1f}% change)

Connections:
  Start: {connections_start}
  End: {connections_end}
  Max: {connections_max}
  Change: {connections_end - connections_start} connections

Samples: {len(self.samples)}
Duration: {self.samples[-1]['time']:.1f} seconds
"""


async def monitor_resources(monitor, stop_event):
    """Monitor resources in the background."""
    while not stop_event.is_set():
        sample = monitor.sample()
        if sample:
            print(f"[{sample['time']:.1f}s] Memory: {sample['memory_mb']:.1f} MB, "
                  f"Connections: {sample['connections']}, Threads: {sample['threads']}")
        await asyncio.sleep(MONITOR_INTERVAL)


async def user_simulation(user_id):
    """Simulate a user making requests."""
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Mix of request types
        queries = [
            "What are the key principles of strategic thinking?",
            "How do I develop a strategic plan?",
            "What is competitive advantage?",
            "Explain strategic positioning",
            "How to implement strategic initiatives?"
        ]
        
        for i in range(REQUESTS_PER_USER):
            query = queries[i % len(queries)]
            data = {
                "message": f"[User {user_id}] {query}",
                "session_id": f"stress-test-{user_id}"
            }
            
            try:
                start = time.time()
                response = await client.post(f"{API_URL}/chat", json=data)
                elapsed = time.time() - start
                
                results.append({
                    'user': user_id,
                    'request': i,
                    'status': response.status_code,
                    'elapsed': elapsed
                })
                
                if response.status_code == 200:
                    print(f"User {user_id} request {i}: {elapsed:.2f}s")
                else:
                    print(f"User {user_id} request {i}: ERROR {response.status_code}")
                
            except Exception as e:
                print(f"User {user_id} request {i}: EXCEPTION {type(e).__name__}")
                results.append({
                    'user': user_id,
                    'request': i,
                    'status': 'error',
                    'elapsed': 0
                })
            
            # Small delay between requests
            await asyncio.sleep(0.5)
    
    return results


async def main():
    """Run the stress test."""
    print("=" * 60)
    print("STRESS TEST: Resource Leak Detection")
    print("=" * 60)
    print(f"Target: {API_URL}")
    print(f"Users: {NUM_CONCURRENT_USERS}")
    print(f"Requests per user: {REQUESTS_PER_USER}")
    print(f"Total requests: {NUM_CONCURRENT_USERS * REQUESTS_PER_USER}")
    print()
    
    # Find the correct API process
    api_pid = 1780208  # From ps output
    
    print(f"Monitoring API process (PID: {api_pid})")
    monitor = ResourceMonitor(api_pid)
    
    # Start monitoring
    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(monitor_resources(monitor, stop_event))
    
    # Initial sample
    monitor.sample()
    await asyncio.sleep(2)
    
    # Run user simulations
    print("\nStarting load test...")
    start_time = time.time()
    
    tasks = []
    for user_id in range(NUM_CONCURRENT_USERS):
        task = user_simulation(user_id)
        tasks.append(task)
    
    # Wait for all users to complete
    all_results = await asyncio.gather(*tasks)
    
    # Continue monitoring for a bit after load
    print("\nLoad complete, monitoring for 10 more seconds...")
    await asyncio.sleep(10)
    
    # Stop monitoring
    stop_event.set()
    await monitor_task
    
    # Final sample
    monitor.sample()
    
    # Analyze results
    total_time = time.time() - start_time
    print(f"\nTest completed in {total_time:.1f} seconds")
    
    # Flatten results
    all_requests = []
    for user_results in all_results:
        all_requests.extend(user_results)
    
    # Calculate statistics
    successful = [r for r in all_requests if r.get('status') == 200]
    failed = [r for r in all_requests if r.get('status') != 200]
    
    print(f"\nRequest Statistics:")
    print(f"- Total: {len(all_requests)}")
    print(f"- Successful: {len(successful)}")
    print(f"- Failed: {len(failed)}")
    
    if successful:
        response_times = [r['elapsed'] for r in successful]
        print(f"- Avg response: {sum(response_times)/len(response_times):.2f}s")
        print(f"- Min response: {min(response_times):.2f}s")
        print(f"- Max response: {max(response_times):.2f}s")
    
    # Resource report
    print(monitor.report())
    
    # Leak detection
    if monitor.samples:
        memory_change = monitor.samples[-1]['memory_mb'] - monitor.samples[0]['memory_mb']
        connection_change = monitor.samples[-1]['connections'] - monitor.samples[0]['connections']
        
        # For MVP, be more lenient with thresholds
        MEMORY_THRESHOLD_MB = 20  # 20MB for small test
        CONNECTION_THRESHOLD = 3   # 3 connections
        
        issues = []
        if abs(memory_change) > MEMORY_THRESHOLD_MB:
            issues.append(f"Memory change: {memory_change:+.1f} MB")
        if abs(connection_change) > CONNECTION_THRESHOLD:
            issues.append(f"Connection change: {connection_change:+d}")
        
        if issues:
            print(f"\n⚠️  POTENTIAL ISSUES: {', '.join(issues)}")
        else:
            print("\n✅ PASSED: No significant resource leaks detected")


if __name__ == "__main__":
    asyncio.run(main())
