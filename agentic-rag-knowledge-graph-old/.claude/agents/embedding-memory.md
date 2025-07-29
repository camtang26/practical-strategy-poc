---
name: embedding-memory
description: Consult for everything related to embedding generation, Jina API integration, dimension handling, and OpenAI client compatibility. Maintains working API patterns and error solutions.
tools: Read, Grep, Task
---

# Embedding Memory Agent - Agentic RAG Knowledge Graph

## Purpose
I maintain all discovered knowledge about embedding generation in this project. Consult me to understand Jina API integration, dimension handling, and the custom solutions we built to bypass OpenAI client issues.

## Quick Context
- Project: Agentic RAG Knowledge Graph (ottomator-agents)
- My Domain: Embedding generation, Jina API, dimension management
- Provider: Jina v4 (2048 dimensions, 32k context)
- Key Issue Solved: OpenAI client adds 'encoding_format' breaking Jina
- Solution: Custom JinaEmbeddingGenerator bypassing OpenAI client

## Working Solutions

### Custom Jina Embedding Generator
**Last Verified**: July 26, 2025
**Discovered After**: OpenAI client kept adding encoding_format parameter causing 422 errors

```python
# This generator WORKS - bypasses OpenAI client
import httpx
import os
from typing import List

class JinaEmbeddingGenerator:
    def __init__(self):
        self.api_key = os.getenv("JINA_API_KEY")
        self.model = "jina-embeddings-v4"
        self.base_url = "https://api.jina.ai/v1"
        
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "input": texts,
                    # NO encoding_format parameter!
                }
            )
            response.raise_for_status()
            data = response.json()
            return [item["embedding"] for item in data["data"]]
```

**Why This Works**:
- Direct HTTP calls bypass OpenAI client middleware
- No automatic parameter injection
- Full control over request payload
- Async for better performance

### Environment Configuration
```bash
# Required environment variables
EMBEDDING_PROVIDER=jina
EMBEDDING_MODEL=jina-embeddings-v4
JINA_API_KEY=your_jina_api_key_here
EMBEDDING_BASE_URL=https://api.jina.ai/v1
VECTOR_DIMENSION=2048
EMBEDDING_CHUNK_SIZE=8192
```

### Batch Processing Pattern
**Last Verified**: July 26, 2025
**Why**: Jina has rate limits, batch for efficiency

```python
async def process_chunks_in_batches(chunks, batch_size=10):
    embedder = JinaEmbeddingGenerator()
    all_embeddings = []
    
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i+batch_size]
        texts = [chunk.content for chunk in batch]
        
        try:
            embeddings = await embedder.generate_embeddings(texts)
            all_embeddings.extend(embeddings)
            print(f"Processed batch {i//batch_size + 1}")
        except Exception as e:
            print(f"Batch {i//batch_size + 1} failed: {e}")
            # Retry logic here
            
    return all_embeddings
```

## Integration Patterns

### With Ingestion Pipeline
```python
# In ingestion/embedder_jina.py
from agent.jina_embedder import JinaEmbeddingGenerator

async def embed_chunks(chunks):
    embedder = JinaEmbeddingGenerator()
    
    for chunk in chunks:
        if not chunk.embedding:  # Skip if already embedded
            embedding = await embedder.generate_embeddings([chunk.content])
            chunk.embedding = embedding[0]  # 2048 dimensions
            
    return chunks
```

### With Search Functions
```python
# Generate query embedding
async def get_query_embedding(query: str) -> List[float]:
    embedder = JinaEmbeddingGenerator()
    embeddings = await embedder.generate_embeddings([query])
    return embeddings[0]  # Returns 2048-dimensional vector
```

## Gotchas & Solutions

### Problem: 422 Unprocessable Entity - Extra inputs not permitted
**Symptoms**: `{"detail":[{"type":"extra_forbidden","loc":["body","encoding_format"],"msg":"Extra inputs are not permitted"}]}`
**Root Cause**: OpenAI client auto-adds encoding_format parameter
**Solution**: Use custom HTTP client, bypass OpenAI SDK
**Prevention**: Never use OpenAI client for Jina API calls

### Problem: Dimension mismatch in database
**Symptoms**: ERROR: expected 1536 dimensions, not 2048
**Root Cause**: Database schema for OpenAI, Jina provides 2048
**Solution**: 
```sql
ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(2048);
```
**Prevention**: Always check VECTOR_DIMENSION env var

### Problem: Rate limit exceeded
**Symptoms**: 429 Too Many Requests
**Root Cause**: Jina API rate limits
**Solution**: Implement exponential backoff
```python
import asyncio

async def with_retry(func, *args, max_retries=3):
    for attempt in range(max_retries):
        try:
            return await func(*args)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = 2 ** attempt
                print(f"Rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                raise
    raise Exception("Max retries exceeded")
```

### Problem: Embeddings not normalized
**Symptoms**: Similarity scores > 1 or negative
**Root Cause**: Jina embeddings are pre-normalized
**Solution**: No normalization needed, use as-is
**Prevention**: Don't apply additional normalization

## API Patterns

### Direct API Test
```python
# Test Jina API directly
import httpx
import os

async def test_jina_api():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.jina.ai/v1/embeddings",
            headers={
                "Authorization": f"Bearer {os.getenv('JINA_API_KEY')}",
                "Content-Type": "application/json"
            },
            json={
                "model": "jina-embeddings-v4",
                "input": ["Test text"]
            }
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
```

### Embedding Dimensions Verification
```python
# Always verify dimensions
embedding = await embedder.generate_embeddings(["test"])
print(f"Dimensions: {len(embedding[0])}")  # Should be 2048
```

## Testing

### Quick API Test
```bash
# Test from command line
ssh root@170.64.129.131 "cd /opt/practical-strategy-poc/agentic-rag-knowledge-graph && python test_jina_api_fixed.py"
```

### Verify Embeddings in Database
```sql
-- Check embedding dimensions
SELECT 
    id,
    array_length(embedding::float[], 1) as dimensions
FROM chunks_unified
WHERE embedding IS NOT NULL
LIMIT 5;
```

## Migration from OpenAI

### Update Existing Code
```python
# OLD (OpenAI pattern)
from openai import OpenAI
client = OpenAI(api_key=jina_key, base_url=jina_url)
response = client.embeddings.create(...)  # FAILS

# NEW (Direct HTTP)
embedder = JinaEmbeddingGenerator()
embeddings = await embedder.generate_embeddings(texts)  # WORKS
```

## Update Instructions
When you discover new embedding patterns or issues:
1. Add to relevant section with date
2. Document exact error messages from APIs
3. Include working HTTP request examples
4. Note dimension specifications
5. Update rate limit handling strategies
