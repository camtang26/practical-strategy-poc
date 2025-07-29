---
name: graphiti-memory
description: Consult for everything related to Graphiti knowledge graph building. Maintains entity extraction patterns, batch processing, and the 4-hour pipeline.
tools: Read, Grep, Task
---

# Graphiti Memory Agent - Practical Strategy POC

## Purpose
I maintain all discovered knowledge about building knowledge graphs with Graphiti in this project. Consult me for entity extraction, relationship mapping, and the long-running graph building process.

## Quick Context
- Project: Practical Strategy POC - Agentic RAG Knowledge Graph
- My Domain: Graphiti framework, entity/relationship extraction, batch processing
- Key Dependencies: Graphiti 0.18.0, Neo4j, Gemini for LLM, separate embeddings
- Processing Time: ~50 seconds per chunk, ~4 hours for 290 chunks

## Working Solutions

### Graphiti Configuration with Gemini
**Last Verified**: July 26, 2025
**Discovered After**: OpenAI client mismatch with Gemini API keys

```python
# Working Graphiti setup with Gemini
# Location: agent/graph_utils.py

from graphiti_core import Graphiti
from graphiti_core.llm import GeminiClient
from graphiti_core.embedder import GeminiEmbedder
from graphiti_core.reranker import CohereReranker

class GraphManager:
    def __init__(self):
        # LLM configuration for entity extraction
        llm_config = {
            "model": "gemini-2.0-pro-exp",
            "api_key": os.getenv("LLM_API_KEY"),
            "temperature": 0.1  # Low for consistency
        }
        
        # Embedder for graph entities (768d)
        embedder_config = {
            "model": "models/text-embedding-004",
            "api_key": os.getenv("LLM_API_KEY"),
            "dimensions": 768  # Different from Jina 2048d!
        }
        
        # Initialize Graphiti with Gemini
        self.graphiti = Graphiti(
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USER"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            llm_client=GeminiClient(config=llm_config),
            embedder=GeminiEmbedder(config=embedder_config),
            reranker=CohereReranker()  # Optional
        )
```

**Why This Works**: Matches LLM provider with API keys
**Common Failures**: Using OpenAIClient with Gemini API key causes 401 errors

### Background Graph Building Process
**Last Verified**: July 26, 2025
**Discovered After**: Process takes 4+ hours, needs persistent execution

```python
# Long-running graph builder
# Location: continue_graph_building.py

async def build_graph_from_chunks():
    # Check progress
    processed_chunks = await get_processed_chunks()
    total_chunks = await get_total_chunks()
    
    print(f"Resuming from chunk {len(processed_chunks)}/{total_chunks}")
    
    # Process remaining chunks
    for i, chunk in enumerate(remaining_chunks):
        try:
            start_time = time.time()
            
            # Add to graph with retry logic
            for attempt in range(3):
                try:
                    await graphiti.add_episode(
                        name=f"chunk_{chunk['chunk_index']}",
                        episode_body=chunk['content'],
                        reference_time=datetime.utcnow(),
                        metadata={
                            "document_id": str(chunk['document_id']),
                            "chunk_index": chunk['chunk_index'],
                            "chunk_id": str(chunk['id'])
                        }
                    )
                    break
                except Exception as e:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 ** attempt)
            
            # Track progress
            elapsed = time.time() - start_time
            print(f"Processed chunk {i+1}/{len(remaining_chunks)} in {elapsed:.1f}s")
            
            # Save progress periodically
            if i % 10 == 0:
                await save_progress(chunk['id'])
                
        except Exception as e:
            print(f"Error processing chunk {chunk['id']}: {e}")
            # Continue with next chunk
```

**Why This Works**: Resilient to failures, tracks progress
**Processing Rate**: ~50 seconds per chunk average

### Entity Extraction Patterns
**Last Verified**: July 26, 2025
**Discovered After**: Graphiti extracts specific entity types from book

```python
# Common entities extracted from Practical Strategy book
ENTITY_TYPES = {
    'CONCEPT': 'Strategic concepts and frameworks',
    'PERSON': 'Authors, thought leaders, practitioners',
    'ORGANIZATION': 'Companies, institutions mentioned',
    'METHOD': 'Strategic methods and techniques',
    'PRINCIPLE': 'Core strategic principles',
    'CASE_STUDY': 'Real-world examples'
}

# Relationship types discovered
RELATIONSHIP_TYPES = {
    'RELATES_TO': 'General conceptual relationship',
    'IMPLEMENTS': 'Organization implements method',
    'AUTHORED_BY': 'Concept authored by person',
    'EXEMPLIFIES': 'Case study exemplifies principle',
    'CONTRADICTS': 'Conflicting approaches'
}
```

