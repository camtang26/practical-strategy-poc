-- Migration: Migrate data from chunks_jina to chunks_unified table
-- This script migrates existing Jina embeddings to the unified schema

BEGIN;

-- Migrate data from chunks_jina to chunks_unified
INSERT INTO chunks_unified (
    id,
    document_id,
    chunk_index,
    content,
    embedding,
    embedding_model,
    embedding_provider,
    embedding_dim,
    metadata,
    created_at,
    updated_at
)
SELECT 
    id,
    document_id,
    chunk_index,
    content,
    embedding,
    'jina-embeddings-v4',
    'jina',
    2048,
    metadata,
    created_at,
    updated_at
FROM chunks_jina
WHERE embedding IS NOT NULL
ON CONFLICT (document_id, chunk_index, embedding_model) DO NOTHING;

-- Verify migration
DO $$
DECLARE
    source_count INTEGER;
    target_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO source_count FROM chunks_jina WHERE embedding IS NOT NULL;
    SELECT COUNT(*) INTO target_count FROM chunks_unified WHERE embedding_provider = 'jina';
    
    RAISE NOTICE 'Source chunks_jina count: %', source_count;
    RAISE NOTICE 'Target chunks_unified count: %', target_count;
    
    IF source_count != target_count THEN
        RAISE EXCEPTION 'Migration failed: counts do not match';
    END IF;
END $$;

-- Create a view for backward compatibility
CREATE OR REPLACE VIEW chunks_jina_compat AS
SELECT 
    id,
    document_id,
    chunk_index,
    content,
    embedding,
    metadata,
    created_at,
    updated_at
FROM chunks_unified
WHERE embedding_provider = 'jina';

COMMIT;
