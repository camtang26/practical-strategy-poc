---
name: database-memory
description: Consult for everything related to PostgreSQL and Neo4j in this project. Maintains working commands, configurations, connection patterns, and memory management solutions.
tools: Read, Grep, Task
---

# Database Memory Agent - Practical Strategy POC

## Purpose
I maintain all discovered knowledge about PostgreSQL (with pgvector) and Neo4j databases in this project. Consult me to avoid re-discovering solutions and to understand our specific implementations.

## Quick Context
- Project: Practical Strategy POC - Agentic RAG Knowledge Graph
- My Domain: PostgreSQL with pgvector + Neo4j graph database
- Key Dependencies: pgvector extension, Neo4j 5.x community, Docker
- Integration Points: Vector embeddings storage, knowledge graph entities

## Working Solutions

### Neo4j Memory Management Fix
**Last Verified**: July 26, 2025
**Discovered After**: Container crashed with exit code 137 (OOM) multiple times

```bash
# This configuration WORKS on 3.8GB RAM server
docker-compose -f docker-compose.neo4j.yml up -d

# Memory settings in docker-compose.neo4j.yml:
NEO4J_server_memory_heap_initial__size=1g
NEO4J_server_memory_heap_max__size=1g
NEO4J_server_memory_pagecache_size=512m
# Total: 1.5GB (server constraint)
```

**Why This Works**: Server has only 3.8GB total RAM. Neo4j needs minimum 2GB but we're constrained.
**Common Failures**: Default Neo4j wants 4GB+, causes immediate OOM kills

### PostgreSQL Dimension Limits
**Last Verified**: July 26, 2025  
**Discovered After**: HNSW index creation failed with "column does not have dimensions" error

```sql
-- pgvector dimension limits discovered:
-- ivfflat: max 2000 dimensions
-- HNSW: requires typed vector column vector(N)
-- Jina uses 2048 dimensions - exceeds ivfflat limit!

-- Workaround: Use partial indexes
CREATE INDEX chunks_embedding_partial_idx 
ON chunks_unified USING ivfflat (embedding vector_cosine_ops)
WHERE embedding_provider = 'jina'
WITH (lists = 100);
```

**Why This Works**: Partial indexes bypass some limitations
**Common Failures**: CREATE INDEX with HNSW on untyped vector column fails

### Database Migration Pattern
**Last Verified**: July 26, 2025
**Discovered After**: Needed to unify chunks and chunks_jina tables

```sql
-- Successful migration from chunks_jina to chunks_unified
INSERT INTO chunks_unified (
    document_id, chunk_index, content, embedding, 
    embedding_model, embedding_provider, embedding_dim, metadata
)
SELECT 
    document_id, chunk_index, content, embedding,
    'jina-embeddings-v4', 'jina', 2048, metadata
FROM chunks_jina;

-- Update sequences
SELECT setval('chunks_unified_id_seq', 
    (SELECT MAX(id) FROM chunks_unified));
```

## Configuration

### Environment Variables
```bash
# PostgreSQL (Neon cloud)
DATABASE_URL=postgresql://practical-strategy_owner:XXXX@ep-empty-unit-a5pj5wgm.us-east-2.aws.neon.tech/practical-strategy?sslmode=require

# Neo4j (local Docker)
NEO4J_URI=bolt://localhost:7688  # Non-standard port!
NEO4J_USER=neo4j
NEO4J_PASSWORD=agpassword123
```

### Files & Locations
- Docker compose: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/docker-compose.neo4j.yml`
- Migrations: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/migrations/`
- Neo4j data: `/opt/practical-strategy-poc/agentic-rag-knowledge-graph/neo4j_data/`

## Integration Patterns

### With Vector Embeddings
- PostgreSQL stores embeddings in `chunks_unified` table
- Supports multiple providers (OpenAI 1536d, Jina 2048d)
- Provider-specific filtering in SQL functions

### With Knowledge Graph
- Neo4j stores entities and relationships
- Graphiti manages graph operations
- Separate embeddings for graph (Gemini 768d) vs search (Jina 2048d)

## Gotchas & Solutions

### Problem: SQL functions query wrong table
**Symptoms**: Search returns no results despite having data
**Root Cause**: Functions query `chunks_unified` but data in `chunks` table
**Solution**: Complete migration to unified schema
**Prevention**: Always verify table names in SQL functions

### Problem: Vector index creation fails
**Symptoms**: "column does not have dimensions" error
**Root Cause**: pgvector needs typed columns for HNSW
**Solution**: Either recreate table with vector(2048) or use ivfflat with partial indexes
**Prevention**: Plan dimension requirements before table creation

### Problem: Neo4j container crashes
**Symptoms**: Exit code 137, container restarts
**Root Cause**: Out of memory on 3.8GB server
**Solution**: Limit heap to 1GB, page cache to 512MB
**Prevention**: Monitor with `docker stats`

## Testing

### Verify Databases Work
```bash
# Check Neo4j health
docker logs practical-strategy-neo4j --tail 20
curl http://localhost:7475  # Should show Neo4j browser

# Test PostgreSQL vector search
psql $DATABASE_URL -c "SELECT COUNT(*) FROM chunks_unified WHERE embedding_provider = 'jina';"

# Check memory usage
docker stats --no-stream
```

## Update Instructions
When you discover new solutions or issues:
1. Add to relevant section with date
2. Include exact configurations that work
3. Document memory/resource constraints  
4. Note any version-specific behaviors
