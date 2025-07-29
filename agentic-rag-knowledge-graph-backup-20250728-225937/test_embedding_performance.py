#!/usr/bin/env python3
"""
Test the performance of the optimized embedding generator directly.
This bypasses the API and tests the raw embedding generation speed.
"""
import asyncio
import time
import os
import sys
from pathlib import Path
from typing import List
import statistics

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))
sys.path.append('/opt/practical-strategy-poc/agentic-rag-knowledge-graph')

from ingestion.experimental_embedder_jina_v2 import OptimizedJinaEmbeddingGenerator


async def measure_embedding_performance():
    """Measure performance of the optimized embedder."""
    print("=== EMBEDDING PERFORMANCE TEST ===")
    print("Testing optimized Jina embedder with connection pooling...")
    print()
    
    # Initialize the embedder
    embedder = OptimizedJinaEmbeddingGenerator(
        model="jina-embeddings-v4",
        base_batch_size=100,
        max_concurrent_requests=3
    )
    
    # Test data
    short_texts = ["Strategic planning"] * 50
    medium_texts = ["Strategic planning involves the formulation and implementation of the major goals and initiatives taken by an organization's managers on behalf of stakeholders, based on consideration of resources and an assessment of the internal and external environments."] * 50
    long_texts = ["Strategic planning is an organization's process of defining its strategy or direction and making decisions on allocating its resources to pursue this strategy. It may also extend to control mechanisms for guiding the implementation of the strategy. Strategic planning became prominent in corporations during the 1960s and remains an important aspect of strategic management. It is executed by strategic planners or strategists, who involve many parties and research sources in their analysis of the organization and its relationship to the environment in which it competes. Strategy has many definitions, but generally involves setting strategic goals, determining actions to achieve the goals, and mobilizing resources to execute the actions. A strategy describes how the ends (goals) will be achieved by the means (resources). The senior leadership of an organization is generally tasked with determining strategy. Strategy can be planned (intended) or can be observed as a pattern of activity (emergent) as the organization adapts to its environment or competes."] * 50
    
    # Test different batch sizes
    test_configs = [
        ("Short texts (18 chars)", short_texts, [1, 10, 50]),
        ("Medium texts (270 chars)", medium_texts, [1, 10, 50]),
        ("Long texts (1070 chars)", long_texts, [1, 10, 20])
    ]
    
    # Warm up the connection
    print("Warming up connection...")
    _ = await embedder.generate_embeddings_batch(["warm up"])
    print("Connection established.")
    print()
    
    results = []
    
    for test_name, texts, batch_sizes in test_configs:
        print(f"\nTesting {test_name}:")
        print("-" * 50)
        
        for batch_size in batch_sizes:
            test_texts = texts[:batch_size]
            
            # Run multiple iterations
            times = []
            for i in range(5):
                start = time.time()
                embeddings = await embedder.generate_embeddings_batch(test_texts)
                end = time.time()
                times.append(end - start)
                
                # Verify we got the right number of embeddings
                assert len(embeddings) == batch_size, f"Expected {batch_size} embeddings, got {len(embeddings)}"
                assert len(embeddings[0]) == 2048, f"Expected 2048 dimensions, got {len(embeddings[0])}"
            
            avg_time = statistics.mean(times)
            std_dev = statistics.stdev(times) if len(times) > 1 else 0
            time_per_text = (avg_time / batch_size) * 1000  # Convert to ms
            
            print(f"  Batch size {batch_size}:")
            print(f"    Average time: {avg_time*1000:.1f}ms (±{std_dev*1000:.1f}ms)")
            print(f"    Time per text: {time_per_text:.1f}ms")
            print(f"    Throughput: {batch_size/avg_time:.1f} texts/second")
            
            results.append({
                'test': test_name,
                'batch_size': batch_size,
                'avg_time': avg_time,
                'time_per_text': time_per_text,
                'throughput': batch_size/avg_time
            })
    
    # Clean up
    if hasattr(embedder, '_client') and embedder._client:
        await embedder._client.aclose()
    
    print("\n" + "="*60)
    print("PERFORMANCE SUMMARY")
    print("="*60)
    
    # Compare with baseline (assuming 200ms per text without optimization)
    baseline_ms_per_text = 200
    
    for test_name in ["Short texts (18 chars)", "Medium texts (270 chars)", "Long texts (1070 chars)"]:
        print(f"\n{test_name}:")
        test_results = [r for r in results if r['test'] == test_name]
        
        best_result = min(test_results, key=lambda x: x['time_per_text'])
        improvement = (baseline_ms_per_text / best_result['time_per_text'] - 1) * 100
        
        print(f"  Best performance: {best_result['time_per_text']:.1f}ms per text (batch size {best_result['batch_size']})")
        print(f"  Improvement vs baseline: {improvement:.0f}% faster")
        print(f"  Max throughput: {best_result['throughput']:.1f} texts/second")
    
    # Check if we meet the 50% faster target
    avg_improvement = statistics.mean([
        (baseline_ms_per_text / r['time_per_text'] - 1) * 100 
        for r in results
    ])
    
    print(f"\nOverall average improvement: {avg_improvement:.0f}% faster")
    if avg_improvement >= 50:
        print("✅ TARGET MET: Embedding generation is 50%+ faster!")
    else:
        print(f"❌ TARGET MISSED: Need {50-avg_improvement:.0f}% more improvement")


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv('/opt/practical-strategy-poc/agentic-rag-knowledge-graph/.env')
    
    # Verify we have the API key
    if not os.getenv('EMBEDDING_API_KEY'):
        print("ERROR: EMBEDDING_API_KEY not set in environment")
        sys.exit(1)
    
    asyncio.run(measure_embedding_performance())
