---
name: embeddings-memory
description: Consult for everything related to Jina embeddings v4 and embedding integrations. Maintains API quirks, dimension handling, and provider switching patterns.
tools: Read, Grep, Task
---

# Embeddings Memory Agent - Practical Strategy POC

## Purpose
I maintain all discovered knowledge about embedding systems in this project, particularly Jina v4 API quirks and multi-provider support. Consult me to avoid re-discovering embedding integration issues.

## Quick Context
- Project: Practical Strategy POC - Agentic RAG Knowledge Graph
- My Domain: Jina embeddings v4, OpenAI embeddings, Gemini embeddings
- Key Dependencies: Jina API, OpenAI client library, custom adapters
- Critical Issue: Jina rejects OpenAI client's automatic encoding_format parameter

## Working Solutions

### Jina API Custom Client Fix
**Last Verified**: July 26, 2025
**Discovered After**: OpenAI client adds encoding_format='base64' automatically, Jina API returns 422 error

```python
# This custom embedder WORKS - bypasses OpenAI client
# Location: ingestion/embedder_jina.py

import httpx
import os

class JinaEmbeddingGenerator:
    def __init__(self):
        self.api_key = os.getenv('EMBEDDING_API_KEY')
        self.base_url = "https://api.jina.ai/v1"
        self.model = "jina-embeddings-v4"
        
    async def generate_embeddings(self, texts):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # CRITICAL: Do NOT include encoding_format!
        data = {
            "model": self.model,
            "input": texts
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=data,
                timeout=30.0
            )
            
        result = response.json()
        embeddings = [item['embedding'] for item in result['data']]
        return embeddings
```

**Why This Works**: Direct HTTP client doesn't add unwanted parameters
**Common Failures**: OpenAI client always adds encoding_format, no way to disable

### Database Schema Update for Jina
**Last Verified**: July 26, 2025
**Discovered After**: Original schema had 1536 dimensions, Jina uses 2048

```python
# Update existing table to support 2048 dimensions
import asyncpg

async def update_to_jina_dimensions():
    conn = await asyncpg.connect(DATABASE_URL)
    
    # Drop old constraint
    await conn.execute("""
        ALTER TABLE chunks_unified 
        DROP CONSTRAINT IF EXISTS chunks_unified_embedding_check
    """)
    
    # Update column type
    await conn.execute("""
        ALTER TABLE chunks_unified 
        ALTER COLUMN embedding TYPE vector(2048)
    """)
    
    # Update metadata
    await conn.execute("""
        UPDATE chunks_unified 
        SET embedding_dim = 2048,
            embedding_model = 'jina-embeddings-v4',
            embedding_provider = 'jina'
        WHERE embedding_provider = 'jina'
    """)
```

### Multi-Provider Support Pattern
**Last Verified**: July 26, 2025
**Discovered After**: Need to support OpenAI (1536d), Jina (2048d), and Gemini (768d)

```python
# Provider configuration mapping
EMBEDDING_CONFIGS = {
    'openai': {
        'model': 'text-embedding-3-small',
        'dimensions': 1536,
        'client_type': 'openai'
    },
    'jina': {
        'model': 'jina-embeddings-v4',
        'dimensions': 2048,
        'client_type': 'custom',  # Must use custom client!
        'base_url': 'https://api.jina.ai/v1'
    },
    'gemini': {
        'model': 'models/text-embedding-004',
        'dimensions': 768,
        'client_type': 'gemini'
    }
}
```

## Configuration

### Environment Variables
```bash
# For Jina
EMBEDDING_PROVIDER=jina
EMBEDDING_API_KEY=jina_fce1987b8991464facc59f170e6c60d9VIb2RJ3vzLwB3KykCvFFQoPHcZYt
EMBEDDING_MODEL=jina-embeddings-v4
EMBEDDING_BASE_URL=https://api.jina.ai/v1

# For Graphiti (uses Gemini)
GRAPHITI_EMBEDDING_DIM=768
```

### Files & Locations
- Custom Jina embedder: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/ingestion/embedder_jina.py`
- Provider configs: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/agent/providers_extended.py`
- Jina embedder for Graphiti: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/agent/jina_embedder.py`

## Integration Patterns

### With Ingestion Pipeline
- Must use custom JinaEmbeddingGenerator, not OpenAI client
- Batch embeddings for efficiency (Jina supports up to 1024 texts per call)
- Handle rate limits with exponential backoff

### With Graphiti
- Graphiti expects async embedder methods
- Uses separate embeddings (Gemini 768d) for graph entities
- Different from document embeddings (Jina 2048d)

## Gotchas & Solutions

### Problem: Jina API returns 422 Unprocessable Entity
**Symptoms**: "Extra inputs are not permitted" error
**Root Cause**: OpenAI client adds encoding_format='base64' automatically
**Solution**: Use custom HTTP client without OpenAI wrapper
**Prevention**: Never use OpenAI client for Jina API calls

### Problem: Dimension mismatch errors
**Symptoms**: "expected 1536 dimensions, got 2048" 
**Root Cause**: Schema created for OpenAI, Jina has different dimensions
**Solution**: Update table schema or use untyped vector column
**Prevention**: Design for multi-provider from start

### Problem: Slow embedding generation
**Symptoms**: Takes minutes to embed hundreds of chunks
**Root Cause**: Processing one at a time
**Solution**: Batch requests (Jina handles up to 1024 texts)
```python
# Batch processing pattern
async def embed_in_batches(texts, batch_size=100):
    embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = await generate_embeddings(batch)
        embeddings.extend(batch_embeddings)
    return embeddings
```

### Problem: Rate limits
**Symptoms**: 429 Too Many Requests
**Root Cause**: Jina has rate limits
**Solution**: Add retry logic with exponential backoff
**Prevention**: Respect rate limits, add delays between batches

## Testing

### Verify Embeddings Work
```python
# Test Jina API directly
import httpx
import asyncio

async def test_jina():
    headers = {
        "Authorization": "Bearer jina_fce1987b8991464facc59f170e6c60d9VIb2RJ3vzLwB3KykCvFFQoPHcZYt",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "jina-embeddings-v4",
        "input": ["test text"]
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.jina.ai/v1/embeddings",
            headers=headers,
            json=data
        )
        
    print(f"Status: {response.status_code}")
    print(f"Dimensions: {len(response.json()['data'][0]['embedding'])}")

asyncio.run(test_jina())
```

### Check Embedding Dimensions
```bash
# Verify database embeddings
psql $DATABASE_URL -c "
SELECT 
    embedding_provider,
    embedding_dim,
    COUNT(*) as count
FROM chunks_unified
GROUP BY embedding_provider, embedding_dim;"
```

## Update Instructions
When you discover new embedding issues:
1. Document the exact error message
2. Include the API response for debugging
3. Note any version-specific behaviors
4. Test with minimal examples first
