---
name: postgresql-memory
description: Consult for everything related to PostgreSQL, pgvector, Neon cloud database, dimension handling, and migrations. Maintains connection strings, SQL functions, and data migration patterns.
tools: Read, Grep, Task
---

# PostgreSQL/pgvector Memory Agent - Agentic RAG Knowledge Graph

## Purpose
I maintain all discovered knowledge about PostgreSQL and pgvector operations in this project. Consult me to understand our database schema, dimension handling, and migration patterns.

## Quick Context
- Project: Agentic RAG Knowledge Graph (ottomator-agents)
- My Domain: PostgreSQL with pgvector, Neon cloud database, migrations
- Database: Neon cloud-hosted PostgreSQL
- Key Issue Solved: Dimension mismatch (1536 → 2048 for Jina)
- Critical Migration: chunks → chunks_unified table

## Working Solutions

### Connecting to Neon Database
**Last Verified**: July 26, 2025
**Connection Pattern**: Use environment variable

```python
# From .env
DATABASE_URL=postgresql://neondb_owner:password@ep-jolly-math-uuid.us-east-2.aws.neon.tech/agentic_kg?sslmode=require

# In Python code
import os
from sqlalchemy import create_engine

engine = create_engine(os.getenv("DATABASE_URL"))
```

### Dimension Update Script
**Last Verified**: July 26, 2025
**Discovered After**: Original schema used 1536 dimensions (OpenAI), Jina uses 2048

```sql
-- Update pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Alter chunks table to support 2048 dimensions
ALTER TABLE chunks 
ALTER COLUMN embedding TYPE vector(2048);

-- Recreate search functions with new dimensions
CREATE OR REPLACE FUNCTION search_chunks(
    query_embedding vector(2048),
    match_limit int DEFAULT 10
)
RETURNS TABLE (
    chunk_id int,
    content text,
    metadata jsonb,
    similarity float
)
LANGUAGE sql
AS $$
    SELECT 
        id as chunk_id,
        content,
        metadata,
        1 - (embedding <=> query_embedding) as similarity
    FROM chunks
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> query_embedding
    LIMIT match_limit;
$$;
```

### Migration to chunks_unified Table
**Last Verified**: July 26, 2025
**Why**: Functions expected chunks_unified but data was in chunks table

```python
# Migration script that WORKS
import psycopg2
from psycopg2.extras import execute_values
import os

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()

# Create chunks_unified if not exists
cur.execute("""
    CREATE TABLE IF NOT EXISTS chunks_unified (
        id SERIAL PRIMARY KEY,
        document_id INTEGER REFERENCES documents(id),
        content TEXT NOT NULL,
        embedding vector(2048),
        metadata JSONB,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

# Copy all data maintaining relationships
cur.execute("""
    INSERT INTO chunks_unified (document_id, content, embedding, metadata, created_at)
    SELECT document_id, content, embedding, metadata, created_at
    FROM chunks
    WHERE NOT EXISTS (
        SELECT 1 FROM chunks_unified cu 
        WHERE cu.content = chunks.content
    )
""")

conn.commit()
print(f"Migrated {cur.rowcount} chunks")
```

## Schema Details

### Current Tables
```sql
-- Documents table
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunks unified table (ACTIVE)
CREATE TABLE chunks_unified (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    content TEXT NOT NULL,
    embedding vector(2048),  -- Jina dimensions
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Old chunks table (DEPRECATED but may exist)
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id),
    content TEXT NOT NULL,
    embedding vector(2048),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Key Functions
```sql
-- Hybrid search function
CREATE OR REPLACE FUNCTION hybrid_search_unified(
    query_text text,
    query_embedding vector(2048),
    match_limit int DEFAULT 10,
    full_text_weight float DEFAULT 1.0,
    semantic_weight float DEFAULT 1.0,
    rrf_k int DEFAULT 60
)
RETURNS TABLE (
    chunk_id int,
    document_id int,
    content text,
    metadata jsonb,
    score float
)
LANGUAGE sql
AS $$
    WITH full_text AS (
        SELECT 
            id,
            document_id,
            content,
            metadata,
            ts_rank_cd(to_tsvector('english', content), plainto_tsquery('english', query_text)) AS rank
        FROM chunks_unified
        WHERE to_tsvector('english', content) @@ plainto_tsquery('english', query_text)
        ORDER BY rank DESC
        LIMIT match_limit * 2
    ),
    semantic AS (
        SELECT 
            id,
            document_id,
            content,
            metadata,
            1 - (embedding <=> query_embedding) AS similarity
        FROM chunks_unified
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> query_embedding
        LIMIT match_limit * 2
    )
    -- RRF combination logic here
    SELECT DISTINCT ON (chunk_id)
        chunk_id,
        document_id,
        content,
        metadata,
        score
    FROM combined_results
    ORDER BY chunk_id, score DESC
    LIMIT match_limit;
$$;
```

## Gotchas & Solutions

### Problem: Dimension mismatch error
**Symptoms**: ERROR: expected 1536 dimensions, not 2048
**Root Cause**: Schema created for OpenAI embeddings, using Jina
**Solution**: Run update_to_jina_dimensions.py script
**Prevention**: Always specify vector dimensions in schema

### Problem: Table 'chunks_unified' doesn't exist
**Symptoms**: Search functions fail with relation not found
**Root Cause**: Functions expect chunks_unified but data in chunks
**Solution**: Run migration script to create and populate chunks_unified
**Prevention**: Check which table functions are querying

### Problem: SSL connection required
**Symptoms**: Connection refused without SSL
**Root Cause**: Neon requires SSL for all connections
**Solution**: Add `?sslmode=require` to connection string
**Prevention**: Always use full DATABASE_URL from .env

### Problem: Vector extension not found
**Symptoms**: type "vector" does not exist
**Root Cause**: pgvector extension not installed
**Solution**: `CREATE EXTENSION vector;`
**Prevention**: Include in migration scripts

## Testing

### Verify Database Connection
```python
# Quick test script
import psycopg2
import os

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cur = conn.cursor()
cur.execute("SELECT version()")
print(cur.fetchone())
cur.execute("SELECT COUNT(*) FROM chunks_unified")
print(f"Chunks: {cur.fetchone()[0]}")
```

### Check Vector Dimensions
```sql
-- Check column type
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'chunks_unified' 
AND column_name = 'embedding';
```

## Migration Patterns

### Safe Migration Template
```python
# Always check before migrating
cur.execute("SELECT COUNT(*) FROM source_table")
source_count = cur.fetchone()[0]

# Migrate with duplicate prevention
cur.execute("""
    INSERT INTO target_table (columns...)
    SELECT columns...
    FROM source_table
    WHERE NOT EXISTS (
        SELECT 1 FROM target_table t
        WHERE t.unique_field = source_table.unique_field
    )
""")

# Verify
cur.execute("SELECT COUNT(*) FROM target_table")
target_count = cur.fetchone()[0]
print(f"Migrated {cur.rowcount} of {source_count} records")
```

## Update Instructions
When you discover new PostgreSQL patterns or issues:
1. Add to relevant section with date
2. Include exact SQL that works
3. Document dimension specifications
4. Note any Neon-specific requirements
5. Update migration patterns if schema changes