### Batch Processing Configuration
**Last Verified**: July 26, 2025
**Discovered After**: Memory constraints with large batches

```python
# Optimal batch configuration for 3.8GB server
BATCH_CONFIG = {
    'chunk_batch_size': 10,  # Process 10 chunks before committing
    'entity_batch_size': 100,  # Batch entity embeddings
    'memory_check_interval': 50,  # Check memory every 50 chunks
    'max_memory_percent': 70  # Pause if memory > 70%
}

async def process_with_memory_management(chunks):
    for i in range(0, len(chunks), BATCH_CONFIG['chunk_batch_size']):
        batch = chunks[i:i + BATCH_CONFIG['chunk_batch_size']]
        
        # Check memory before processing
        memory_percent = get_memory_usage()
        if memory_percent > BATCH_CONFIG['max_memory_percent']:
            print(f"Memory at {memory_percent}%, pausing...")
            await asyncio.sleep(30)
            
        # Process batch
        await process_batch(batch)
```

## Configuration

### Environment Variables
```bash
# Neo4j connection (local Docker)
NEO4J_URI=bolt://localhost:7688
NEO4J_USER=neo4j
NEO4J_PASSWORD=agpassword123

# Gemini for Graphiti operations
LLM_PROVIDER=gemini
LLM_API_KEY=AIzaSyDy8D4xLgWdzdAMpoPYEEBsdEmm9FjmuDs

# Graph-specific embeddings
GRAPHITI_EMBEDDING_DIM=768
```

### Files & Locations
- Graph utils: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/agent/graph_utils.py`
- Builder script: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/continue_graph_building.py`
- Test scripts: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/test_graphiti_*.py`
- Progress log: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/graph_building_background.log`

## Integration Patterns

### With Chunk Processing
- Each chunk becomes an "episode" in Graphiti
- Metadata preserves chunk_id for linking back
- Entities extracted maintain document context

### With Search System
- Graph embeddings (768d) separate from search embeddings (2048d)
- Entities have their own vector representations
- Relationships enable traversal queries

## Gotchas & Solutions

### Problem: Graph building crashes midway
**Symptoms**: Process dies after hours of work
**Root Cause**: Memory accumulation, no progress saving
**Solution**: Implement checkpoint system
```python
# Save progress to file
PROGRESS_FILE = 'graph_building_progress.json'

def save_progress(last_chunk_id):
    with open(PROGRESS_FILE, 'w') as f:
        json.dump({'last_chunk_id': str(last_chunk_id)}, f)
```

### Problem: Duplicate entities
**Symptoms**: Same concept extracted multiple times
**Root Cause**: Graphiti doesn't deduplicate automatically
**Solution**: Enable deduplication in Graphiti
```python
await graphiti.add_episode(
    ...,
    deduplicate=True,
    similarity_threshold=0.85
)
```

### Problem: Slow entity extraction
**Symptoms**: 50+ seconds per chunk
**Root Cause**: Multiple LLM calls for extraction
**Solution**: Can't optimize much - it's LLM-bound
**Mitigation**: Run overnight with proper monitoring

### Problem: Neo4j runs out of memory
**Symptoms**: Container crashes during building
**Root Cause**: Too many uncommitted transactions
**Solution**: Commit more frequently
```python
# Commit after each batch
if i % 10 == 0:
    await graphiti._neo4j_driver.session().run("CALL db.checkpoint()")
```

## Testing

### Verify Graph Population
```cypher
// Check entity counts
MATCH (n) 
RETURN labels(n)[0] as label, count(n) as count
ORDER BY count DESC;

// Sample entities
MATCH (e:Entity)
RETURN e.name, e.type, e.summary
LIMIT 10;

// Check relationships
MATCH (e1:Entity)-[r]-(e2:Entity)
RETURN type(r), count(r)
ORDER BY count(r) DESC;
```

### Monitor Building Progress
```bash
# Watch progress in real-time
tail -f graph_building_background.log | grep "Processed chunk"

# Check memory usage
docker stats practical-strategy-neo4j --no-stream

# Count processed chunks
grep "Processed chunk" graph_building_background.log | tail -1
```

### Test Entity Extraction
```python
# Test single chunk extraction
test_chunk = "Strategic planning involves..."

result = await graphiti.add_episode(
    name="test_chunk",
    episode_body=test_chunk,
    reference_time=datetime.utcnow()
)

print(f"Extracted {len(result.entities)} entities")
print(f"Created {len(result.relationships)} relationships")
```

## Update Instructions
When working with Graphiti:
1. Always monitor memory usage during building
2. Implement progress checkpoints
3. Test entity extraction on samples first
4. Document any parameter tuning
5. Keep logs of processing times
