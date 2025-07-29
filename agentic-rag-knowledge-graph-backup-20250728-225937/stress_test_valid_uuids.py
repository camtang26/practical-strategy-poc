"""Proper stress test with valid UUIDs to test embedding generation."""
import asyncio
import time
import httpx
import psutil
import uuid

# Test configuration  
API_URL = "http://localhost:8058"
NUM_USERS = 3         # Small for MVP
REQUESTS_PER_USER = 10  # Enough to see patterns
MONITOR_INTERVAL = 2

class ResourceMonitor:
    def __init__(self, pid):
        self.pid = pid
        self.process = psutil.Process(pid)
        self.samples = []
        self.start_time = time.time()
        
    def sample(self):
        try:
            memory_info = self.process.memory_info()
            connections = len(self.process.net_connections())
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
        if not self.samples:
            return "No samples collected"
        
        memory_start = self.samples[0]['memory_mb']
        memory_end = self.samples[-1]['memory_mb']
        memory_max = max(s['memory_mb'] for s in self.samples)
        
        connections_start = self.samples[0]['connections']
        connections_end = self.samples[-1]['connections']
        connections_max = max(s['connections'] for s in self.samples)
        
        return f"""
Resource Report:
===============
Memory:
  Start: {memory_start:.1f} MB
  End: {memory_end:.1f} MB  
  Max: {memory_max:.1f} MB
  Change: {memory_end - memory_start:.1f} MB

Connections:
  Start: {connections_start}
  End: {connections_end}
  Max: {connections_max}  
  Change: {connections_end - connections_start}

Samples: {len(self.samples)}
Duration: {self.samples[-1]['time']:.1f}s
"""


async def monitor_loop(monitor, stop_event):
    while not stop_event.is_set():
        sample = monitor.sample()
        if sample:
            print(f"[{sample['time']:.1f}s] Memory: {sample['memory_mb']:.1f} MB, "
                  f"Connections: {sample['connections']}, Threads: {sample['threads']}")
        await asyncio.sleep(MONITOR_INTERVAL)


async def simulate_user(user_id):
    """Simulate a user with VALID session UUID."""
    session_id = str(uuid.uuid4())  # Valid UUID!
    results = []
    
    queries = [
        "What are the key principles of strategic thinking?",
        "How do I develop a competitive advantage?",
        "Explain the value chain concept",
        "What is strategic positioning?",
        "How to implement strategic planning?"
    ]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        print(f"User {user_id} starting (session: {session_id})")
        
        for i in range(REQUESTS_PER_USER):
            query = queries[i % len(queries)]
            data = {
                "message": query,
                "session_id": session_id
            }
            
            try:
                start = time.time()
                response = await client.post(f"{API_URL}/chat", json=data)
                elapsed = time.time() - start
                
                results.append({
                    'status': response.status_code,
                    'elapsed': elapsed
                })
                
                status = "✓" if response.status_code == 200 else f"✗ {response.status_code}"
                print(f"User {user_id} req {i}: {status} ({elapsed:.1f}s)")
                
            except Exception as e:
                print(f"User {user_id} req {i}: ERROR {type(e).__name__}")
                results.append({'status': 'error', 'elapsed': 0})
            
            await asyncio.sleep(1)  # Slower pace for MVP
    
    return results


async def main():
    print("=" * 60)
    print("PROPER STRESS TEST - Valid UUIDs")
    print("=" * 60)
    print(f"Users: {NUM_USERS}")
    print(f"Requests/user: {REQUESTS_PER_USER}")
    print(f"Total: {NUM_USERS * REQUESTS_PER_USER}")
    print()
    
    # Monitor the correct API process
    api_pid = 1780208
    monitor = ResourceMonitor(api_pid)
    
    # Start monitoring
    stop_event = asyncio.Event()
    monitor_task = asyncio.create_task(monitor_loop(monitor, stop_event))
    
    # Initial sample
    print("Initial state:")
    monitor.sample()
    await asyncio.sleep(2)
    
    # Run users
    print("\nStarting users...")
    start = time.time()
    
    tasks = [simulate_user(i) for i in range(NUM_USERS)]
    all_results = await asyncio.gather(*tasks)
    
    # Monitor after load
    print("\nMonitoring post-load for 10s...")
    await asyncio.sleep(10)
    
    # Stop monitoring
    stop_event.set()
    await monitor_task
    monitor.sample()
    
    # Results
    duration = time.time() - start
    print(f"\nCompleted in {duration:.1f}s")
    
    # Flatten results
    all_requests = []
    for user_results in all_results:
        all_requests.extend(user_results)
    
    successful = [r for r in all_requests if r.get('status') == 200]
    
    print(f"\nResults:")
    print(f"- Total: {len(all_requests)}")
    print(f"- Successful: {len(successful)}")
    print(f"- Failed: {len(all_requests) - len(successful)}")
    
    if successful:
        times = [r['elapsed'] for r in successful]
        print(f"- Avg time: {sum(times)/len(times):.1f}s")
    
    print(monitor.report())
    
    # Check for issues
    if monitor.samples:
        memory_change = monitor.samples[-1]['memory_mb'] - monitor.samples[0]['memory_mb']
        conn_change = monitor.samples[-1]['connections'] - monitor.samples[0]['connections']
        
        # MVP thresholds
        issues = []
        if memory_change > 50:  # 50MB threshold
            issues.append(f"Memory: +{memory_change:.1f} MB")
        if conn_change > 5:     # 5 connection threshold
            issues.append(f"Connections: +{conn_change}")
        
        if issues:
            print(f"\n⚠️ POTENTIAL LEAKS: {', '.join(issues)}")
        else:
            print("\n✅ NO SIGNIFICANT LEAKS DETECTED")


if __name__ == "__main__":
    asyncio.run(main())
