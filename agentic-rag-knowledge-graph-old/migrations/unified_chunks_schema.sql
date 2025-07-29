-- Migration: Create unified chunks table supporting multiple embedding providers
-- This migration creates a new schema that supports both OpenAI (1536) and Jina (2048) embeddings

BEGIN;

-- Create the unified chunks table with variable embedding dimensions
CREATE TABLE IF NOT EXISTS chunks_unified (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding vector, -- Variable dimensions
    embedding_model TEXT NOT NULL, -- e.g., 'text-embedding-3-small', 'jina-embeddings-v4'
    embedding_provider TEXT NOT NULL, -- e.g., 'openai', 'jina'
    embedding_dim INTEGER NOT NULL, -- 1536, 2048, etc.
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_document_chunk_model UNIQUE(document_id, chunk_index, embedding_model)
);

-- Create indexes for performance
-- Note: HNSW index will be created separately after data migration due to pgvector limitations

-- Text search index
CREATE INDEX IF NOT EXISTS chunks_unified_content_gin_idx 
ON chunks_unified 
USING gin(to_tsvector('english', content));

-- Document and provider indexes
CREATE INDEX IF NOT EXISTS chunks_unified_document_id_idx ON chunks_unified(document_id);
CREATE INDEX IF NOT EXISTS chunks_unified_embedding_model_idx ON chunks_unified(embedding_model);
CREATE INDEX IF NOT EXISTS chunks_unified_embedding_provider_idx ON chunks_unified(embedding_provider);

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS chunks_unified_doc_model_idx ON chunks_unified(document_id, embedding_model);

-- Update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_chunks_unified_updated_at 
BEFORE UPDATE ON chunks_unified 
FOR EACH ROW 
EXECUTE FUNCTION update_updated_at_column();

-- Create provider-agnostic search functions
CREATE OR REPLACE FUNCTION match_chunks_unified(
    query_embedding vector,
    embedding_provider_filter TEXT DEFAULT NULL,
    match_count INTEGER DEFAULT 10
)
RETURNS TABLE(
    chunk_id uuid,
    document_id uuid,
    content text,
    similarity double precision,
    metadata jsonb,
    document_title text,
    document_source text,
    embedding_model text,
    embedding_provider text
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        c.id AS chunk_id,
        c.document_id,
        c.content,
        1 - (c.embedding <=> query_embedding) AS similarity,
        c.metadata,
        d.title AS document_title,
        d.source AS document_source,
        c.embedding_model,
        c.embedding_provider
    FROM chunks_unified c
    JOIN documents d ON c.document_id = d.id
    WHERE c.embedding IS NOT NULL
    AND (embedding_provider_filter IS NULL OR c.embedding_provider = embedding_provider_filter)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Create hybrid search function
CREATE OR REPLACE FUNCTION hybrid_search_unified(
    query_embedding vector,
    query_text text,
    embedding_provider_filter TEXT DEFAULT NULL,
    match_count INTEGER DEFAULT 10,
    text_weight double precision DEFAULT 0.3
)
RETURNS TABLE(
    chunk_id uuid,
    document_id uuid,
    content text,
    combined_score double precision,
    vector_similarity double precision,
    text_similarity double precision,
    metadata jsonb,
    document_title text,
    document_source text,
    embedding_model text,
    embedding_provider text
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH vector_results AS (
        SELECT 
            c.id AS chunk_id,
            c.document_id,
            c.content,
            1 - (c.embedding <=> query_embedding) AS vector_sim,
            c.metadata,
            d.title AS doc_title,
            d.source AS doc_source,
            c.embedding_model,
            c.embedding_provider
        FROM chunks_unified c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
        AND (embedding_provider_filter IS NULL OR c.embedding_provider = embedding_provider_filter)
    ),
    text_results AS (
        SELECT 
            c.id AS chunk_id,
            c.document_id,
            c.content,
            ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', query_text))::double precision AS text_sim,
            c.metadata,
            d.title AS doc_title,
            d.source AS doc_source,
            c.embedding_model,
            c.embedding_provider
        FROM chunks_unified c
        JOIN documents d ON c.document_id = d.id
        WHERE to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
        AND (embedding_provider_filter IS NULL OR c.embedding_provider = embedding_provider_filter)
    )
    SELECT 
        COALESCE(v.chunk_id, t.chunk_id) AS chunk_id,
        COALESCE(v.document_id, t.document_id) AS document_id,
        COALESCE(v.content, t.content) AS content,
        (COALESCE(v.vector_sim, 0) * (1 - text_weight) + COALESCE(t.text_sim, 0) * text_weight) AS combined_score,
        COALESCE(v.vector_sim, 0) AS vector_similarity,
        COALESCE(t.text_sim, 0) AS text_similarity,
        COALESCE(v.metadata, t.metadata) AS metadata,
        COALESCE(v.doc_title, t.doc_title) AS document_title,
        COALESCE(v.doc_source, t.doc_source) AS document_source,
        COALESCE(v.embedding_model, t.embedding_model) AS embedding_model,
        COALESCE(v.embedding_provider, t.embedding_provider) AS embedding_provider
    FROM vector_results v
    FULL OUTER JOIN text_results t ON v.chunk_id = t.chunk_id
    ORDER BY combined_score DESC
    LIMIT match_count;
END;
$$;

-- Helper view for easier querying
CREATE OR REPLACE VIEW chunks_unified_summary AS
SELECT 
    embedding_provider,
    embedding_model,
    embedding_dim,
    COUNT(*) as chunk_count,
    COUNT(DISTINCT document_id) as document_count,
    MIN(created_at) as first_created,
    MAX(created_at) as last_created
FROM chunks_unified
GROUP BY embedding_provider, embedding_model, embedding_dim;

COMMIT;
