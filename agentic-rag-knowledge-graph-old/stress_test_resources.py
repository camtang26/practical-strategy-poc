"""Stress test to verify no resource leaks under load."""
import asyncio
import time
import httpx
import psutil
import os
from concurrent.futures import ThreadPoolExecutor
import json

# API configuration
API_URL = "http://localhost:8058"
NUM_CONCURRENT_USERS = 10
REQUESTS_PER_USER = 50
MONITOR_INTERVAL = 5  # seconds

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
            connections = len(self.process.connections())
            threads = self.process.num_threads()
            
            sample = {
                'time': time.time() - self.start_time,
                'memory_mb': memory_info.rss / 1024 / 1024,
                'connections': connections,
                'threads': threads
            }
            self.samples.append(sample)
            return sample
        except:
            return None
    
    def report(self):
        """Generate a resource usage report."""
        if not self.samples:
            return "No samples collected"
        
        # Calculate trends
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
  Leak: {memory_end - memory_start:.1f} MB ({(memory_end/memory_start - 1)*100:.1f}% increase)

Connections:
  Start: {connections_start}
  End: {connections_end}
  Max: {connections_max}
  Leak: {connections_end - connections_start} connections

Samples: {len(self.samples)}
Duration: {self.samples[-1]['time']:.1f} seconds
"""


async def make_request(session, endpoint, data):
    """Make a single API request."""
    try:
        response = await session.get(endpoint) if "health" in endpoint else await session.post(endpoint, json=data)
        return response.status_code, response.elapsed.total_seconds()
    except Exception as e:
        return None, str(e)


async def user_simulation(user_id, num_requests):
    """Simulate a user making multiple requests."""
    results = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for i in range(num_requests):
            # Vary the request types
            if i % 3 == 0:
                # Vector search
                data = {
                    "message": f"User {user_id} request {i}: What are the key principles of strategic thinking?",
                    "session_id": f"stress-test-{user_id}"
                }
                endpoint = f"{API_URL}/chat"
            elif i % 3 == 1:
                # Hybrid search
                data = {
                    "message": f"User {user_id} request {i}: How do I implement strategic planning in my organization?",
                    "session_id": f"stress-test-{user_id}"
                }
                endpoint = f"{API_URL}/chat"
            else:
                # Health check
                endpoint = f"{API_URL}/health"
                data = {}
            
            start = time.time()
            status, elapsed = await make_request(client, endpoint, data)
            results.append({
                'user': user_id,
                'request': i,
                'status': status,
                'elapsed': elapsed,
                'timestamp': time.time()
            })
            
            # Small delay between requests
            await asyncio.sleep(0.1)
    
    return results


async def monitor_resources(monitor, stop_event):
    """Monitor resources in the background."""
    while not stop_event.is_set():
        sample = monitor.sample()
        if sample:
            print(f"[{sample['time']:.1f}s] Memory: {sample['memory_mb']:.1f} MB, "
                  f"Connections: {sample['connections']}, Threads: {sample['threads']}")
        await asyncio.sleep(MONITOR_INTERVAL)


async def stress_test():
    """Run the stress test."""
    print(f"Starting stress test:")
    print(f"- Concurrent users: {NUM_CONCURRENT_USERS}")
    print(f"- Requests per user: {REQUESTS_PER_USER}")
    print(f"- Total requests: {NUM_CONCURRENT_USERS * REQUESTS_PER_USER}")
    print()
    
    # Find API process
    api_pid = None
    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'agent.api' in ' '.join(cmdline):
                api_pid = proc.info['pid']
                break
        except:
            continue
    
    if not api_pid:
        print("ERROR: Could not find API process")
        return
    
    print(f"Monitoring API process (PID: {api_pid})")
    monitor = ResourceMonitor(api_pid)
    
    # Start monitoring
    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(monitor_resources(monitor, stop_event))
    
    # Initial sample
    monitor.sample()
    
    # Run user simulations
    print("\nStarting load test...")
    start_time = time.time()
    
    tasks = []
    for user_id in range(NUM_CONCURRENT_USERS):
        task = user_simulation(user_id, REQUESTS_PER_USER)
        tasks.append(task)
    
    # Wait for all users to complete
    all_results = await asyncio.gather(*tasks)
    
    # Stop monitoring
    stop_event.set()
    await monitor_task
    
    # Final sample after a delay
    await asyncio.sleep(5)
    monitor.sample()
    
    end_time = time.time()
    
    # Analyze results
    print(f"\nLoad test completed in {end_time - start_time:.1f} seconds")
    
    # Flatten results
    all_requests = []
    for user_results in all_results:
        all_requests.extend(user_results)
    
    # Calculate statistics
    successful = [r for r in all_requests if r['status'] == 200]
    failed = [r for r in all_requests if r['status'] != 200]
    
    print(f"\nRequest Statistics:")
    print(f"- Total requests: {len(all_requests)}")
    print(f"- Successful: {len(successful)}")
    print(f"- Failed: {len(failed)}")
    
    if successful:
        response_times = [r['elapsed'] for r in successful if isinstance(r['elapsed'], (int, float))]
        if response_times:
            print(f"- Avg response time: {sum(response_times)/len(response_times):.3f}s")
            print(f"- Min response time: {min(response_times):.3f}s")
            print(f"- Max response time: {max(response_times):.3f}s")
    
    # Resource report
    print(monitor.report())
    
    # Check for leaks
    if monitor.samples:
        memory_increase = monitor.samples[-1]['memory_mb'] - monitor.samples[0]['memory_mb']
        connection_increase = monitor.samples[-1]['connections'] - monitor.samples[0]['connections']
        
        # Thresholds
        MEMORY_LEAK_THRESHOLD_MB = 50  # Allow 50MB increase
        CONNECTION_LEAK_THRESHOLD = 5   # Allow 5 connection increase
        
        leak_detected = False
        if memory_increase > MEMORY_LEAK_THRESHOLD_MB:
            print(f"\n⚠️  POTENTIAL MEMORY LEAK: {memory_increase:.1f} MB increase")
            leak_detected = True
        if connection_increase > CONNECTION_LEAK_THRESHOLD:
            print(f"\n⚠️  POTENTIAL CONNECTION LEAK: {connection_increase} connection increase")
            leak_detected = True
        
        if not leak_detected:
            print("\n✅ NO RESOURCE LEAKS DETECTED")
    
    return all_requests, monitor


if __name__ == "__main__":
    asyncio.run(stress_test())
