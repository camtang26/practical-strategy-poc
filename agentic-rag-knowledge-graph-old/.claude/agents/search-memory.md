---
name: search-memory
description: Consult for everything related to vector, graph, and hybrid search implementations. Maintains SQL functions, performance optimizations, and search patterns.
tools: Read, Grep, Task
---

# Search Memory Agent - Practical Strategy POC

## Purpose
I maintain all discovered knowledge about search implementations in this project, including vector search, graph traversal, and hybrid approaches. Consult me for SQL functions, performance issues, and search optimizations.

## Quick Context
- Project: Practical Strategy POC - Agentic RAG Knowledge Graph  
- My Domain: Vector search (pgvector), graph search (Neo4j), hybrid search
- Key Dependencies: PostgreSQL functions, Neo4j Cypher queries, PydanticAI tools
- Performance Target: <2 seconds for hybrid search (currently ~2.6s)

## Working Solutions

### Vector Search SQL Function
**Last Verified**: July 26, 2025
**Discovered After**: Multiple iterations to get provider filtering right

```sql
-- Provider-aware vector search function
CREATE OR REPLACE FUNCTION match_chunks_unified(
    query_embedding vector,
    embedding_provider_filter TEXT,
    match_count INTEGER
)
RETURNS TABLE(
    id UUID,
    document_id UUID,
    chunk_index INTEGER,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id,
        c.document_id,
        c.chunk_index,
        c.content,
        c.metadata,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM chunks_unified c
    WHERE c.embedding_provider = embedding_provider_filter
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
```

**Why This Works**: Provider filtering ensures correct dimension matching
**Common Failures**: Without provider filter, dimension mismatches cause errors

### Hybrid Search Implementation
**Last Verified**: July 26, 2025
**Discovered After**: Need to combine vector and text search efficiently

```sql
CREATE OR REPLACE FUNCTION hybrid_search_unified(
    query_embedding vector,
    query_text TEXT,
    embedding_provider_filter TEXT,
    match_count INTEGER,
    full_text_weight FLOAT DEFAULT 1.0,
    semantic_weight FLOAT DEFAULT 1.0,
    rrf_k INTEGER DEFAULT 60
)
RETURNS TABLE(
    id UUID,
    document_id UUID, 
    chunk_index INTEGER,
    content TEXT,
    metadata JSONB,
    semantic_similarity FLOAT,
    full_text_rank FLOAT,
    rrf_score FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH semantic_search AS (
        SELECT 
            c.id,
            c.document_id,
            c.chunk_index,
            c.content,
            c.metadata,
            1 - (c.embedding <=> query_embedding) AS similarity,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) AS rank
        FROM chunks_unified c
        WHERE c.embedding_provider = embedding_provider_filter
        ORDER BY c.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    full_text_search AS (
        SELECT 
            c.id,
            ts_rank_cd(to_tsvector('english', c.content), query) AS rank_score,
            ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', c.content), query) DESC) AS rank
        FROM chunks_unified c,
             plainto_tsquery('english', query_text) query
        WHERE to_tsvector('english', c.content) @@ query
          AND c.embedding_provider = embedding_provider_filter
        ORDER BY rank_score DESC
        LIMIT match_count * 2
    )
    SELECT 
        COALESCE(ss.id, fts.id) AS id,
        ss.document_id,
        ss.chunk_index,
        ss.content,
        ss.metadata,
        ss.similarity AS semantic_similarity,
        fts.rank_score AS full_text_rank,
        COALESCE(1.0 / (rrf_k + ss.rank), 0.0) * semantic_weight + 
        COALESCE(1.0 / (rrf_k + fts.rank), 0.0) * full_text_weight AS rrf_score
    FROM semantic_search ss
    FULL OUTER JOIN full_text_search fts ON ss.id = fts.id
    ORDER BY rrf_score DESC
    LIMIT match_count;
END;
$$;
```

**Why This Works**: RRF (Reciprocal Rank Fusion) balances vector and text relevance
**Performance**: ~2.6 seconds with proper indexes

### Graph Search Pattern
**Last Verified**: July 26, 2025
**Discovered After**: Need to traverse Neo4j relationships efficiently

```python
# Graph search implementation in tools.py
async def graph_search(ctx: AgentContext, query: str, limit: int = 5) -> str:
    """Search using Neo4j knowledge graph traversal"""
    
    # Get query embedding for entity matching
    embeddings = await ctx.embedding_generator.generate_embeddings([query])
    query_embedding = embeddings[0]
    
    # Search for relevant entities in Neo4j
    async with ctx.graph_client.session() as session:
        # Find entities similar to query
        entity_query = """
        MATCH (e:Entity)
        WHERE e.embedding IS NOT NULL
        WITH e, gds.similarity.cosine(e.embedding, $embedding) AS similarity
        WHERE similarity > 0.7
        RETURN e, similarity
        ORDER BY similarity DESC
        LIMIT 10
        """
        
        entities = await session.run(
            entity_query,
            embedding=query_embedding
        )
        
        # Traverse relationships to find connected chunks
        chunk_query = """
        MATCH (e:Entity)-[r:RELATES_TO]-(c:Chunk)
        WHERE e.id IN $entity_ids
        RETURN DISTINCT c.content AS content,
               c.chunk_id AS chunk_id,
               collect(DISTINCT e.name) AS entities,
               avg(r.weight) AS relevance
        ORDER BY relevance DESC
        LIMIT $limit
        """
        
        entity_ids = [record["e"]["id"] for record in entities]
        chunks = await session.run(
            chunk_query,
            entity_ids=entity_ids,
            limit=limit
        )
    
    return format_graph_results(chunks)
```

## Configuration

### Database Indexes
```sql
-- Text search index (GIN)
CREATE INDEX IF NOT EXISTS chunks_content_gin_idx 
ON chunks_unified USING gin(to_tsvector('english', content));

-- Vector index (partial due to dimension limits)
CREATE INDEX chunks_embedding_partial_idx 
ON chunks_unified USING ivfflat (embedding vector_cosine_ops)
WHERE embedding_provider = 'jina'
WITH (lists = 100);

-- Provider index for filtering
CREATE INDEX chunks_provider_idx ON chunks_unified(embedding_provider);
```

### Search Parameters
```python
# Default search configurations
SEARCH_CONFIG = {
    'vector': {
        'default_limit': 5,
        'similarity_threshold': 0.7
    },
    'hybrid': {
        'default_limit': 5,
        'full_text_weight': 1.0,
        'semantic_weight': 1.0,
        'rrf_k': 60
    },
    'graph': {
        'default_limit': 5,
        'entity_similarity_threshold': 0.7,
        'max_traversal_depth': 2
    }
}
```

## Integration Patterns

### With PydanticAI Tools
- Each search type is a separate tool function
- Tools return formatted markdown strings
- Agent selects tool based on search_type parameter

### With Embeddings
- Vector search requires matching embedding provider
- Graph search uses separate embeddings (Gemini 768d)
- Hybrid search combines both approaches

## Gotchas & Solutions

### Problem: Slow vector search (10+ seconds)
**Symptoms**: Sequential scan instead of index usage
**Root Cause**: Missing or incompatible vector index
**Solution**: Create partial indexes with provider filtering
**Prevention**: Always check query plans with EXPLAIN

### Problem: No search results
**Symptoms**: Empty results despite having data
**Root Cause**: SQL functions querying wrong table
**Solution**: Ensure functions query chunks_unified, not chunks
**Prevention**: Verify table names in all SQL functions

### Problem: Dimension mismatch in search
**Symptoms**: "different vector dimensions" error
**Root Cause**: Mixing embeddings from different providers
**Solution**: Always filter by embedding_provider
```sql
WHERE c.embedding_provider = embedding_provider_filter
```

### Problem: Graph search returns empty
**Symptoms**: No results from knowledge graph
**Root Cause**: Graph not built or entities not connected
**Solution**: Verify graph population status
```cypher
MATCH (n) RETURN labels(n), count(n)
```

## Testing

### Verify Search Performance
```bash
# Test vector search speed
time curl -X POST http://localhost:8000/search/vector \
  -H "Content-Type: application/json" \
  -d '{"query": "practical strategy", "limit": 5}'

# Test hybrid search
time curl -X POST http://localhost:8000/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{"query": "strategic planning", "limit": 5}'
```

### Check Index Usage
```sql
-- Explain vector search
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM match_chunks_unified(
    (SELECT embedding FROM chunks_unified LIMIT 1),
    'jina',
    5
);

-- Check index stats
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'chunks_unified';
```

## Update Instructions
When optimizing search:
1. Always measure before and after performance
2. Use EXPLAIN ANALYZE for SQL optimization
3. Document index creation commands
4. Note any provider-specific requirements
